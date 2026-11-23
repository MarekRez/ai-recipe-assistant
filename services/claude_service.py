"""Claude fallback for structured recipe extraction (ADR-012, photos: ADR-016).

Used only when Gemini is rate limited or down. Same prompt and schema as `gemini_service`, so the
extraction rules (no invented values, null when unknown) are identical. No sampling parameters:
API version 2026-10-21 rejects `temperature`.

Photos (not video - Claude cannot read video) are re-encoded as JPEG and shrunk so the long edge is at
most CLAUDE_MAX_IMAGE_EDGE px: Claude accepts only JPEG/PNG/GIF/WEBP and limits the size per image, and
phone photos are often larger. HEIC cannot be opened without an extra plugin, so it has no fallback.
"""

from __future__ import annotations

import base64
import io
import logging

import anthropic
from PIL import Image, ImageOps, UnidentifiedImageError

from models.recipe import Recipe
from services.config import claude_model
from services.errors import ProviderUnavailableError, ServiceError
from services.gemini_service import EXTRACTION_PROMPT, MEDIA_PROMPT

logger = logging.getLogger(__name__)

CLAUDE_MAX_IMAGE_EDGE = 1568  # px; larger images are scaled down by the API anyway - only slower and bigger
CLAUDE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}  # what the fallback can re-encode (no HEIC)


def _client() -> anthropic.Anthropic:
    # Reads ANTHROPIC_API_KEY from the environment.
    return anthropic.Anthropic()


def _parse(content) -> dict:
    client = _client()
    try:
        response = client.messages.parse(
            model=claude_model(),
            max_tokens=16000,
            messages=[{"role": "user", "content": content}],
            output_format=Recipe,
        )
    except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as exc:
        logger.exception("Claude request failed")
        raise ProviderUnavailableError("Claude is not reachable right now. Try again later.", str(exc)) from exc
    except anthropic.APIStatusError as exc:
        logger.exception("Claude request rejected")
        raise ServiceError("Claude rejected the request. Check ANTHROPIC_API_KEY and CLAUDE_MODEL.", str(exc)) from exc

    if response.stop_reason == "refusal":
        raise ServiceError("Claude declined to process this input.", str(response.stop_details))
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ServiceError("The model returned an incomplete answer. Try again.", str(response.stop_reason))
    return response.parsed_output.model_dump(mode="json")


def extract_recipe_structured(raw_text: str) -> dict:
    """Return Claude's structured extraction payload as a dict (validated again by the caller)."""
    return _parse(EXTRACTION_PROMPT + raw_text)


def to_claude_jpeg(data: bytes) -> bytes:
    """Re-encode a photo as JPEG with the long edge at most CLAUDE_MAX_IMAGE_EDGE px (EXIF rotation applied)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)  # phone photos store "rotate me" separately - bake it in
            img.thumbnail((CLAUDE_MAX_IMAGE_EDGE, CLAUDE_MAX_IMAGE_EDGE))  # keeps aspect ratio, never enlarges
            out = io.BytesIO()
            img.convert("RGB").save(out, format="JPEG", quality=85)
            return out.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ServiceError("One of the photos could not be opened. Try another file.", str(exc)) from exc


def extract_recipe_from_images(images: list[bytes], caption: str = "") -> dict:
    """Claude fallback for photo uploads: the same media prompt as Gemini, photos in upload order."""
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(to_claude_jpeg(d)).decode()},
        }
        for d in images
    ]
    content.append({"type": "text", "text": MEDIA_PROMPT + (caption or "")})
    return _parse(content)
