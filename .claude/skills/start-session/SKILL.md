---
name: start-session
description: Start a work session on this project with a fresh context - sync git, pick or continue the branch, read HANDOFF.md, verify tests are green, agree on the task. Use at the beginning of every session, or when the user says "začínam", "pokračujem", "pick up", "what's next".
---

# Start session

Follow `AGENTS.md` -> "Team Handoff Protocol" -> "Start of session". Concretely:

1. Run `git status` and `git branch --show-current`.
   - Uncommitted changes you did not make: stop and ask the user what they are.
2. Ask (or infer from the user's message) whether this continues the user's own unfinished branch or starts a new piece of work.
   - **Continue**: `git checkout <branch>`, `git pull`.
   - **New piece**: `git checkout main`, `git pull`, then `git branch -r`. If a `feat/`, `fix/` or `docs/` branch other
     than `main` is still on the remote, the previous piece is not merged - stop and tell the user (the team works
     serially). Otherwise create `feat/<topic>` (or `fix/`, `docs/`) once the task is agreed in step 5.
   - If `git pull` fails with an SSL certificate error on Windows, suggest `git config --global http.sslBackend schannel`.
3. Read `HANDOFF.md` completely. Then read only the docs/code it points to for the likely task.
4. Run `.venv/Scripts/python -m pytest -q`. If it is not green, report the failures before changing anything.
   If `.venv` is missing or dependencies are not installed, set it up per `README.md` (Quick Start) first.
5. Give the user a short briefing in their language:
   - current status (2-3 lines),
   - half-done work and open questions from `HANDOFF.md`,
   - gotchas relevant to the next items,
   - the top 1-3 "Next Up" items with your recommendation which to take.
   Ask which item(s) this piece of work covers, then create the branch if it is a new piece.

Do not start implementing before the user confirms the task.
