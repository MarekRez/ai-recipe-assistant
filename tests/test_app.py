"""UI smoke tests with Streamlit AppTest: review-before-save flow (services mocked)."""

from pathlib import Path

import pandas as pd

import pytest
from streamlit.testing.v1 import AppTest

from agent import recipe_agent, tools
from models.recipe import Recipe
from services.errors import ServiceError
from tests.conftest import load_expected

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def no_duplicates(monkeypatch):
    """The duplicate check would read Notion; tests that need duplicates override this."""
    checked = []
    monkeypatch.setattr(tools, "find_duplicate_recipes", lambda draft: checked.append(draft) or [])
    return checked


@pytest.fixture
def saved(monkeypatch):
    calls = []
    monkeypatch.setattr(tools, "parse_recipe_draft", lambda text: load_expected("05_lentil_soup"))
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
        return "Draft ready."

    monkeypatch.setattr(recipe_agent, "ask_agent", fake_ask)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("Add this guacamole recipe ...")
    next(b for b in at.button if b.label == "Ask Agent").click()
    at.run()
    assert not at.exception
    assert at.text_input[0].value == "Simple Guacamole"
    assert saved == []



def question_box(at: AppTest):
    return next(t for t in at.text_input if t.label == "Question")


def ask(at: AppTest, text: str) -> AppTest:
    question_box(at).input(text)
    next(b for b in at.button if b.label == "Ask Agent").click()
    return at.run()


def test_follow_up_questions_get_the_conversation(monkeypatch):
    seen = []

    def fake_ask(question, on_draft=None, model=None, history=None):
        seen.append((question, [t["question"] for t in history or []]))
        return f"Answer to {question}"

    monkeypatch.setattr(recipe_agent, "ask_agent", fake_ask)
    at = ask(AppTest.from_file(APP, default_timeout=30).run(), "breakfast ideas?")
    at = ask(at, "yes, show the steps")
    assert not at.exception
    assert seen == [("breakfast ideas?", []), ("yes, show the steps", ["breakfast ideas?"])]
    assert [m.markdown[0].value for m in at.chat_message] == [
        "breakfast ideas?", "Answer to breakfast ideas?", "yes, show the steps", "Answer to yes, show the steps",
    ]
    assert not any("Claude" in c.value for c in at.caption)  # end users are not told which model answered
    next(b for b in at.button if b.label == "Clear conversation").click()
    at.run()
    assert len(at.chat_message) == 0


def login(at: AppTest, password: str) -> AppTest:
    next(t for t in at.text_input if t.label == "Password").input(password)
    next(b for b in at.button if b.label == "Enter").click()
    return at.run()


def test_password_screen_blocks_the_app(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Password"]  # nothing else is rendered
    assert not any(b.label in ("Process Recipe", "Ask Agent") for b in at.button)
    at = login(at, "wrong")
    assert any("Wrong password" in e.value for e in at.error)
    at = login(at, "s3cret")
    assert not at.exception
    assert any(b.label == "Ask Agent" for b in at.button)


def test_no_password_screen_without_app_password():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not any(t.label == "Password" for t in at.text_input)


# --- duplicate detection (ADR-014) ---------------------------------------------------------------

EXISTING = {
    "id": "p0", "name": "Red Lentil Soup", "url": "https://notion.so/p0", "total_time_minutes": None,
    "category": "Soup", "vegetarian": True, "tags": [], "same_name": True, "same_source_url": False,
}


def test_duplicate_draft_shows_a_warning_but_can_still_be_saved(monkeypatch, saved, no_duplicates):
    monkeypatch.setattr(tools, "find_duplicate_recipes", lambda draft: no_duplicates.append(draft) or [EXISTING])
    at = process(AppTest.from_file(APP, default_timeout=30).run())
    assert not at.exception
    warning = next(w.value for w in at.warning if "already be in your cookbook" in w.value)
    assert "[Red Lentil Soup](https://notion.so/p0)" in warning and "same name" in warning
    assert len(no_duplicates) == 1  # checked once per draft, not on every rerun
    next(b for b in at.button if b.label == "Save to Notion").click()
    at.run()
    assert len(saved) == 1  # a warning, not a block
    assert not any("already be in your cookbook" in w.value for w in at.warning)  # cleared with the draft


def test_no_warning_for_a_new_recipe(saved, no_duplicates):
    at = process(AppTest.from_file(APP, default_timeout=30).run())
    assert no_duplicates and no_duplicates[0]["name"] == "Red Lentil Soup"
    assert not any("already be in your cookbook" in w.value for w in at.warning)


def test_failed_duplicate_check_does_not_block_the_review(monkeypatch, saved):
    def broken(draft):
        raise ServiceError("Notion is not reachable right now. Try again later.")

    monkeypatch.setattr(tools, "find_duplicate_recipes", broken)
    at = process(AppTest.from_file(APP, default_timeout=30).run())
    assert not at.exception and not at.error
    assert at.text_input[0].value == "Red Lentil Soup"
    next(b for b in at.button if b.label == "Save to Notion").click()
    at.run()
    assert len(saved) == 1


# --- My recipes (ADR-015) ------------------------------------------------------------------------


def show_recipes(at: AppTest) -> AppTest:
    next(t for t in at.toggle if t.label == "Show saved recipes").set_value(True)
    return at.run()


def test_my_recipes_is_not_loaded_until_opened(monkeypatch):
    calls = []
    monkeypatch.setattr(tools, "list_saved_recipes", lambda refresh=False: calls.append(refresh) or [])
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception and calls == []  # no Notion read on every page load
    at = show_recipes(at)
    assert calls == [False]
    assert any("No recipes saved yet" in i.value for i in at.info)


def test_my_recipes_lists_saved_recipes_without_the_agent(monkeypatch, sample_records):
    from services.recipe_search import summarize

    monkeypatch.setattr(tools, "list_saved_recipes", lambda refresh=False: [summarize(r) for r in sample_records])
    monkeypatch.setattr(recipe_agent, "ask_agent", lambda *a, **k: pytest.fail("the list must not use the agent"))
    at = show_recipes(AppTest.from_file(APP, default_timeout=30).run())
    assert not at.exception
    table = at.dataframe[0].value
    assert len(table) == len(sample_records)
    curry = table[table["Name"] == "Easy Chicken Curry"].iloc[0]
    assert curry["Total time (min)"] == 45 and curry["Vegetarian"] == "No"  # 15 prep + 30 cook
    assert curry["Notion"].startswith("https://notion.so/")
    salad = table[table["Name"] == "Greek Salad"].iloc[0]
    assert pd.isna(salad["Total time (min)"])  # unknown stays empty, never 0


def test_my_recipes_refresh_and_errors(monkeypatch):
    calls = []

    def fake_list(refresh=False):
        calls.append(refresh)
        if len(calls) > 1:
            raise ServiceError("Notion is not reachable right now. Try again later.")
        return []

    monkeypatch.setattr(tools, "list_saved_recipes", fake_list)
    at = show_recipes(AppTest.from_file(APP, default_timeout=30).run())
    next(b for b in at.button if b.label == "Refresh").click()
    at.run()
    assert not at.exception
    assert calls == [False, True]
    assert any("not reachable" in e.value for e in at.error)


def test_add_recipe_offers_a_video_upload():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    # AppTest cannot upload files; the video path itself is covered in test_video.py.
    assert len(at.get("file_uploader")) == 1
