"""Claude fallback (ADR-012): switch only on a Gemini outage, only when configured. No live API calls."""

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from agent import claude_agent, recipe_agent
from agent import tools as tools_module
from agent.tools import make_agent_tools
from services import claude_service, gemini_service, recipe_parser
from services.errors import ProviderUnavailableError, ServiceError
from tests.conftest import load_expected
from tests.test_agent import ScriptedModel

SOUP = load_expected("05_lentil_soup")


def gemini_down(text):
    raise ProviderUnavailableError("Gemini rate limit reached. Wait a minute and try again.")


@pytest.fixture
def claude_on(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    calls = []
    monkeypatch.setattr(claude_service, "extract_recipe_structured", lambda text: calls.append(text) or dict(SOUP))
    return calls


# --- extraction --------------------------------------------------------------------


def test_gemini_outage_falls_back_to_claude(monkeypatch, claude_on):
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", gemini_down)
    recipe, provider = recipe_parser.parse_recipe_with_provider("Red lentil soup ...")
    assert provider == "claude"
    assert recipe.name == "Red Lentil Soup"
    assert claude_on == ["Red lentil soup ..."]


def test_gemini_success_does_not_call_claude(monkeypatch, claude_on):
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", lambda text: dict(SOUP))
    assert recipe_parser.parse_recipe_with_provider("soup")[1] == "gemini"
    assert claude_on == []


def test_no_fallback_without_anthropic_key(monkeypatch):
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", gemini_down)
    monkeypatch.setattr(claude_service, "extract_recipe_structured", lambda text: pytest.fail("must not call Claude"))
    with pytest.raises(ProviderUnavailableError):
        recipe_parser.parse_recipe("soup")


@pytest.mark.parametrize(
    "gemini_result",
    [
        {"name": "NOT_A_RECIPE"},  # a real answer about the input - Claude would not change it
        ServiceError("Gemini rejected the request. Check GEMINI_API_KEY and GEMINI_MODEL."),  # config problem
    ],
)
def test_no_fallback_on_non_outage_results(monkeypatch, claude_on, gemini_result):
    def gemini(text):
        if isinstance(gemini_result, Exception):
            raise gemini_result
        return gemini_result

    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", gemini)
    with pytest.raises(ServiceError):
        recipe_parser.parse_recipe("meeting notes")
    assert claude_on == []


def test_pinned_provider_never_switches(monkeypatch, claude_on):
    # The eval pins one provider so its metrics describe one model.
    monkeypatch.setattr(recipe_parser, "extract_recipe_structured", gemini_down)
    with pytest.raises(ProviderUnavailableError):
        recipe_parser.parse_recipe("soup", provider="gemini")
    assert recipe_parser.parse_recipe_with_provider("soup", provider="claude")[1] == "claude"


@pytest.mark.parametrize("code, outage", [(429, True), (503, True), (500, True), (400, False), (404, False)])
def test_gemini_errors_are_classified(monkeypatch, code, outage):
    class FailingModels:
        @staticmethod
        def generate_content(**kwargs):
            raise genai_errors.APIError(code, {"error": {"code": code, "message": "x", "status": "X"}})

    monkeypatch.setattr(gemini_service, "_client", lambda: SimpleNamespace(models=FailingModels))
    with pytest.raises(ServiceError) as info:
        gemini_service.extract_recipe_structured("text")
    assert isinstance(info.value, ProviderUnavailableError) is outage


def _claude_client(response, sent=None):
    def parse(**kwargs):
        if sent is not None:
            sent.update(kwargs)
        return response

    return SimpleNamespace(messages=SimpleNamespace(parse=parse))


def test_claude_refusal_is_a_service_error(monkeypatch):
    response = SimpleNamespace(stop_reason="refusal", stop_details={"category": "x"}, parsed_output=None)
    monkeypatch.setattr(claude_service, "_client", lambda: _claude_client(response))
    with pytest.raises(ServiceError, match="declined"):
        claude_service.extract_recipe_structured("text")


def test_claude_request_has_no_sampling_params(monkeypatch):
    # API version 2026-10-21 rejects temperature/top_p/top_k.
    sent = {}
    parsed = SimpleNamespace(model_dump=lambda mode=None: {"name": "X"})
    response = SimpleNamespace(stop_reason="end_turn", stop_details=None, parsed_output=parsed)
    monkeypatch.setattr(claude_service, "_client", lambda: _claude_client(response, sent))
    assert claude_service.extract_recipe_structured("text") == {"name": "X"}
    assert not {"temperature", "top_p", "top_k"} & sent.keys()
    assert sent["model"] == "claude-haiku-5-5"


# --- agent -------------------------------------------------------------------------


def test_tool_definitions_translate_to_anthropic_format():
    defs = {t.name: claude_agent.to_anthropic_tool(t) for t in make_agent_tools()}
    assert set(defs) == {"search_recipes", "browse_recipes", "get_recipe", "parse_recipe"}  # still no save tool (ADR-005)
    assert defs["browse_recipes"]["input_schema"]["required"] == []
    search = defs["search_recipes"]["input_schema"]
    assert search["required"] == []  # every filter is optional
    assert search["properties"]["max_time"]["type"] == "integer"
    assert search["properties"]["tags"]["items"] == {"type": "string"}
    assert defs["get_recipe"]["input_schema"]["required"] == ["name_or_id"]


def test_claude_agent_runs_tools_then_answers(monkeypatch):
    monkeypatch.setattr(tools_module, "search_recipes_in_notion", lambda filters: [{"name": "Pasta", "total_time": 25}])
    turns = [
        SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use", id="t1", name="search_recipes", input={"vegetarian": True})],
        ),
        SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Pasta, 25 min.")]),
    ]
    requests = []

    def create(**kwargs):
        requests.append({**kwargs, "messages": list(kwargs["messages"])})  # snapshot: the loop keeps appending
        return turns[len(requests) - 1]

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(claude_agent.anthropic, "Anthropic", lambda: client)
    answer = claude_agent.run_claude_agent("veggie?", make_agent_tools(), "rules", max_steps=4)
    assert answer == "Pasta, 25 min."
    tool_result = requests[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and '"Pasta"' in tool_result["content"]
    assert not {"temperature", "top_p", "top_k"} & requests[0].keys()


def _rate_limited_model():
    class Broken(ScriptedModel):
        def generate(self, *args, **kwargs):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    return Broken([])


def test_agent_falls_back_to_claude_on_gemini_outage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setattr(recipe_agent, "run_claude_agent", lambda q, tools, instr, steps: "Claude answer")
    assert recipe_agent.ask_agent_with_provider("pasta?", model=_rate_limited_model()) == ("Claude answer", "claude")


def test_agent_does_not_fall_back_without_key(monkeypatch):
    monkeypatch.setattr(recipe_agent, "run_claude_agent", lambda *a: pytest.fail("must not call Claude"))
    with pytest.raises(ServiceError, match="rate limit"):
        recipe_agent.ask_agent("pasta?", model=_rate_limited_model())


def test_smolagents_retry_is_off_when_fallback_is_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    assert recipe_agent.build_model().retryer.max_attempts == 1
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert recipe_agent.build_model().retryer.max_attempts > 1


# --- daily limit message --------------------------------------------------------------------------

DAILY_429 = {
    "error": {
        "code": 429,
        "message": "Quota exceeded for metric: generate_content_free_tier_requests, limit: 20. Generate content "
        "requests per day limit exceeded on Free Tier.",
        "status": "RESOURCE_EXHAUSTED",
        "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}],
    }
}


def _gemini_raising(monkeypatch, error):
    class FailingModels:
        @staticmethod
        def generate_content(**kwargs):
            raise error

    monkeypatch.setattr(gemini_service, "_client", lambda: SimpleNamespace(models=FailingModels))


def test_daily_quota_says_tomorrow_not_wait_a_minute(monkeypatch):
    _gemini_raising(monkeypatch, genai_errors.APIError(429, DAILY_429))
    with pytest.raises(ProviderUnavailableError) as info:
        gemini_service.extract_recipe_structured("text")
    assert "daily" in info.value.user_message and "tomorrow" in info.value.user_message
    assert "Wait a minute" not in info.value.user_message


def test_per_minute_limit_still_says_wait_a_minute(monkeypatch):
    _gemini_raising(monkeypatch, genai_errors.APIError(429, {"error": {"code": 429, "message": "per minute"}}))
    with pytest.raises(ProviderUnavailableError, match="Wait a minute"):
        gemini_service.extract_recipe_structured("text")


def test_agent_reports_daily_limit_without_claude(monkeypatch):
    class DailyLimitModel(ScriptedModel):
        def generate(self, *args, **kwargs):
            raise RuntimeError("Error code: 429 - Generate content requests per day limit exceeded on Free Tier")

    with pytest.raises(ServiceError, match="daily request limit"):
        recipe_agent.ask_agent("dinner ideas", model=DailyLimitModel([]))


# --- photo fallback (ADR-016) ---------------------------------------------------------------------


def _png(width=40, height=20) -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def gemini_media_down(monkeypatch):
    def down(files, caption):
        raise ProviderUnavailableError(gemini_service.DAILY_LIMIT_MESSAGE, "429 PerDay")

    monkeypatch.setattr(recipe_parser, "extract_recipe_from_media", down)


def test_photos_fall_back_to_claude_when_gemini_is_down(monkeypatch, gemini_media_down):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    sent = {}
    response = SimpleNamespace(stop_reason="end_turn", parsed_output=SimpleNamespace(model_dump=lambda mode: dict(SOUP)))
    monkeypatch.setattr(claude_service, "_client", lambda: _claude_client(response, sent))
    photos = [(_png(), "image/png"), (_png(), "image/jpeg")]
    recipe, provider = recipe_parser.parse_recipe_media_with_provider(photos, "https://example.com/card")
    assert provider == "claude" and recipe.name == SOUP["name"]
    assert recipe.source_url == "https://example.com/card"  # from the input, not the model
    content = sent["messages"][0]["content"]
    assert [b["type"] for b in content] == ["image", "image", "text"]  # photos in order, then the prompt
    assert all(b["source"]["media_type"] == "image/jpeg" for b in content[:2])  # re-encoded
    assert content[2]["text"] == gemini_service.MEDIA_PROMPT  # the link is not sent to the model
    assert "temperature" not in sent


@pytest.mark.parametrize("mime", ["video/mp4", "image/heic"])
def test_video_and_heic_have_no_claude_fallback(monkeypatch, gemini_media_down, mime):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setattr(claude_service, "extract_recipe_from_images", lambda *a: pytest.fail("no Claude for this"))
    with pytest.raises(ProviderUnavailableError, match="can only be read by Gemini") as info:
        recipe_parser.parse_recipe_media([(b"data", mime)])
    assert "tomorrow" in info.value.user_message  # the daily-limit reason is kept


def test_no_photo_fallback_without_anthropic_key(monkeypatch, gemini_media_down):
    monkeypatch.setattr(claude_service, "extract_recipe_from_images", lambda *a: pytest.fail("no key, no Claude"))
    with pytest.raises(ProviderUnavailableError, match="Paste the recipe text"):
        recipe_parser.parse_recipe_media([(_png(), "image/png")])


def test_photos_are_shrunk_rotated_and_reencoded_for_claude():
    import io

    from PIL import Image

    big = io.BytesIO()
    img = Image.new("RGB", (4000, 1000), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # EXIF orientation: rotate 90 degrees (typical phone portrait photo)
    img.save(big, format="JPEG", exif=exif)
    with Image.open(io.BytesIO(claude_service.to_claude_jpeg(big.getvalue()))) as out:
        assert out.format == "JPEG"
        assert max(out.size) == claude_service.CLAUDE_MAX_IMAGE_EDGE
        assert out.size[1] > out.size[0]  # rotation applied: now portrait
    with Image.open(io.BytesIO(claude_service.to_claude_jpeg(_png(40, 20)))) as small:
        assert small.size == (40, 20)  # never enlarged


def test_unreadable_photo_is_a_clear_error():
    with pytest.raises(ServiceError, match="could not be opened"):
        claude_service.to_claude_jpeg(b"not an image")
