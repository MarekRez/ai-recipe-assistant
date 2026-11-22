# HANDOFF

Living baton for serial teamwork. Read it first, update it last (protocol: `AGENTS.md` -> Team Handoff Protocol).
This file is **overwritten**, not appended - history lives in git log and `AI_LOG.md`. Keep it under ~80 lines.

## Status

- MVP is complete and verified against **live** Gemini, Claude and Notion (2026-11-22): text/URL extraction, review
  form, save to Notion, cookbook agent with short conversation memory (follow-ups like "yes" work), Enter submits.
- Offline test suite: 103 tests, all passing. Evaluation done (Step 6-8, results in `AI_LOG.md`).
- Optional Claude fallback (ADR-012, `claude-haiku-5-5`) when Gemini hits its limit; optional password screen
  (`APP_PASSWORD`, ADR-013) for the deployed app.
- Notion: shared database "Recipes" on the page "Recipe Assistant (app data)", 10 fixture recipes as demo data.
- **Not deployed yet - next step is for Marek (repo owner), see below.**

## Next Up (in priority order)

1. [ ] **Deploy to Streamlit Community Cloud - Marek (`MarekRez`) must do this.** Streamlit requires *admin* rights on
   the repo, and on a personal GitHub repo only the owner has them (a teammate's attempt got `403` on `/api/v1/deploy`).
   1. Get privately from MLabska (never via git or the group chat): `NOTION_API_KEY`, `NOTION_DATA_SOURCE_ID`, and -
      only if MLabska agrees, since it uses MLabska's Claude credits - `ANTHROPIC_API_KEY`. Use your own `GEMINI_API_KEY`.
   2. Choose an `APP_PASSWORD` (not a personal password); share it with the team and the teacher only.
   3. https://share.streamlit.io -> sign in with GitHub as `MarekRez` -> **Create app** -> "Paste GitHub URL":
      `https://github.com/MarekRez/ai-recipe-assistant/blob/main/app.py`; App URL e.g. `euba-ai-recipe-assistant`.
   4. **Advanced settings**: Python **3.12**; Secrets (TOML, top-level keys):
      ```toml
      GEMINI_API_KEY = "..."
      GEMINI_MODEL = "gemini-3.6-flash"
      NOTION_API_KEY = "..."
      NOTION_DATA_SOURCE_ID = "..."
      ANTHROPIC_API_KEY = "..."   # optional - delete the line to run on Gemini only
      APP_PASSWORD = "..."
      ```
      Never deploy with API keys but without `APP_PASSWORD` - the app would be open to anyone with the link.
   5. **Deploy** (first build takes a few minutes). Smoke test on the live URL: password screen -> sidebar "Check
      Notion database" -> add a recipe (review, then Save) -> ask the agent "dinner ideas", then reply "yes".
   6. Put the live URL into `README.md` and this file; tick this item. Later pushes to `main` redeploy automatically.
2. [ ] Optional: re-run the Gemini eval cases `--only 03,06,07,11` (quota ran out) for a full Gemini vs. Claude comparison.
3. [ ] Optional: decide whether the 10 fixture recipes stay as demo data in Notion.

Done earlier: items 1-8 of the original list (merge, decisions, Notion setup, model id, live smoke test, eval answer
key review, extraction eval, agent scenarios) - see `AI_LOG.md` and git log.

## In Progress / Half-Done

Nothing.

## Open Questions (need a human decision)

- Does the online app get `ANTHROPIC_API_KEY`? It is MLabska's credit balance, so MLabska decides. Without it the app runs on
  Gemini only and may hit the free-tier limit (20 requests/day) during the demo. Recommendation: yes, with `APP_PASSWORD`.

## Decisions

- **One shared Notion integration + database** for the whole team. Secret and data source id are shared privately.
- **Gemini keys:** each teammate uses their own Google AI Studio key (free-tier quota is per project).
- **Deployment owner:** Marek (repo owner) - see item 1 for why.

## Gotchas (not yet promoted to CLAUDE.md / AGENTS.md)

- **Gemini free tier = 20 requests per day per model per key** (`gemini-3.6-flash`, Nov 2026) and ~20 s per call.
  A full eval is 11 requests, an agent question 2-4. With `ANTHROPIC_API_KEY` set the app switches to Claude instead.
- Getting the Notion secret + `NOTION_DATA_SOURCE_ID`: ask a teammate privately (shared database, see Decisions).
- Streamlit Cloud: a failed deploy can look like "nothing happens" after clicking Deploy - check the browser network
  tab (`/api/v1/deploy` status). Secret changes take about a minute to reach the running app.

## Last Session

- 2026-11-22, MLabska + Claude Code (branches `feat/evaluation`, `feat/claude-fallback`, `feat/evaluation-claude`,
  `feat/agent-memory`, `feat/deploy`, all merged): eval answer key review, eval fixes, optional Claude fallback,
  full eval + agent scenarios on Claude Haiku, short agent memory, Enter-to-submit, password screen for deployment.
  Deployment attempt from MLabska's Streamlit account failed with 403 (needs repo admin) - handed to Marek.
- Left unfinished: nothing; deployment is item 1 for Marek.
