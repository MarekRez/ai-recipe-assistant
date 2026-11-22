"""UI smoke tests with Streamlit AppTest: review-before-save flow (services mocked)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from agent import recipe_agent, tools
from models.recipe import Recipe
from tests.conftest import load_expected

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def saved(monkeypatch):
    calls = []
    monkeypatch.setattr(tools, "parse_recipe_draft_with_provider", lambda text: (load_expected("05_lentil_soup"), "gemini"))
    monkeypatch.setattr(tools, "save_recipe", lambda recipe: calls.append(recipe) or {"id": "p1", "url": "https://notion.so/p1"})
    return calls


def process(at: AppTest) -> AppTest:
    at.text_area[0].input("Red lentil soup ...")
    next(b for b in at.button if b.label == "Process Recipe").click()
    return at.run()


def test_nothing_is_saved_without_confirmation(saved):
    at = process(AppTest.from_file(APP, default_timeout=30).run())
    assert not at.exception
    assert at.text_input[0].value == "Red Lentil Soup"  # draft shown for review
    assert saved == []


def test_confirmed_edits_are_saved(saved):
    at = process(AppTest.from_file(APP, default_timeout=30).run())
    at.text_input[0].set_value("Red Lentil Soup (edited)")
    next(b for b in at.button if b.label == "Save to Notion").click()
    at.run()
    assert not at.exception
    assert len(saved) == 1
    recipe = saved[0]
    Recipe.model_validate(recipe)  # what the real save_recipe does first
    assert all(type(v) in (str, float, type(None)) for ing in recipe["ingredients"] for v in ing.values())
    assert recipe["name"] == "Red Lentil Soup (edited)"
    assert recipe["total_time_minutes"] is None  # missing stays null
    assert recipe["vegetarian"] is True
    assert recipe["ingredients"][1]["name"] == "carrots" and recipe["ingredients"][1]["quantity"] is None
    assert len(recipe["instructions"]) == 3
    assert any("Saved" in s.value for s in at.success)


def test_agent_draft_goes_to_review(monkeypatch, saved):
    def fake_ask(question, on_draft=None, model=None, history=None):
        on_draft(load_expected("09_guacamole"))
        return "Draft ready.", "gemini"

    monkeypatch.setattr(recipe_agent, "ask_agent_with_provider", fake_ask)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("Add this guacamole recipe ...")
    next(b for b in at.button if b.label == "Ask Agent").click()
    at.run()
    assert not at.exception
    assert at.text_input[0].value == "Simple Guacamole"
    assert saved == []


def test_claude_answers_are_labelled(monkeypatch):
    monkeypatch.setattr(recipe_agent, "ask_agent_with_provider", lambda q, on_draft=None, model=None, history=None: ("Pasta.", "claude"))
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("pasta?")
    next(b for b in at.button if b.label == "Ask Agent").click()
    at.run()
    assert not at.exception
    assert any("Answered by Claude" in c.value for c in at.caption)


def ask(at: AppTest, text: str) -> AppTest:
    at.text_input(key="question_input").input(text)
    next(b for b in at.button if b.label == "Ask Agent").click()
    return at.run()


def test_follow_up_questions_get_the_conversation(monkeypatch):
    seen = []

    def fake_ask(question, on_draft=None, model=None, history=None):
        seen.append((question, [t["question"] for t in history or []]))
        return f"Answer to {question}", "gemini"

    monkeypatch.setattr(recipe_agent, "ask_agent_with_provider", fake_ask)
    at = ask(AppTest.from_file(APP, default_timeout=30).run(), "breakfast ideas?")
    at = ask(at, "yes, show the steps")
    assert not at.exception
    assert seen == [("breakfast ideas?", []), ("yes, show the steps", ["breakfast ideas?"])]
    assert at.text_input(key="question_input").value == ""  # input cleared for the next question
    assert [m.markdown[0].value for m in at.chat_message] == [
        "breakfast ideas?", "Answer to breakfast ideas?", "yes, show the steps", "Answer to yes, show the steps",
    ]
    next(b for b in at.button if b.label == "Clear conversation").click()
    at.run()
    assert len(at.chat_message) == 0
