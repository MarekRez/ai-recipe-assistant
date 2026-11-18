"""Scoring logic of the live extraction eval."""

from evals.scoring import is_hallucination_free, names_match, norm_unit, score_case
from models.recipe import Recipe
from tests.conftest import load_expected


def test_perfect_extraction_scores_full():
    expected = Recipe.model_validate(load_expected("01_chicken_curry"))
    score = score_case(expected, expected)
    assert score["ingredient_recall"] == score["ingredient_precision"] == 1.0
    assert score["quantity_accuracy"] == score["unit_accuracy"] == 1.0
    assert score["times_ok"] and is_hallucination_free(score)


def test_invented_values_are_flagged():
    expected = Recipe.model_validate(load_expected("05_lentil_soup"))
    actual = expected.model_copy(deep=True)
    actual.total_time_minutes = 30  # source only says "simmer for 25 minutes"
    actual.ingredients[1].quantity = 2  # "1-2 carrots"
    actual.ingredients.append(actual.ingredients[0].model_copy(update={"name": "cream"}))
    score = score_case(expected, actual)
    assert score["invented_times"] == ["total_time_minutes"]
    assert score["invented_quantities"] == 1
    assert score["extra_ingredients"] == ["cream"]
    assert not is_hallucination_free(score)


def test_name_and_unit_normalisation():
    assert names_match("zemiaky", "zemiakov")
    assert names_match("garlic", "garlic cloves")
    assert not names_match("salt", "salmon fillets")
    assert norm_unit("Tablespoons") == "tbsp"
    assert norm_unit("cup") == norm_unit("cups")
    assert norm_unit(None) is None
