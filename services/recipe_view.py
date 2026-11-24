"""Display helpers for one saved recipe (the "View recipe" dialog in My Recipes).

Pure functions over a stored record (`Recipe.model_dump()` + `id`/`url`), so they are unit-testable without
Streamlit. Missing values are shown as NOT_STATED - never guessed.
"""

from __future__ import annotations

NOT_STATED = "not stated"
_VEGETARIAN = {True: "Yes", False: "No", None: "Unknown"}


def format_quantity(quantity: float | None) -> str | None:
    """1.0 -> "1", 0.5 -> "0.5", None -> None."""
    if quantity is None:
        return None
    return str(int(quantity)) if float(quantity).is_integer() else f"{quantity:g}"


def ingredient_line(ingredient: dict) -> str:
    """The original line if we have it, else "quantity unit name" without the missing parts."""
    raw = (ingredient.get("raw") or "").strip()
    if raw:
        return raw
    parts = [format_quantity(ingredient.get("quantity")), ingredient.get("unit"), ingredient.get("name")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def minutes_text(minutes: int | None) -> str:
    return NOT_STATED if minutes is None else f"{minutes} min"


def total_time_text(record: dict) -> str:
    """Stated total; else prep + cook (marked as such) when both are stated; else NOT_STATED."""
    total = record.get("total_time_minutes")
    if total is not None:
        return minutes_text(total)
    prep, cook = record.get("prep_time_minutes"), record.get("cook_time_minutes")
    if prep is not None and cook is not None:
        return f"{prep + cook} min (prep + cook)"
    return NOT_STATED


def recipe_overview(record: dict) -> list[tuple[str, str]]:
    """(label, value) pairs for the summary block of the dialog, in display order."""
    return [
        ("Category", record.get("category") or NOT_STATED),
        ("Prep time", minutes_text(record.get("prep_time_minutes"))),
        ("Cook time", minutes_text(record.get("cook_time_minutes"))),
        ("Total time", total_time_text(record)),
        ("Vegetarian", _VEGETARIAN[record.get("vegetarian")]),
        ("Tags", ", ".join(record.get("tags") or []) or NOT_STATED),
    ]
