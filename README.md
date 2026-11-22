# AI Recipe Knowledge Assistant

Minimal semester MVP proving an end-to-end AI agent workflow for recipe knowledge management.

## What This Project Demonstrates

1. Add recipe input from plain text or URL.
2. Extract normalized structured recipe data with an LLM (Gemini, JSON schema mode).
3. Let the user review and edit extracted data before saving.
4. Save confirmed recipes to Notion.
5. Ask natural-language cookbook questions.
6. Let an AI agent choose backend tools (`search_recipes`, `get_recipe`, `parse_recipe`). Saving happens only after
   user confirmation in the UI (`save_recipe`, see ADR-005).

## MVP Constraints

- Keep architecture intentionally small.
- No vector DB and no complex RAG for MVP - deterministic filtering.
- No microservices, no separate frontend/backend stack.
- Human-in-the-loop verification is required before saving.

See `PROJECT_CONTEXT.md` and `docs/` for source-of-truth details.

## Stack

Python 3.12, Streamlit, smolagents (`ToolCallingAgent`), Gemini API (`google-genai` + OpenAI-compatible endpoint),
optional Claude fallback (`anthropic`),
Notion API (`notion-client` 3.x), Pydantic.

## Project Layout

```
.
|-- app.py                      Streamlit UI
|-- agent/
|   |-- recipe_agent.py         agent setup + ask_agent()
|   `-- tools.py                agent tools + UI save/parse functions
|-- services/
|   |-- gemini_service.py       structured extraction
|   |-- recipe_parser.py        text/URL input + validation
|   |-- url_fetcher.py          URL -> recipe text (JSON-LD first)
|   |-- notion_service.py       Notion mapping and CRUD
|   |-- recipe_search.py        deterministic filtering
|   |-- config.py / errors.py
|-- models/recipe.py            Pydantic schema
|-- evals/                      live extraction eval
|-- tests/                      offline pytest suite + fixtures/recipes
|-- docs/                       specs, ADRs, Notion setup, runbook
|-- AGENTS.md / CLAUDE.md       rules for coding agents (incl. team handoff protocol)
|-- HANDOFF.md                  current status + next steps - read first
|-- .claude/skills/             /start-session and /handoff for Claude Code
|-- AI_LOG.md                   AI implementation log
`-- PROJECT_CONTEXT.md          source of truth
```

## Quick Start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
copy .env.example .env          # then fill the values
.venv/Scripts/python -m streamlit run app.py
```

Set up the Notion database first: `docs/NOTION_SETUP.md`.

## Environment Variables

| Variable                | Purpose                                                      |
|-------------------------|--------------------------------------------------------------|
| `GEMINI_API_KEY`        | Google AI Studio key                                         |
| `GEMINI_MODEL`          | Gemini Flash model id (e.g. `gemini-3.6-flash`)              |
| `ANTHROPIC_API_KEY`     | Optional. Claude fallback when Gemini hits its limit (ADR-012) |
| `CLAUDE_MODEL`          | Optional. Claude model id, default `claude-opus-5-5`         |
| `NOTION_API_KEY`        | Notion internal integration secret                           |
| `NOTION_DATA_SOURCE_ID` | Notion data source id (not the database id)                  |
| `APP_ENV`               | `development` / `production` (informational)                 |

## Tests and Evaluation

```bash
.venv/Scripts/python -m pytest                     # offline, mocks Gemini and Notion
.venv/Scripts/python -m evals.run_extraction_eval  # live Gemini, uses free-tier quota
```

## Documentation Map

Start from `docs/DOCS_INDEX.md`.
