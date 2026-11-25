# HANDOFF

Living baton for serial teamwork. Read it first, update it last (protocol: `AGENTS.md` -> Team Handoff Protocol).
This file is **overwritten**, not appended - history lives in git log and `AI_LOG.md`. Keep it under ~80 lines.

## Status

- MVP is complete and verified against **live** Gemini, Claude and Notion (2026-11-22): text/URL extraction, review
  form, save to Notion, cookbook agent with short conversation memory (follow-ups like "yes" work), Enter submits
  a question; Add Recipe submits with Ctrl+Enter and clears its input after a successful save.
- Offline test suite: 180 tests, all passing. Evaluation done (Step 6-8, results in `AI_LOG.md`).
- Optional Claude fallback (ADR-012, `claude-haiku-5-5`) when Gemini hits its limit; optional password screen
  (`APP_PASSWORD`, ADR-013) for the deployed app.
- Duplicate warning in the review form (ADR-014): same name or same source URL as a saved recipe -> warning with
  a link; saving is still allowed.
- "My Recipes" table (toggle, no AI request) and a 60 s recipe-list cache cleared on save (ADR-015). "View recipe"
  (select a row, click the button) shows the saved recipe read-only in a dialog styled like the review form, with
  an "Open in Notion" button; the "Open" link column stays. Reads the cache, no AI, no extra Notion request.
- Video or photo upload in Add Recipe (ADR-016) - photos fall back to Claude when Gemini is out, video does not; vague requests ("light, summery, slightly spicy") via the
  `browse_recipes` agent tool - the model picks from compact summaries (ADR-017).
- Agent scope rule (2026-11-25, `INSTRUCTIONS` rule 9): questions unrelated to recipes/cooking are declined in one
  sentence without tool calls. Before, the agent answered anything. **Not verified live yet** (Next Up 4).
- Notion: shared database "Recipes" on the page "Recipe Assistant (app data)", 10 fixture recipes as demo data.
- **Deployed:** https://mis-ai-recipe-assistant.streamlit.app/.

## Next Up (in priority order)

1. [x] Deployed to Streamlit Community Cloud by Marek: https://mis-ai-recipe-assistant.streamlit.app/ - later pushes to
   `main` redeploy automatically (reboot after new imports, see Gotchas). Secrets live in the app settings, never in git.
2. [ ] Test video/photo upload live **on Gemini** (its quota was used up on 2026-11-23; the Claude photo fallback was
   tested live and works): a short recipe Reel (MP4) with and without the caption, and 1-2 photos of a cookbook
   page; amounts only visible in the picture must stay empty. Merged to `main` on 2026-11-23 - **reboot the
   deployed app** after this push (new imports, see Gotchas); Streamlit Cloud installs the `pillow` pin itself.
3. [ ] **Reboot the deployed app** after the 2026-11-24 push (new module `services/recipe_view.py`, see Gotchas),
   then click through View recipe online. Locally it was checked with AppTest and live Notion data (17 recipes),
   but nobody has looked at the dialog in a browser yet - do that once, with a recipe that has missing times.
4. [ ] Live-check the scope rule (rule 9): ask the app an unrelated question ("what's the capital of France?",
   "write me a poem") and a borderline one ("what wine goes with risotto?"); expect a one-sentence decline for
   the first two. Check on both Gemini and the Claude fallback if possible; tighten the wording if it still answers.
5. [ ] Optional: re-run the Gemini eval cases `--only 03,06,07,11` (quota ran out) for a full Gemini vs. Claude comparison.
6. [ ] Optional: decide whether the 10 fixture recipes stay as demo data in Notion.
7. [ ] Small doc fix: `docs/ROADMAP.md` Phase 2 still says "needs live verification" (done 2026-11-22).

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

- 2026-11-25, MLabska + Claude Code (branch `fix/off-topic-questions`): found that the agent had no scope rule and
  answered any unrelated question (costing a rate-limited Gemini request). Added rule 9 to `INSTRUCTIONS` in
  `agent/recipe_agent.py` (applies to the Claude fallback too), a prompt test, and the rule in `docs/AGENT_SPEC.md`.
  180 tests green; offline only, live check is Next Up 4. Merged into `main`.
