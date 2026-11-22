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

## ADR-005: The Agent Cannot Save; It Stages Drafts

- Date: 2026-11-18
- Decision: The agent has `search_recipes`, `get_recipe` and `parse_recipe` only. `parse_recipe` stages a draft
  (callback into UI session state). `save_recipe` is a tool-layer function called only by the UI "Save to Notion"
  button after review.
- Why: An agent run cannot pause for a Streamlit confirmation, so a save tool would bypass ADR-004.

## ADR-006: `vegetarian` Stored as Select Yes / No / Unknown

- Date: 2026-11-18
- Decision: Notion `Vegetarian` is a Select, not a Checkbox.
- Why: A checkbox cannot represent `null`; unknown must not become "not vegetarian".

## ADR-007: `Ingredient.raw` Keeps the Original Line

- Date: 2026-11-18
- Decision: Add optional `raw` to `Ingredient`; non-numeric amounts ("1-2", "to taste") keep `quantity: null`.
- Why: Preserves information without forcing the LLM to invent a single number.

## ADR-008: Notion Data Source Id (API 2025-09-03)

- Date: 2026-11-18
- Decision: Configure `NOTION_DATA_SOURCE_ID`; query via `data_sources.query`, create pages with a
  `data_source_id` parent.
- Why: notion-client 3.x targets API 2025-09-03, which removed `databases.query`.

## ADR-009: Search = Load All + Filter in Python

- Date: 2026-11-18
- Decision: `search_recipes` loads all recipe pages and filters with the pure function `filter_recipes`.
- Why: Dataset is ~15 recipes; logic stays deterministic, unit-testable offline and independent of Notion filter syntax.
  Revisit only if the cookbook grows to hundreds of recipes.

## ADR-010: Gemini Access

- Date: 2026-11-18
- Decision: Extraction uses `google-genai` with `response_schema=Recipe` (JSON mode). The agent uses
  smolagents `OpenAIServerModel` against Gemini's OpenAI-compatible endpoint. Model id comes from `GEMINI_MODEL`.
- Why: `google-generativeai` is deprecated. The OpenAI-compatible endpoint needs only the light `openai` package
  (no LiteLLM dependency tree).

## ADR-011: URL Input via JSON-LD First

- Date: 2026-11-18
- Decision: Fetch the page with `requests`; use schema.org `Recipe` JSON-LD if present, otherwise visible text.
  Blocked sites produce a "paste the text instead" message.
- Why: Most recipe sites embed JSON-LD, which gives clean input and fewer hallucinations.

## ADR-012: Optional Claude Fallback When Gemini Is Unavailable

- Date: 2026-11-22
- Decision: Gemini stays the primary model. If Gemini returns a rate limit or outage (HTTP 429 / 5xx ->
  `ProviderUnavailableError`) and `ANTHROPIC_API_KEY` is set, the same extraction request, or the whole agent
  question, is retried with Claude (`CLAUDE_MODEL`, default `claude-opus-5-5`). Without the key nothing changes.
  - Extraction: `services/claude_service.py`, same prompt, `Recipe` as structured output, re-validated as usual.
  - Agent: smolagents has no Anthropic model class (only via LiteLLM, see ADR-010), so `agent/claude_agent.py`
    runs a small tool loop on the official `anthropic` SDK with the same smolagents tools and instructions.
    A question is answered by one model only, never a mix. smolagents' own rate-limit retry (minutes of waiting)
    is turned off when the fallback is configured.
  - No fallback on non-outage results (`NOT_A_RECIPE`, validation errors, rejected config) - Claude would not
    change those.
  - The UI labels Claude answers. The eval pins one provider per run (`--provider`), so metrics describe one model.
- Why: The Gemini free tier allows ~20 requests per day per model and newer Flash models often return 503 "high
  demand"; a teammate has Claude API credits. Teammates without a Claude key keep the free Gemini-only setup.
