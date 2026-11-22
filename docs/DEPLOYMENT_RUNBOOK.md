# Deployment Runbook

## Local Run

1. `python -m venv .venv` (Python 3.12).
2. `.venv/Scripts/python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill all values (Notion: see `NOTION_SETUP.md`).
4. `.venv/Scripts/python -m streamlit run app.py`
5. Sidebar: confirm "Configuration loaded", click "Check Notion database".

## Pre-Deployment Checklist

1. `python -m pytest` passes.
2. Required env vars: `GEMINI_API_KEY`, `GEMINI_MODEL`, `NOTION_API_KEY`, `NOTION_DATA_SOURCE_ID`.
3. Notion database is shared with the integration and passes the schema check.
4. Smoke test: parse -> review -> save -> search.

## Streamlit Community Cloud

1. Push the repository to GitHub (`.env` and `.streamlit/secrets.toml` are git-ignored).
2. Create the app from the repo, main file `app.py`, Python 3.12.
3. Add secrets in the app settings as top-level keys (Streamlit exposes them as environment variables):

   ```toml
   GEMINI_API_KEY = "..."
   GEMINI_MODEL = "gemini-3.6-flash"
   NOTION_API_KEY = "..."
   NOTION_DATA_SOURCE_ID = "..."
   # optional Claude fallback (ADR-012) - omit to run on Gemini only
   ANTHROPIC_API_KEY = "..."
   ```

4. Deploy from the main branch and repeat the smoke test.

Note: the deployed app has no login. Anyone with the URL can read and add recipes and spend the Gemini quota -
share the URL only for the demo.

## Monitoring (MVP Level)

1. Keep `AI_LOG.md` updated with significant changes and eval results.
2. Parse failures and Notion/Gemini errors are logged (`logging`, visible in the Streamlit Cloud log console).
