# CLAUDE.md

@AGENTS.md

## Project

Semester MVP: Streamlit app + smolagents agent that extracts recipes (Gemini), lets the user review/edit them, saves them to Notion, and answers cookbook questions via tools.

Source of truth, in order: `PROJECT_CONTEXT.md` > `docs/*` > code. If they disagree, fix the docs in the same change (see AGENTS.md tooling rule 3). Decisions live in `docs/DECISIONS.md` (ADR-005..011 cover the non-obvious ones).

## Commands (Windows, Python 3.12 venv in `.venv`)

```bash
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m streamlit run app.py
.venv/Scripts/python -m pytest                       # offline; Gemini and Notion are mocked
.venv/Scripts/python -m evals.run_extraction_eval    # LIVE Gemini - spends free-tier quota, run only when asked
```

## Layering

- `models/recipe.py` - the only schema definition. Everything validates through it.
- `services/*` - plain Python integrations (Gemini, Notion, URL fetch, parsing, search). No Streamlit or smolagents imports. Failures raise `ServiceError(user_message, detail)`.
- `agent/tools.py` - smolagents tools (`search_recipes`, `get_recipe`, `parse_recipe`) + UI functions (`parse_recipe_draft`, `save_recipe`). JSON-compatible args/returns; tools return `{"error": ...}` instead of raising.
- `agent/recipe_agent.py` - builds the agent (model + tools + instructions), `ask_agent()`.
- `app.py` - UI only. Drafts in `st.session_state` (every click reruns the script).
- `evals/` - live eval script + pure scoring functions.

## Invariants (do not break)

- The agent never gets a save tool. Saving happens only via the UI "Save to Notion" button after review (ADR-005).
- Missing data stays `None`. Never ask the LLM to "estimate"; `source_url` comes from the input, not the LLM.
- Search is deterministic: load all pages, filter with `services/recipe_search.filter_recipes` (ADR-009).
- Notion property names/types are defined once in `notion_service.PROPERTY_SCHEMA`; keep `docs/NOTION_SETUP.md` in sync.
- Tests never call live Gemini or Notion.
- Secrets only via `os.environ` (`.env` locally, Streamlit secrets in cloud). Never commit `.env` / `.streamlit/secrets.toml`.

## Library facts that differ from most online tutorials (verified Nov 2026)

1. **Gemini SDK is `google-genai`** (`from google import genai`); `google-generativeai` is deprecated. Extraction uses `response_mime_type="application/json"` + `response_schema=Recipe`, then `Recipe.model_validate` anyway. Model id from env `GEMINI_MODEL`.
2. **notion-client 3.x = Notion API 2025-09-03**: no `databases.query`. Use `client.data_sources.query(data_source_id=...)`; page parent `{"type": "data_source_id", "data_source_id": ...}`. Rich text item max 2000 chars (we chunk).
3. **smolagents `@tool`** needs an `Args:` docstring entry for every parameter, and the function source must be in a file. Non-primitive hints become `"object"` - the tool receives a plain `dict`.
4. **Agent model**: `OpenAIServerModel` against `https://generativelanguage.googleapis.com/v1beta/openai/` (needs `smolagents[openai]`, no LiteLLM). `ToolCallingAgent`, `max_steps=4` - every step is one rate-limited Gemini request.
5. **Streamlit `st.data_editor`**: all-`None` text columns become float and break `TextColumn` - cast to `"string"` dtype; edited cells come back as `pd.NA`/`NaN`, normalize to `None`.

## Workflow

- After changing a tool signature or the schema: update `docs/AGENT_SPEC.md` / `docs/DATA_CONTRACTS.md` and tests in the same change.
- Log notable implementation results (especially eval metrics) in `AI_LOG.md`; architectural decisions as new ADRs.
