"""Deterministic recipe filtering (no embeddings, no RAG).

Pure functions over stored recipe records, so they are unit-testable without Notion.
A stored record is `Recipe.model_dump()` plus `id` and `url` (see docs/DATA_CONTRACTS.md).
"""

from __future__ import annotations

from models.recipe import Recipe, SearchFilters


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def effective_time(record: dict) -> int | None:
    return Recipe.model_validate(record).effective_total_time()


def _haystack(record: dict) -> str:
    parts = [record.get("name"), record.get("category"), *record.get("tags", [])]
    for ing in record.get("ingredients", []):
        parts.extend([ing.get("name"), ing.get("raw")])
    return " ".join(_norm(p) for p in parts if p)


def matches(record: dict, filters: SearchFilters) -> bool:
    if filters.vegetarian is not None and record.get("vegetarian") is not filters.vegetarian:
        return False
    if filters.max_time is not None:
        total = effective_time(record)
        if total is None or total > filters.max_time:
            return False
    if filters.category and _norm(record.get("category")) != _norm(filters.category):
        return False
    if filters.tags:
        record_tags = {_norm(t) for t in record.get("tags", [])}
        if not all(_norm(t) in record_tags for t in filters.tags):
            return False
    if filters.ingredient:
        needle = _norm(filters.ingredient)
        if not any(
            needle in _norm(ing.get("name")) or needle in _norm(ing.get("raw"))
            for ing in record.get("ingredients", [])
        ):
            return False
    if filters.text_query:
        haystack = _haystack(record)
        if not all(token in haystack for token in _norm(filters.text_query).split()):
            return False
    return True


def summarize(record: dict) -> dict:
    """Compact shape returned to the agent for search results (RecipeSummary)."""
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "total_time_minutes": effective_time(record),
        "category": record.get("category"),
        "vegetarian": record.get("vegetarian"),
        "tags": record.get("tags", []),
        "url": record.get("url"),
    }


def filter_recipes(records: list[dict], filters: SearchFilters) -> list[dict]:
    return [summarize(r) for r in records if matches(r, filters)]
