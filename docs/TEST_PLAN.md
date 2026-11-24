# Test Plan

## Scope

Validate extraction quality, schema adherence, Notion integration, and tool-driven agent behavior.

## Test Data

`tests/fixtures/recipes/` - 10 recipes (`NN_name.txt`) with manually written expected output (`NN_name.json`)
plus one negative case (`11_not_a_recipe`, `{"expect_error": true}`).
Coverage: complete recipes, missing times, step durations that must not become times, ranges/"to taste",
fractions, prose format, a Slovak recipe, meat/fish vs. vegetarian.

Before reporting results, re-check the expected JSON files by hand - they are the ground truth.

## Automated Tests (pytest, offline)

Run: `.venv/Scripts/python -m pytest`. No test calls Gemini or Notion.

| File                       | What it covers                                                        |
|----------------------------|-----------------------------------------------------------------------|
| `test_models.py`           | schema rules, nulls, effective total time                             |
| `test_extraction.py`       | fixtures are schema-valid, parser validation, URL detection, JSON-LD  |
| `test_search.py`           | deterministic filters for the example intents, duplicate matching     |
| `test_notion.py`           | property mapping, chunking, round trip, errors, schema check, cache   |
| `test_agent.py`            | tool contracts, no save tool, scripted-model tool chain               |
| `test_app.py`              | review-before-save flow, duplicate warning, My Recipes, View recipe   |
| `test_recipe_view.py`      | `get_saved_recipe` (cached lookup by id), dialog display helpers      |
| `test_media.py`            | video/photo upload, processing wait, cleanup, input checks            |
| `test_fallback.py`         | Claude fallback (text, agent, photos), daily-limit messages           |
| `test_eval_scoring.py`     | eval metric logic                                                     |

## Live Extraction Eval (manual)

Run: `.venv/Scripts/python -m evals.run_extraction_eval --out evals/results/<date>.json`
(`--provider claude` evaluates the Claude fallback instead of Gemini; one model per run, ADR-012).
Rows that hit a rate limit / outage are shown as SKIP and left out of every metric.

Metrics:

1. Schema validity - `valid_outputs / total_outputs`.
2. Extraction accuracy - name, ingredient recall/precision, quantity and unit accuracy, time fields.
3. Hallucination control - extra ingredients, quantities filled where the source had none, invented times.
   Flagged cases are printed for manual review.
4. Negative case - non-recipe text is rejected.

## Notion Integration (manual)

1. Sidebar "Check Notion database" reports no problems.
2. Save 10 fixture recipes through the UI, verify pages and properties in Notion.
3. Ask the agent about them (next section).

## Agent Search (manual, after saving the fixtures)

| Query                                  | Expected recipes                                    |
|----------------------------------------|-----------------------------------------------------|
| vegetarian meals under 30 minutes      | Tomato Pasta, Pancakes, Mug Cake, Guacamole         |
| something with chicken                 | Easy Chicken Curry                                  |
| I want pasta tonight                   | Quick Vegetarian Tomato Pasta                       |
| dinner ideas                           | all Main course recipes                             |
| how do I make the salmon?              | full Oven-Baked Lemon Salmon recipe                 |

| something light, summery and slightly spicy | `browse_recipes`, max 5 picks with reasons, says if nothing fits well |

Video / photos (manual, uses Gemini): upload a short recipe video with and without its caption, and 1-2 photos of
a cookbook page or handwritten card; amounts that are only visible in the picture must stay empty; a non-recipe
clip or photo must be rejected.

Record pass/fail and the tool calls the agent made (shown in logs) in `AI_LOG.md`.
