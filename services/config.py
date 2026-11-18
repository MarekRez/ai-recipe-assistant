"""Environment configuration.

Values come from `os.environ` only. Locally `app.py` loads `.env` via python-dotenv;
Streamlit Community Cloud exposes top-level secrets as environment variables.
"""

from __future__ import annotations

import os

from services.errors import ServiceError

REQUIRED_SETTINGS = ("GEMINI_API_KEY", "GEMINI_MODEL", "NOTION_API_KEY", "NOTION_DATA_SOURCE_ID")


def get_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ServiceError(
            f"Missing configuration value `{name}`. Add it to `.env` (local) or app secrets (cloud).",
        )
    return value


def missing_settings() -> list[str]:
    return [name for name in REQUIRED_SETTINGS if not os.environ.get(name, "").strip()]
