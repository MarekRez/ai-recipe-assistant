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

## 2026-11-22 - Live Integration (first run against Gemini + Notion)

- Context: HANDOFF items 3-5. Team decision: one shared Notion database, one Gemini key per teammate.
- Change: Created the "Recipes" Notion database via the API with the exact `PROPERTY_SCHEMA` (schema check: 0 problems).
  Fixed `gemini_service.extract_recipe_structured`: google-genai 3.x closes its HTTP client when the `Client` is
  garbage-collected, and `_client().models.generate_content(...)` dropped the only reference ("Cannot send a request,
  as the client has been closed"); added a regression test. Default model changed to `gemini-3.6-flash`.
- Why: `gemini-2.5-flash` returns 404 for new keys ("no longer available to new users"); `gemini-3.7-flash` and
  `gemini-3.8-flash` returned 503 "high demand" repeatedly; `gemini-3.6-flash` worked.
- Result: Extraction from text (2 fixtures) and URL (BBC Good Food, JSON-LD) correct; ranges/"to taste" kept as null.
  Save to Notion works, Select/Multi-select options are auto-created. Agent answered "vegetarian under 30 minutes",
  "ingredients for Greek Salad" and "I want a soup" via tool calls through the OpenAI-compatible endpoint.
  Full UI flow (process -> review -> Save to Notion -> Ask Agent) works. Latency ~20 s per Gemini call.
- Next: evaluation (HANDOFF items 6-8).

## 2026-11-22 - Partial Extraction Eval + Claude Fallback

- Context: HANDOFF items 6-7. The Gemini free tier (20 requests/day/model) ran out during the eval run.
- Result (gemini-3.6-flash, 7 of 11 cases scored, 4 skipped): name 100 %, ingredient recall/precision 100 %,
  quantities 100 %, units 92 %, times 6/7, vegetarian 7/7, category 6/7. Differences: guacamole -> "Side dish"
  (answer key: Snack, judgment call); "handful"/"pinch" returned as units (answer key: null); lentil soup
  cook time 25 invented from "simmer for 25 minutes" (only real rule violation).
- Change: the eval counted a rate-limited negative case as passed - outages are now skipped, not scored.
  Added an optional Claude fallback (ADR-012) for extraction and agent questions; `--provider` pins the eval
  to one model. Live check: with Gemini over quota, extraction (5-9 s) and agent answers (~7 s) came from
  claude-opus-5-5; it did not invent the lentil soup cook time. Default then changed to claude-haiku-5-5 (much
  cheaper): re-checked live - extraction ~5.5 s, agent ~4.5 s, all correct; like Gemini it reads "simmer for
  25 minutes" as cook time.
- Next: re-run the 4 skipped cases on Gemini; optionally a full `--provider claude` run for comparison.

## Log Entry Template

```
## YYYY-MM-DD - Short title
- Context:
- Change:
- Why:
- Result:
- Next:
```
