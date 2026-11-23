"""Notion mapping and operations with a fake client (no network)."""

import json

import httpx
import pytest
from notion_client import APIErrorCode, APIResponseError

from models.recipe import Recipe
from services import notion_service as ns
from services.errors import ServiceError
from tests.conftest import load_expected


def make_api_error(code: APIErrorCode, status: int = 400) -> APIResponseError:
    return APIResponseError(code, status, "boom", httpx.Headers(), "{}")


def as_page(properties: dict, page_id: str = "abc", url: str = "https://notion.so/abc") -> dict:
    """Turn create-payload properties into the shape Notion returns (adds plain_text)."""
    returned = {}
    for name, prop in properties.items():
        prop = json.loads(json.dumps(prop))
        for key in ("title", "rich_text"):
            for item in prop.get(key, []):
                item["plain_text"] = item["text"]["content"]
        returned[name] = prop
    returned["Created at"] = {"created_time": "2026-11-18T10:00:00.000Z"}
    return {"object": "page", "id": page_id, "url": url, "properties": returned}


class FakePages:
    def __init__(self, store):
        self.store = store
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        page = as_page(kwargs["properties"], page_id=f"id-{len(self.created)}")
        self.store.append(page)
        return page

    def retrieve(self, page_id):
        for page in self.store:
            if page["id"].replace("-", "") == page_id:
                return page
        raise make_api_error(APIErrorCode.ObjectNotFound, 404)


class FakeDataSources:
    def __init__(self, store, schema=None):
        self.store = store
        self.schema = schema or {name: {"type": t} for name, t in ns.PROPERTY_SCHEMA.items()}
        self.query_kwargs = []

    def query(self, data_source_id, **kwargs):
        self.query_kwargs.append((data_source_id, kwargs))
        return {"results": list(self.store), "has_more": False, "next_cursor": None}

    def retrieve(self, data_source_id):
        return {"properties": self.schema}


class FakeClient:
    def __init__(self, schema=None):
        self.store: list[dict] = []
        self.pages = FakePages(self.store)
        self.data_sources = FakeDataSources(self.store, schema)


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ns, "_client", lambda: client)
    return client


def curry() -> Recipe:
    return Recipe.model_validate(load_expected("01_chicken_curry"))


# --- mapping ---------------------------------------------------------------


def test_properties_mapping():
    props = ns.recipe_to_properties(curry())
    assert set(props) == set(ns.PROPERTY_SCHEMA) - {"Created at"}
    assert props["Name"]["title"][0]["text"]["content"] == "Easy Chicken Curry"
    assert props["Total time"] == {"number": None}
    assert props["Prep time"] == {"number": 15}
    assert props["Vegetarian"] == {"select": {"name": "No"}}
    assert props["Category"] == {"select": {"name": "Main course"}}
    assert [t["name"] for t in props["Tags"]["multi_select"]] == ["chicken", "curry", "indian"]


@pytest.mark.parametrize(("value", "label"), [(True, "Yes"), (False, "No"), (None, "Unknown")])
def test_vegetarian_unknown_is_preserved(value, label):
    recipe = Recipe(name="X", vegetarian=value)
    assert ns.recipe_to_properties(recipe)["Vegetarian"]["select"]["name"] == label
    assert ns.page_to_record(as_page(ns.recipe_to_properties(recipe)))["vegetarian"] is value


def test_long_text_is_chunked_under_notion_limit():
    recipe = Recipe(name="Long", instructions=[f"Step {i} " + "x" * 300 for i in range(30)])
    chunks = ns.recipe_to_properties(recipe)["Instructions"]["rich_text"]
    assert len(chunks) > 1
    assert all(len(c["text"]["content"]) <= ns.TEXT_CHUNK for c in chunks)
    assert ns.page_to_record(as_page(ns.recipe_to_properties(recipe)))["instructions"] == recipe.instructions


def test_select_names_drop_commas_and_empty_category():
    props = ns.recipe_to_properties(Recipe(name="X", tags=["a,b", "a b", ""], category=None))
    assert [t["name"] for t in props["Tags"]["multi_select"]] == ["a b"]
    assert props["Category"] == {"select": None}


def test_round_trip_preserves_recipe():
    recipe = curry()
    record = ns.page_to_record(as_page(ns.recipe_to_properties(recipe)))
    assert Recipe.model_validate(record) == recipe
    assert record["id"] == "abc" and record["url"] and record["created_at"]


def test_page_with_broken_data_is_skipped():
    page = as_page(ns.recipe_to_properties(Recipe(name="X")))
    page["properties"]["Name"]["title"] = []
    assert ns.page_to_record(page) is None


def test_page_body_blocks_are_readable():
    blocks = ns.recipe_to_blocks(curry())
    assert blocks[0]["type"] == "heading_2"
    assert sum(b["type"] == "numbered_list_item" for b in blocks) == 5
    assert len(blocks) <= ns.MAX_CHILD_BLOCKS


# --- operations --------------------------------------------------------------


def test_save_uses_data_source_parent(fake_client):
    result = ns.save_recipe_to_notion(curry())
    sent = fake_client.pages.created[0]
    assert sent["parent"] == {"type": "data_source_id", "data_source_id": "test-notion_data_source_id"}
    assert result == {"id": "id-1", "url": "https://notion.so/abc"}


def test_search_loads_all_and_filters(fake_client):
    ns.save_recipe_to_notion(curry())
    ns.save_recipe_to_notion(Recipe(name="Salad", vegetarian=True))
    from models.recipe import SearchFilters

    results = ns.search_recipes_in_notion(SearchFilters(vegetarian=True))
    assert [r["name"] for r in results] == ["Salad"]
    assert fake_client.data_sources.query_kwargs[0][0] == "test-notion_data_source_id"


def test_get_recipe_by_name_exact_then_partial(fake_client):
    ns.save_recipe_to_notion(curry())
    assert ns.get_recipe_from_notion("easy chicken curry")["name"] == "Easy Chicken Curry"
    assert ns.get_recipe_from_notion("curry")["name"] == "Easy Chicken Curry"
    assert ns.get_recipe_from_notion("pizza") is None


def test_find_duplicates_reads_the_saved_recipes(fake_client):
    ns.save_recipe_to_notion(curry())
    found = ns.find_duplicate_recipes_in_notion("EASY chicken curry", None)
    assert [d["name"] for d in found] == ["Easy Chicken Curry"] and found[0]["same_name"] is True
    assert ns.find_duplicate_recipes_in_notion("Pizza", None) == []


def test_get_recipe_by_id(fake_client):
    fake_client.store.append(as_page(ns.recipe_to_properties(curry()), page_id="0123456789abcdef0123456789abcdef"))
    assert ns.get_recipe_from_notion("01234567-89ab-cdef-0123-456789abcdef")["name"] == "Easy Chicken Curry"
    assert ns.get_recipe_from_notion("ffffffffffffffffffffffffffffffff") is None


@pytest.mark.parametrize(
    ("code", "fragment"),
    [
        (APIErrorCode.Unauthorized, "NOTION_API_KEY"),
        (APIErrorCode.ObjectNotFound, "NOTION_DATA_SOURCE_ID"),
        (APIErrorCode.ValidationError, "NOTION_SETUP"),
        (APIErrorCode.RateLimited, "rate limit"),
    ],
)
def test_api_errors_become_user_messages(fake_client, monkeypatch, code, fragment):
    def fail(**kwargs):
        raise make_api_error(code)

    monkeypatch.setattr(fake_client.pages, "create", fail)
    with pytest.raises(ServiceError) as info:
        ns.save_recipe_to_notion(curry())
    assert fragment in info.value.user_message


def test_network_error_becomes_user_message(fake_client, monkeypatch):
    def fail(data_source_id, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(fake_client.data_sources, "query", fail)
    with pytest.raises(ServiceError, match="not reachable"):
        ns.list_all_recipes()


def test_check_setup_ok(fake_client):
    assert ns.check_notion_setup() == []


def test_check_setup_reports_problems(monkeypatch):
    schema = {name: {"type": t} for name, t in ns.PROPERTY_SCHEMA.items()}
    del schema["Tags"]
    schema["Vegetarian"] = {"type": "checkbox"}
    client = FakeClient(schema=schema)
    monkeypatch.setattr(ns, "_client", lambda: client)
    problems = ns.check_notion_setup()
    assert any("Tags" in p for p in problems)
    assert any("Vegetarian" in p and "checkbox" in p for p in problems)


def test_missing_config_is_reported(monkeypatch):
    monkeypatch.delenv("NOTION_DATA_SOURCE_ID")
    with pytest.raises(ServiceError, match="NOTION_DATA_SOURCE_ID"):
        ns._data_source_id()
