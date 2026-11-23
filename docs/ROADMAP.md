# Roadmap

## Phase 1 - Foundation (done)

1. Finalize schema and tool contracts.
2. Set up app skeleton and environment configuration.
3. Prepare sample recipes for testing (`tests/fixtures/recipes`).

## Phase 2 - Core MVP Flow (implemented, needs live verification)

1. Implement recipe parsing via Gemini.
2. Implement review/edit UI.
3. Implement Notion save and retrieval.
4. Wire agent with custom tools.

Remaining: run against real Gemini + Notion credentials and fix whatever the live run reveals.

## Phase 3 - Validation

1. Run `evals.run_extraction_eval` and record results in `AI_LOG.md`.
2. Validate agent query behavior with the manual scenarios in `TEST_PLAN.md`.
3. Improve prompts and error messages based on results.

## Phase 4 - Demo Readiness

1. Deploy to Streamlit Community Cloud.
2. Final smoke test and script demo scenarios.
3. Freeze MVP scope.

## Post-MVP Backlog

1. ~~MP4/Reel upload parsing.~~ Done: video or photo upload in Add Recipe (ADR-016).
2. ~~Improved semantic query handling.~~ Done: `browse_recipes` for vague requests (ADR-017).
3. ~~Duplicate detection.~~ Done: warning in the review form (ADR-014).
