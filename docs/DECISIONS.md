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
  question, is retried with Claude (`CLAUDE_MODEL`, default `claude-haiku-5-5`). Without the key nothing changes.
  Haiku is enough for schema extraction and three simple tools and costs a fraction of the larger models.
  - Extraction: `services/claude_service.py`, same prompt, `Recipe` as structured output, re-validated as usual.
  - Agent: smolagents has no Anthropic model class (only via LiteLLM, see ADR-010), so `agent/claude_agent.py`
    runs a small tool loop on the official `anthropic` SDK with the same smolagents tools and instructions.
    A question is answered by one model only, never a mix. smolagents' own rate-limit retry (minutes of waiting)
    is turned off when the fallback is configured.
  - No fallback on non-outage results (`NOT_A_RECIPE`, validation errors, rejected config) - Claude would not
    change those.
  - The switch is logged (warning) but not shown to end users. The eval pins one provider per run (`--provider`),
    so metrics describe one model.
- Why: The Gemini free tier allows ~20 requests per day per model and newer Flash models often return 503 "high
  demand"; a teammate has Claude API credits. Teammates without a Claude key keep the free Gemini-only setup.

## ADR-013: Shared Password for the Deployed App

- Date: 2026-11-22
- Decision: If `APP_PASSWORD` is set, `app.py` shows only a password screen until the shared password is entered
  (compared with `hmac.compare_digest`, remembered for the browser session). Unset = no screen (local development).
- Why: The deployed app holds the team's API keys (Gemini quota, Claude credits) and writes to the shared Notion
  database. Real user accounts are out of MVP scope; a shared password for the team and the teacher is enough.

## ADR-014: Duplicate Recipe Warning Before Save

- Date: 2026-11-23
- Decision: When a draft reaches the review form (Process Recipe or the agent's `parse_recipe`), the app checks
  the saved recipes once (`agent.tools.find_duplicate_recipes` -> `services/recipe_search.find_duplicates`) and shows
  a warning with links to matching Notion pages. A match is the same name (ignoring case, spacing and punctuation)
  or the same source URL (ignoring http/https, `www.`, trailing slash, `#fragment` and tracking parameters such as
  `utm_*`/`fbclid`; other query parameters count, e.g. `?id=2`). Saving is still allowed - the user decides.
  A failed check (Notion down) only means no warning; it never blocks the review or the save.
- Why: Bonus feature 3 in `PROJECT_CONTEXT.md`. Deterministic and cheap (one Notion read, no LLM request), in line
  with ADR-009. Fuzzy name matching ("Chicken Curry" vs. "Easy Chicken Curry") was left out: it would warn about
  genuinely different recipes, and a warning that is often wrong gets ignored. Not an agent tool: the agent has no
  save step to guard, and the review form shows the warning for agent drafts as well.

## ADR-015: Recipe List Cache and "My Recipes" View

- Date: 2026-11-23
- Decision: `notion_service.list_all_recipes()` keeps the loaded recipes for 60 s (`CACHE_TTL_SECONDS`), shared by
  all sessions of the app process. `save_recipe_to_notion` clears it, so a saved recipe is visible right away;
  changes made directly in Notion show up after at most 60 s, or at once via "Refresh" in My Recipes. Failed reads
  are not cached; callers get copies. A "My Recipes" section (behind a toggle, so Notion is read only when opened)
  shows all saved recipes as a table through the UI function `list_saved_recipes` - no LLM request.
  Update 2026-11-24: "View recipe" (select a row, click the button) opens one recipe read-only in a dialog. The UI
  function `get_saved_recipe` takes the full record from the same cache - no per-recipe `pages.retrieve` request.
- Why: Search, name lookup and the duplicate check (ADR-014) each load the whole data source (ADR-009), and one agent
  answer often makes 2-3 of these calls (~0.7 s each, measured live). Seeing what is saved should not cost one of the
  ~20 free Gemini requests per day. Still deterministic, no new dependency; a module-level dict instead of
  `st.cache_data` keeps Streamlit out of `services/`.

## ADR-016: Recipe Extraction From an Uploaded Video or Photos

- Date: 2026-11-23
- Decision: Add Recipe accepts one uploaded video (MP4/MOV/WEBM) or up to 5 photos/screenshots (JPG/PNG/WEBP/HEIC)
  - never mixed - max 100 MB per file (`MAX_UPLOAD_MB` = `server.maxUploadSize`), optionally with the caption pasted
  in the text field. The files go to the Gemini Files API, the app waits until they are processed (max 120 s),
  extracts one recipe in one request with the text rules plus media rules (amounts only when said or written, never
  read off the picture; several photos are one recipe, in order), then deletes the uploads. A caption that is just
  a link (e.g. the Reel URL) becomes `source_url` and is not sent to the model. Same review form and duplicate check.
  Gemini first. On a Gemini outage (incl. the daily free-tier limit) JPG/PNG/WEBP photos go to Claude if
  `ANTHROPIC_API_KEY` is set (ADR-012): re-encoded as JPEG, long edge max 1568 px, EXIF rotation applied (Pillow),
  same media prompt. Video (Claude cannot read it) and HEIC (Pillow cannot open it without a plugin) have no
  fallback - the user is told to upload JPG/PNG or paste the text.
  Not an agent tool - the chat cannot take files. No Instagram downloading: a pasted Reel URL goes through the normal
  URL path, which Instagram blocks with a login page (non-goal in `PROJECT_CONTEXT.md`).
- Why: Bonus feature 1 in `PROJECT_CONTEXT.md`; photos (cookbook pages, handwritten cards, caption screenshots)
  reuse the same path. Gemini reads both natively, so no new dependency, OCR or transcription step. The Files API
  works for any Reel or phone-photo size, unlike inline bytes (~20 MB per request).
- Also: a 429 for the *daily* free-tier quota now says "try again tomorrow" instead of "wait a minute"
  (`gemini_service.is_daily_limit`), for extraction and for the agent without Claude.
- Also: `source_url` is now always set from the input (or `None`) for text extraction too - before, a URL invented
  by the model could survive when the input was plain text (CLAUDE.md invariant).

## ADR-017: Vague Requests - the Model Picks From Compact Recipe Summaries

- Date: 2026-11-23
- Decision: New agent tool `browse_recipes(vegetarian, max_time)` returns every saved recipe (after those optional
  hard filters) as name, category, total time, vegetarian, tags and ingredient names - no quantities or steps, max
  150. For requests no filter can express ("light, summery and slightly spicy") the instructions (rule 3a) tell the
  agent to browse and choose at most 5 itself, with a reason per pick taken from the listed data, and to say so when
  nothing fits. Clear requests still use `search_recipes` (ADR-009 unchanged).
- Why: Bonus feature 2 in `PROJECT_CONTEXT.md`, which allows only a small extension - no vector DB or RAG. The agent
  model already runs for the question, so this costs no extra LLM request (browse + answer = 2 steps of 4); the
  picks can only be recipes the tool returned. Embeddings would add a dependency and an index to keep in sync for a
  cookbook of tens of recipes. Above ~150 recipes this would need real retrieval.
