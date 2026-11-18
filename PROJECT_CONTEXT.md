# AI Recipe Knowledge Assistant

## Purpose

This file is the source of truth for the semester project.  
The main goal is to build the smallest possible functional AI-agent prototype that demonstrates useful AI orchestration, structured data extraction, external API integration, and personal knowledge management.

The project should stay intentionally small. Avoid unnecessary architecture, frameworks, databases, or features unless they are required for the MVP.

---

## Project Goal

Build an AI Recipe Knowledge Assistant that allows a user to:

1. Add a recipe from text or a recipe URL.
2. Automatically extract the recipe into a normalized structured format using an LLM.
3. Review the extracted data.
4. Save the recipe into a personal Notion recipe database.
5. Ask natural-language questions about saved recipes.
6. Let an AI agent decide which backend tool to use to fulfill the user's request.

Example user queries:

- "Find me something with chicken."
- "Show me vegetarian meals under 30 minutes."
- "I want pasta tonight."
- "Save this recipe to my cookbook."

The important part is not building a large cooking platform.  
The important part is demonstrating a simple end-to-end AI agent workflow.

---

## MVP Scope

### Required functionality

### 1. Recipe input

The user can provide:

- plain recipe text
- recipe URL

Optional bonus:

- uploaded MP4 / downloaded Reel video

Instagram scraping or automatic downloading from Instagram is NOT part of the MVP.

---

### 2. AI recipe extraction

The LLM converts recipe content into a structured format.

Suggested schema:

```json
{
  "name": "Chicken Tikka Masala",
  "ingredients": [
    {
      "name": "chicken breast",
      "quantity": 500,
      "unit": "g"
    }
  ],
  "instructions": [
    "Cut the chicken.",
    "Prepare the sauce.",
    "Cook everything together."
  ],
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "total_time_minutes": 45,
  "category": "Main course",
  "vegetarian": false,
  "tags": ["chicken", "indian", "dinner"],
  "source_url": null
}
```

Use Pydantic or another schema validation mechanism.

Important rule:

The model must NOT invent missing quantities, times, or ingredients.

If information is missing, use `null` or an equivalent representation.

---

### 3. Human review

Before saving an AI-extracted recipe:

- show the extracted structure to the user
- allow the user to verify or edit it
- save only after confirmation

This reduces hallucination risk and demonstrates a simple human-in-the-loop process.

---

### 4. Notion storage

Use the Notion API as the central structured recipe knowledge store.

Notion should NOT be described as a relational database.

Suggested Notion recipe properties:

- Name
- Ingredients
- Instructions
- Total time
- Category
- Vegetarian
- Tags
- Source URL
- Created at

For the semester project it is acceptable to store ingredients and instructions as JSON or formatted text instead of creating a complex relational schema.

---

### 5. AI agent

Use `smolagents` as the lightweight agent framework.

The agent should have access to custom Python tools such as:

```python
parse_recipe(...)
save_recipe(...)
search_recipes(...)
get_recipe(...)
```

The custom tools are implemented by us.

> Decision update (2026-11-18, ADR-005 in `docs/DECISIONS.md`): `save_recipe` is called by the UI after the user
> confirms the reviewed draft; it is not exposed to the agent, because an agent run cannot pause for confirmation.
> The agent's `parse_recipe` only stages a draft for review.

The agent framework handles the orchestration loop:

1. User sends a request.
2. LLM interprets the request.
3. Agent decides which tool to use.
4. Tool is executed.
5. Result is returned to the LLM.
6. Agent either calls another tool or produces the final answer.

This is the main reason the solution can legitimately be described as an AI agent rather than only a chatbot.

---

## Search Strategy

Do NOT implement a vector database or full RAG architecture for the MVP.

Most recipe queries can be solved using structured filtering.

Example:

User:

> Find vegetarian meals under 30 minutes.

Agent interprets this approximately as:

```python
search_recipes(
    vegetarian=True,
    max_time=30
)
```

Use normal filtering over Notion data where possible.

Semantic search / embeddings / RAG may be mentioned as future work for vague requests such as:

> I want something light, summery and slightly spicy.

---

## Technology Stack

Keep the stack minimal.

### Language

- Python

### UI

- Streamlit

### Agent framework

- smolagents

### LLM

- Gemini API
- Prefer a Gemini Flash model available through the free API tier

### Data storage

- Notion API

### Validation

- Pydantic

### Source control

- GitHub

### Deployment

- Streamlit Community Cloud

Expected project cost:

- potentially 0 EUR using available free tiers

---

## High-Level Architecture

```text
User
  |
  v
Streamlit UI
  |
  v
smolagents Agent
  |
  +---------------------+
  |                     |
  v                     v
Gemini API         Custom Python Tools
                        |
                +-------+-------+
                |               |
                v               v
          save_recipe()   search_recipes()
                |               |
                +-------+-------+
                        |
                        v
                    Notion API
                        |
                        v
                Recipe Knowledge Base
```

Everything can live in one Python project.

A separate Angular frontend, FastAPI backend, microservices, Docker orchestration, or separate frontend/backend deployment are NOT required for the MVP.

---

## Suggested Project Structure

```text
ai-recipe-assistant/
|
|-- app.py
|
|-- agent/
|   |-- recipe_agent.py
|   `-- tools.py
|
|-- services/
|   |-- gemini_service.py
|   |-- notion_service.py
|   `-- recipe_parser.py
|
|-- models/
|   `-- recipe.py
|
|-- tests/
|   |-- test_extraction.py
|   |-- test_notion.py
|   `-- test_agent.py
|
|-- requirements.txt
|-- .env.example
|-- README.md
`-- PROJECT_CONTEXT.md
```

This structure is only a suggestion. Prefer simplicity over unnecessary layering.

---

## Suggested Agent Tools

### `parse_recipe`

Input:

- raw recipe text
- optionally extracted website text

Output:

- validated Recipe object

Responsibility:

- use Gemini to extract structured recipe data

---

### `save_recipe`

Input:

- validated Recipe object

Output:

- saved Notion record ID / confirmation

Responsibility:

- write recipe into the Notion database

---

### `search_recipes`

Possible inputs:

- text query
- vegetarian
- max_time
- category
- tags
- ingredient

Output:

- matching recipes

Responsibility:

- query/filter the Notion database

---

### `get_recipe`

Input:

- recipe name or recipe ID

Output:

- complete recipe

Responsibility:

- retrieve a single saved recipe

---

## UI Concept

The Streamlit UI can stay very simple.

Possible layout:

```text
AI Recipe Assistant

[ Add Recipe ]

Paste recipe text or URL:

[_____________________________________]

[ Process Recipe ]

---------------------------------------

Extracted recipe:
Name:
Ingredients:
Instructions:
Time:
Tags:

[ Save to Notion ]

---------------------------------------

[ Ask My Cookbook ]

Question:

[_____________________________________]

Agent:
I found these recipes...
```

A polished frontend is not the goal of the project.

---

## Testing

Keep testing measurable but small.

Use approximately 10-15 sample recipes.

### 1. Extraction accuracy

Create manually verified expected results for sample recipes.

Check:

- recipe name
- ingredient names
- quantities
- units
- instructions
- cooking/preparation time

---

### 2. Schema validity

Measure whether the LLM output passes the Pydantic schema.

Example metric:

```text
valid outputs / total outputs
```

---

### 3. Hallucination check

Verify that the model did not invent:

- ingredients
- quantities
- times
- preparation steps

---

### 4. Notion integration

Verify that extracted recipes are successfully written to Notion.

---

### 5. Agent search

Prepare example requests such as:

- vegetarian under 30 minutes
- contains chicken
- pasta
- dinner meal

Check whether the returned recipes satisfy the requested constraints.

---

## MIS / Information Systems Context

The project can be described using the following concepts:

- Knowledge Management System
- Personal Information Management
- Decision Support
- Data integration
- Information extraction
- Workflow automation
- API integration
- Human-in-the-loop validation

Avoid forcing Supply Chain Management terminology into the project unless pantry management or grocery planning is later implemented.

---

## Explicit Non-Goals

Do NOT implement these as part of the MVP:

- weekly meal planning
- grocery shopping lists
- pantry inventory
- expiration tracking
- food cost optimization
- nutrition tracking
- calorie counting
- automatic Instagram scraping
- automatic Instagram Reel downloading
- vector database
- complex RAG architecture
- recommendation engine
- multi-user authentication
- payments
- mobile app
- Angular frontend
- separate FastAPI backend unless technically necessary
- microservices
- production-grade infrastructure

If time remains, these may be discussed or implemented only as optional extensions.

---

## Optional Bonus Features

Only implement these after the full MVP works end-to-end.

Priority order:

1. MP4 / Reel video upload and multimodal recipe extraction
2. Better semantic search
3. Duplicate recipe detection
4. Meal planning
5. Grocery list generation
6. Pantry-aware recommendations

None of these are required for successful completion of the semester project.

---

## Development Principle

Always prefer the smallest implementation that proves the concept.

Before adding any dependency or feature, ask:

> Is this required to demonstrate the core AI-agent workflow?

If not, leave it out.

The target end-to-end demo is:

```text
Paste recipe
   ->
AI extracts structured recipe
   ->
User reviews it
   ->
Recipe is saved to Notion
   ->
User asks for a type of meal
   ->
Agent chooses the correct tool
   ->
Agent searches Notion
   ->
Agent returns relevant saved recipes
```

If this flow works reliably, the MVP is complete.
