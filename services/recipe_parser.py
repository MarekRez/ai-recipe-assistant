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
from services.gemini_service import extract_recipe_from_media, extract_recipe_structured
from services.url_fetcher import fetch_recipe_text, is_url

logger = logging.getLogger(__name__)

NOT_A_RECIPE = "NOT_A_RECIPE"
NOT_A_RECIPE_MESSAGE = "No recipe found in the given text."

Provider = Literal["auto", "gemini", "claude"]

# Video / photo upload (ADR-016). Gemini only - no Claude fallback for this path.
VIDEO_TYPES = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
IMAGE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
    "heic": "image/heic", "heif": "image/heif",
}
MEDIA_TYPES = VIDEO_TYPES | IMAGE_TYPES  # file extension -> mime type
MAX_UPLOAD_MB = 100  # per file; keep in sync with server.maxUploadSize in .streamlit/config.toml
MAX_IMAGES = 5  # e.g. a recipe over two cookbook pages, or a few caption screenshots


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


def _check_media(files: list[tuple[bytes, str]]) -> None:
    """One video, or 1..MAX_IMAGES photos - never mixed. Checked before any request is sent."""
    if not files:
        raise ServiceError("Upload a video or at least one photo.")
    supported = set(MEDIA_TYPES.values())
    for data, mime_type in files:
        if mime_type not in supported:
            raise ServiceError("Unsupported file type. Upload an MP4, MOV or WEBM video, or JPG, PNG, WEBP or HEIC photos.")
        if not data:
            raise ServiceError("One of the uploaded files is empty.")
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise ServiceError(f"A file is larger than {MAX_UPLOAD_MB} MB. Upload a shorter clip or a smaller photo.")
    videos = sum(mime in VIDEO_TYPES.values() for _, mime in files)
    if videos and len(files) > 1:
        raise ServiceError("Upload either one video or photos - not both, and only one video at a time.")
    if len(files) > MAX_IMAGES:
        raise ServiceError(f"Upload at most {MAX_IMAGES} photos for one recipe.")


def parse_recipe_media(files: list[tuple[bytes, str]], caption: str = "") -> Recipe:
    """Extract one recipe from an uploaded video or photos (`(data, mime_type)` pairs) plus optional caption text.

    A caption that is a single URL (e.g. the Reel's link) becomes source_url instead of being sent to the model.
    """
    return parse_recipe_media_with_provider(files, caption)[0]


def parse_recipe_media_with_provider(files: list[tuple[bytes, str]], caption: str = "") -> tuple[Recipe, str]:
    """Like `parse_recipe_media`, also reporting which model answered.

    Gemini first. On a Gemini outage, photos (JPEG/PNG/WEBP) go to Claude if ANTHROPIC_API_KEY is set; video and
    HEIC have no fallback, because Claude cannot read video and HEIC needs an extra plugin to convert.
    """
    _check_media(files)
    caption = (caption or "").strip()
    source_url = caption if is_url(caption) else None
    model_caption = "" if source_url else caption
    try:
        return _to_recipe(extract_recipe_from_media(files, model_caption), source_url), "gemini"
    except ProviderUnavailableError as exc:
        claude_can_read = all(mime in claude_service.CLAUDE_IMAGE_TYPES for _, mime in files)
        if claude_fallback_enabled() and claude_can_read:
            logger.warning("Gemini unavailable (%s) - reading the photos with Claude", exc.user_message)
            payload = claude_service.extract_recipe_from_images([data for data, _ in files], model_caption)
            return _to_recipe(payload, source_url), "claude"
        hint = "Paste the recipe text instead."
        if claude_fallback_enabled() and not claude_can_read:
            hint = "Videos and HEIC photos can only be read by Gemini - upload JPG/PNG photos or paste the recipe text."
        raise ProviderUnavailableError(f"{exc.user_message} {hint}", exc.detail) from exc


def parse_recipe(raw_text: str, source_url: str | None = None, provider: Provider = "auto") -> Recipe:
    return parse_recipe_with_provider(raw_text, source_url, provider)[0]


def parse_recipe_input(text_or_url: str) -> Recipe:
    """Accept either pasted recipe text or a single recipe URL."""
    value = (text_or_url or "").strip()
    if is_url(value):
        return parse_recipe(fetch_recipe_text(value), source_url=value)
    return parse_recipe(value)
