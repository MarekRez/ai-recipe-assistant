"""Pydantic models for recipe extraction and storage."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    name: str = Field(min_length=1)
    quantity: Optional[float] = None
    unit: Optional[str] = None


class Recipe(BaseModel):
    name: str = Field(min_length=1)
    ingredients: list[Ingredient] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    total_time_minutes: Optional[int] = None
    category: Optional[str] = None
    vegetarian: Optional[bool] = None
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class SearchFilters(BaseModel):
    text_query: Optional[str] = None
    vegetarian: Optional[bool] = None
    max_time: Optional[int] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    ingredient: Optional[str] = None
