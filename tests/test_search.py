"""Deterministic search over stored records (docs/AGENT_SPEC.md example intents)."""

from models.recipe import SearchFilters
from services.recipe_search import filter_recipes, find_duplicates


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


# --- duplicate detection (ADR-014) ---------------------------------------------------------------


def test_duplicate_by_name_ignores_case_spacing_and_punctuation(sample_records):
    found = find_duplicates(sample_records, "  easy chicken-CURRY! ")
    assert [d["name"] for d in found] == ["Easy Chicken Curry"]
    assert found[0]["same_name"] is True and found[0]["same_source_url"] is False
    assert found[0]["url"]  # link to the existing Notion page


def test_similar_but_different_name_is_not_a_duplicate(sample_records):
    assert find_duplicates(sample_records, "Chicken Curry") == []
    assert find_duplicates(sample_records, "") == []


def test_duplicate_by_source_url_ignores_scheme_www_slash_and_tracking(sample_records):
    records = [dict(sample_records[0], source_url="https://www.example.com/recipes/curry/?utm_source=ig&id=7")]
    found = find_duplicates(records, "Another Name", "http://EXAMPLE.com/recipes/curry?id=7&fbclid=x#steps")
    assert len(found) == 1 and found[0]["same_source_url"] is True and found[0]["same_name"] is False


def test_different_recipe_id_in_query_is_not_a_duplicate(sample_records):
    records = [dict(sample_records[0], source_url="https://example.com/recipe.php?id=1")]
    assert find_duplicates(records, "Another Name", "https://example.com/recipe.php?id=2") == []


def test_missing_source_urls_never_match(sample_records):
    records = [dict(r, source_url=None) for r in sample_records]
    assert find_duplicates(records, "Something New", None) == []
