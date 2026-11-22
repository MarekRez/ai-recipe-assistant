"""Live extraction eval against tests/fixtures/recipes (calls Gemini - costs free-tier quota).

Usage:
    .venv/Scripts/python -m evals.run_extraction_eval [--delay 6] [--only 01,05] [--out evals/results/run.json]

Metrics (docs/TEST_PLAN.md): schema-valid rate, name/ingredient/quantity/unit/time accuracy,
hallucination-free rate (no extra ingredients, no invented quantities or times).
Note: `extra_ingredients` are *candidates* - review them manually (e.g. "salt and pepper" split differently).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from evals.scoring import is_api_failure, is_hallucination_free, score_case
from models.recipe import Recipe
from services.errors import ServiceError
from services.recipe_parser import NOT_A_RECIPE_MESSAGE, parse_recipe

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "recipes"


def _fmt(value: float) -> str:
    return f"{value * 100:5.1f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=6.0, help="seconds between Gemini calls (rate limit)")
    parser.add_argument("--only", default="", help="comma-separated fixture prefixes, e.g. 01,05")
    parser.add_argument("--out", default="", help="optional path for JSON results")
    args = parser.parse_args()
    load_dotenv()

    prefixes = [p.strip() for p in args.only.split(",") if p.strip()]
    cases = sorted(FIXTURES.glob("*.txt"))
    if prefixes:
        cases = [c for c in cases if any(c.name.startswith(p) for p in prefixes)]

    rows = []
    for i, txt in enumerate(cases):
        if i:
            time.sleep(args.delay)
        expected_raw = json.loads(txt.with_suffix(".json").read_text(encoding="utf-8"))
        row: dict = {"case": txt.stem}
        try:
            actual = parse_recipe(txt.read_text(encoding="utf-8"))
            row["schema_valid"] = True
        except ServiceError as exc:
            actual = None
            row["schema_valid"] = False
            row["error"] = exc.user_message
        if is_api_failure(row.get("error")):
            # Rate limit / outage says nothing about extraction quality - leave the case out of every metric.
            row["skipped"] = True
        elif expected_raw.get("expect_error"):
            row["negative_case_ok"] = row.get("error") == NOT_A_RECIPE_MESSAGE
        elif actual is not None:
            score = score_case(Recipe.model_validate(expected_raw), actual)
            row.update(score, hallucination_free=is_hallucination_free(score), actual=actual.model_dump())
        rows.append(row)
        status = "SKIP" if row.get("skipped") else "OK " if row.get("schema_valid") or row.get("negative_case_ok") else "ERR"
        print(f"[{status}] {txt.stem}", row.get("error", ""), flush=True)

    scored = [r for r in rows if "ingredient_recall" in r]
    positives = [r for r in rows if "negative_case_ok" not in r and not r.get("skipped")]
    negatives = [r for r in rows if "negative_case_ok" in r]

    def avg(key: str) -> float:
        return sum(float(r[key]) for r in scored) / len(scored) if scored else 0.0

    summary = {
        "cases": len(rows),
        "skipped_api_errors": sum(bool(r.get("skipped")) for r in rows),
        "schema_valid_rate": sum(r["schema_valid"] for r in positives) / len(positives) if positives else 0.0,
        "name_accuracy": avg("name_ok"),
        "ingredient_recall": avg("ingredient_recall"),
        "ingredient_precision": avg("ingredient_precision"),
        "quantity_accuracy": avg("quantity_accuracy"),
        "unit_accuracy": avg("unit_accuracy"),
        "times_accuracy": avg("times_ok"),
        "vegetarian_accuracy": avg("vegetarian_ok"),
        "hallucination_free_rate": avg("hallucination_free"),
        "negative_cases_ok": f"{sum(r['negative_case_ok'] for r in negatives)}/{len(negatives)}",
    }

    print("\nSummary")
    for key, value in summary.items():
        print(f"  {key:26} {_fmt(value) if isinstance(value, float) else value}")
    for r in scored:
        if not r["hallucination_free"]:
            print(f"  review {r['case']}: extra={r['extra_ingredients']} invented_times={r['invented_times']} "
                  f"invented_quantities={r['invented_quantities']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
