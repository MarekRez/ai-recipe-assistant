"""Deterministic recipe filtering (no embeddings, no RAG).

Pure functions over stored recipe records, so they are unit-testable without Notion.
A stored record is `Recipe.model_dump()` plus `id` and `url` (see docs/DATA_CONTRACTS.md).
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit

from models.recipe import Recipe, SearchFilters


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def effective_time(record: dict) -> int | None:
    return Recipe.model_validate(record).effective_total_time()


def _haystack(record: dict) -> str:
    parts = [record.get("name"), record.get("category"), *record.get("tags", [])]
    for ing in record.get("ingredients", []):
        parts.extend([ing.get("name"), ing.get("raw")])
    return " ".join(_norm(p) for p in parts if p)


def matches(record: dict, filters: SearchFilters) -> bool:
    if filters.vegetarian is not None and record.get("vegetarian") is not filters.vegetarian:
        return False
    if filters.max_time is not None:
        total = effective_time(record)
        if total is None or total > filters.max_time:
            return False
    if filters.category and _norm(record.get("category")) != _norm(filters.category):
        return False
    if filters.tags:
        record_tags = {_norm(t) for t in record.get("tags", [])}
        if not all(_norm(t) in record_tags for t in filters.tags):
            return False
    if filters.ingredient:
        needle = _norm(filters.ingredient)
        if not any(
            needle in _norm(ing.get("name")) or needle in _norm(ing.get("raw"))
            for ing in record.get("ingredients", [])
        ):
            return False
    if filters.text_query:
        haystack = _haystack(record)
        if not all(token in haystack for token in _norm(filters.text_query).split()):
            return False
    return True


def summarize(record: dict) -> dict:
    """Compact shape returned to the agent for search results (RecipeSummary)."""
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "total_time_minutes": effective_time(record),
        "category": record.get("category"),
        "vegetarian": record.get("vegetarian"),
        "tags": record.get("tags", []),
        "url": record.get("url"),
    }


def filter_recipes(records: list[dict], filters: SearchFilters) -> list[dict]:
    return [summarize(r) for r in records if matches(r, filters)]


# ---------------------------------------------------------------------------
# Duplicate detection (ADR-014)
# ---------------------------------------------------------------------------


def _norm_name(value: str | None) -> str:
    """Case-, whitespace- and punctuation-insensitive name: "Easy Chicken-Curry!" == "easy chicken curry"."""
    return " ".join(re.sub(r"[^\w]+", " ", (value or "").casefold()).split())


_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "igshid", "mc_")


def _norm_url(value: str | None) -> str:
    """Same page regardless of http/https, "www.", host case, trailing slash, tracking parameters or #fragment."""
    if not value or not value.strip():
        return ""
    parts = urlsplit(value.strip())
    host = parts.netloc.lower().removeprefix("www.")
    if not host:
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING_PARAMS)]
    return host + parts.path.rstrip("/") + ("?" + urlencode(sorted(query)) if query else "")


def find_duplicates(records: list[dict], name: str | None, source_url: str | None = None) -> list[dict]:
    """Saved recipes with the same (normalized) name or the same source URL, as summaries."""
    wanted_name, wanted_url = _norm_name(name), _norm_url(source_url)
    found = []
    for record in records:
        same_name = bool(wanted_name) and _norm_name(record.get("name")) == wanted_name
        same_url = bool(wanted_url) and _norm_url(record.get("source_url")) == wanted_url
        if same_name or same_url:
            found.append(summarize(record) | {"same_name": same_name, "same_source_url": same_url})
    return found
