"""smolagents setup for the Recipe Knowledge Assistant.

ToolCallingAgent (no generated-code execution) on Gemini via its OpenAI-compatible endpoint.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from smolagents import Model, OpenAIServerModel, ToolCallingAgent
from smolagents.monitoring import LogLevel
from smolagents.utils import AgentError

from agent.claude_agent import run_claude_agent
from agent.tools import make_agent_tools
from services.config import claude_fallback_enabled, get_setting
from services.errors import ServiceError
from services.gemini_service import DAILY_LIMIT_MESSAGE, is_daily_limit

logger = logging.getLogger(__name__)

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MAX_STEPS = 4  # each step is one Gemini request; the free tier is rate limited

INSTRUCTIONS = """You are a cookbook assistant for the user's personal recipe collection stored in Notion.

Rules:
1. Get all recipe data through tools. Never invent recipes, ingredients, times or tool results.
2. For cookbook questions call search_recipes with explicit filters:
   - "vegetarian" -> vegetarian=True
   - "under/within N minutes" -> max_time=N
   - a specific ingredient ("with chicken") -> ingredient="chicken"
   - a dish type or keyword ("pasta", "curry") -> text_query
   - meal type: "dinner"/"lunch" -> category="Main course"; "breakfast" -> category="Breakfast"; "dessert" -> category="Dessert"
3. If a search returns no results, retry once with fewer filters (e.g. only text_query) and say which filter you relaxed.
3a. Vague or mood-based requests that no filter expresses ("light", "summery", "slightly spicy", "comfort food",
    "healthy", "something fresh") -> call browse_recipes (pass vegetarian / max_time only if the user stated them)
    and choose at most 5 recipes yourself. Judge only from the returned names, categories, tags, times and
    ingredients, and give a short reason for each pick (e.g. "chili flakes -> slightly spicy"). If nothing fits
    well, say so honestly and offer the closest one or two - never invent a recipe or an ingredient.
4. Use get_recipe when the user wants details of one recipe (ingredients, steps).
5. When the user provides recipe text or a URL to add/save, call parse_recipe. You cannot save recipes yourself:
   tell the user the draft is ready for review and must be confirmed with "Save to Notion" in the Add Recipe section.
6. If a tool returns {"error": ...}, tell the user the error briefly. Do not retry the same call.
7. Answer concisely in the user's language. For each recipe list the name, total time and category.
8. The task may start with the earlier conversation. Use it only to understand short follow-ups ("yes",
   "the second one", "show me the steps"); still get recipe data through tools, never from the earlier answers.
9. You only help with the user's recipe collection and cooking. If the question is unrelated (general knowledge,
   coding, news, homework, ...), do not answer it and do not call tools: reply in one sentence that you can only
   help with their recipes, and suggest an example question such as "Find vegetarian meals under 30 minutes".
"""

HISTORY_TURNS = 3  # earlier question/answer pairs passed to the agent (short memory, per browser session)
HISTORY_ANSWER_CHARS = 1500  # long answers (full recipes) are cut - details are fetched again via tools


def build_model() -> Model:
    return OpenAIServerModel(
        model_id=get_setting("GEMINI_MODEL"),
        api_base=GEMINI_OPENAI_BASE_URL,
        api_key=get_setting("GEMINI_API_KEY"),
        # smolagents retries rate limits itself (60 s, then longer, 3 attempts). With the Claude fallback
        # configured, fail fast and switch instead of keeping the user waiting for minutes.
        retry=not claude_fallback_enabled(),
    )


def build_agent(on_draft: Callable[[dict], None] | None = None, model: Model | None = None) -> ToolCallingAgent:
    """Create the agent with the custom tools registered. `model` can be injected in tests."""
    return ToolCallingAgent(
        tools=make_agent_tools(on_draft),
        model=model or build_model(),
        instructions=INSTRUCTIONS,
        max_steps=MAX_STEPS,
        verbosity_level=LogLevel.OFF,
    )


_OUTAGE_MARKERS = ("429", "RateLimit", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "InternalServerError")


def _is_provider_outage(detail: str) -> bool:
    return any(marker in detail for marker in _OUTAGE_MARKERS)


def build_task(question: str, history: list[dict] | None = None) -> str:
    """Prefix the question with the last few exchanges so follow-ups like "yes" make sense.

    Plain text, so the Gemini agent and the Claude fallback get exactly the same input.
    """
    turns = (history or [])[-HISTORY_TURNS:]
    if not turns:
        return question
    lines = ["Earlier conversation (most recent last):"]
    for turn in turns:
        answer = turn["answer"]
        if len(answer) > HISTORY_ANSWER_CHARS:
            answer = answer[:HISTORY_ANSWER_CHARS] + " [...]"
        lines += [f"User: {turn['question']}", f"Assistant: {answer}"]
    lines += ["", f"Current question: {question}"]
    return "\n".join(lines)


def ask_agent_with_provider(
    question: str,
    on_draft: Callable[[dict], None] | None = None,
    model: Model | None = None,
    history: list[dict] | None = None,
) -> tuple[str, str]:
    """Run one cookbook question and return (answer, provider).

    Gemini first; if Gemini is rate limited or down and ANTHROPIC_API_KEY is set, the whole question is
    answered again by Claude with the same tools (ADR-012) - never a mix of both models in one answer.
    """
    task = build_task(question, history)
    agent = build_agent(on_draft=on_draft, model=model)
    try:
        return str(agent.run(task)), "gemini"
    except AgentError as exc:
        logger.exception("Agent run failed")
        detail = f"{exc} | cause: {exc.__cause__!r}"
        if not _is_provider_outage(detail):
            raise ServiceError("The agent could not answer this request. Try rephrasing it.", detail) from exc
        if not claude_fallback_enabled():
            if is_daily_limit(detail):
                raise ServiceError(DAILY_LIMIT_MESSAGE, detail) from exc
            raise ServiceError("Gemini rate limit reached or Gemini is unavailable. Try again later.", detail) from exc
        logger.warning("Gemini unavailable - answering with Claude")
        answer = run_claude_agent(task, make_agent_tools(on_draft), INSTRUCTIONS, MAX_STEPS)
        return answer, "claude"


def ask_agent(
    question: str,
    on_draft: Callable[[dict], None] | None = None,
    model: Model | None = None,
    history: list[dict] | None = None,
) -> str:
    """Run one cookbook question through the agent and return its final answer as text."""
    return ask_agent_with_provider(question, on_draft=on_draft, model=model, history=history)[0]
