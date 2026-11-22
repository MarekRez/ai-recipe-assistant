# HANDOFF

Living baton for serial teamwork. Read it first, update it last (protocol: `AGENTS.md` -> Team Handoff Protocol).
This file is **overwritten**, not appended - history lives in git log and `AI_LOG.md`. Keep it under ~80 lines.

## Status

- MVP works end-to-end against **live** Gemini + Notion (verified 2026-11-22, in code and in the Streamlit UI):
  text and URL extraction, review form, save to Notion, agent answers via `search_recipes` / `get_recipe`.
- Offline test suite: 99 tests, all passing.
- **Optional Claude fallback (ADR-012):** if Gemini hits its limit / is down and `ANTHROPIC_API_KEY` is set,
  extraction and agent questions are answered by Claude Haiku 5.5 (labelled in the UI). Verified live 2026-11-22.
  Without the key nothing changes - teammates do not need one.
- Shared Notion database "Recipes" lives on the page "Recipe Assistant (app data)" in the team workspace;
  only that page is connected to the "Cooking Agent" integration. It holds the 10 fixture recipes (sample cookbook for the demo).

## Next Up (in priority order)

1. [x] Merge `feat/mvp-core` into `main`.
2. [x] Decide the open questions (shared Notion database, Gemini keys) - see Decisions.
3. [x] Create the Notion integration + database; "Check Notion database" passes.
4. [x] Verify the free-tier Flash model id -> `gemini-3.6-flash` (see Gotchas).
5. [x] Live smoke test: paste recipe -> review -> save -> ask agent. Fixed: genai client closed mid-request.
6. [x] Manually review expected outputs in `tests/fixtures/recipes/*.json` (written by an AI assistant - they are the eval ground truth).
7. [x] Run `python -m evals.run_extraction_eval --out evals/results/<date>.json`, record metrics in `AI_LOG.md`.
   Done on Claude Haiku 5.5 (11/11, results in `AI_LOG.md`). Gemini run is partial (7/11, quota) - optional:
   re-run `--only 03,06,07,11` on Gemini for a full side-by-side comparison.
8. [x] Run the manual agent scenarios from `docs/TEST_PLAN.md`, record results in `AI_LOG.md`.
9. [ ] Deploy to Streamlit Community Cloud (`docs/DEPLOYMENT_RUNBOOK.md`).
10. [ ] Optional: decide whether the 10 fixture recipes stay as demo data in Notion.

Next piece of work: deployment (item 9); the open question "who owns the deployment" needs an answer first.

## In Progress / Half-Done

Nothing.

## Open Questions (need a human decision)

- Who owns the Streamlit Community Cloud deployment?

## Decisions

- **One shared Notion integration + database** for the whole team (everyone demos the same cookbook). The Notion secret
  and data source id are shared privately between teammates, never in git.
- **Gemini keys:** each teammate uses their own Google AI Studio key (free-tier quota is per project).

## Gotchas (not yet promoted to CLAUDE.md / AGENTS.md)

- `git fetch/push` can fail on Windows with `SSL certificate problem: unable to get local issuer certificate`. Fix: `git config --global http.sslBackend schannel`.
- The eval makes ~11 Gemini requests per full run (6 s delay between them) - mind the free-tier daily quota.
- Getting the Notion secret + `NOTION_DATA_SOURCE_ID`: ask a teammate privately (shared database, see Decisions).
- **Gemini free tier = 20 requests per day per model per key** (`gemini-3.6-flash`, Nov 2026). A full eval is 11
  requests, an agent question 2-4. Spread testing across teammates' keys / days; failed calls show as SKIP in the eval.
- Gemini is slow on the free tier: ~20 s per extraction, ~20-40 s per agent question. Not a bug.

## Last Session

- 2026-11-22, teammate + Claude Code, branch `feat/live-integration`: created the shared Notion database (via API, exact
  `PROPERTY_SCHEMA`), switched the default model to `gemini-3.6-flash`, fixed the genai client being garbage-collected
  mid-request (+ regression test), ran the live smoke test in code and in the UI - everything passed.
- Same day, MLabska + Claude Code: reviewed the eval answer key (Step 6, no changes; pancakes=Breakfast and
  guacamole=Snack kept as judgment calls), partial eval run, fixed the eval scoring outages as results,
  added the optional Claude fallback (branch `feat/claude-fallback`, built on `feat/evaluation`).
- Then (branch `feat/evaluation-claude`): full extraction eval and all 5 agent scenarios on Claude Haiku 5.5 -
  all scenarios pass; saved the 7 remaining fixture recipes to Notion (10 total).
- Then (branch `feat/agent-memory`): the agent keeps a short conversation memory so follow-ups like "yes" work.
- Left unfinished: nothing. Optional Gemini comparison run; next real item is deployment (9).
