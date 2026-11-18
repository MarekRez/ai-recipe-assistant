# Data Contracts

## Recipe Schema (Canonical, `models/recipe.py`)

```json
{
  "name": "string",
  "ingredients": [
    {
      "name": "string",
      "quantity": "number|null",
      "unit": "string|null",
      "raw": "string|null"
    }
  ],
  "instructions": ["string"],
  "prep_time_minutes": "integer>=0|null",
  "cook_time_minutes": "integer>=0|null",
  "total_time_minutes": "integer>=0|null",
  "category": "string|null",
  "vegetarian": "boolean|null",
  "tags": ["string"],
  "source_url": "string|null"
}
```

## Validation Rules

1. `name` is required and non-blank.
2. `ingredients` and `instructions` must be lists; blank instruction lines and tags are dropped.
3. Numeric time fields are `null` when absent and never negative.
4. Do not infer missing quantities/times. Ranges and vague amounts ("1-2", "to taste", "a pinch") -> `quantity: null`;
   the original wording is kept in `raw` (ADR-007).
5. `vegetarian` is `null` when unknown (stored as `Unknown` in Notion, ADR-006).
6. `total_time_minutes` holds only an explicitly stated total. For filtering, the *effective* total time is
   `total_time_minutes`, else `prep + cook` if both are stated, else unknown (`Recipe.effective_total_time`).
7. `source_url` is set by the app from the input URL, never taken from the LLM.

Category vocabulary used by the extraction prompt and the UI: Breakfast, Main course, Soup, Salad, Side dish,
Dessert, Snack, Drink.

## Stored Record (`RecipeRecord`)

What Notion reads return: all Recipe fields plus `id` (Notion page id), `url` (Notion page URL), `created_at`.

## Search Result (`RecipeSummary`)

```json
{"id": "string", "name": "string", "total_time_minutes": "integer|null (effective)", "category": "string|null",
 "vegetarian": "boolean|null", "tags": ["string"], "url": "string"}
```

## Notion Mapping

Exact property setup: `NOTION_SETUP.md`.

| Recipe field         | Notion property | Type          |
|----------------------|-----------------|---------------|
| `name`               | Name            | Title         |
| `ingredients`        | Ingredients     | Text (JSON, split into 2000-char chunks) |
| `instructions`       | Instructions    | Text (JSON, split into 2000-char chunks) |
| `prep_time_minutes`  | Prep time       | Number        |
| `cook_time_minutes`  | Cook time       | Number        |
| `total_time_minutes` | Total time      | Number        |
| `category`           | Category        | Select        |
| `vegetarian`         | Vegetarian      | Select `Yes`/`No`/`Unknown` |
| `tags`               | Tags            | Multi-select (commas removed) |
| `source_url`         | Source URL      | URL           |
| -                    | Created at      | Created time (set by Notion) |

The page body additionally contains a readable "Ingredients" bullet list and "Instructions" numbered list.
