"""Custom tools used by the recipe agent and by the UI.

Contracts: docs/AGENT_SPEC.md. All tool args/returns are JSON-compatible; Recipe validation
happens inside. Errors are returned as {"error": "..."} so the agent can report them instead of retrying.

Human-in-the-loop (ADR-005): the agent can only *stage* a parsed draft (via `on_draft`);
`save_recipe` is called by the UI after the user reviewed and confirmed the draft.
"""

from __future__ import annotations

from collections.abc import Callable

from smolagents import Tool, tool

from models.recipe import Recipe, SearchFilters
from services.errors import ServiceError
from services.notion_service import (
    get_recipe_from_notion,
    save_recipe_to_notion,
    search_recipes_in_notion,
)
from services.recipe_parser import parse_recipe_input

# ---------------------------------------------------------------------------
# Plain functions (used by the UI and wrapped by the agent tools)
# ---------------------------------------------------------------------------


def parse_recipe_draft(text_or_url: str) -> dict:
    """Extract a recipe draft from text or URL. Raises ServiceError."""
    return parse_recipe_input(text_or_url).model_dump()


def save_recipe(recipe: dict) -> dict:
    """Validate and save a user-confirmed recipe. UI-only, never exposed to the agent. Raises ServiceError."""
    return save_recipe_to_notion(Recipe.model_validate(recipe))


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------


@tool
def search_recipes(
    text_query: str | None = None,
    vegetarian: bool | None = None,
    max_time: int | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    ingredient: str | None = None,
) -> dict:
    """Search saved recipes in the cookbook with deterministic filters. All filters are optional and combined with AND.

    Args:
        text_query: Keywords matched against recipe name, category, tags and ingredients (e.g. "pasta").
        vegetarian: True for vegetarian only, False for non-vegetarian only. Omit if the user did not ask.
        max_time: Maximum total time in minutes (e.g. 30 for "under 30 minutes").
        category: One of Breakfast, Main course, Soup, Salad, Side dish, Dessert, Snack, Drink.
        tags: Tags that must all be present (lowercase keywords, e.g. ["indian"]).
        ingredient: Ingredient that must be in the recipe (e.g. "chicken").
    """
    try:
        filters = SearchFilters(
            text_query=text_query,
            vegetarian=vegetarian,
            max_time=max_time,
            category=category,
            tags=tags or [],
            ingredient=ingredient,
        )
        results = search_recipes_in_notion(filters)
    except ServiceError as exc:
        return {"error": exc.user_message}
    return {"count": len(results), "results": results}


@tool
def get_recipe(name_or_id: str) -> dict:
    """Get one complete saved recipe (ingredients, instructions, times) by its name or Notion page id.

    Args:
        name_or_id: Recipe name (exact or partial) or the id returned by search_recipes.
    """
    try:
        record = get_recipe_from_notion(name_or_id)
    except ServiceError as exc:
        return {"error": exc.user_message}
    if record is None:
        return {"found": False}
    return {"found": True, "recipe": record}


def make_parse_recipe_tool(on_draft: Callable[[dict], None] | None = None) -> Tool:
    """Build the parse_recipe tool; `on_draft` receives the staged draft (e.g. stores it in UI session state)."""

    @tool
    def parse_recipe(text_or_url: str) -> dict:
        """Extract a structured recipe from pasted recipe text or a recipe URL and stage it as a draft for user review. It does NOT save the recipe; the user saves it after review in the Add Recipe section.

        Args:
            text_or_url: The full recipe text or a single recipe URL, exactly as provided by the user.
        """
        try:
            draft = parse_recipe_draft(text_or_url)
        except ServiceError as exc:
            return {"error": exc.user_message}
        if on_draft is not None:
            on_draft(draft)
        return {"status": "draft staged for user review - not saved yet", "draft": draft}

    return parse_recipe


def make_agent_tools(on_draft: Callable[[dict], None] | None = None) -> list[Tool]:
    return [search_recipes, get_recipe, make_parse_recipe_tool(on_draft)]
