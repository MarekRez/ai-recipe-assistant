"""Gemini service wrapper for structured recipe extraction."""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from models.recipe import Recipe
from services.config import get_setting
from services.errors import ProviderUnavailableError, ServiceError

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You extract recipes into structured JSON.

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

Source text:
"""


def _client() -> genai.Client:
    return genai.Client(api_key=get_setting("GEMINI_API_KEY"))


def extract_recipe_structured(raw_text: str) -> dict:
    """Return Gemini's structured extraction payload as a dict (not yet validated)."""
    # Keep a reference to the client for the whole request: google-genai 3.x closes its HTTP client when the
    # Client object is garbage-collected, so `_client().models.generate_content(...)` can fail mid-request with
    # "Cannot send a request, as the client has been closed".
    client = _client()
    try:
        response = client.models.generate_content(
            model=get_setting("GEMINI_MODEL"),
            contents=EXTRACTION_PROMPT + raw_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Recipe,
                temperature=0,
            ),
        )
    except genai_errors.APIError as exc:
        logger.exception("Gemini request failed")
        if exc.code == 429:
            raise ProviderUnavailableError("Gemini rate limit reached. Wait a minute and try again.", str(exc)) from exc
        if exc.code in (400, 401, 403, 404):
            raise ServiceError("Gemini rejected the request. Check GEMINI_API_KEY and GEMINI_MODEL.", str(exc)) from exc
        raise ProviderUnavailableError("Gemini is not reachable right now. Try again later.", str(exc)) from exc

    text = response.text or ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON output: %s", text[:500])
        raise ServiceError("The model returned an unreadable answer. Try again.", text[:500]) from exc
    if not isinstance(payload, dict):
        raise ServiceError("The model returned an unexpected structure. Try again.", text[:500])
    return payload
