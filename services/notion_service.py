"""Notion API integration for recipe persistence and querying."""

from __future__ import annotations

from models.recipe import Recipe, SearchFilters


def save_recipe_to_notion(recipe: Recipe) -> dict:
    """Persist a recipe and return a Notion record reference.

    TODO: implement Notion page create call.
    """
    raise NotImplementedError("Notion save is not implemented yet.")


def search_recipes_in_notion(filters: SearchFilters) -> list[dict]:
    """Search recipes with deterministic filtering.

    TODO: implement Notion database query.
    """
    raise NotImplementedError("Notion search is not implemented yet.")


def get_recipe_from_notion(name_or_id: str) -> dict | None:
    """Fetch one recipe by identifier.

    TODO: implement Notion read.
    """
    raise NotImplementedError("Notion get is not implemented yet.")
