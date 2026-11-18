# Architecture Decisions (ADR Lite)

## ADR-001: Single Python Project

- Date: 2026-11-18
- Decision: Keep everything in one Python project.
- Why: Fastest path to MVP and easiest semester demo.

## ADR-002: Notion as Structured Knowledge Store

- Date: 2026-11-18
- Decision: Use Notion API as central recipe store.
- Why: Meets project goals with low infrastructure overhead.

## ADR-003: No Vector DB in MVP

- Date: 2026-11-18
- Decision: Use deterministic structured filtering for search.
- Why: Simpler, cheaper, and aligned with requirements.

## ADR-004: Mandatory Human Review Before Save

- Date: 2026-11-18
- Decision: User confirmation is required before `save_recipe`.
- Why: Reduces hallucination risk and demonstrates HITL control.
