"""Fetch recipe text from a URL.

Strategy: prefer schema.org Recipe JSON-LD (most recipe sites embed it), fall back to visible page text.
"""

from __future__ import annotations

import json
import logging
import re

import requests
from bs4 import BeautifulSoup

from services.errors import ServiceError

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 20_000
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RecipeAssistant/0.1; +https://streamlit.io)",
    "Accept-Language": "en,sk;q=0.8",
}


def is_url(text: str) -> bool:
    return bool(_URL_RE.match(text.strip()))


def fetch_recipe_text(url: str, timeout: int = 15) -> str:
    try:
        response = requests.get(url, headers=_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Fetching %s failed: %s", url, exc)
        raise ServiceError(
            "Could not load this URL (the site may block automated access). Paste the recipe text instead.",
            str(exc),
        ) from exc
    text = html_to_recipe_text(response.text)
    if not text.strip():
        raise ServiceError("The page contains no readable text. Paste the recipe text instead.")
    return text


def html_to_recipe_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    recipe = _find_json_ld_recipe(soup)
    if recipe is not None:
        return _json_ld_to_text(recipe)
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)[:MAX_TEXT_CHARS]


def _find_json_ld_recipe(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        found = _search_recipe_node(data)
        if found is not None:
            return found
    return None


def _search_recipe_node(node: object) -> dict | None:
    if isinstance(node, list):
        for item in node:
            found = _search_recipe_node(item)
            if found is not None:
                return found
        return None
    if isinstance(node, dict):
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if "Recipe" in types:
            return node
        if "@graph" in node:
            return _search_recipe_node(node["@graph"])
    return None


def _flatten_instructions(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        steps: list[str] = []
        for item in value:
            steps.extend(_flatten_instructions(item))
        return steps
    if isinstance(value, dict):
        if "itemListElement" in value:  # HowToSection
            return _flatten_instructions(value["itemListElement"])
        text = value.get("text") or value.get("name")
        return [text] if isinstance(text, str) else []
    return []


def _json_ld_to_text(recipe: dict) -> str:
    parts: list[str] = []
    if recipe.get("name"):
        parts.append(f"Recipe: {recipe['name']}")
    for key, label in (("prepTime", "Prep time"), ("cookTime", "Cook time"), ("totalTime", "Total time")):
        if recipe.get(key):
            parts.append(f"{label}: {recipe[key]}")
    if recipe.get("recipeCategory"):
        parts.append(f"Category: {recipe['recipeCategory']}")
    if recipe.get("suitableForDiet"):
        parts.append(f"Diet: {recipe['suitableForDiet']}")
    ingredients = recipe.get("recipeIngredient") or []
    if ingredients:
        parts.append("Ingredients:")
        parts.extend(f"- {line}" for line in ingredients if isinstance(line, str))
    steps = _flatten_instructions(recipe.get("recipeInstructions"))
    if steps:
        parts.append("Instructions:")
        parts.extend(f"{i}. {step.strip()}" for i, step in enumerate(steps, start=1))
    return "\n".join(parts)[:MAX_TEXT_CHARS]
