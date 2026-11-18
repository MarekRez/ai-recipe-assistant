# Agent Specification

## Agent Role

Interpret user cookbook requests and decide which backend tool to call, in sequence, until it can provide a final response.

Implementation: `smolagents.ToolCallingAgent` (no generated-code execution) on Gemini via its OpenAI-compatible
endpoint (`agent/recipe_agent.py`). `max_steps = 4` because every step is one rate-limited Gemini request.

## Agent Tools (`agent/tools.py`)

All arguments and return values are JSON-compatible. Tools never raise to the agent; failures are returned as
`{"error": "<user-facing message>"}`.

1. `search_recipes(text_query: str | None, vegetarian: bool | None, max_time: int | None, category: str | None, tags: list[str] | None, ingredient: str | None) -> {"count": int, "results": list[RecipeSummary]}`
2. `get_recipe(name_or_id: str) -> {"found": true, "recipe": RecipeRecord} | {"found": false}`
3. `parse_recipe(text_or_url: str) -> {"status": str, "draft": Recipe}` - extracts a draft and stages it for user review. Does **not** save.

`RecipeSummary` and `RecipeRecord` are defined in `DATA_CONTRACTS.md`.

## UI-only Functions (not exposed to the agent)

- `parse_recipe_draft(text_or_url: str) -> dict` - used by the "Process Recipe" button.
- `save_recipe(recipe: dict) -> {"id": str, "url": str}` - validates with `Recipe` and saves to Notion. Called only by
  the "Save to Notion" button after the user reviewed the draft (ADR-005).

## Orchestration Rules

1. Do not invent tool outputs; all recipe data comes from tools.
2. Prefer explicit filters for search.
3. If a search returns nothing, retry once with fewer filters and say which filter was relaxed.
4. If a recipe is not found, return a concise not-found response.
5. The agent cannot save recipes; it tells the user to review the staged draft and press "Save to Notion".

## Example Intent Mapping

1. "Find vegetarian meals under 30 minutes." -> `search_recipes(vegetarian=True, max_time=30)`
2. "Show me recipes with chicken." -> `search_recipes(ingredient="chicken")`
3. "I want pasta tonight." -> `search_recipes(text_query="pasta")`
4. "Something for dinner." -> `search_recipes(category="Main course")`
5. "How do I make the curry?" -> `get_recipe(name_or_id="curry")`
6. "Save this recipe: ..." -> `parse_recipe(...)` -> draft appears in the review form -> user presses "Save to Notion".

## Prompt Baseline

The system instructions (`INSTRUCTIONS` in `agent/recipe_agent.py`) contain:

1. Requirement to use tools for all data access and never invent data.
2. Filter mapping rules (vegetarian, time, ingredient, keyword, meal type -> category).
3. The no-save rule and the review hand-off.
4. Concise answers in the user's language.
