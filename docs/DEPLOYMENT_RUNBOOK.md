# Deployment Runbook

## Local Run

1. Create venv.
2. Install `requirements.txt`.
3. Configure `.env` from `.env.example`.
4. Run `streamlit run app.py`.

## Pre-Deployment Checklist

1. Required env vars exist in deployment environment.
2. Notion integration token has proper permissions.
3. Target Notion database properties align with mapping.
4. Smoke test: parse -> review -> save -> search.

## Streamlit Community Cloud

1. Connect repository.
2. Add secrets in app settings.
3. Deploy from main branch.

## Monitoring (MVP Level)

1. Keep `AI_LOG.md` updated with significant changes.
2. Capture parse failures and Notion API errors in application logs.
