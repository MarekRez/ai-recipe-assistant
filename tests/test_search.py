"""Deterministic search over stored records (docs/AGENT_SPEC.md example intents)."""

from models.recipe import SearchFilters
from services.recipe_search import filter_recipes


def names(results):
    return {r["name"] for r in results}


def test_vegetarian_under_30_minutes(sample_records):
    results = filter_recipes(sample_records, SearchFilters(vegetarian=True, max_time=30))
    # pasta 25 (total), pancakes 25, mug cake 5, guacamole 10; salad/soup have no time -> excluded
    assert names(results) == {"Quick Vegetarian Tomato Pasta", "Fluffy Pancakes", "Chocolate Mug Cake", "Simple Guacamole"}


def test_max_time_uses_prep_plus_cook_when_total_missing(sample_records):
    results = filter_recipes(sample_records, SearchFilters(max_time=22))
    assert "Beef and Broccoli Stir-Fry" in names(results)  # 10 + 12
    assert "Easy Chicken Curry" not in names(results)  # 15 + 30


def test_ingredient_contains_chicken(sample_records):
    assert names(filter_recipes(sample_records, SearchFilters(ingredient="chicken"))) == {"Easy Chicken Curry"}


def test_text_query_pasta(sample_records):
    assert names(filter_recipes(sample_records, SearchFilters(text_query="pasta"))) == {"Quick Vegetarian Tomato Pasta"}


def test_text_query_requires_all_tokens(sample_records):
    assert names(filter_recipes(sample_records, SearchFilters(text_query="salmon lemon"))) == {"Oven-Baked Lemon Salmon"}
    assert filter_recipes(sample_records, SearchFilters(text_query="salmon chocolate")) == []


def test_category_is_case_insensitive(sample_records):
    results = filter_recipes(sample_records, SearchFilters(category="main COURSE"))
    assert len(results) == 5


def test_tags_must_all_match(sample_records):
    assert names(filter_recipes(sample_records, SearchFilters(tags=["Fish", "lemon"]))) == {"Oven-Baked Lemon Salmon"}


def test_unknown_vegetarian_is_excluded_from_both_filters(sample_records):
    record = dict(sample_records[0], name="Mystery", vegetarian=None)
    assert filter_recipes([record], SearchFilters(vegetarian=True)) == []
    assert filter_recipes([record], SearchFilters(vegetarian=False)) == []


def test_no_filters_returns_all_as_summaries(sample_records):
    results = filter_recipes(sample_records, SearchFilters())
    assert len(results) == len(sample_records)
    assert set(results[0]) == {"id", "name", "total_time_minutes", "category", "vegetarian", "tags", "url"}
