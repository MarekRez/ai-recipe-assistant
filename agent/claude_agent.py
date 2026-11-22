"""Claude fallback for the cookbook agent (ADR-012).

smolagents has no Anthropic model class (only via LiteLLM, which this project does not use), so when
Gemini is rate limited or down the question is answered by a small tool loop on the official Anthropic
SDK. It uses the *same* smolagents Tool objects, instructions and step limit as the Gemini agent - there
is still no save tool (ADR-005).
"""

from __future__ import annotations

import json
import logging

import anthropic
from smolagents import Tool

from services.config import claude_model
from services.errors import ProviderUnavailableError, ServiceError

logger = logging.getLogger(__name__)

_JSON_TYPES = {"string", "boolean", "integer", "number", "array", "object"}


def to_anthropic_tool(tool: Tool) -> dict:
    """Translate a smolagents Tool definition into an Anthropic tool definition."""
    properties, required = {}, []
    for name, spec in tool.inputs.items():
        prop = {"description": spec.get("description", "")}
        if spec.get("type") in _JSON_TYPES:
            prop["type"] = spec["type"]
        if "items" in spec:
            prop["items"] = spec["items"]
        properties[name] = prop
        if not spec.get("nullable"):
            required.append(name)
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


def _run_tool(tool: Tool | None, name: str, args: dict) -> tuple[str, bool]:
    if tool is None:
        return json.dumps({"error": f"Unknown tool {name}"}), True
    try:
        result = tool.forward(**args)
    except Exception as exc:  # tools normally return {"error": ...}; this guards against bad arguments
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": f"Tool failed: {exc}"}), True
    return json.dumps(result, ensure_ascii=False, default=str), isinstance(result, dict) and "error" in result


def run_claude_agent(question: str, tools: list[Tool], instructions: str, max_steps: int) -> str:
    """Answer one question with Claude calling the given tools. Each step is one API request."""
    client = anthropic.Anthropic()
    tool_defs = [to_anthropic_tool(t) for t in tools]
    by_name = {t.name: t for t in tools}
    messages: list[dict] = [{"role": "user", "content": question}]

    for _ in range(max_steps):
        try:
            response = client.messages.create(
                model=claude_model(),
                max_tokens=16000,
                system=instructions,
                tools=tool_defs,
                messages=messages,
            )
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as exc:
            raise ProviderUnavailableError("Claude is not reachable right now. Try again later.", str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise ServiceError("Claude rejected the request. Check ANTHROPIC_API_KEY and CLAUDE_MODEL.", str(exc)) from exc

        if response.stop_reason == "refusal":
            raise ServiceError("Claude declined to answer this request.", str(response.stop_details))
        # Append the full content unchanged (incl. thinking blocks) - required for the next turn.
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            if response.stop_reason == "pause_turn":
                continue
            return "".join(b.text for b in response.content if b.type == "text").strip()

        results = []
        for block in tool_uses:
            content, is_error = _run_tool(by_name.get(block.name), block.name, dict(block.input))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    raise ServiceError("The agent could not answer this request. Try rephrasing it.", "Claude step limit reached")
