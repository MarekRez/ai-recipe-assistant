# HANDOFF

Living baton for serial teamwork. Read it first, update it last (protocol: `AGENTS.md` -> Team Handoff Protocol).
This file is **overwritten**, not appended - history lives in git log and `AI_LOG.md`. Keep it under ~80 lines.

## Status

- MVP is complete and verified against **live** Gemini, Claude and Notion (2026-11-22): text/URL extraction, review
  form, save to Notion, cookbook agent with short conversation memory (follow-ups like "yes" work), Enter submits
  a question; Add Recipe submits with Ctrl+Enter and clears its input after a successful save.
- Offline test suite: 140 tests, all passing. Evaluation done (Step 6-8, results in `AI_LOG.md`).
- Optional Claude fallback (ADR-012, `claude-haiku-5-5`) when Gemini hits its limit; optional password screen
  (`APP_PASSWORD`, ADR-013) for the deployed app.
- Duplicate warning in the review form (ADR-014): same name or same source URL as a saved recipe -> warning with
  a link; saving is still allowed.
- "My Recipes" table (toggle, no AI request) and a 60 s recipe-list cache cleared on save (ADR-015).
- Video upload in Add Recipe, Gemini only (ADR-016); vague requests ("light, summery, slightly spicy") via the
  `browse_recipes` agent tool - the model picks from compact summaries (ADR-017).
- Notion: shared database "Recipes" on the page "Recipe Assistant (app data)", 10 fixture recipes as demo data.
- **Deployed:** https://mis-ai-recipe-assistant.streamlit.app/.

## Next Up (in priority order)

1. [x] Deployed to Streamlit Community Cloud by Marek: https://mis-ai-recipe-assistant.streamlit.app/ - later pushes to
   `main` redeploy automatically (reboot after new imports, see Gotchas). Secrets live in the app settings, never in git.
2. [ ] Test video upload live with a real short recipe Reel (MP4), with and without the caption; check that
   amounts only visible in the picture stay empty. Then reboot the deployed app (see Gotchas).
3. [ ] Optional: re-run the Gemini eval cases `--only 03,06,07,11` (quota ran out) for a full Gemini vs. Claude comparison.
4. [ ] Optional: decide whether the 10 fixture recipes stay as demo data in Notion.

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

- **Streamlit Cloud: reboot after a push that adds new imports.** The live app reruns `app.py` with the new code
  but keeps old modules (e.g. `agent/tools.py`) loaded -> `ImportError` on `from agent.tools import ...`
  (seen 2026-11-23). Fix: "Manage app" -> menu -> **Reboot app**. Changing `.streamlit/config.toml` needs a reboot too.
- Live app: https://mis-ai-recipe-assistant.streamlit.app/ (deployed by Marek).

- **Gemini free tier = 20 requests per day per model per key** (`gemini-3.6-flash`, Nov 2026) and ~20 s per call.
  A full eval is 11 requests, an agent question 2-4. With `ANTHROPIC_API_KEY` set the app switches to Claude instead.
- Getting the Notion secret + `NOTION_DATA_SOURCE_ID`: ask a teammate privately (shared database, see Decisions).
- Streamlit Cloud: a failed deploy can look like "nothing happens" after clicking Deploy - check the browser network
  tab (`/api/v1/deploy` status). Secret changes take about a minute to reach the running app.
- Push `403 ... denied to LabskaSchool` on MLabska's laptop: Git Credential Manager has the wrong GitHub account.
  This clone now uses `gh` (logged in as MLabska) only: `git config credential.helper ""` then
  `git config --add credential.helper "!gh auth git-credential"` (the empty entry drops the system `manager`).

## Last Session

- 2026-11-23, MLabska + Claude Code (branch `feat/video-and-vague-search`): bonus features 1 and 2 from
  `PROJECT_CONTEXT.md`. Video upload via the Gemini Files API (upload -> wait -> extract -> delete; a link in the
  caption field becomes `source_url`). Agent tool `browse_recipes` + instruction 3a for vague requests; live check
  passed (see `AI_LOG.md`). Also: `source_url` can no longer come from the model for text input. 140 tests green.
  Earlier the same day (merged): duplicate warning (ADR-014), recipe cache + My Recipes (ADR-015).
- Left unfinished: live video test (Next Up 2).
