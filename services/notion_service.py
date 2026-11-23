"""Notion API integration for recipe persistence and querying.

Uses notion-client 3.x (Notion API 2025-09-03): pages live in a *data source*,
queried via `data_sources.query`. See docs/NOTION_SETUP.md for the required properties.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import threading
import time

import httpx
from notion_client import APIErrorCode, APIResponseError, Client
from notion_client.errors import HTTPResponseError, RequestTimeoutError
from notion_client.helpers import collect_paginated_api
from pydantic import ValidationError

from models.recipe import Recipe, SearchFilters
from services.config import get_setting
from services.errors import ServiceError
from services.recipe_search import browse_recipes, filter_recipes, find_duplicates

logger = logging.getLogger(__name__)

# Notion property name -> expected property type. Must match the database exactly.
PROPERTY_SCHEMA: dict[str, str] = {
    "Name": "title",
    "Ingredients": "rich_text",
    "Instructions": "rich_text",
    "Prep time": "number",
    "Cook time": "number",
    "Total time": "number",
    "Category": "select",
    "Vegetarian": "select",
    "Tags": "multi_select",
    "Source URL": "url",
    "Created at": "created_time",
}

VEGETARIAN_TO_NOTION = {True: "Yes", False: "No", None: "Unknown"}
VEGETARIAN_FROM_NOTION = {"Yes": True, "No": False}

TEXT_CHUNK = 2000  # Notion limit per rich_text item / block text
MAX_RICH_TEXT_ITEMS = 100
MAX_CHILD_BLOCKS = 100
_NOTION_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# Recipe list cache (ADR-015): every search, name lookup and duplicate check needs all recipes, and one agent
# answer can make several of those calls. Shared by all sessions of the app process (one shared database).
CACHE_TTL_SECONDS = 60
_cache_lock = threading.Lock()
_cache: dict = {"key": None, "at": 0.0, "records": None}


# ---------------------------------------------------------------------------
# Client + error handling
# ---------------------------------------------------------------------------


def _client() -> Client:
    return Client(auth=get_setting("NOTION_API_KEY"))


def _data_source_id() -> str:
    return get_setting("NOTION_DATA_SOURCE_ID")


def _to_service_error(exc: Exception) -> ServiceError:
    if isinstance(exc, APIResponseError):
        messages = {
            APIErrorCode.Unauthorized: "Notion rejected the API key. Check NOTION_API_KEY.",
            APIErrorCode.RestrictedResource: "The Notion integration has no access. Share the database with it.",
            APIErrorCode.ObjectNotFound: "Notion database not found. Check NOTION_DATA_SOURCE_ID and share the database with the integration.",
            APIErrorCode.ValidationError: "Notion rejected the data. Database properties probably do not match docs/NOTION_SETUP.md.",
            APIErrorCode.RateLimited: "Notion rate limit reached. Wait a moment and try again.",
        }
        message = messages.get(exc.code, "Notion request failed. Try again later.")
        return ServiceError(message, f"{exc.code}: {exc}")
    if isinstance(exc, (RequestTimeoutError, HTTPResponseError, httpx.HTTPError)):
        return ServiceError("Notion is not reachable right now. Try again later.", str(exc))
    return ServiceError("Unexpected Notion error.", repr(exc))


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (APIResponseError, RequestTimeoutError, HTTPResponseError, httpx.HTTPError) as exc:
        logger.exception("Notion call failed")
        raise _to_service_error(exc) from exc


# ---------------------------------------------------------------------------
# Mapping (pure functions)
# ---------------------------------------------------------------------------


def _chunks(text: str, size: int = TEXT_CHUNK) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _rich_text(text: str) -> list[dict]:
    chunks = _chunks(text)
    if len(chunks) > MAX_RICH_TEXT_ITEMS:
        raise ServiceError("Recipe is too long to store in Notion.")
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks if chunk]


def _select_name(value: str) -> str:
    # Notion select option names cannot contain commas and are limited to 100 chars.
    return value.replace(",", " ").strip()[:100]


def recipe_to_properties(recipe: Recipe) -> dict:
    ingredients_json = json.dumps([i.model_dump() for i in recipe.ingredients], ensure_ascii=False)
    instructions_json = json.dumps(recipe.instructions, ensure_ascii=False)
    tags = list(dict.fromkeys(_select_name(t) for t in recipe.tags if _select_name(t)))
    return {
        "Name": {"title": [{"type": "text", "text": {"content": recipe.name[:TEXT_CHUNK]}}]},
        "Ingredients": {"rich_text": _rich_text(ingredients_json)},
        "Instructions": {"rich_text": _rich_text(instructions_json)},
        "Prep time": {"number": recipe.prep_time_minutes},
        "Cook time": {"number": recipe.cook_time_minutes},
        "Total time": {"number": recipe.total_time_minutes},
        "Category": {"select": {"name": _select_name(recipe.category)} if recipe.category else None},
        "Vegetarian": {"select": {"name": VEGETARIAN_TO_NOTION[recipe.vegetarian]}},
        "Tags": {"multi_select": [{"name": t} for t in tags]},
        "Source URL": {"url": recipe.source_url or None},
    }


def _text_block(block_type: str, text: str) -> dict:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": [{"type": "text", "text": {"content": text[:TEXT_CHUNK]}}]},
    }


def recipe_to_blocks(recipe: Recipe) -> list[dict]:
    """Human-readable page body. Properties hold the machine-readable data."""
    blocks = [_text_block("heading_2", "Ingredients")]
    for ing in recipe.ingredients:
        line = ing.raw or " ".join(str(p) for p in (ing.quantity, ing.unit, ing.name) if p is not None)
        blocks.append(_text_block("bulleted_list_item", line))
    blocks.append(_text_block("heading_2", "Instructions"))
    blocks.extend(_text_block("numbered_list_item", step) for step in recipe.instructions)
    return blocks[:MAX_CHILD_BLOCKS]


def _plain_text(prop: dict, key: str) -> str:
    return "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in prop.get(key) or [])


def _json_list(prop: dict) -> list:
    text = _plain_text(prop, "rich_text")
    if not text:
        return []
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Notion rich_text is not valid JSON: %s", text[:200])
        return []
    return value if isinstance(value, list) else []


def page_to_record(page: dict) -> dict | None:
    """Convert a Notion page into a stored recipe record (Recipe fields + id/url/created_at)."""
    props = page.get("properties", {})

    def prop(name: str) -> dict:
        return props.get(name) or {}

    category = (prop("Category").get("select") or {}).get("name")
    vegetarian = (prop("Vegetarian").get("select") or {}).get("name")
    data = {
        "name": _plain_text(prop("Name"), "title"),
        "ingredients": _json_list(prop("Ingredients")),
        "instructions": _json_list(prop("Instructions")),
        "prep_time_minutes": prop("Prep time").get("number"),
        "cook_time_minutes": prop("Cook time").get("number"),
        "total_time_minutes": prop("Total time").get("number"),
        "category": category,
        "vegetarian": VEGETARIAN_FROM_NOTION.get(vegetarian),
        "tags": [o["name"] for o in prop("Tags").get("multi_select") or []],
        "source_url": prop("Source URL").get("url"),
    }
    try:
        recipe = Recipe.model_validate(data)
    except ValidationError as exc:
        logger.warning("Skipping Notion page %s that is not a valid recipe: %s", page.get("id"), exc)
        return None
    record = recipe.model_dump()
    record.update(id=page.get("id"), url=page.get("url"), created_at=prop("Created at").get("created_time"))
    return record


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def save_recipe_to_notion(recipe: Recipe) -> dict:
    """Create a page for the recipe. Returns {"id", "url"}."""
    page = _call(
        _client().pages.create,
        parent={"type": "data_source_id", "data_source_id": _data_source_id()},
        properties=recipe_to_properties(recipe),
        children=recipe_to_blocks(recipe),
    )
    clear_recipe_cache()  # the next read must include the new recipe
    return {"id": page["id"], "url": page.get("url")}


def clear_recipe_cache() -> None:
    with _cache_lock:
        _cache.update(key=None, at=0.0, records=None)


def list_all_recipes() -> list[dict]:
    """All saved recipes, cached for CACHE_TTL_SECONDS. Edits made directly in Notion show up after that."""
    key = _data_source_id()
    with _cache_lock:
        if _cache["key"] == key and time.monotonic() - _cache["at"] < CACHE_TTL_SECONDS:
            return copy.deepcopy(_cache["records"])  # callers may change their copy
    pages = _call(collect_paginated_api, _client().data_sources.query, data_source_id=key)
    records = (page_to_record(p) for p in pages if not p.get("in_trash") and not p.get("archived"))
    result = [r for r in records if r is not None]
    with _cache_lock:
        _cache.update(key=key, at=time.monotonic(), records=copy.deepcopy(result))
    return result


def search_recipes_in_notion(filters: SearchFilters) -> list[dict]:
    """Deterministic search: load all recipes (small dataset) and filter in Python."""
    return filter_recipes(list_all_recipes(), filters)


def browse_recipes_in_notion(filters: SearchFilters) -> dict:
    """Compact list of all (optionally filtered) recipes for vague requests (ADR-017)."""
    return browse_recipes(list_all_recipes(), filters)


def find_duplicate_recipes_in_notion(name: str | None, source_url: str | None = None) -> list[dict]:
    """Saved recipes with the same name or source URL as a new draft (ADR-014)."""
    return find_duplicates(list_all_recipes(), name, source_url)


def get_recipe_from_notion(name_or_id: str) -> dict | None:
    """Fetch one recipe by Notion page id or by name (exact match first, then substring)."""
    key = (name_or_id or "").strip()
    if not key:
        return None
    compact = key.replace("-", "").lower()
    if _NOTION_ID_RE.match(compact):
        try:
            page = _client().pages.retrieve(page_id=compact)
        except APIResponseError as exc:
            if exc.code in (APIErrorCode.ObjectNotFound, APIErrorCode.ValidationError):
                return None
            raise _to_service_error(exc) from exc
        except (RequestTimeoutError, HTTPResponseError, httpx.HTTPError) as exc:
            raise _to_service_error(exc) from exc
        return page_to_record(page)

    records = list_all_recipes()
    wanted = key.lower()
    for record in records:
        if record["name"].lower() == wanted:
            return record
    for record in records:
        if wanted in record["name"].lower():
            return record
    return None


def check_notion_setup() -> list[str]:
    """Compare the Notion data source schema with PROPERTY_SCHEMA. Returns a list of problems."""
    data_source = _call(_client().data_sources.retrieve, data_source_id=_data_source_id())
    actual = {name: spec.get("type") for name, spec in (data_source.get("properties") or {}).items()}
    problems = []
    for name, expected_type in PROPERTY_SCHEMA.items():
        if name not in actual:
            problems.append(f"Missing property `{name}` (type `{expected_type}`).")
        elif actual[name] != expected_type:
            problems.append(f"Property `{name}` has type `{actual[name]}`, expected `{expected_type}`.")
    return problems
