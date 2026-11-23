# Agent Specification

## Agent Role

Interpret user cookbook requests and decide which backend tool to call, in sequence, until it can provide a final response.

Implementation: `smolagents.ToolCallingAgent` (no generated-code execution) on Gemini via its OpenAI-compatible
endpoint (`agent/recipe_agent.py`). `max_steps = 4` because every step is one rate-limited Gemini request.
If Gemini is rate limited or down and `ANTHROPIC_API_KEY` is set, the whole question is answered again by Claude
(`agent/claude_agent.py`) with the same tools, instructions and step limit (ADR-012). Still no save tool.

Short memory: the UI keeps the conversation of the current browser session; `build_task()` prefixes each
question with the last 3 exchanges (long answers cut), so replies like "yes" or "the second one" work.
Recipe data is still fetched through tools, never taken from earlier answers. "Clear conversation" resets it.

## Agent Tools (`agent/tools.py`)

All arguments and return values are JSON-compatible. Tools never raise to the agent; failures are returned as
`{"error": "<user-facing message>"}`.

1. `search_recipes(text_query: str | None, vegetarian: bool | None, max_time: int | None, category: str | None, tags: list[str] | None, ingredient: str | None) -> {"count": int, "results": list[RecipeSummary]}`
2. `browse_recipes(vegetarian: bool | None, max_time: int | None) -> {"count": int, "truncated": bool, "recipes": list[BrowseEntry]}` -
   compact list of all saved recipes for vague requests; the agent picks matches itself (ADR-017).
3. `get_recipe(name_or_id: str) -> {"found": true, "recipe": RecipeRecord} | {"found": false}`
4. `parse_recipe(text_or_url: str) -> {"status": str, "draft": Recipe}` - extracts a draft and stages it for user review. Does **not** save.

`RecipeSummary` and `RecipeRecord` are defined in `DATA_CONTRACTS.md`.

## UI-only Functions (not exposed to the agent)

- `parse_recipe_draft(text_or_url: str) -> dict` - used by the "Process Recipe" button.
- `parse_recipe_video_draft(data: bytes, mime_type: str, caption: str = "") -> dict` - "Process Recipe" with an uploaded
  video; Gemini only (ADR-016).
- `list_saved_recipes(refresh: bool = False) -> list[RecipeSummary]` - all saved recipes sorted by name, for the
  "My Recipes" table; `refresh=True` skips the 60 s recipe cache (ADR-015). Raises `ServiceError`.
- `find_duplicate_recipes(draft: dict) -> list[DuplicateMatch]` - saved recipes with the same name or source URL
  as the draft; the review form shows them as a warning (ADR-014). Raises `ServiceError`; the UI then shows no warning.
- `save_recipe(recipe: dict) -> {"id": str, "url": str}` - validates with `Recipe` and saves to Notion. Called only by
  the "Save to Notion" button after the user reviewed the draft (ADR-005).

## Orchestration Rules

1. Do not invent tool outputs; all recipe data comes from tools.
2. Prefer explicit filters for search; use `browse_recipes` only for requests no filter can express.
3. If a search returns nothing, retry once with fewer filters and say which filter was relaxed.
4. If a recipe is not found, return a concise not-found response.
5. The agent cannot save recipes; it tells the user to review the staged draft and press "Save to Notion".

## Example Intent Mapping

1. "Find vegetarian meals under 30 minutes." -> `search_recipes(vegetarian=True, max_time=30)`
2. "Show me recipes with chicken." -> `search_recipes(ingredient="chicken")`
3. "I want pasta tonight." -> `search_recipes(text_query="pasta")`
4. "Something for dinner." -> `search_recipes(category="Main course")`
5. "How do I make the curry?" -> `get_recipe(name_or_id="curry")`
6. "Something light, summery and slightly spicy." -> `browse_recipes()` -> the agent picks and explains.
7. "Save this recipe: ..." -> `parse_recipe(...)` -> draft appears in the review form -> user presses "Save to Notion".

## Prompt Baseline

The system instructions (`INSTRUCTIONS` in `agent/recipe_agent.py`) contain:

1. Requirement to use tools for all data access and never invent data.
2. Filter mapping rules (vegetarian, time, ingredient, keyword, meal type -> category).
3. The no-save rule and the review hand-off.
4. Concise answers in the user's language.
