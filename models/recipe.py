"""Pydantic models for recipe extraction and storage.

This is the single schema definition of the project (see docs/DATA_CONTRACTS.md).
Missing information is always `None` - never a guessed value.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Ingredient(BaseModel):
    name: str = Field(min_length=1, description="Ingredient name, e.g. 'chicken breast'.")
    quantity: Optional[float] = Field(
        default=None,
        description="Single numeric amount if explicitly stated, otherwise null.",
    )
    unit: Optional[str] = Field(default=None, description="Unit if explicitly stated, otherwise null.")
    raw: Optional[str] = Field(
        default=None,
        description="Original ingredient line as written in the source, e.g. '1-2 cloves garlic'.",
    )


class Recipe(BaseModel):
    name: str = Field(min_length=1)
    ingredients: list[Ingredient] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    prep_time_minutes: Optional[int] = Field(default=None, ge=0)
    cook_time_minutes: Optional[int] = Field(default=None, ge=0)
    total_time_minutes: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None
    vegetarian: Optional[bool] = None
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("instructions", "tags")
    @classmethod
    def _drop_blank_strings(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    def effective_total_time(self) -> Optional[int]:
        """Total time for filtering: stated total, else prep + cook if both are stated."""
        if self.total_time_minutes is not None:
            return self.total_time_minutes
        if self.prep_time_minutes is not None and self.cook_time_minutes is not None:
            return self.prep_time_minutes + self.cook_time_minutes
        return None


class SearchFilters(BaseModel):
    text_query: Optional[str] = None
    vegetarian: Optional[bool] = None
    max_time: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    ingredient: Optional[str] = None
