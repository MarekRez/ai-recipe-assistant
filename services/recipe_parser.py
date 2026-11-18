"""Recipe parsing service: input handling + LLM extraction + schema validation."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from models.recipe import Recipe
from services.errors import ServiceError
from services.gemini_service import extract_recipe_structured
from services.url_fetcher import fetch_recipe_text, is_url

logger = logging.getLogger(__name__)

NOT_A_RECIPE = "NOT_A_RECIPE"


def parse_recipe(raw_text: str, source_url: str | None = None) -> Recipe:
    """Parse recipe text into a validated Recipe.

    Missing values stay None - they are never fabricated here.
    """
    if not raw_text or not raw_text.strip():
        raise ServiceError("Recipe text is empty.")
    payload = extract_recipe_structured(raw_text)
    if payload.get("name") == NOT_A_RECIPE:
        raise ServiceError("No recipe found in the given text.")
    if source_url:
        payload["source_url"] = source_url
    try:
        return Recipe.model_validate(payload)
    except ValidationError as exc:
        logger.error("Extraction failed schema validation: %s", exc)
        raise ServiceError("The extracted recipe did not pass validation. Try again or edit the input.", str(exc)) from exc


def parse_recipe_input(text_or_url: str) -> Recipe:
    """Accept either pasted recipe text or a single recipe URL."""
    value = (text_or_url or "").strip()
    if is_url(value):
        return parse_recipe(fetch_recipe_text(value), source_url=value)
    return parse_recipe(value)
