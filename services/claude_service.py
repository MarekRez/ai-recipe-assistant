"""Claude fallback for structured recipe extraction (ADR-012).

Used only when Gemini is rate limited or down. Same prompt and schema as `gemini_service`, so the
extraction rules (no invented values, null when unknown) are identical. No sampling parameters:
API version 2026-10-21 rejects `temperature`.
"""

from __future__ import annotations

import logging

import anthropic

from models.recipe import Recipe
from services.config import claude_model
from services.errors import ProviderUnavailableError, ServiceError
from services.gemini_service import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

# Server-side refusal fallback: if a safety classifier declines, the API re-runs the request on a fallback model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client() -> anthropic.Anthropic:
    # Reads ANTHROPIC_API_KEY from the environment.
    return anthropic.Anthropic()


def extract_recipe_structured(raw_text: str) -> dict:
    """Return Claude's structured extraction payload as a dict (validated again by the caller)."""
    client = _client()
    try:
        response = client.beta.messages.parse(
            model=claude_model(),
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            messages=[{"role": "user", "content": EXTRACTION_PROMPT + raw_text}],
            output_format=Recipe,
        )
    except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as exc:
        logger.exception("Claude request failed")
        raise ProviderUnavailableError("Claude is not reachable right now. Try again later.", str(exc)) from exc
    except anthropic.APIStatusError as exc:
        logger.exception("Claude request rejected")
        raise ServiceError("Claude rejected the request. Check ANTHROPIC_API_KEY and CLAUDE_MODEL.", str(exc)) from exc

    if response.stop_reason == "refusal":
        raise ServiceError("Claude declined to process this text.", str(response.stop_details))
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ServiceError("The model returned an incomplete answer. Try again.", str(response.stop_reason))
    return response.parsed_output.model_dump(mode="json")
