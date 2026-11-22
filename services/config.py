"""Environment configuration.

Values come from `os.environ` only. Locally `app.py` loads `.env` via python-dotenv;
Streamlit Community Cloud exposes top-level secrets as environment variables.
"""

from __future__ import annotations

import os

from services.errors import ServiceError

REQUIRED_SETTINGS = ("GEMINI_API_KEY", "GEMINI_MODEL", "NOTION_API_KEY", "NOTION_DATA_SOURCE_ID")

# Optional Claude fallback (ADR-012): used only when Gemini is rate limited or down, and only if a key is set.
CLAUDE_DEFAULT_MODEL = "claude-haiku-5-5"  # small and cheap - enough for extraction and simple tool calls


def get_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ServiceError(
            f"Missing configuration value `{name}`. Add it to `.env` (local) or app secrets (cloud).",
        )
    return value


def missing_settings() -> list[str]:
    return [name for name in REQUIRED_SETTINGS if not os.environ.get(name, "").strip()]


def claude_fallback_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def claude_model() -> str:
    return os.environ.get("CLAUDE_MODEL", "").strip() or CLAUDE_DEFAULT_MODEL
