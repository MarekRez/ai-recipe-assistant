# AI Log

Chronological log of important AI-related implementation decisions, experiments, and outcomes.

## 2026-11-18 - Initial Project Scaffolding

- Created baseline documentation and project skeleton from `PROJECT_CONTEXT.md`.
- Added core docs for product spec, technical design, agent tool contracts, and tests.
- Added minimal file structure for app, models, services, tools, and tests.
- Next target: implement `Recipe` schema and `parse_recipe` flow with strict non-hallucination rules.

## 2026-11-18 - Plan Review and MVP Implementation

- Context: Review of the scaffold found gaps: agent save vs. HITL, deprecated Gemini SDK, Notion API 2025-09-03
  (no `databases.query`), smolagents tools receiving dicts, no URL fetching, checkbox cannot store unknown,
  2000-char rich text limit, unpinned deps, placeholder tests.
- Change: ADR-005..011 (`docs/DECISIONS.md`). Implemented the Phase 2 flow: Gemini extraction with
  `response_schema`, URL fetch (JSON-LD first), Notion mapping/CRUD/schema check, deterministic search,
  smolagents `ToolCallingAgent` via Gemini OpenAI-compatible endpoint, Streamlit review form, live eval script.
  Added 10+1 fixture recipes and an offline pytest suite (models, extraction, search, Notion, agent, UI, eval scoring).
- Why: Make the MVP flow complete and testable without spending API quota.
- Result: Offline test suite passes. Not yet verified against live Gemini/Notion (no credentials in the dev environment).
- Next: Fill `.env`, create the Notion database (`docs/NOTION_SETUP.md`), run the app end-to-end, run
  `python -m evals.run_extraction_eval` and record the metrics here.

## Log Entry Template

```
## YYYY-MM-DD - Short title
- Context:
- Change:
- Why:
- Result:
- Next:
```
