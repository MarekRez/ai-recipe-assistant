"""View recipe dialog: get_saved_recipe (fake Notion client) and the pure display helpers."""

import pytest

from agent import tools
from services import notion_service as ns
from services.errors import ServiceError
from services.recipe_view import (
    NOT_STATED,
    format_quantity,
    ingredient_line,
    minutes_text,
    recipe_overview,
    total_time_text,
)
from tests.test_notion import as_page, curry, fake_client  # noqa: F401 - fake_client is a fixture

PAGE_ID = "2b6f0c1e-8d4a-4f5b-9c3d-1e2f3a4b5c6d"


@pytest.fixture
def saved_curry(fake_client):  # noqa: F811
    fake_client.store.append(as_page(ns.recipe_to_properties(curry()), page_id=PAGE_ID, url="https://notion.so/curry"))
    return fake_client


# --- get_saved_recipe --------------------------------------------------------


@pytest.mark.parametrize("key", [PAGE_ID, PAGE_ID.replace("-", ""), PAGE_ID.upper()])
def test_get_saved_recipe_matches_id_with_or_without_dashes(saved_curry, key):
    record = tools.get_saved_recipe(key)
    assert record["id"] == PAGE_ID
    assert record["url"] == "https://notion.so/curry"


def test_get_saved_recipe_returns_the_complete_recipe(saved_curry):
    record = tools.get_saved_recipe(PAGE_ID)
    expected = curry()
    assert record["name"] == expected.name
    assert record["instructions"] == expected.instructions
    assert record["ingredients"] == [i.model_dump() for i in expected.ingredients]


@pytest.mark.parametrize("key", ["00000000-0000-0000-0000-000000000000", "", "   ", None])
def test_get_saved_recipe_unknown_id_is_none(saved_curry, key):
    assert tools.get_saved_recipe(key) is None


def test_get_saved_recipe_uses_the_cached_list(saved_curry):
    tools.list_saved_recipes()
    tools.get_saved_recipe(PAGE_ID)
    assert len(saved_curry.data_sources.query_kwargs) == 1  # no extra Notion request for the dialog


def test_get_saved_recipe_raises_service_errors(monkeypatch):
    def fail():
        raise ServiceError("Notion is not reachable right now.")

    monkeypatch.setattr(tools, "list_all_recipes", fail)
    with pytest.raises(ServiceError):
        tools.get_saved_recipe(PAGE_ID)


# --- display helpers -----------------------------------------------------------


def test_raw_line_wins():
    assert ingredient_line({"name": "garlic", "quantity": 1, "unit": "clove", "raw": "1-2 cloves garlic"}) == "1-2 cloves garlic"


def test_line_built_from_parts():
    assert ingredient_line({"name": "flour", "quantity": 200.0, "unit": "g", "raw": None}) == "200 g flour"


def test_line_without_quantity_or_unit():
    assert ingredient_line({"name": "salt", "quantity": None, "unit": None, "raw": "  "}) == "salt"
    assert ingredient_line({"name": "onion", "quantity": 1.0, "unit": None}) == "1 onion"


@pytest.mark.parametrize(("value", "text"), [(1.0, "1"), (0.5, "0.5"), (1.25, "1.25"), (None, None)])
def test_format_quantity(value, text):
    assert format_quantity(value) == text


def test_missing_times_are_not_stated():
    assert minutes_text(None) == NOT_STATED
    assert minutes_text(0) == "0 min"
    assert total_time_text({"prep_time_minutes": 10, "cook_time_minutes": None}) == NOT_STATED


def test_total_time_stated_or_prep_plus_cook():
    assert total_time_text({"total_time_minutes": 40, "prep_time_minutes": 10, "cook_time_minutes": 20}) == "40 min"
    assert total_time_text({"prep_time_minutes": 15, "cook_time_minutes": 30}) == "45 min (prep + cook)"


def test_overview_never_guesses():
    overview = dict(recipe_overview({"name": "Mystery"}))
    assert overview == {
        "Category": NOT_STATED,
        "Prep time": NOT_STATED,
        "Cook time": NOT_STATED,
        "Total time": NOT_STATED,
        "Vegetarian": "Unknown",
        "Tags": NOT_STATED,
    }


def test_overview_of_a_full_recipe():
    overview = dict(recipe_overview(curry().model_dump()))
    assert overview["Total time"] == "45 min (prep + cook)"
    assert overview["Vegetarian"] == "No"
