"""Production resilience of the LLM layer: retries, fallback chain, remote Ollama key, SSE ping."""

import json
import threading

import httpx
import pytest
from pydantic import ValidationError

from coffer.agent import llm as llm_mod
from coffer.agent import sse
from coffer.agent.llm import (
    _STATUS_CACHE,
    FallbackLLM,
    GeminiClient,
    LLMMessage,
    LLMStatus,
    LLMUnavailable,
    OllamaClient,
    get_llm_client,
    provider_name,
)
from coffer.agent.testing import FakeLLM
from coffer.core.config import Settings
from coffer.main import app

MSG = [LLMMessage("user", "hej")]
GEMINI_OK = {
    "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
    "modelVersion": "gemini-3.8-flash",
}


@pytest.fixture(autouse=True)
def clear_status_cache():
    _STATUS_CACHE.clear()
    yield
    _STATUS_CACHE.clear()


@pytest.fixture
def mock_transport(monkeypatch):
    def install(handler):
        orig = httpx.Client.__init__

        def init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            orig(self, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "__init__", init)

    return install


def scripted(responses):
    """Handler returning the scripted responses in order; records requests."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    return handler, calls


def gemini(timeout_s: float = 60) -> GeminiClient:
    return GeminiClient("secret-key", "gemini-3.8-flash", timeout_s)


# --- retries ---------------------------------------------------------------------------


def test_retry_503_then_200(mock_transport, no_retry_sleep):
    handler, calls = scripted(
        [
            httpx.Response(503, json={"error": {"message": "high demand"}}),
            httpx.Response(200, json=GEMINI_OK),
        ]
    )
    mock_transport(handler)
    assert gemini().complete(system="s", messages=MSG).content == "{}"
    assert len(calls) == 2
    assert len(no_retry_sleep) == 1 and 0 < no_retry_sleep[0] <= llm_mod.BACKOFF_BASE_S


def test_retry_429_respects_retry_after(mock_transport, no_retry_sleep):
    handler, calls = scripted(
        [
            httpx.Response(429, headers={"Retry-After": "7"}, json={}),
            httpx.Response(200, json=GEMINI_OK),
        ]
    )
    mock_transport(handler)
    gemini().complete(system="s", messages=MSG)
    assert len(calls) == 2
    assert no_retry_sleep == [7.0]


def test_retry_after_beyond_budget_fails_fast(mock_transport, no_retry_sleep):
    handler, calls = scripted([httpx.Response(429, headers={"Retry-After": "120"}, json={})])
    mock_transport(handler)
    with pytest.raises(LLMUnavailable, match="429"):
        gemini(timeout_s=30).complete(system="s", messages=MSG)
    assert len(calls) == 1 and no_retry_sleep == []


def test_retries_exhausted(mock_transport, no_retry_sleep):
    handler, calls = scripted([httpx.Response(503, json={})] * 3)
    mock_transport(handler)
    with pytest.raises(LLMUnavailable, match="503"):
        gemini().complete(system="s", messages=MSG)
    assert len(calls) == 1 + llm_mod.MAX_RETRIES
    assert len(no_retry_sleep) == llm_mod.MAX_RETRIES


def test_retry_on_timeout(mock_transport):
    handler, calls = scripted([httpx.ReadTimeout("slow"), httpx.Response(200, json=GEMINI_OK)])
    mock_transport(handler)
    gemini().complete(system="s", messages=MSG)
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_no_retry_on_client_errors(mock_transport, no_retry_sleep, status):
    handler, calls = scripted([httpx.Response(status, json={})] * 3)
    mock_transport(handler)
    with pytest.raises(LLMUnavailable, match=str(status)) as exc:
        gemini().complete(system="s", messages=MSG)
    assert "secret-key" not in str(exc.value)
    assert len(calls) == 1 and no_retry_sleep == []


def test_total_budget_respected(mock_transport, monkeypatch, no_retry_sleep):
    now = [0.0]
    monkeypatch.setattr(llm_mod, "_clock", lambda: now[0])

    def handler(request):
        now[0] += 30.0  # each attempt "takes" 30 s of a 60 s budget
        return httpx.Response(503, json={})

    mock_transport(handler)
    with pytest.raises(LLMUnavailable):
        gemini(timeout_s=60).complete(system="s", messages=MSG)
    # 1st attempt ends at 30 s, 2nd at ~31+30 s: no time left for a 3rd.
    assert len(no_retry_sleep) == 1


# --- fallback chain --------------------------------------------------------------------


def test_fallback_chain_moves_on_unavailable():
    first = FakeLLM([LLMUnavailable("503")])
    second = FakeLLM(["ok"])
    chain = FallbackLLM([first, second])
    assert chain.complete(system="s", messages=MSG).content == "ok"
    assert len(first.calls) == 1 and len(second.calls) == 1


def test_fallback_chain_all_fail_raises_last():
    chain = FallbackLLM([FakeLLM([LLMUnavailable("a")]), FakeLLM([LLMUnavailable("b")])])
    with pytest.raises(LLMUnavailable, match="b"):
        chain.complete(system="s", messages=MSG)


def test_fallback_chain_other_errors_propagate():
    second = FakeLLM(["ok"])
    chain = FallbackLLM([FakeLLM([ValueError("bug")]), second])
    with pytest.raises(ValueError):
        chain.complete(system="s", messages=MSG)
    assert second.calls == []


def test_fallback_status_reports_first_available(mock_transport):
    def handler(request):
        ok = request.url.path.endswith("gemini-3.5-flash-lite")
        return httpx.Response(200 if ok else 404, json={})

    mock_transport(handler)
    chain = FallbackLLM(
        [
            GeminiClient("k", "gemini-3.8-flash", 30),
            GeminiClient("k", "gemini-3.5-flash-lite", 30),
        ]
    )
    assert chain.status() == LLMStatus(True, "gemini-3.5-flash-lite")
    assert provider_name(chain) == "gemini"


def test_fallback_status_none_available():
    chain = FallbackLLM([FakeLLM([], available=False), FakeLLM([], available=False)])
    assert chain.status().available is False


@pytest.fixture
def settings(monkeypatch):
    def install(**values):
        s = Settings.model_construct(**values)
        monkeypatch.setattr("coffer.agent.llm.get_settings", lambda: s)
        return s

    return install


def test_factory_builds_chain_skipping_primary_duplicate(settings):
    settings(
        llm_provider="gemini",
        gemini_api_key="k",
        anthropic_api_key="a",
        llm_fallbacks=[
            "gemini:gemini-3.5-flash-lite",  # = default primary model: skipped
            "gemini:gemini-3.8-flash",
            "anthropic:claude-haiku-5-5",
        ],
    )
    client = get_llm_client()
    assert isinstance(client, FallbackLLM)
    assert [(provider_name(c), c.model) for c in client.clients] == [  # type: ignore[attr-defined]
        ("gemini", "gemini-3.5-flash-lite"),
        ("gemini", "gemini-3.8-flash"),
        ("anthropic", "claude-haiku-5-5"),
    ]


def test_factory_without_fallbacks_is_plain_client(settings):
    settings(llm_provider="gemini", llm_fallbacks=[])
    assert isinstance(get_llm_client(), GeminiClient)


def test_factory_none_ignores_fallbacks(settings):
    settings(llm_provider="none", llm_fallbacks=["gemini:gemini-3.8-flash"])
    assert get_llm_client() is None


def test_settings_parse_fallbacks(monkeypatch):
    monkeypatch.setenv(
        "COFFER_LLM_FALLBACKS", "gemini:gemini-3.5-flash-lite, ollama:qwen3:8b ,anthropic:x"
    )
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_fallbacks == ["gemini:gemini-3.5-flash-lite", "ollama:qwen3:8b", "anthropic:x"]


@pytest.mark.parametrize("value", ["gemini", "foo:bar", "gemini:", "none:x"])
def test_settings_reject_bad_fallbacks(monkeypatch, value):
    monkeypatch.setenv("COFFER_LLM_FALLBACKS", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_status_endpoint_reports_active_fallback(auth_client):
    chain = FallbackLLM([FakeLLM([], available=False), FakeLLM([], available=True)])
    chain.clients[1].provider = "anthropic"  # type: ignore[attr-defined]
    app.dependency_overrides[get_llm_client] = lambda: chain
    try:
        body = auth_client.get("/api/agent/status").json()
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
    assert body == {"provider": "anthropic", "model": "fake", "available": True}


# --- remote Ollama ---------------------------------------------------------------------


def test_ollama_sends_bearer_key(mock_transport):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gpt-oss:120b"}]})
        return httpx.Response(200, json={"message": {"content": "x"}, "model": "gpt-oss:120b"})

    mock_transport(handler)
    client = OllamaClient("https://ollama.com", "gpt-oss:120b", 30, api_key="ollama-secret")
    assert client.status().available is True
    client.complete(system="s", messages=MSG)
    assert [r.headers.get("authorization") for r in seen] == ["Bearer ollama-secret"] * 2
    assert "ollama-secret" not in repr(client)


def test_ollama_local_sends_no_auth(mock_transport):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"message": {"content": "x"}})

    mock_transport(handler)
    OllamaClient("http://localhost:11434", "qwen3:8b", 30).complete(system="s", messages=MSG)
    assert "authorization" not in seen[0].headers


def test_factory_passes_ollama_key(settings):
    settings(llm_provider="ollama", ollama_url="https://ollama.com", ollama_api_key="k")
    client = get_llm_client()
    assert isinstance(client, OllamaClient)
    assert client._headers() == {"Authorization": "Bearer k"}


# --- SSE keep-alive --------------------------------------------------------------------


def test_sse_first_byte_immediate_and_ping_while_waiting(monkeypatch):
    monkeypatch.setattr(sse, "PING_INTERVAL_S", 0.02)
    release = threading.Event()

    def slow_work(on_event):  # a "slow LLM": silent until released
        release.wait(5)
        on_event({"type": "result", "data": {"ok": True}})

    gen = sse.stream_events(slow_work)
    assert next(gen) == sse.PING  # before the worker produced anything
    assert next(gen) == sse.PING  # keep-alive while waiting
    release.set()
    rest = list(gen)
    frames = [f for f in rest if f != sse.PING]
    assert frames == ['event: result\ndata: {"ok": true}\n\n']


def test_sse_endpoint_starts_with_comment(auth_client):
    app.dependency_overrides[get_llm_client] = lambda: None
    try:
        r = auth_client.post("/api/agent/surplus/stream", json={"month": "2025-03"})
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
    assert r.text.startswith(": ping\n\n")
    events = [b for b in r.text.split("\n\n") if b.startswith("event:")]
    assert events[-1].startswith("event: result")
    json.loads(events[-1].split("data: ", 1)[1])


# --- shared deadline (advisor budget) --------------------------------------------------


def test_request_timeout_capped_by_deadline(mock_transport, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(llm_mod, "_clock", lambda: now[0])
    seen: list[dict] = []

    def handler(request):
        seen.append(request.extensions["timeout"])
        return httpx.Response(200, json=GEMINI_OK)

    mock_transport(handler)
    with llm_mod.llm_deadline(60):
        now[0] = 45.0
        gemini(timeout_s=40).complete(system="s", messages=MSG)
    assert seen[0]["read"] == pytest.approx(15.0)


def test_request_after_deadline_raises_timeout(mock_transport, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(llm_mod, "_clock", lambda: now[0])
    handler, calls = scripted([httpx.Response(200, json=GEMINI_OK)])
    mock_transport(handler)
    with llm_mod.llm_deadline(10):
        now[0] = 11.0
        with pytest.raises(llm_mod.LLMTimeout):
            gemini().complete(system="s", messages=MSG)
    assert calls == []


def test_fallback_chain_stops_on_timeout():
    second = FakeLLM(["ok"])
    chain = FallbackLLM([FakeLLM([llm_mod.LLMTimeout("budget")]), second])
    with pytest.raises(llm_mod.LLMTimeout):
        chain.complete(system="s", messages=MSG)
    assert second.calls == []


@pytest.mark.parametrize("value", ["0", "110", "300"])
def test_settings_reject_bad_advisor_timeout(monkeypatch, value):
    monkeypatch.setenv("COFFER_ADVISOR_TIMEOUT_S", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
