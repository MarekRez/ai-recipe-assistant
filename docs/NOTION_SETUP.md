# Notion Setup

The app writes to and reads from one Notion database. Property names and types must match exactly
(`services/notion_service.py::PROPERTY_SCHEMA`). The sidebar button **Check Notion database** verifies this.

## 1. Create the integration

1. Open https://www.notion.so/profile/integrations and create an **internal** integration.
2. Capabilities: Read content, Update content, Insert content.
3. Copy the secret into `NOTION_API_KEY`.

## 2. Create the database

Create a full-page database (e.g. "Recipes") with these properties:

| Property      | Type          | Notes                                                    |
|---------------|---------------|----------------------------------------------------------|
| `Name`        | Title         | default title property, rename to `Name` if needed       |
| `Ingredients` | Text          | JSON list of `{name, quantity, unit, raw}` (app-managed) |
| `Instructions`| Text          | JSON list of steps (app-managed)                         |
| `Prep time`   | Number        | minutes, empty = unknown                                 |
| `Cook time`   | Number        | minutes, empty = unknown                                 |
| `Total time`  | Number        | minutes as stated in the source, empty = unknown         |
| `Category`    | Select        | options are created automatically                        |
| `Vegetarian`  | Select        | options `Yes`, `No`, `Unknown`                           |
| `Tags`        | Multi-select  | options are created automatically                        |
| `Source URL`  | URL           |                                                          |
| `Created at`  | Created time  | filled by Notion                                         |

Do not edit `Ingredients` / `Instructions` by hand - they hold JSON the app parses. The page body
contains a human-readable copy (headings + lists) for browsing in Notion.

## 3. Share the database with the integration

Database page -> `...` menu -> **Connections** -> add your integration.
Without this every call fails with "object not found".

## 4. Get the data source id

Notion API 2025-09-03 (used by notion-client 3.x) addresses databases through *data sources*.
The id in the database URL is the **database id**, not the data source id.

Option A (UI): database -> `...` -> **Manage data sources** -> `...` next to the source -> **Copy data source ID**.

Option B (script):

```bash
.venv/Scripts/python -c "import os; from dotenv import load_dotenv; from notion_client import Client; load_dotenv(); print(Client(auth=os.environ['NOTION_API_KEY']).databases.retrieve(database_id='<DATABASE_ID_FROM_URL>')['data_sources'])"
```

Put the id into `NOTION_DATA_SOURCE_ID`.

## 5. Verify

Run the app and click **Check Notion database** in the sidebar. It should report that the schema matches.
