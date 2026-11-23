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

## 2026-11-22 - Evaluation on Claude Haiku 5.5 (HANDOFF items 7-8)

- Context: Gemini free-tier quota exhausted for the day; the team member chose to finish the evaluation on the
  Claude fallback (`claude-haiku-5-5`). The Gemini run stays partial (7/11, see entry above).
- Extraction eval (`--provider claude`, 11 cases, 0 skipped): schema validity 100 %, name 100 %, ingredient
  recall/precision 100 %, quantities 100 %, units 100 %, times 90 %, vegetarian 100 %, category 9/10,
  hallucination-free 90 %, negative case 1/1. Only slip: lentil soup cook time 25 from "simmer for 25 minutes"
  (same as Gemini). Guacamole category left null (prompt allows null when unclear; answer key says Snack).
- Notion: the 7 missing fixture recipes were saved from their reviewed expected JSON (10 recipes in total).
- Agent scenarios (docs/TEST_PLAN.md, Claude tool loop), all 5 pass, one tool call each, 2-3 s:
  - "vegetarian meals under 30 minutes" -> search_recipes(vegetarian=true, max_time=30) -> Guacamole, Mug Cake,
    Pancakes, Tomato Pasta (expected 4/4).
  - "something with chicken" -> search_recipes(ingredient="chicken") -> Easy Chicken Curry.
  - "I want pasta tonight" -> search_recipes(text_query="pasta") -> Quick Vegetarian Tomato Pasta.
  - "dinner ideas" -> search_recipes(category="Main course") -> all 5 main courses.
  - "how do I make the salmon?" -> get_recipe("salmon") -> full Oven-Baked Lemon Salmon recipe.
- Next: when Gemini quota is available, optionally re-run `--only 03,06,07,11` and the scenarios on Gemini for a
  complete side-by-side comparison; deployment (item 9).

## 2026-11-22 - Agent Short Memory

- Context: Manual test: the agent ended with "Would you like the ingredients and steps?", but every question was a
  fresh run, so replying "yes" got "I don't have the recipe you mean yet".
- Change: the Ask My Cookbook section is now a conversation (this browser session only). `build_task()` passes the
  last 3 exchanges (answers cut at 1500 chars) as plain text, so Gemini and the Claude fallback get the same input;
  instruction 8 says to use them only to resolve follow-ups and still fetch data via tools. Input clears after
  sending; "Clear conversation" resets.
- Result: live (Claude Haiku): "any breakfast recipes?" -> Fluffy Pancakes; "yes" -> full pancake recipe.

## 2026-11-22 - UI Tweaks After Manual Testing

- Change: removed the "Answered by Claude" note and the sidebar fallback status - end users do not need to know
  which model answered (the switch is still logged). The question box is now a form, so Enter sends the question
  and the box clears afterwards.
- Result: verified in the browser: Enter submits, input clears, no model note.

## 2026-11-23 - Bonus Features: Duplicates, Recipe Cache, Video Upload, Vague Search

- Context: MVP complete; implemented bonus features 1-3 from `PROJECT_CONTEXT.md` plus a cache and a saved-recipes
  table (ADR-014..017).
- Result (live, read-only on Notion): duplicate check found "Easy Chicken Curry" for "easy chicken curry!" and nothing
  for "Pizza Margherita". Recipe list: ~0.7 s per Notion load, ~0 s on a warm cache.
- Result (live, vague search): "something light, summery and slightly spicy" -> Gemini returned 503, Claude fallback
  answered. One tool call, `browse_recipes()` with no filters; 5 picks, all real recipes, each with a reason from
  its ingredients (Baked Feta Pasta first: red pepper flakes + tomato/lemon/basil). It said that no recipe is clearly
  both light and spicy, and pointed to the curry as spicy but heavier. Pass.
- Video: covered by offline tests (fake Gemini client); a live check with a real Reel is still open (HANDOFF).

## Log Entry Template

```
## YYYY-MM-DD - Short title
- Context:
- Change:
- Why:
- Result:
- Next:
```
