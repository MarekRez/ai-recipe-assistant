---
name: handoff
description: End a work session and preserve all context for the next session or teammate - commit everything, update HANDOFF.md, promote durable gotchas, push; optionally finish the piece of work by merging into main. Use when the user says they are done, "končím", "odovzdaj", "handoff", "merge do main", or before a session ends with unsaved context.
---

# Handoff

Follow `AGENTS.md` -> "Team Handoff Protocol" -> "End of session" (and "Finishing a piece of work" if the user wants to merge).

1. **Ask** (unless the user already said it): is the piece of work finished and should it be merged into `main`, or does only this session end?
2. **Commit everything.** `git status` must end clean.
   - Finished units: normal Conventional Commits, `python -m pytest -q` green.
   - Unfinished work: `wip: <what>` commit on the branch (never on `main`).
3. **Update `HANDOFF.md`** (overwrite, keep it short and concrete - the reader is an agent with zero context):
   - *Status*: what works now, what is verified vs. not, current branch.
   - *Next Up*: tick done items, re-prioritize, add tasks discovered in this session.
   - *In Progress / Half-Done*: for unfinished work - what is done, what is missing, the exact next step, files involved. `Nothing.` if finished.
   - *Open Questions*: decisions that need a human, with your recommendation.
   - *Gotchas*: surprises from this session (errors and their fixes, misleading docs, env quirks).
   - *Last Session*: date, who, branch, what was done - replace the previous entry.
   Review the whole conversation for things worth keeping; do not just summarize the last few messages.
4. **Promote durable knowledge**: gotchas that will stay true go to `CLAUDE.md` ("Library facts" / "Invariants") or
   `AGENTS.md` and are removed from `HANDOFF.md`. Architectural decisions -> new ADR in `docs/DECISIONS.md`.
   Notable results (eval metrics, live test outcomes) -> append to `AI_LOG.md`.
5. Commit `docs(handoff): <one-line summary>` and push the branch. If the push fails, tell the user exactly why.
6. **If finishing the piece** (user confirmed): "In Progress" must be `Nothing.` and tests green, then
   `git checkout main && git pull && git merge --ff-only <branch> && git push`, delete the branch locally and on the
   remote. If `--ff-only` fails, `main` moved - stop and ask the user instead of creating a merge commit.
   (The user may prefer a GitHub PR instead - then push the branch and give them the compare link.)
7. Tell the user in their language: what was committed, what `HANDOFF.md` now says is next, and whether `main` is
   ready for the next teammate.
