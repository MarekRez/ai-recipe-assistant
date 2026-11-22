"""Pure scoring functions for the extraction eval (unit-tested in tests/test_eval_scoring.py)."""

from __future__ import annotations

from difflib import SequenceMatcher

from models.recipe import Ingredient, Recipe

TIME_FIELDS = ("prep_time_minutes", "cook_time_minutes", "total_time_minutes")
_UNIT_ALIASES = {
    "tablespoon": "tbsp",
    "teaspoon": "tsp",
    "gram": "g",
    "grams": "g",
    "milliliter": "ml",
    "millilitre": "ml",
    "liter": "l",
    "litre": "l",
    "kilogram": "kg",
    "cup": "cups",
    "clove": "cloves",
}


def norm_text(value: str | None) -> str:
    return " ".join((value or "").lower().replace(",", " ").split())


def norm_unit(value: str | None) -> str | None:
    if not value:
        return None
    unit = value.lower().strip().rstrip(".")
    unit = _UNIT_ALIASES.get(unit, _UNIT_ALIASES.get(unit.rstrip("s"), unit))
    return unit


def names_match(a: str, b: str) -> bool:
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.75


def match_ingredients(expected: list[Ingredient], actual: list[Ingredient]) -> list[tuple[Ingredient, Ingredient]]:
    """Greedy one-to-one matching by name."""
    pairs = []
    remaining = list(actual)
    for exp in expected:
        for act in remaining:
            if names_match(exp.name, act.name):
                pairs.append((exp, act))
                remaining.remove(act)
                break
    return pairs


def _same_quantity(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) < 0.01


def score_case(expected: Recipe, actual: Recipe) -> dict:
    pairs = match_ingredients(expected.ingredients, actual.ingredients)
    n_exp, n_act, n_match = len(expected.ingredients), len(actual.ingredients), len(pairs)
    invented_quantities = sum(1 for e, a in pairs if e.quantity is None and a.quantity is not None)
    invented_times = [f for f in TIME_FIELDS if getattr(expected, f) is None and getattr(actual, f) is not None]
    return {
        "name_ok": names_match(expected.name, actual.name),
        "ingredient_recall": n_match / n_exp if n_exp else 1.0,
        "ingredient_precision": n_match / n_act if n_act else 1.0,
        "extra_ingredients": [a.name for a in actual.ingredients if all(a is not p[1] for p in pairs)],
        "quantity_accuracy": sum(_same_quantity(e.quantity, a.quantity) for e, a in pairs) / n_match if n_match else 1.0,
        "unit_accuracy": sum(norm_unit(e.unit) == norm_unit(a.unit) for e, a in pairs) / n_match if n_match else 1.0,
        "times_ok": all(getattr(expected, f) == getattr(actual, f) for f in TIME_FIELDS),
        "invented_times": invented_times,
        "invented_quantities": invented_quantities,
        "step_count_diff": len(actual.instructions) - len(expected.instructions),
        "vegetarian_ok": expected.vegetarian == actual.vegetarian,
        "category_ok": norm_text(expected.category) == norm_text(actual.category),
    }


def is_hallucination_free(score: dict) -> bool:
    return not score["extra_ingredients"] and not score["invented_times"] and score["invented_quantities"] == 0


def is_api_failure(error: str | None) -> bool:
    """True for Gemini outages / rate limits (services.gemini_service messages), not for extraction results."""
    return bool(error) and error.startswith("Gemini ")
