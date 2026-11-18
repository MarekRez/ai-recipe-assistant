# Technical Design

## Architecture Overview

```text
User -> Streamlit UI -> smolagents Agent -> Custom Tools -> Notion API
                              |
                              +-> Gemini API (recipe extraction)
```

## Components

1. `app.py`

- Streamlit UI.
- Handles recipe input, review UI, save confirmation, and query chat.

2. `agent/recipe_agent.py`

- Initializes smolagents agent.
- Registers custom tools.
- Defines base system instructions.

3. `agent/tools.py`

- Tool wrappers for parse/save/search/get operations.
- Keeps tool input/output deterministic and typed.

4. `services/recipe_parser.py`

- Runs extraction with Gemini.
- Validates structured output against `Recipe` schema.

5. `services/notion_service.py`

- Encapsulates Notion CRUD operations.
- Maps Recipe fields to Notion properties.

6. `services/gemini_service.py`

- Handles Gemini client initialization and prompt execution.

7. `models/recipe.py`

- Pydantic schema definitions.

## Data Flow

1. User submits text/URL.
2. `parse_recipe` extracts and validates recipe.
3. UI shows result for review/edit.
4. On confirm, `save_recipe` persists to Notion.
5. Query flow routes through agent, which calls `search_recipes` or `get_recipe`.

## Error Handling Strategy

1. API failures return user-safe message and debug detail for logs.
2. Validation failures block save and highlight offending fields.
3. Tool-level exceptions are normalized to consistent error payloads.
