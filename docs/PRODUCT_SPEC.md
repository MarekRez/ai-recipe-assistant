# Product Specification

## Objective

Build a small AI Recipe Knowledge Assistant MVP that demonstrates AI orchestration + structured extraction + API integration + personal knowledge management.

## Primary User Flows

1. User pastes recipe text or URL.
2. System extracts structured recipe data.
3. User reviews and edits extracted data.
4. User confirms save to Notion.
5. User asks natural-language cookbook query.
6. Agent chooses tools and returns relevant recipes.
7. User browses saved recipes in "My Recipes" (table, no AI request) and opens one with "View recipe" to read it in
   the app; the "Open" link still goes to the Notion page.

## Functional Requirements

1. Input supports plain text and URL.
2. LLM extraction maps input into recipe schema.
3. Missing values are set to `null` (no invention).
4. User confirmation is mandatory before save.
5. Notion storage must persist recipe fields.
6. Agent can search and fetch saved recipes through tools.
7. "View recipe" (select a row in My Recipes, then the button) shows one saved recipe read-only in a dialog:
   overview (category, prep/cook/total time, vegetarian, tags), ingredients, numbered steps, source link and an
   "Open in Notion" button. Missing values read "not stated"; nothing is estimated and nothing is written.

## Non-Functional Requirements

1. Keep architecture intentionally minimal.
2. Clear error messages for API failures.
3. Reasonable response time for common requests.
4. Environment secrets managed via `.env`.

## Acceptance Criteria (MVP)

1. End-to-end flow works for at least 10 sample recipes.
2. Schema validation success rate is measurable.
3. Hallucination checks show no invented values in reviewed samples.
4. Notion write and read operations succeed reliably.
5. Agent handles example query set from project context.
