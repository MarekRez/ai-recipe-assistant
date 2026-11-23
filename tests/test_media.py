"""Video / photo upload extraction (ADR-016) with a fake Gemini client - no network."""

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from agent import tools
from services import gemini_service, recipe_parser
from services.errors import ProviderUnavailableError, ServiceError

MP4 = b"\x00\x00\x00\x18ftypmp42 fake video bytes"
JPG = b"\xff\xd8\xff\xe0 fake jpeg bytes"
VIDEO = [(MP4, "video/mp4")]


class FakeFiles:
    """Each upload gets its own name; `states` is the sequence every file goes through."""

    def __init__(self, states=("PROCESSING", "ACTIVE")):
        self.states = list(states)
        self.uploaded, self.deleted, self.fail_upload_at = [], [], None
        self._progress = {}

    def _file(self, name):
        step = self._progress.get(name, 0)
        self._progress[name] = step + 1
        state = self.states[min(step, len(self.states) - 1)]
        return SimpleNamespace(name=name, state=types.FileState(state))

    def upload(self, file, config):
        if self.fail_upload_at == len(self.uploaded):
            raise genai_errors.APIError(503, {"error": {"message": "busy"}})
        self.uploaded.append((file.read(), config.mime_type))
        return self._file(f"files/{len(self.uploaded)}")

    def get(self, name):
        return self._file(name)

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


# --- video ---------------------------------------------------------------------------------------


def test_video_is_uploaded_waited_for_extracted_and_deleted(gemini):
    recipe = recipe_parser.parse_recipe_media(VIDEO, "Spicy noodles, 10 min #recipe")
    assert recipe.name == "Spicy Noodles"
    assert gemini.files.uploaded == [(MP4, "video/mp4")]
    file_part, prompt = gemini.models.calls[0]
    assert file_part.name == "files/1" and file_part.state == types.FileState.ACTIVE  # waited for processing
    assert prompt.startswith(gemini_service.EXTRACTION_RULES) and prompt.endswith("Spicy noodles, 10 min #recipe")
    assert "Never read amounts off the picture" in prompt
    assert gemini.files.deleted == ["files/1"]


def test_link_as_caption_becomes_source_url_not_model_input(gemini):
    recipe = recipe_parser.parse_recipe_media(VIDEO, "  https://www.instagram.com/reel/XYZ/ ")
    assert recipe.source_url == "https://www.instagram.com/reel/XYZ/"
    assert "instagram" not in gemini.models.calls[0][-1]


def test_model_cannot_set_source_url(gemini):
    gemini.models.text = '{"name": "Soup", "source_url": "https://invented.example"}'
    assert recipe_parser.parse_recipe_media(VIDEO, "").source_url is None


def test_upload_without_recipe_is_rejected_and_still_deleted(gemini):
    gemini.models.text = '{"name": "NOT_A_RECIPE"}'
    with pytest.raises(ServiceError, match="No recipe found"):
        recipe_parser.parse_recipe_media(VIDEO)
    assert gemini.files.deleted == ["files/1"]


def test_failed_processing_is_a_clear_error(gemini):
    gemini.files.states = ["PROCESSING", "FAILED"]
    with pytest.raises(ServiceError, match="could not read this file"):
        recipe_parser.parse_recipe_media(VIDEO)
    assert gemini.models.calls == [] and gemini.files.deleted == ["files/1"]


def test_processing_timeout(gemini, monkeypatch):
    gemini.files.states = ["PROCESSING"]
    monkeypatch.setattr(gemini_service, "MEDIA_PROCESSING_TIMEOUT", -1)
    with pytest.raises(ProviderUnavailableError, match="too long"):
        recipe_parser.parse_recipe_media(VIDEO)


def test_rate_limit_says_gemini_only_and_never_calls_claude(gemini, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")  # fallback configured, but this path is Gemini-only
    monkeypatch.setattr(recipe_parser.claude_service, "extract_recipe_structured", lambda t: pytest.fail("no Claude"))
    gemini.models.error = genai_errors.APIError(429, {"error": {"message": "quota"}})
    with pytest.raises(ProviderUnavailableError, match="only be read by Gemini"):
        recipe_parser.parse_recipe_media(VIDEO)
    assert gemini.files.deleted == ["files/1"]


# --- photos --------------------------------------------------------------------------------------


def test_photos_go_to_gemini_together_in_order(gemini):
    gemini.files.states = ["ACTIVE"]  # images are ready immediately
    photos = [(JPG + b"1", "image/jpeg"), (b"\x89PNG page 2", "image/png"), (b"heic page 3", "image/heic")]
    recipe = recipe_parser.parse_recipe_media(photos, "Grandma's cake")
    assert recipe.name == "Spicy Noodles"
    assert [mime for _, mime in gemini.files.uploaded] == ["image/jpeg", "image/png", "image/heic"]
    *parts, prompt = gemini.models.calls[0]
    assert [p.name for p in parts] == ["files/1", "files/2", "files/3"]  # one request, pages in upload order
    assert "Several photos belong to one recipe" in prompt and prompt.endswith("Grandma's cake")
    assert gemini.files.deleted == ["files/1", "files/2", "files/3"]


def test_failed_upload_of_a_later_photo_still_deletes_the_earlier_ones(gemini):
    gemini.files.fail_upload_at = 1
    with pytest.raises(ProviderUnavailableError):
        recipe_parser.parse_recipe_media([(JPG, "image/jpeg"), (JPG, "image/jpeg")])
    assert gemini.files.deleted == ["files/1"] and gemini.models.calls == []


# --- checks before any request -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ([], "at least one photo"),
        ([(b"", "video/mp4")], "empty"),
        ([(MP4, "application/pdf")], "Unsupported"),
        ([(MP4, "video/x-msvideo")], "Unsupported"),
        ([(MP4, "video/mp4"), (JPG, "image/jpeg")], "either one video or photos"),
        ([(MP4, "video/mp4"), (MP4, "video/mp4")], "one video at a time"),
        ([(JPG, "image/jpeg")] * 6, "at most 5 photos"),
    ],
)
def test_bad_uploads_are_rejected_before_any_request(gemini, files, message):
    with pytest.raises(ServiceError, match=message):
        recipe_parser.parse_recipe_media(files)
    assert gemini.files.uploaded == []


def test_too_large_file_is_rejected(gemini, monkeypatch):
    monkeypatch.setattr(recipe_parser, "MAX_UPLOAD_MB", 0)
    with pytest.raises(ServiceError, match="larger than"):
        recipe_parser.parse_recipe_media(VIDEO)


def test_ui_function_returns_a_plain_draft(gemini):
    draft = tools.parse_recipe_media_draft([(MP4, "video/quicktime")], "caption")
    assert draft["name"] == "Spicy Noodles" and draft["ingredients"][0]["quantity"] is None


def test_upload_limit_matches_streamlit_config():
    import tomllib
    from pathlib import Path

    config = tomllib.loads((Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text("utf-8"))
    assert config["server"]["maxUploadSize"] == recipe_parser.MAX_UPLOAD_MB
