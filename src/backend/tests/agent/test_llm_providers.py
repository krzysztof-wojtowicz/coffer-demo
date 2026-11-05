import json

import httpx
import pytest

from coffer.agent.llm import (
    _STATUS_CACHE,
    AnthropicClient,
    GeminiClient,
    LLMMessage,
    LLMStatus,
    LLMUnavailable,
    OllamaClient,
    OpenAIClient,
    anthropic_schema,
    gemini_schema,
    get_llm_client,
    provider_name,
)
from coffer.core.config import Settings

SCHEMA = {
    "type": "object",
    "title": "Draft",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string", "title": "Summary"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
    },
    "required": ["summary", "risks"],
}

MESSAGES = [
    LLMMessage("user", "hej"),
    LLMMessage("assistant", "{}"),
    LLMMessage("user", "popraw"),
]


@pytest.fixture(autouse=True)
def clear_status_cache():
    _STATUS_CACHE.clear()
    yield
    _STATUS_CACHE.clear()


@pytest.fixture
def mock_transport(monkeypatch):
    """Injects a MockTransport into every httpx.Client (including the one behind httpx.post)."""

    def install(handler):
        orig = httpx.Client.__init__

        def init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            orig(self, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "__init__", init)

    return install


def _openai(key="sk-secret"):
    return OpenAIClient(key, "gpt-4o-mini", "https://api.example.test/v1/", 5.0)


def _gemini(key="g-secret"):
    return GeminiClient(key, "gemini-3.8-flash", 5.0)


def _anthropic(key="sk-ant-secret", model="claude-sonnet-5-5"):
    return AnthropicClient(key, model, "https://api.anthropic.example/", 5.0)


# --- OpenAI ---


def test_openai_request_and_response(mock_transport):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini-2024-07-18",
                "choices": [{"message": {"role": "assistant", "content": '{"summary": "ok"}'}}],
                "usage": {"prompt_tokens": 21, "completion_tokens": 9},
            },
        )

    mock_transport(handler)
    resp = _openai().complete(system="SYS", messages=MESSAGES, response_schema=SCHEMA)
    assert seen["url"] == "https://api.example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-secret"
    body = seen["body"]
    assert body["model"] == "gpt-4o-mini"
    assert body["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hej"},
        {"role": "assistant", "content": "{}"},
        {"role": "user", "content": "popraw"},
    ]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["response_format"]["json_schema"]["name"]
    assert resp.content == '{"summary": "ok"}'
    assert resp.model == "gpt-4o-mini-2024-07-18"
    assert (resp.input_tokens, resp.output_tokens) == (21, 9)


def test_openai_without_schema_and_usage(mock_transport):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    mock_transport(handler)
    resp = _openai().complete(system="s", messages=[LLMMessage("user", "u")])
    assert "response_format" not in seen["body"]
    assert resp.content == "x"
    assert resp.model == "gpt-4o-mini"
    assert resp.input_tokens is None and resp.output_tokens is None


# --- Gemini ---


def test_gemini_request_and_response(mock_transport):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": '{"a":'}, {"text": "1}"}]}}
                ],
                "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 4},
                "modelVersion": "gemini-3.8-flash-001",
            },
        )

    mock_transport(handler)
    resp = _gemini().complete(system="SYS", messages=MESSAGES, response_schema=SCHEMA)
    assert seen["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
    )
    assert "g-secret" not in seen["url"]
    assert seen["key"] == "g-secret"
    body = seen["body"]
    assert body["systemInstruction"] == {"parts": [{"text": "SYS"}]}
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "hej"}]},
        {"role": "model", "parts": [{"text": "{}"}]},
        {"role": "user", "parts": [{"text": "popraw"}]},
    ]
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    assert cfg["responseSchema"] == gemini_schema(SCHEMA)
    assert resp.content == '{"a":1}'
    assert resp.model == "gemini-3.8-flash-001"
    assert (resp.input_tokens, resp.output_tokens) == (30, 4)


def test_gemini_without_schema(mock_transport):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]})

    mock_transport(handler)
    resp = _gemini().complete(system="s", messages=[LLMMessage("user", "u")])
    assert "responseSchema" not in seen["body"]["generationConfig"]
    assert "responseMimeType" not in seen["body"]["generationConfig"]
    assert resp.content == "x"
    assert resp.input_tokens is None and resp.output_tokens is None


def test_gemini_schema_cleanup():
    pydantic_like = {
        "$defs": {
            "Item": {"type": "object", "title": "Item", "properties": {"n": {"type": "integer"}}}
        },
        "type": "object",
        "title": "Root",
        "additionalProperties": False,
        "properties": {
            "items": {"type": "array", "items": {"$ref": "#/$defs/Item"}},
            "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            "tag": {"type": ["string", "null"], "enum": ["a", "b", None]},
        },
        "required": ["items"],
    }
    assert gemini_schema(pydantic_like) == {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "object", "properties": {"n": {"type": "integer"}}},
            },
            "note": {"type": "string", "nullable": True},
            "tag": {"type": "string", "nullable": True, "enum": ["a", "b", None]},
        },
        "required": ["items"],
    }


def test_gemini_empty_candidates(mock_transport):
    mock_transport(lambda r: httpx.Response(200, json={"candidates": []}))
    with pytest.raises(LLMUnavailable):
        _gemini().complete(system="s", messages=[LLMMessage("user", "u")])


# --- Anthropic ---


def test_anthropic_request_and_response(mock_transport):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-5-5",
                "stop_reason": "end_turn",
                "content": [
                    {"type": "thinking", "thinking": ""},
                    {"type": "text", "text": '{"summary":'},
                    {"type": "text", "text": ' "ok"}'},
                ],
                "usage": {"input_tokens": 40, "output_tokens": 12},
            },
        )

    mock_transport(handler)
    resp = _anthropic().complete(system="SYS", messages=MESSAGES, response_schema=SCHEMA)
    assert seen["url"] == "https://api.anthropic.example/v1/messages"
    assert "secret" not in seen["url"]
    assert seen["headers"]["x-api-key"] == "sk-ant-secret"
    assert seen["headers"]["anthropic-version"] == AnthropicClient.API_VERSION
    assert "authorization" not in seen["headers"]
    body = seen["body"]
    assert body["model"] == "claude-sonnet-5-5"
    assert body["system"] == "SYS"
    assert body["max_tokens"] > 0
    assert body["messages"] == [
        {"role": "user", "content": "hej"},
        {"role": "assistant", "content": "{}"},
        {"role": "user", "content": "popraw"},
    ]
    assert "temperature" not in body
    assert "tool_choice" not in body
    assert body["output_config"]["format"] == {
        "type": "json_schema",
        "schema": anthropic_schema(SCHEMA),
    }
    assert body["fallbacks"] == "default"
    assert seen["headers"]["anthropic-beta"] == AnthropicClient._FALLBACK_BETA
    assert resp.content == '{"summary": "ok"}'
    assert resp.model == "claude-sonnet-5-5"
    assert (resp.input_tokens, resp.output_tokens) == (40, 12)


def test_anthropic_without_schema_and_usage(mock_transport):
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "x"}]})

    mock_transport(handler)
    resp = _anthropic(model="claude-haiku-4-5").complete(
        system="s", messages=[LLMMessage("user", "u")]
    )
    assert "output_config" not in seen["body"]
    assert "fallbacks" not in seen["body"]
    assert "anthropic-beta" not in seen["headers"]
    assert resp.content == "x"
    assert resp.model == "claude-haiku-4-5"
    assert resp.input_tokens is None and resp.output_tokens is None


@pytest.mark.parametrize(
    "payload",
    [
        {"stop_reason": "refusal", "content": [{"type": "text", "text": "{}"}]},
        {"stop_reason": "max_tokens", "content": [{"type": "text", "text": '{"a"'}]},
        {"content": []},
        {"content": "nope"},
        {"model": "x"},
    ],
)
def test_anthropic_unusable_responses(mock_transport, payload):
    mock_transport(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(LLMUnavailable):
        _anthropic().complete(system="s", messages=[LLMMessage("user", "u")])


def test_anthropic_schema_cleanup():
    pydantic_like = {
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {"n": {"type": "integer", "minimum": 0, "maximum": 9}},
            }
        },
        "type": "object",
        "title": "Root",
        "properties": {
            "items": {
                "type": "array",
                "items": {"$ref": "#/$defs/Item"},
                "minItems": 1,
                "maxItems": 5,
            },
            "name": {"type": "string", "minLength": 1, "maxLength": 80},
            "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
        },
        "required": ["items"],
    }
    assert anthropic_schema(pydantic_like) == {
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {"n": {"type": "integer"}},
                "additionalProperties": False,
            }
        },
        "type": "object",
        "title": "Root",
        "properties": {
            "items": {"type": "array", "items": {"$ref": "#/$defs/Item"}, "minItems": 1},
            "name": {"type": "string"},
            "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
        },
        "required": ["items"],
        "additionalProperties": False,
    }
    # property names that collide with dropped keywords are kept
    assert anthropic_schema({"type": "object", "properties": {"maximum": {"type": "number"}}})[
        "properties"
    ] == {"maximum": {"type": "number"}}


# --- shared error handling ---

CLIENTS = [
    pytest.param(_openai, id="openai"),
    pytest.param(_gemini, id="gemini"),
    pytest.param(_anthropic, id="anthropic"),
]


@pytest.mark.parametrize("make", CLIENTS)
@pytest.mark.parametrize("status", [400, 401, 429, 500, 503])
def test_bad_status(mock_transport, make, status):
    mock_transport(lambda r: httpx.Response(status, json={"error": {"message": "x"}}))
    with pytest.raises(LLMUnavailable) as info:
        make().complete(system="s", messages=[LLMMessage("user", "u")])
    assert "secret" not in str(info.value)


@pytest.mark.parametrize("make", CLIENTS)
@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
def test_connection_errors(mock_transport, make, exc):
    def handler(request):
        raise exc

    mock_transport(handler)
    with pytest.raises(LLMUnavailable):
        make().complete(system="s", messages=[LLMMessage("user", "u")])


@pytest.mark.parametrize("make", CLIENTS)
def test_malformed_response(mock_transport, make):
    mock_transport(lambda r: httpx.Response(200, content=b"not json"))
    with pytest.raises(LLMUnavailable):
        make().complete(system="s", messages=[LLMMessage("user", "u")])


@pytest.mark.parametrize("make", CLIENTS)
def test_status_without_key_makes_no_request(mock_transport, make):
    def handler(request):
        raise AssertionError("status() must not call the network")

    mock_transport(handler)
    assert make(key="").status().available is False
    with pytest.raises(LLMUnavailable):
        make(key="").complete(system="s", messages=[LLMMessage("user", "u")])


STATUS_PROBES = [
    pytest.param(_openai, "https://api.example.test/v1/models", "authorization", id="openai"),
    pytest.param(
        _gemini,
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash",
        "x-goog-api-key",
        id="gemini",
    ),
    pytest.param(
        _anthropic,
        "https://api.anthropic.example/v1/models/claude-sonnet-5-5",
        "x-api-key",
        id="anthropic",
    ),
]


@pytest.mark.parametrize(("make", "url", "key_header"), STATUS_PROBES)
def test_status_probe_ok_and_cached(mock_transport, make, url, key_header):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    mock_transport(handler)
    assert make().status().available is True
    assert make().status().available is True  # new instance, same config: cached
    assert len(calls) == 1
    req = calls[0]
    assert req.method == "GET"
    assert str(req.url) == url
    assert "secret" not in str(req.url)
    assert "secret" in req.headers[key_header]


@pytest.mark.parametrize(("make", "url", "key_header"), STATUS_PROBES)
@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_status_probe_bad_status(mock_transport, make, url, key_header, status):
    mock_transport(lambda r: httpx.Response(status, json={"error": {}}))
    assert make().status().available is False


@pytest.mark.parametrize("make", CLIENTS)
def test_status_probe_network_error(mock_transport, make):
    def handler(request):
        raise httpx.ConnectTimeout("slow")

    mock_transport(handler)
    assert make().status().available is False


def test_status_cache_expires(mock_transport, monkeypatch):
    codes = iter([401, 200])
    mock_transport(lambda r: httpx.Response(next(codes)))
    clock = iter([1000.0, 1030.0, 1100.0])
    monkeypatch.setattr("coffer.agent.llm.time.monotonic", lambda: next(clock))
    assert _anthropic().status().available is False
    assert _anthropic().status().available is False  # within TTL: cached
    assert _anthropic().status().available is True  # TTL elapsed: probed again


def test_status_cache_is_per_key(mock_transport):
    mock_transport(lambda r: httpx.Response(200 if r.headers["x-api-key"] == "good" else 401))
    assert _anthropic(key="bad").status().available is False
    assert _anthropic(key="good").status().available is True
    assert not any("good" in str(k) or "bad" in str(k) for k in _STATUS_CACHE)


@pytest.mark.parametrize("make", CLIENTS)
def test_key_not_in_repr(make):
    assert "secret" not in repr(make())


# --- factory ---


@pytest.fixture
def settings(monkeypatch):
    def install(**values):
        monkeypatch.setattr(
            "coffer.agent.llm.get_settings", lambda: Settings.model_construct(**values)
        )

    return install


def test_factory_none(settings):
    settings(llm_provider="none")
    assert get_llm_client() is None


def test_factory_ollama(settings):
    settings(llm_provider="ollama")
    assert isinstance(get_llm_client(), OllamaClient)


def test_factory_openai(settings, mock_transport):
    mock_transport(lambda r: httpx.Response(200, json={"data": []}))
    settings(llm_provider="openai", openai_api_key="sk-x", openai_base_url="http://local:1234/v1")
    client = get_llm_client()
    assert isinstance(client, OpenAIClient)
    assert client.base_url == "http://local:1234/v1"
    assert client.status() == LLMStatus(True, "gpt-4o-mini")


def test_factory_gemini_without_key(settings):
    settings(llm_provider="gemini")
    client = get_llm_client()
    assert isinstance(client, GeminiClient)
    assert client.status() == LLMStatus(False, "gemini-3.8-flash")


def test_factory_anthropic(settings, mock_transport):
    mock_transport(lambda r: httpx.Response(200, json={}))
    settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-x",
        anthropic_model="claude-sonnet-5-5",
        anthropic_base_url="https://api.anthropic.com",
    )
    client = get_llm_client()
    assert isinstance(client, AnthropicClient)
    assert client.base_url == "https://api.anthropic.com"
    assert client.status() == LLMStatus(True, "claude-sonnet-5-5")
    assert provider_name(client) == "anthropic"


def test_factory_anthropic_defaults_without_key(settings):
    settings(llm_provider="anthropic")
    client = get_llm_client()
    assert isinstance(client, AnthropicClient)
    assert client.status() == LLMStatus(False, "claude-sonnet-5-5")


def test_provider_name():
    assert provider_name(None) == "none"
    assert provider_name(_openai()) == "openai"
    assert provider_name(_gemini()) == "gemini"
    assert provider_name(_anthropic()) == "anthropic"
    assert provider_name(OllamaClient("http://x", "m", 1.0)) == "ollama"


def test_settings_repr_hides_keys():
    s = Settings.model_construct(
        openai_api_key="sk-hidden", gemini_api_key="g-hidden", anthropic_api_key="a-hidden"
    )
    assert "hidden" not in repr(s)
