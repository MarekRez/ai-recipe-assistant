# Data Contracts

## Recipe Schema (Canonical)

```json
{
  "name": "string",
  "ingredients": [
    {
      "name": "string",
      "quantity": "number|null",
      "unit": "string|null"
    }
  ],
  "instructions": ["string"],
  "prep_time_minutes": "integer|null",
  "cook_time_minutes": "integer|null",
  "total_time_minutes": "integer|null",
  "category": "string|null",
  "vegetarian": "boolean|null",
  "tags": ["string"],
  "source_url": "string|null"
}
```

## Validation Rules

1. `name` is required and non-empty.
2. `ingredients` and `instructions` must be lists.
3. Numeric time fields can be `null` when absent.
4. Do not infer missing quantities/times.
5. Unknown booleans may be `null`.

## Notion Mapping (Suggested)

1. `name` -> Title
2. `ingredients` -> Rich text (JSON string)
3. `instructions` -> Rich text (JSON string)
4. `total_time_minutes` -> Number
5. `category` -> Select
6. `vegetarian` -> Checkbox
7. `tags` -> Multi-select
8. `source_url` -> URL
9. `created_at` -> Date
