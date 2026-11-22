"""Recipe parsing service: input handling + LLM extraction + schema validation.

Extraction uses Gemini; if Gemini is rate limited or down and ANTHROPIC_API_KEY is set, the same request
is retried with Claude (ADR-012) and a warning is logged. `parse_recipe_with_provider` also reports which
model answered (used by tests).
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import ValidationError

from models.recipe import Recipe
from services import claude_service
from services.config import claude_fallback_enabled
from services.errors import ProviderUnavailableError, ServiceError
from services.gemini_service import extract_recipe_structured
from services.url_fetcher import fetch_recipe_text, is_url

logger = logging.getLogger(__name__)

NOT_A_RECIPE = "NOT_A_RECIPE"
NOT_A_RECIPE_MESSAGE = "No recipe found in the given text."

Provider = Literal["auto", "gemini", "claude"]


def _extract(raw_text: str, provider: Provider) -> tuple[dict, str]:
    """Run the extraction; `auto` = Gemini first, Claude only on a Gemini outage and only if configured."""
    if provider == "claude":
        return claude_service.extract_recipe_structured(raw_text), "claude"
    try:
        return extract_recipe_structured(raw_text), "gemini"
    except ProviderUnavailableError as exc:
        if provider == "gemini" or not claude_fallback_enabled():
            raise
        logger.warning("Gemini unavailable (%s) - falling back to Claude", exc.user_message)
        return claude_service.extract_recipe_structured(raw_text), "claude"


def parse_recipe_with_provider(
    raw_text: str, source_url: str | None = None, provider: Provider = "auto"
) -> tuple[Recipe, str]:
    """Parse recipe text into a validated Recipe and report which provider produced it.

    Missing values stay None - they are never fabricated here.
    """
    if not raw_text or not raw_text.strip():
        raise ServiceError("Recipe text is empty.")
    payload, used = _extract(raw_text, provider)
    if payload.get("name") == NOT_A_RECIPE:
        raise ServiceError(NOT_A_RECIPE_MESSAGE)
    if source_url:
        payload["source_url"] = source_url
    try:
        return Recipe.model_validate(payload), used
    except ValidationError as exc:
        logger.error("Extraction failed schema validation: %s", exc)
        raise ServiceError("The extracted recipe did not pass validation. Try again or edit the input.", str(exc)) from exc


def parse_recipe(raw_text: str, source_url: str | None = None, provider: Provider = "auto") -> Recipe:
    return parse_recipe_with_provider(raw_text, source_url, provider)[0]


def parse_recipe_input(text_or_url: str) -> Recipe:
    """Accept either pasted recipe text or a single recipe URL."""
    value = (text_or_url or "").strip()
    if is_url(value):
        return parse_recipe(fetch_recipe_text(value), source_url=value)
    return parse_recipe(value)
