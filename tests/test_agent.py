"""Agent tools and tool-selection flow with a scripted model and mocked services."""

import pytest
from smolagents import Model
from smolagents.models import ChatMessage, ChatMessageToolCall, ChatMessageToolCallFunction, MessageRole

from agent import recipe_agent, tools
from models.recipe import SearchFilters
from services.errors import ServiceError


class ScriptedModel(Model):
    """Returns pre-defined assistant messages instead of calling an LLM."""

    def __init__(self, replies):
        super().__init__(model_id="scripted")
        self.replies = list(replies)
        self.offered_tools = []

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        self.offered_tools.append(sorted(t.name for t in tools_to_call_from or []))
        return self.replies.pop(0)


def tool_call(name, arguments, call_id="call_1"):
    return ChatMessage(
        role=MessageRole.ASSISTANT,
        content=None,
        tool_calls=[
            ChatMessageToolCall(
                id=call_id, type="function", function=ChatMessageToolCallFunction(name=name, arguments=arguments)
            )
        ],
    )


# --- tools -------------------------------------------------------------------


def test_agent_cannot_save_recipes():
    names = {t.name for t in tools.make_agent_tools()}
    assert names == {"search_recipes", "get_recipe", "parse_recipe"}


def test_search_tool_builds_filters(monkeypatch):
    seen = []
    monkeypatch.setattr(tools, "search_recipes_in_notion", lambda f: seen.append(f) or [{"name": "A"}])
    result = tools.search_recipes(vegetarian=True, max_time=30)
    assert seen == [SearchFilters(vegetarian=True, max_time=30)]
    assert result == {"count": 1, "results": [{"name": "A"}]}


def test_tools_return_errors_instead_of_raising(monkeypatch):
    def fail(*args):
        raise ServiceError("Notion is down")

    monkeypatch.setattr(tools, "search_recipes_in_notion", fail)
    monkeypatch.setattr(tools, "get_recipe_from_notion", fail)
    assert tools.search_recipes(text_query="x") == {"error": "Notion is down"}
    assert tools.get_recipe(name_or_id="x") == {"error": "Notion is down"}


def test_get_recipe_not_found(monkeypatch):
    monkeypatch.setattr(tools, "get_recipe_from_notion", lambda key: None)
    assert tools.get_recipe(name_or_id="pizza") == {"found": False}


def test_parse_tool_only_stages_draft(monkeypatch):
    monkeypatch.setattr(tools, "parse_recipe_draft", lambda value: {"name": "Soup"})
    monkeypatch.setattr(tools, "save_recipe_to_notion", lambda r: pytest.fail("agent must not save"))
    staged = []
    result = tools.make_parse_recipe_tool(staged.append)(text_or_url="Soup recipe")
    assert staged == [{"name": "Soup"}]
    assert "not saved" in result["status"]


def test_save_recipe_validates_before_saving(monkeypatch):
    monkeypatch.setattr(tools, "save_recipe_to_notion", lambda r: pytest.fail("invalid recipe must not be saved"))
    with pytest.raises(Exception):
        tools.save_recipe({"name": ""})


# --- agent loop ----------------------------------------------------------------


def test_agent_runs_search_tool_chain(monkeypatch):
    seen = []
    monkeypatch.setattr(
        tools,
        "search_recipes_in_notion",
        lambda f: seen.append(f) or [{"name": "Greek Salad", "total_time_minutes": 15}],
    )
    model = ScriptedModel(
        [
            tool_call("search_recipes", {"vegetarian": True, "max_time": 30}),
            tool_call("final_answer", {"answer": "Greek Salad (15 min)"}, call_id="call_2"),
        ]
    )
    answer = recipe_agent.ask_agent("Vegetarian meals under 30 minutes?", model=model)
    assert answer == "Greek Salad (15 min)"
    assert seen == [SearchFilters(vegetarian=True, max_time=30)]
    assert "save_recipe" not in model.offered_tools[0]


def test_agent_parse_flow_stages_draft(monkeypatch):
    monkeypatch.setattr(tools, "parse_recipe_draft", lambda value: {"name": "Pancakes"})
    staged = []
    model = ScriptedModel(
        [
            tool_call("parse_recipe", {"text_or_url": "Pancakes: 1 egg"}),
            tool_call("final_answer", {"answer": "Draft ready for review."}, call_id="call_2"),
        ]
    )
    recipe_agent.ask_agent("Save this: Pancakes: 1 egg", on_draft=staged.append, model=model)
    assert staged == [{"name": "Pancakes"}]


def test_agent_model_failure_becomes_service_error():
    class BrokenModel(ScriptedModel):
        def generate(self, *args, **kwargs):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with pytest.raises(ServiceError, match="rate limit"):
        recipe_agent.ask_agent("anything", model=BrokenModel([]))
