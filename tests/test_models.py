"""Schema rules from docs/DATA_CONTRACTS.md."""

import pytest
from pydantic import ValidationError

from models.recipe import Recipe


def test_missing_values_default_to_none_or_empty():
    recipe = Recipe.model_validate({"name": "Toast"})
    assert recipe.ingredients == [] and recipe.instructions == [] and recipe.tags == []
    assert recipe.prep_time_minutes is None and recipe.vegetarian is None and recipe.category is None


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_is_rejected(name):
    with pytest.raises(ValidationError):
        Recipe.model_validate({"name": name})


def test_negative_time_is_rejected():
    with pytest.raises(ValidationError):
        Recipe.model_validate({"name": "X", "cook_time_minutes": -5})


def test_ingredient_requires_name_and_keeps_raw_line():
    recipe = Recipe.model_validate(
        {"name": "Soup", "ingredients": [{"name": "carrots", "quantity": None, "raw": "1-2 carrots"}]}
    )
    assert recipe.ingredients[0].raw == "1-2 carrots"
    with pytest.raises(ValidationError):
        Recipe.model_validate({"name": "Soup", "ingredients": [{"name": ""}]})


def test_blank_instruction_lines_are_dropped():
    recipe = Recipe.model_validate({"name": "X", "instructions": ["Mix.", "  ", ""]})
    assert recipe.instructions == ["Mix."]


@pytest.mark.parametrize(
    ("times", "expected"),
    [
        ({"total_time_minutes": 40, "prep_time_minutes": 10, "cook_time_minutes": 10}, 40),
        ({"prep_time_minutes": 10, "cook_time_minutes": 20}, 30),
        ({"prep_time_minutes": 10}, None),
        ({}, None),
    ],
)
def test_effective_total_time(times, expected):
    assert Recipe.model_validate({"name": "X", **times}).effective_total_time() == expected
