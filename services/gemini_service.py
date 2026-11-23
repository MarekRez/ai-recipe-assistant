"""Gemini service wrapper for structured recipe extraction (text and video, ADR-016)."""

from __future__ import annotations

import io
import json
import logging
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from models.recipe import Recipe
from services.config import get_setting
from services.errors import ProviderUnavailableError, ServiceError

logger = logging.getLogger(__name__)

EXTRACTION_RULES = """You extract recipes into structured JSON.

Strict rules:
1. Use ONLY information present in the source text. Never invent ingredients, quantities, units, times or steps.
2. If a value is not stated, use null (or an empty list). Do not estimate.
3. quantity: a single number only when the source states one (fractions like 1/2 -> 0.5 are fine).
   Ranges ("1-2"), "to taste", "a pinch" -> quantity null. unit: null when not stated.
4. raw: copy the original ingredient line exactly as written.
5. Times in whole minutes, only when explicitly stated (convert hours/ISO durations like PT1H30M to minutes).
   Do not compute total_time_minutes yourself - fill it only when the source states a total time.
6. vegetarian: false if any meat, poultry, fish or seafood ingredient is listed; true only if stated as
   vegetarian or every listed ingredient is clearly meat- and fish-free; otherwise null.
7. category: one of Breakfast, Main course, Soup, Salad, Side dish, Dessert, Snack, Drink - or null if unclear.
8. tags: 2-6 short lowercase keywords describing the dish (main ingredient, cuisine, meal type).
9. Keep name, ingredients and instructions in the language of the source. One instruction step per list item.
10. If the text does not contain a recipe, return {"name": "NOT_A_RECIPE"}.
"""

EXTRACTION_PROMPT = EXTRACTION_RULES + "\nSource text:\n"

MEDIA_PROMPT = EXTRACTION_RULES + """11. The source is the attached video or photos (cookbook pages, handwritten cards, screenshots) plus the
    caption below. Use what is said, what is written (on-screen text, printed or handwritten text, screenshots)
    and the caption. Several photos belong to one recipe - read them in order. Never read amounts off the picture
    (how full a cup looks, how many pieces you see) - an amount counts only when it is said or written.
12. raw: the ingredient as said or written in the source.
13. Instructions: the steps as said, written or clearly shown, in order. If the source does not show a recipe at
    all, return {"name": "NOT_A_RECIPE"}.

Caption / extra text from the user (may be empty):
"""

MEDIA_PROCESSING_TIMEOUT = 120  # seconds Gemini may take to process uploaded files before we give up
_POLL_SECONDS = 2


def _client() -> genai.Client:
    return genai.Client(api_key=get_setting("GEMINI_API_KEY"))


DAILY_LIMIT_MESSAGE = "Gemini's free daily request limit is used up. It resets within 24 hours - try again tomorrow."
_DAILY_LIMIT_MARKERS = ("PerDay", "per day")  # quotaId "GenerateRequestsPerDay..." / "requests per day limit"


def is_daily_limit(detail: str) -> bool:
    """A 429 for the daily free-tier quota (waiting a minute will not help) rather than the per-minute limit."""
    return any(marker in detail for marker in _DAILY_LIMIT_MARKERS)


def _api_error(exc: genai_errors.APIError) -> ServiceError:
    logger.exception("Gemini request failed")
    if exc.code == 429:
        if is_daily_limit(str(exc)):
            return ProviderUnavailableError(DAILY_LIMIT_MESSAGE, str(exc))
        return ProviderUnavailableError("Gemini rate limit reached. Wait a minute and try again.", str(exc))
    if exc.code in (400, 401, 403, 404):
        return ServiceError("Gemini rejected the request. Check GEMINI_API_KEY and GEMINI_MODEL.", str(exc))
    return ProviderUnavailableError("Gemini is not reachable right now. Try again later.", str(exc))


def _generate(client: genai.Client, contents) -> dict:
    """One structured-output request; returns the parsed JSON payload (not yet validated)."""
    try:
        response = client.models.generate_content(
            model=get_setting("GEMINI_MODEL"),
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Recipe,
                temperature=0,
            ),
        )
    except genai_errors.APIError as exc:
        raise _api_error(exc) from exc
    return _payload(response.text or "")


def extract_recipe_structured(raw_text: str) -> dict:
    """Return Gemini's structured extraction payload as a dict (not yet validated)."""
    # Keep a reference to the client for the whole request: google-genai 3.x closes its HTTP client when the
    # Client object is garbage-collected, so `_client().models.generate_content(...)` can fail mid-request with
    # "Cannot send a request, as the client has been closed".
    client = _client()
    return _generate(client, EXTRACTION_PROMPT + raw_text)


def _wait_until_processed(client: genai.Client, uploaded, deadline: float):
    while uploaded.state == types.FileState.PROCESSING:
        if time.monotonic() > deadline:
            raise ProviderUnavailableError("Gemini is taking too long to process the upload. Try again later.")
        time.sleep(_POLL_SECONDS)
        try:
            uploaded = client.files.get(name=uploaded.name)
        except genai_errors.APIError as exc:
            raise _api_error(exc) from exc
    if uploaded.state == types.FileState.FAILED:
        raise ServiceError("Gemini could not read this file. Try another file or paste the recipe text.")
    return uploaded


def extract_recipe_from_media(files: list[tuple[bytes, str]], caption: str = "") -> dict:
    """Upload a video or photos (`(data, mime_type)` pairs) to the Gemini Files API, extract one recipe from them,
    then delete the uploads.

    Uploading (instead of inline bytes) works for any Reel or phone-photo size (inline requests are limited to
    ~20 MB); the files are removed right after the answer (Gemini would otherwise keep them for 48 h).
    """
    client = _client()
    uploads = []
    try:
        for data, mime_type in files:
            try:
                uploads.append(
                    client.files.upload(
                        file=io.BytesIO(data), config=types.UploadFileConfig(mime_type=mime_type, display_name="recipe")
                    )
                )
            except genai_errors.APIError as exc:
                raise _api_error(exc) from exc
        deadline = time.monotonic() + MEDIA_PROCESSING_TIMEOUT
        ready = [_wait_until_processed(client, u, deadline) for u in uploads]
        return _generate(client, [*ready, MEDIA_PROMPT + (caption or "")])
    finally:
        for uploaded in uploads:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:  # cleanup only - Gemini deletes uploads after 48 h anyway
                logger.warning("Could not delete uploaded file %s", uploaded.name, exc_info=True)


def _payload(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON output: %s", text[:500])
        raise ServiceError("The model returned an unreadable answer. Try again.", text[:500]) from exc
    if not isinstance(payload, dict):
        raise ServiceError("The model returned an unexpected structure. Try again.", text[:500])
    return payload
