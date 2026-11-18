"""Custom tools used by the recipe agent."""

from __future__ import annotations

from models.recipe import Recipe, SearchFilters
from services.notion_service import (
    get_recipe_from_notion,
    save_recipe_to_notion,
    search_recipes_in_notion,
)
from services.recipe_parser import parse_recipe as parse_recipe_service


def parse_recipe(raw_text: str, source_url: str | None = None) -> Recipe:
    return parse_recipe_service(raw_text=raw_text, source_url=source_url)


def save_recipe(recipe: Recipe) -> dict:
    return save_recipe_to_notion(recipe)


def search_recipes(
    text_query: str | None = None,
    vegetarian: bool | None = None,
    max_time: int | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    ingredient: str | None = None,
) -> list[dict]:
    filters = SearchFilters(
        text_query=text_query,
        vegetarian=vegetarian,
        max_time=max_time,
        category=category,
        tags=tags or [],
        ingredient=ingredient,
    )
    return search_recipes_in_notion(filters)


def get_recipe(name_or_id: str) -> dict | None:
    return get_recipe_from_notion(name_or_id)
