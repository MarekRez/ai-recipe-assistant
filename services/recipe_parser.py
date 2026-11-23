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
from services.gemini_service import extract_recipe_from_video, extract_recipe_structured
from services.url_fetcher import fetch_recipe_text, is_url

logger = logging.getLogger(__name__)

NOT_A_RECIPE = "NOT_A_RECIPE"
NOT_A_RECIPE_MESSAGE = "No recipe found in the given text."

Provider = Literal["auto", "gemini", "claude"]

# Video upload (ADR-016). Gemini only - Claude cannot read video, so there is no fallback for this path.
VIDEO_TYPES = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
MAX_VIDEO_MB = 100  # keep in sync with server.maxUploadSize in .streamlit/config.toml


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
    return _to_recipe(payload, source_url), used


def _to_recipe(payload: dict, source_url: str | None) -> Recipe:
    if payload.get("name") == NOT_A_RECIPE:
        raise ServiceError(NOT_A_RECIPE_MESSAGE)
    payload["source_url"] = source_url  # from the input, never from the model
    try:
        return Recipe.model_validate(payload)
    except ValidationError as exc:
        logger.error("Extraction failed schema validation: %s", exc)
        raise ServiceError("The extracted recipe did not pass validation. Try again or edit the input.", str(exc)) from exc


def parse_recipe_video(data: bytes, mime_type: str, caption: str = "") -> Recipe:
    """Extract a recipe from an uploaded video plus optional caption text. A caption that is a single URL
    (e.g. the Reel's link) becomes source_url instead of being sent to the model."""
    if not data:
        raise ServiceError("The video file is empty.")
    if mime_type not in VIDEO_TYPES.values():
        raise ServiceError("Unsupported video format. Upload an MP4, MOV or WEBM file.")
    if len(data) > MAX_VIDEO_MB * 1024 * 1024:
        raise ServiceError(f"The video is larger than {MAX_VIDEO_MB} MB. Upload a shorter clip.")
    caption = (caption or "").strip()
    source_url = caption if is_url(caption) else None
    try:
        payload = extract_recipe_from_video(data, mime_type, "" if source_url else caption)
    except ProviderUnavailableError as exc:
        raise ProviderUnavailableError(
            exc.user_message + " Videos can only be read by Gemini - or paste the recipe text instead.", exc.detail
        ) from exc
    return _to_recipe(payload, source_url)


def parse_recipe(raw_text: str, source_url: str | None = None, provider: Provider = "auto") -> Recipe:
    return parse_recipe_with_provider(raw_text, source_url, provider)[0]


def parse_recipe_input(text_or_url: str) -> Recipe:
    """Accept either pasted recipe text or a single recipe URL."""
    value = (text_or_url or "").strip()
    if is_url(value):
        return parse_recipe(fetch_recipe_text(value), source_url=value)
    return parse_recipe(value)
