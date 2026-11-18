"""Recipe parsing service: LLM extraction + schema validation."""

from __future__ import annotations

from models.recipe import Recipe
from services.gemini_service import extract_recipe_structured


def parse_recipe(raw_text: str, source_url: str | None = None) -> Recipe:
    """Parse recipe input into validated Recipe schema.

    Missing values should remain null-equivalent (None), never fabricated.
    """
    payload = extract_recipe_structured(raw_text)
    if source_url:
        payload["source_url"] = source_url
    return Recipe.model_validate(payload)
