# Technical Design

## Architecture Overview

```text
                 +--> Add Recipe: parse_recipe_draft -> review form -> save_recipe -> Notion
User -> Streamlit|
                 +--> Ask: smolagents ToolCallingAgent --(Gemini, OpenAI-compatible API)
                              |
                              +-> search_recipes / get_recipe -> Notion (load all, filter in Python)
                              +-> parse_recipe -> Gemini extraction -> draft staged in the review form
```

## Components

1. `app.py` - Streamlit UI: recipe input, review/edit form, save confirmation, cookbook question, setup sidebar.
   Drafts live in `st.session_state`.
2. `agent/recipe_agent.py` - builds the `ToolCallingAgent` (model, tools, instructions, `max_steps`), `ask_agent()`.
   `agent/claude_agent.py` - Claude fallback tool loop with the same tools and instructions (ADR-012).
3. `agent/tools.py` - smolagents tools (`search_recipes`, `browse_recipes`, `get_recipe`, `parse_recipe`) and UI
   functions (`parse_recipe_draft`, `parse_recipe_media_draft`, `find_duplicate_recipes`, `list_saved_recipes`,
   `get_saved_recipe`, `save_recipe`). JSON-compatible inputs/outputs.
4. `services/recipe_parser.py` - text/URL input handling, extraction call, `Recipe` validation.
5. `services/gemini_service.py` - Gemini (`google-genai`) structured extraction prompt + JSON mode.
   `services/claude_service.py` - same prompt and schema on Claude, used only as fallback (ADR-012).
6. `services/url_fetcher.py` - URL fetch, JSON-LD recipe extraction, text fallback.
7. `services/notion_service.py` - Notion mapping, CRUD, schema check, error translation.
8. `services/recipe_search.py` - pure deterministic filtering (`filter_recipes`).
   `services/recipe_view.py` - pure display helpers for the "View recipe" dialog (ingredient line, times,
   overview; missing values -> "not stated").
9. `services/config.py`, `services/errors.py` - env settings and the `ServiceError` type.
10. `models/recipe.py` - Pydantic schema definitions.
11. `evals/` - live extraction eval script and its scoring functions.

Layering rule: `services/*` import neither Streamlit nor smolagents.

## Data Flow

1. User submits text/URL -> `parse_recipe_draft` -> `parse_recipe_input` (fetch if URL) -> Gemini -> `Recipe` validation.
2. UI shows the draft in an editable form; nothing is saved yet.
3. On "Save to Notion", the edited values are validated by `Recipe` again and saved via `save_recipe`.
4. Questions go to `ask_agent`, which calls `search_recipes` / `get_recipe` (or `parse_recipe` to stage a draft).
   The session's last 3 question/answer pairs are passed along (`st.session_state.history`) for follow-ups.
5. My Recipes: `list_saved_recipes` fills the table (`st.dataframe`, single-row selection). "View recipe" calls
   `get_saved_recipe(id)`, which takes the full record from the cached list (ADR-015, no extra Notion request), and
   `@st.dialog` renders it read-only. The dialog opens only on the button, because the selection survives reruns.

## Error Handling Strategy

1. Services catch Gemini/Notion/HTTP errors and raise `ServiceError(user_message, detail)`; details are logged.
2. Agent tools convert `ServiceError` into `{"error": ...}` so the agent reports instead of retrying.
3. Agent failures (e.g. rate limits) become `ServiceError` in `ask_agent`.
   Gemini rate limits / outages raise `ProviderUnavailableError`; if `ANTHROPIC_API_KEY` is set, extraction and
   agent questions are retried once with Claude; the switch is logged, not shown to end users (ADR-012).
4. Validation errors on save block the save and list the offending fields.
5. Missing configuration is shown in the sidebar; "Check Notion database" validates the property schema.
