"""Streamlit entrypoint for AI Recipe Knowledge Assistant MVP."""

import streamlit as st


st.set_page_config(page_title="AI Recipe Assistant", page_icon="🍲", layout="wide")

st.title("AI Recipe Knowledge Assistant")
st.caption("Minimal MVP scaffold - implement parsing, review, save, and query flows.")

st.subheader("Add Recipe")
input_text = st.text_area("Paste recipe text or URL", height=180)

if st.button("Process Recipe"):
    if not input_text.strip():
        st.warning("Please provide recipe text or a URL.")
    else:
        st.info("TODO: call parse_recipe tool and render editable structured output.")

st.divider()

st.subheader("Ask My Cookbook")
question = st.text_input("Question")
if st.button("Ask Agent"):
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        st.info("TODO: call agent and show tool-driven answer.")
