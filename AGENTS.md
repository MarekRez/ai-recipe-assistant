# Agent Operating Notes

This file defines practical rules for implementing and iterating this project.

## Mission

Deliver the smallest reliable end-to-end AI agent demo for recipe knowledge management.

## Guardrails

1. Keep MVP minimal. Do not add architecture that is not required for demo flow.
2. Validate LLM output through schema checks before persistence.
3. Never auto-save extracted recipe without explicit user confirmation.
4. Missing recipe information must be represented as `null`, not fabricated.
5. Prefer deterministic filtering over semantic/RAG methods in MVP search.

## Tooling Rules

1. The agent should orchestrate custom tools, not bypass them with ad-hoc logic.
2. Tool contracts are defined in `docs/AGENT_SPEC.md`.
3. Any tool signature change must update tests and docs in same change set.

## Git Workflow

1. Commit progressively, one logical unit per commit (e.g. config/deps, schema, one service + its tests, agent, UI, docs) - not one big commit at the end.
2. Each commit contains the code together with its tests and doc updates, and `python -m pytest` passes before committing.
3. Commit messages: Conventional Commits (`feat(scope): ...`, `fix: ...`, `test: ...`, `docs: ...`, `chore: ...`), imperative mood, body explains why when not obvious.
4. Never commit secrets (`.env`, `.streamlit/secrets.toml`) or local eval outputs (`evals/results/`).

## Definition of Done (MVP)

1. Recipe text/URL input works.
2. Structured extraction works and passes schema validation.
3. User can review/edit before save.
4. Save to Notion works with meaningful error handling.
5. Agent can answer cookbook queries by invoking tool chain.

## Non-Goals

Do not implement optional extensions until MVP flow is complete and stable.
