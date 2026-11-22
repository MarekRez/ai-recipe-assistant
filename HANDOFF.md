# HANDOFF

Living baton for serial teamwork. Read it first, update it last (protocol: `AGENTS.md` -> Team Handoff Protocol).
This file is **overwritten**, not appended - history lives in git log and `AI_LOG.md`. Keep it under ~80 lines.

## Status

- MVP code is complete and covered by an offline test suite (`python -m pytest`, 79 tests, all passing).
- **Never run against live Gemini / Notion yet.** No credentials were available in the dev environment.
- `feat/mvp-core` is merged into `main` (PR #1).
- Current piece of work: branch `feat/live-integration` - Next Up items 3-5.

## Next Up (in priority order)

1. [x] Merge `feat/mvp-core` into `main`, push, delete the branch (finishes the current piece).
2. [x] Decide the open questions (shared Notion database, Gemini keys) - see Decisions.
3. [ ] Create the Notion integration + database per `docs/NOTION_SETUP.md`; sidebar "Check Notion database" passes.
4. [ ] Verify the current free-tier Flash model id in Google AI Studio and set `GEMINI_MODEL` (`.env.example` says `gemini-2.5-flash`, not verified).
5. [ ] Live smoke test: paste recipe -> review -> save -> ask agent. Fix what breaks (first live run of Notion writes and Gemini tool calling).
6. [ ] Manually review expected outputs in `tests/fixtures/recipes/*.json` (written by an AI assistant - they are the eval ground truth).
7. [ ] Run `python -m evals.run_extraction_eval --out evals/results/<date>.json`, record metrics in `AI_LOG.md`.
8. [ ] Run the manual agent scenarios from `docs/TEST_PLAN.md`, record results in `AI_LOG.md`.
9. [ ] Deploy to Streamlit Community Cloud (`docs/DEPLOYMENT_RUNBOOK.md`).

Items 3-5 are a natural single piece of work ("live integration"); 6-8 another ("evaluation").

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
- Live behaviours not yet verified: Notion auto-creating Select/Multi-select options on write, and Gemini's OpenAI-compatible endpoint handling smolagents tool calls.

## Last Session

- 2026-11-18, Marek Rezny + Claude Code, branch `feat/mvp-core`: reviewed the scaffold, recorded ADR-005..011,
  implemented the full MVP flow (parsing, Notion, search, agent, UI, eval) with tests, set up CLAUDE.md and the
  serial handoff protocol (`HANDOFF.md`, `/start-session`, `/handoff`).
- Left unfinished: nothing; merge is item 1, live verification is item 5.
