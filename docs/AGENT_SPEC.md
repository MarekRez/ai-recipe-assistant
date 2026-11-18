# Agent Specification

## Agent Role

Interpret user cookbook requests and decide which backend tool to call, in sequence, until it can provide a final response.

## Available Tools

1. `parse_recipe(raw_text: str, source_url: str | None = None) -> Recipe`
2. `save_recipe(recipe: Recipe) -> dict`
3. `search_recipes(filters: SearchFilters) -> list[RecipeSummary]`
4. `get_recipe(name_or_id: str) -> Recipe`

## Orchestration Rules

1. Do not invent tool outputs.
2. Prefer explicit filters for search.
3. Ask a follow-up question only when user intent is ambiguous and filter inference is unsafe.
4. If a recipe is not found, return a concise not-found response with possible alternatives.

## Example Intent Mapping

1. "Find vegetarian meals under 30 minutes." -> `search_recipes(vegetarian=True, max_time=30)`
2. "Show me recipes with chicken." -> `search_recipes(ingredient="chicken")`
3. "Save this recipe." -> `parse_recipe(...)` then `save_recipe(...)` after user confirmation.

## Prompt Baseline

The agent system prompt should include:

1. Scope constraints from `PROJECT_CONTEXT.md`.
2. Non-hallucination rule for extraction fields.
3. Requirement to use tools for data access.
4. Concise response style.
