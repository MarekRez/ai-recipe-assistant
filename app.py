"""Streamlit entrypoint for AI Recipe Knowledge Assistant MVP.

Flow: paste text/URL -> extract draft -> user reviews/edits -> user confirms save -> ask the cookbook agent.
"""

from __future__ import annotations

import hmac
import logging

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from agent.recipe_agent import ask_agent
from agent.tools import parse_recipe_draft, save_recipe
from services.config import app_password, missing_settings
from services.errors import ServiceError
from services.notion_service import check_notion_setup

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

CATEGORIES = ["", "Breakfast", "Main course", "Soup", "Salad", "Side dish", "Dessert", "Snack", "Drink"]
VEGETARIAN_OPTIONS = {"Unknown": None, "Yes": True, "No": False}
INGREDIENT_COLUMNS = ["name", "quantity", "unit", "raw"]

st.set_page_config(page_title="AI Recipe Assistant", page_icon="🍲", layout="wide")
state = st.session_state

# --- Password screen (ADR-013): only when APP_PASSWORD is set, e.g. on Streamlit Community Cloud ---------
password = app_password()
if password and not state.get("authenticated"):
    st.title("🍲 AI Recipe Assistant")
    with st.form("login", border=False):
        entered = st.text_input("Password", type="password")
        if st.form_submit_button("Enter", type="primary"):
            if hmac.compare_digest(entered.encode(), password.encode()):
                state.authenticated = True
                st.rerun()
            st.error("Wrong password.")
    st.stop()
state.setdefault("draft", None)
state.setdefault("draft_version", 0)
state.setdefault("history", [])  # [{"question", "answer"}] - short agent memory, this session only
state.setdefault("flash", None)


def set_draft(draft: dict | None) -> None:
    state.draft = draft
    state.draft_version += 1  # forces fresh form widgets for a new draft


def _none_if_blank(value):
    if value is None or pd.isna(value):  # NaN / pd.NA from the data editor
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def ingredients_from_editor(df: pd.DataFrame) -> list[dict]:
    rows = []
    for row in df.to_dict("records"):
        cleaned = {col: _none_if_blank(row.get(col)) for col in INGREDIENT_COLUMNS}
        if cleaned["name"] is None and cleaned["raw"] is None:
            continue  # empty row added in the editor
        if cleaned["name"] is None:
            cleaned["name"] = cleaned["raw"]
        if cleaned["quantity"] is not None:
            cleaned["quantity"] = float(cleaned["quantity"])
        rows.append(cleaned)
    return rows


def format_validation_error(exc: ValidationError) -> str:
    return "\n".join(f"- `{'.'.join(str(p) for p in err['loc'])}`: {err['msg']}" for err in exc.errors())


# --- Sidebar: configuration status ------------------------------------------------

with st.sidebar:
    st.header("Setup")
    missing = missing_settings()
    if missing:
        st.error("Missing configuration: " + ", ".join(f"`{m}`" for m in missing))
    else:
        st.success("Configuration loaded.")
    if st.button("Check Notion database", disabled=bool(missing)):
        try:
            problems = check_notion_setup()
        except ServiceError as exc:
            st.error(exc.user_message)
        else:
            if problems:
                st.warning("Notion schema problems:\n" + "\n".join(f"- {p}" for p in problems))
            else:
                st.success("Notion database matches docs/NOTION_SETUP.md.")

st.title("🍲 AI Recipe Assistant")
st.caption("Save recipes from text or a link, then ask your cookbook what to cook.")

if state.flash:
    st.success(state.flash)
    state.flash = None

# --- Add recipe -------------------------------------------------------------------

st.subheader("📝 Add Recipe")
input_text = st.text_area("Paste recipe text or a recipe URL", height=180)

if st.button("Process Recipe", type="primary"):
    if not input_text.strip():
        st.warning("Please provide recipe text or a URL.")
    else:
        with st.spinner("Reading the recipe... 🥕"):
            try:
                set_draft(parse_recipe_draft(input_text))
            except ServiceError as exc:
                st.error(exc.user_message)

draft = state.draft
if draft:
    v = state.draft_version
    st.markdown("#### Review before saving")
    st.caption("Check every field. Empty means the source did not state it - leave it empty rather than guessing.")
    with st.form(f"review_{v}"):
        name = st.text_input("Name", value=draft.get("name") or "")
        col1, col2, col3 = st.columns(3)
        prep = col1.number_input("Prep time (min)", min_value=0, step=1, value=draft.get("prep_time_minutes"))
        cook = col2.number_input("Cook time (min)", min_value=0, step=1, value=draft.get("cook_time_minutes"))
        total = col3.number_input("Total time (min)", min_value=0, step=1, value=draft.get("total_time_minutes"))
        col4, col5 = st.columns(2)
        category_value = draft.get("category") or ""
        category_options = CATEGORIES if category_value in CATEGORIES else CATEGORIES + [category_value]
        category = col4.selectbox("Category", category_options, index=category_options.index(category_value))
        veg_label = {None: "Unknown", True: "Yes", False: "No"}[draft.get("vegetarian")]
        vegetarian = col5.selectbox("Vegetarian", list(VEGETARIAN_OPTIONS), index=list(VEGETARIAN_OPTIONS).index(veg_label))
        tags = st.text_input("Tags (comma separated)", value=", ".join(draft.get("tags") or []))
        source_url = st.text_input("Source URL", value=draft.get("source_url") or "")

        st.markdown("Ingredients")
        ingredients_df = pd.DataFrame(draft.get("ingredients") or [], columns=INGREDIENT_COLUMNS)
        ingredients_df["quantity"] = pd.to_numeric(ingredients_df["quantity"], errors="coerce")
        for text_col in ("name", "unit", "raw"):  # all-None columns would otherwise become float
            ingredients_df[text_col] = ingredients_df[text_col].astype("string")
        edited_ingredients = st.data_editor(
            ingredients_df,
            num_rows="dynamic",
            width="stretch",
            column_config={
                "name": st.column_config.TextColumn("Name", required=True),
                "quantity": st.column_config.NumberColumn("Quantity", min_value=0),
                "unit": st.column_config.TextColumn("Unit"),
                "raw": st.column_config.TextColumn("Original line"),
            },
        )
        instructions = st.text_area(
            "Instructions (one step per line)", value="\n".join(draft.get("instructions") or []), height=200
        )
        save_col, discard_col = st.columns([1, 1])
        save_clicked = save_col.form_submit_button("Save to Notion", type="primary")
        discard_clicked = discard_col.form_submit_button("Discard draft")

    if discard_clicked:
        set_draft(None)
        st.rerun()

    if save_clicked:
        confirmed = {
            "name": name,
            "ingredients": ingredients_from_editor(edited_ingredients),
            "instructions": instructions.splitlines(),
            "prep_time_minutes": prep,
            "cook_time_minutes": cook,
            "total_time_minutes": total,
            "category": category or None,
            "vegetarian": VEGETARIAN_OPTIONS[vegetarian],
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "source_url": source_url.strip() or None,
        }
        try:
            with st.spinner("Saving to your cookbook... 📒"):
                result = save_recipe(confirmed)
        except ValidationError as exc:
            st.error("Fix these fields before saving:\n" + format_validation_error(exc))
        except ServiceError as exc:
            st.error(exc.user_message)
        else:
            set_draft(None)
            state.flash = f"Saved **{confirmed['name']}** to Notion: {result.get('url') or result['id']}"
            st.rerun()

st.divider()

# --- Ask the cookbook -------------------------------------------------------------

st.subheader("🧑‍🍳 Ask My Cookbook")
st.caption('Examples: "vegetarian meals under 30 minutes", "something with chicken", "I want pasta tonight".')


for turn in state.history:
    with st.chat_message("user", avatar="🙂"):
        st.markdown(turn["question"])
    with st.chat_message("assistant", avatar="🧑‍🍳"):
        st.markdown(turn["answer"])

# A form submits on Enter and clears the input afterwards.
with st.form("ask_form", clear_on_submit=True, border=False):
    question = st.text_input("Question", placeholder="Ask a question or reply to the agent")
    asked = st.form_submit_button("Ask Agent", type="primary")
if state.history and st.button("Clear conversation"):
    state.history = []
    st.rerun()

if asked and question.strip():
    staged: list[dict] = []
    with st.spinner("Agent is cooking... 🍳"):
        try:
            answer = ask_agent(question.strip(), on_draft=staged.append, history=state.history)
        except ServiceError as exc:
            st.error(exc.user_message)
        else:
            state.history.append({"question": question.strip(), "answer": answer})
            if staged:
                set_draft(staged[-1])
                state.flash = "The agent prepared a recipe draft - review it in Add Recipe before saving."
            st.rerun()
