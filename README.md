# AI Recipe Knowledge Assistant

Minimal semester MVP proving an end-to-end AI agent workflow for recipe knowledge management.

## What This Project Demonstrates

1. Add recipe input from plain text or URL.
2. Extract normalized structured recipe data with an LLM.
3. Let user review and edit extracted data before save.
4. Save confirmed recipes to Notion.
5. Ask natural-language cookbook questions.
6. Let an AI agent choose backend tools (`parse_recipe`, `save_recipe`, `search_recipes`, `get_recipe`).

## MVP Constraints

- Keep architecture intentionally small.
- No vector DB and no complex RAG for MVP.
- No microservices, no separate frontend/backend stack.
- Human-in-the-loop verification is required before saving.

See `PROJECT_CONTEXT.md` and `docs/` for source-of-truth details.

## Suggested Stack

- Python
- Streamlit
- smolagents
- Gemini API (Flash model)
- Notion API
- Pydantic

## Project Layout

```
.
|-- app.py
|-- agent/
|   |-- recipe_agent.py
|   `-- tools.py
|-- services/
|   |-- gemini_service.py
|   |-- notion_service.py
|   `-- recipe_parser.py
|-- models/
|   `-- recipe.py
|-- tests/
|   |-- test_extraction.py
|   |-- test_notion.py
|   `-- test_agent.py
|-- docs/
|   |-- DOCS_INDEX.md
|   |-- PRODUCT_SPEC.md
|   |-- TECHNICAL_DESIGN.md
|   |-- AGENT_SPEC.md
|   |-- DATA_CONTRACTS.md
|   |-- TEST_PLAN.md
|   |-- DEPLOYMENT_RUNBOOK.md
|   |-- DECISIONS.md
|   `-- ROADMAP.md
|-- AGENTS.md
|-- AI_LOG.md
|-- requirements.txt
|-- .env.example
`-- PROJECT_CONTEXT.md
```

## Quick Start

1. Create and activate a Python virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and fill values.
4. Run Streamlit app:

```bash
streamlit run app.py
```

## Environment Variables

- `GEMINI_API_KEY`
- `NOTION_API_KEY`
- `NOTION_DATABASE_ID`
- `APP_ENV`

## Documentation Map

Start from `docs/DOCS_INDEX.md`.
