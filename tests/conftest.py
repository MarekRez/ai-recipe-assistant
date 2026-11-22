"""Shared test fixtures. Tests never call live Gemini or Notion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from models.recipe import Recipe

FIXTURES = Path(__file__).parent / "fixtures" / "recipes"


def load_expected(stem: str) -> dict:
    return json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))


def positive_fixture_stems() -> list[str]:
    return [p.stem for p in sorted(FIXTURES.glob("*.json")) if not load_expected(p.stem).get("expect_error")]


@pytest.fixture(autouse=True)
def _fake_env(monkeypatch):
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL", "NOTION_API_KEY", "NOTION_DATA_SOURCE_ID"):
        monkeypatch.setenv(name, f"test-{name.lower()}")
    # Claude fallback off by default. Set to "" (not deleted) so app.py's load_dotenv() cannot pull a real key
    # from .env into the test process. Tests that need the fallback enable it explicitly.
    for name in ("ANTHROPIC_API_KEY", "CLAUDE_MODEL", "APP_PASSWORD"):
        monkeypatch.setenv(name, "")


@pytest.fixture
def sample_records() -> list[dict]:
    """Stored records (Recipe + id/url) built from the fixture recipes."""
    records = []
    for i, stem in enumerate(positive_fixture_stems()):
        record = Recipe.model_validate(load_expected(stem)).model_dump()
        record.update(id=f"page-{i}", url=f"https://notion.so/page-{i}")
        records.append(record)
    return records
