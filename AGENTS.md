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

1. The team (3-4 people) works **serially**: the team agrees who takes the next piece of work; the next person starts only after the previous one has merged into `main`. So there is never more than one open branch and no merge conflicts.
2. Each piece of work gets its own short-lived branch from up-to-date `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
3. The piece is finished by merging into `main` (GitHub PR or `git merge --ff-only`; fast-forward always works because `main` did not move), pushing `main` and deleting the branch.
4. Commit progressively, one logical unit per commit (e.g. config/deps, schema, one service + its tests, agent, UI, docs) - not one big commit at the end.
5. Each commit contains the code together with its tests and doc updates, and `python -m pytest` passes before committing.
6. Commit messages: Conventional Commits (`feat(scope): ...`, `fix: ...`, `test: ...`, `docs: ...`, `chore: ...`), imperative mood, body explains why when not obvious.
7. Never commit secrets (`.env`, `.streamlit/secrets.toml`) or local eval outputs (`evals/results/`).

## Team Handoff Protocol

Every agent session starts with a fresh context, so all context that matters must be in the repo.
`HANDOFF.md` is the baton: status, prioritized next steps, half-done work, open questions, gotchas.
Who takes the next piece of work is agreed in the team; the repo only carries the context.
In Claude Code use `/start-session` and `/handoff`; with any other agent follow the steps below manually.

Two levels:

- **Session** - one agent conversation. A piece of work may take several sessions of the same person on the same branch.
- **Piece of work** - one branch. Finished by merging into `main`; only then can the next teammate start.

Where things belong:

| What                                                  | Where                                   |
|-------------------------------------------------------|-----------------------------------------|
| Current state, next TODOs, half-done work, questions  | `HANDOFF.md` (overwrite, keep it short) |
| Durable rules and library/tooling gotchas             | `AGENTS.md` / `CLAUDE.md`               |
| Architecture decisions                                | `docs/DECISIONS.md` (new ADR)           |
| Implementation history, eval results                  | `AI_LOG.md` (append)                    |
| Code-level details                                    | the code, tests and git log             |

### Start of session

1. Continuing your own unfinished piece: `git checkout <your branch>` and `git pull`.
   Starting a new piece: `git checkout main`, `git pull`; check that no other `feat/`/`fix/`/`docs/` branch is open on
   the remote (`git branch -r`) - if one is, the previous piece is not merged yet: stop and tell the human.
   Then create the branch: `git checkout -b feat/<topic>`.
2. Read `HANDOFF.md` fully (on the branch you work on), then the docs it points to for the chosen task.
3. Run `python -m pytest` to confirm the baseline is green; if not, report before changing anything.
4. Confirm with the human which "Next Up" item(s) this piece of work covers.

### During the session

- Commit per logical unit (Git Workflow above) and tick finished items in `HANDOFF.md` as you go.
- Write a gotcha into `HANDOFF.md` the moment you hit it - not at the end, when it is easy to forget.

### End of session (never skip, even after a short session)

1. No uncommitted changes. Unfinished work is committed as `wip: ...` (only on your own branch; tests may fail only
   in a `wip` commit) and described under "In Progress / Half-Done": what is done, what is missing, the exact next
   step, which files.
2. Update `HANDOFF.md`: Status, Next Up (re-prioritize, add newly discovered tasks), In Progress, Open Questions,
   Gotchas, Last Session (date, who, branch, what was done - overwrite the previous entry).
3. Promote gotchas that will stay true (library quirks, environment fixes) from `HANDOFF.md` into `CLAUDE.md` /
   `AGENTS.md` and remove them from `HANDOFF.md`.
4. Notable results or decisions: append to `AI_LOG.md`; architectural decisions as a new ADR.
5. Commit `docs(handoff): <one-line summary>` and push the branch (so the work is never only on one laptop).

### Finishing a piece of work (handing over to the next teammate)

1. Everything from "End of session"; additionally "In Progress / Half-Done" must say `Nothing.` and the last commit
   must have green `python -m pytest`.
2. Merge into `main` (PR or `git checkout main && git pull && git merge --ff-only <branch>`), push `main`,
   delete the branch locally and on the remote.
3. Tell the human it is merged, so the team can hand over to the next person.

## Definition of Done (MVP)

1. Recipe text/URL input works.
2. Structured extraction works and passes schema validation.
3. User can review/edit before save.
4. Save to Notion works with meaningful error handling.
5. Agent can answer cookbook queries by invoking tool chain.

## Non-Goals

Do not implement optional extensions until MVP flow is complete and stable.
