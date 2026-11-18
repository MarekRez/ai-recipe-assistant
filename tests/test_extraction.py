"""Parsing pipeline: input handling, schema validation, URL fetching. Gemini is mocked.

Live extraction quality is measured by `python -m evals.run_extraction_eval`, not here.
"""

import json

import pytest
import requests

from models.recipe import Recipe
from services import recipe_parser, url_fetcher
from services.errors import ServiceError
from tests.conftest import FIXTURES, load_expected, positive_fixture_stems


@pytest.mark.parametrize("stem", positive_fixture_stems())
def test_fixture_expected_outputs_are_schema_valid(stem):
    Recipe.model_validate(load_expected(stem))


def test_every_fixture_has_text_and_expected_json():
    texts = {p.stem for p in FIXTURES.glob("*.txt")}
    expected = {p.stem for p in FIXTURES.glob("*.json")}
    assert texts == expected and len(texts) >= 10


def test_parse_recipe_validates_llm_payload(monkeypatch):
    payload = load_expected("05_lentil_soup")
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", lambda text: dict(payload))
    recipe = recipe_parser.parse_recipe("some text")
    assert recipe.name == "Red Lentil Soup"
    assert recipe.ingredients[1].quantity is None  # "1-2 carrots" stays null
    assert recipe.total_time_minutes is None


def test_parse_recipe_rejects_invalid_payload(monkeypatch):
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", lambda text: {"name": "", "ingredients": "x"})
    with pytest.raises(ServiceError, match="validation"):
        recipe_parser.parse_recipe("some text")


def test_parse_recipe_detects_non_recipe(monkeypatch):
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", lambda text: {"name": "NOT_A_RECIPE"})
    with pytest.raises(ServiceError, match="No recipe"):
        recipe_parser.parse_recipe("meeting notes")


def test_parse_recipe_rejects_empty_input():
    with pytest.raises(ServiceError):
        recipe_parser.parse_recipe("   ")


def test_source_url_is_set_from_input_not_from_llm(monkeypatch):
    monkeypatch.setattr(
        recipe_parser, "extract_recipe_structured", lambda text: {"name": "X", "source_url": "https://invented.example"}
    )
    monkeypatch.setattr(recipe_parser, "fetch_recipe_text", lambda url: "Recipe text")
    recipe = recipe_parser.parse_recipe_input("https://real.example/recipe")
    assert recipe.source_url == "https://real.example/recipe"


def test_text_input_does_not_fetch(monkeypatch):
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", lambda text: {"name": "X"})
    monkeypatch.setattr(recipe_parser, "fetch_recipe_text", lambda url: pytest.fail("must not fetch"))
    assert recipe_parser.parse_recipe_input("Pancakes\n1 egg").name == "X"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/recipe", True),
        ("  http://example.com/a?b=1  ", True),
        ("Pancakes https://example.com", False),
        ("1 egg\n2 cups flour", False),
    ],
)
def test_is_url(value, expected):
    assert url_fetcher.is_url(value) is expected


def test_html_with_json_ld_graph_is_converted():
    recipe_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "name": "Page"},
            {
                "@type": ["Recipe"],
                "name": "Lemon Cake",
                "totalTime": "PT45M",
                "recipeIngredient": ["200 g flour", "1 lemon"],
                "recipeInstructions": [
                    {"@type": "HowToSection", "itemListElement": [{"@type": "HowToStep", "text": "Mix."}]},
                    {"@type": "HowToStep", "text": "Bake."},
                ],
            },
        ],
    }
    html = f'<html><head><script type="application/ld+json">{json.dumps(recipe_ld)}</script></head><body>Ads</body></html>'
    text = url_fetcher.html_to_recipe_text(html)
    assert "Recipe: Lemon Cake" in text
    assert "Total time: PT45M" in text
    assert "- 200 g flour" in text
    assert "1. Mix." in text and "2. Bake." in text
    assert "Ads" not in text


def test_html_without_json_ld_falls_back_to_visible_text():
    html = "<html><body><nav>Menu</nav><script>var x=1</script><h1>Soup</h1><p>1 onion</p></body></html>"
    text = url_fetcher.html_to_recipe_text(html)
    assert "Soup" in text and "1 onion" in text
    assert "Menu" not in text and "var x" not in text


def test_fetch_errors_become_user_friendly(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("blocked")

    monkeypatch.setattr(url_fetcher.requests, "get", boom)
    with pytest.raises(ServiceError, match="Paste the recipe text"):
        url_fetcher.fetch_recipe_text("https://example.com")
