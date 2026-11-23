"""Video upload extraction (ADR-016) with a fake Gemini client - no network."""

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from agent import tools
from services import gemini_service, recipe_parser
from services.errors import ProviderUnavailableError, ServiceError

MP4 = b"\x00\x00\x00\x18ftypmp42 fake video bytes"


class FakeFiles:
    def __init__(self, states=("PROCESSING", "ACTIVE")):
        self.states = list(states)
        self.uploaded, self.deleted = [], []

    def _file(self):
        return SimpleNamespace(name="files/abc", state=types.FileState(self.states.pop(0)))

    def upload(self, file, config):
        self.uploaded.append((file.read(), config.mime_type))
        return self._file()

    def get(self, name):
        return self._file()

    def delete(self, name):
        self.deleted.append(name)


class FakeModels:
    def __init__(self, text='{"name": "Spicy Noodles", "ingredients": [{"name": "noodles"}]}', error=None):
        self.text, self.error, self.calls = text, error, []

    def generate_content(self, model, contents, config):
        self.calls.append(contents)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


@pytest.fixture
def gemini(monkeypatch):
    client = SimpleNamespace(files=FakeFiles(), models=FakeModels())
    monkeypatch.setattr(gemini_service, "_client", lambda: client)
    monkeypatch.setattr(gemini_service, "_POLL_SECONDS", 0)
    return client


def test_video_is_uploaded_waited_for_extracted_and_deleted(gemini):
    recipe = recipe_parser.parse_recipe_video(MP4, "video/mp4", "Spicy noodles, 10 min #recipe")
    assert recipe.name == "Spicy Noodles"
    assert gemini.files.uploaded == [(MP4, "video/mp4")]
    file_part, prompt = gemini.models.calls[0]
    assert file_part.name == "files/abc" and file_part.state == types.FileState.ACTIVE  # waited for processing
    assert prompt.startswith(gemini_service.EXTRACTION_RULES) and prompt.endswith("Spicy noodles, 10 min #recipe")
    assert "Never read amounts off the picture" in prompt
    assert gemini.files.deleted == ["files/abc"]


def test_link_as_caption_becomes_source_url_not_model_input(gemini):
    recipe = recipe_parser.parse_recipe_video(MP4, "video/mp4", "  https://www.instagram.com/reel/XYZ/ ")
    assert recipe.source_url == "https://www.instagram.com/reel/XYZ/"
    assert "instagram" not in gemini.models.calls[0][1]


def test_model_cannot_set_source_url(gemini):
    gemini.models.text = '{"name": "Soup", "source_url": "https://invented.example"}'
    assert recipe_parser.parse_recipe_video(MP4, "video/mp4", "").source_url is None


def test_video_without_recipe_is_rejected_and_still_deleted(gemini):
    gemini.models.text = '{"name": "NOT_A_RECIPE"}'
    with pytest.raises(ServiceError, match="No recipe found"):
        recipe_parser.parse_recipe_video(MP4, "video/mp4")
    assert gemini.files.deleted == ["files/abc"]


def test_failed_processing_is_a_clear_error(gemini):
    gemini.files.states = ["PROCESSING", "FAILED"]
    with pytest.raises(ServiceError, match="could not read this video"):
        recipe_parser.parse_recipe_video(MP4, "video/mp4")
    assert gemini.models.calls == [] and gemini.files.deleted == ["files/abc"]


def test_processing_timeout(gemini, monkeypatch):
    gemini.files.states = ["PROCESSING"] * 5
    monkeypatch.setattr(gemini_service, "VIDEO_PROCESSING_TIMEOUT", -1)
    with pytest.raises(ProviderUnavailableError, match="too long"):
        recipe_parser.parse_recipe_video(MP4, "video/mp4")


def test_rate_limit_says_video_needs_gemini_and_never_calls_claude(gemini, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")  # fallback configured, but Claude cannot read video
    monkeypatch.setattr(recipe_parser.claude_service, "extract_recipe_structured", lambda t: pytest.fail("no Claude"))
    gemini.models.error = genai_errors.APIError(429, {"error": {"message": "quota"}})
    with pytest.raises(ProviderUnavailableError, match="only be read by Gemini"):
        recipe_parser.parse_recipe_video(MP4, "video/mp4")
    assert gemini.files.deleted == ["files/abc"]


@pytest.mark.parametrize(
    ("data", "mime", "message"),
    [(b"", "video/mp4", "empty"), (MP4, "image/png", "Unsupported"), (MP4, "video/x-msvideo", "Unsupported")],
)
def test_bad_uploads_are_rejected_before_any_request(gemini, data, mime, message):
    with pytest.raises(ServiceError, match=message):
        recipe_parser.parse_recipe_video(data, mime)
    assert gemini.files.uploaded == []


def test_too_large_video_is_rejected(gemini, monkeypatch):
    monkeypatch.setattr(recipe_parser, "MAX_VIDEO_MB", 0)
    with pytest.raises(ServiceError, match="larger than"):
        recipe_parser.parse_recipe_video(MP4, "video/mp4")


def test_ui_function_returns_a_plain_draft(gemini):
    draft = tools.parse_recipe_video_draft(MP4, "video/quicktime", "caption")
    assert draft["name"] == "Spicy Noodles" and draft["ingredients"][0]["quantity"] is None


def test_upload_limit_matches_streamlit_config():
    import tomllib
    from pathlib import Path

    config = tomllib.loads((Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text("utf-8"))
    assert config["server"]["maxUploadSize"] == recipe_parser.MAX_VIDEO_MB
