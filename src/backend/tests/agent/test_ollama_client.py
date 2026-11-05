import json

import httpx
import pytest

from coffer.agent.llm import LLMMessage, LLMUnavailable, OllamaClient

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}}


@pytest.fixture
def mock_transport(monkeypatch):
    """Wstrzykuje MockTransport do każdego httpx.Client (także tworzonego przez httpx.post)."""

    def install(handler):
        orig = httpx.Client.__init__

        def init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            orig(self, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "__init__", init)

    return install


def _client():
    return OllamaClient("http://ollama.test:11434", "qwen3:8b", 5.0)


def test_request_and_response(mock_transport):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": '{"a": "b"}'},
                "prompt_eval_count": 12,
                "eval_count": 7,
            },
        )

    mock_transport(handler)
    resp = _client().complete(
        system="SYS", messages=[LLMMessage("user", "hej")], response_schema=SCHEMA
    )
    assert seen["method"] == "POST"
    assert seen["url"] == "http://ollama.test:11434/api/chat"
    body = seen["body"]
    assert body["model"] == "qwen3:8b"
    assert body["stream"] is False
    assert body["think"] is False
    assert body["format"] == SCHEMA
    assert body["options"]["temperature"] == 0.2
    assert body["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hej"},
    ]
    assert resp.content == '{"a": "b"}'
    assert resp.input_tokens == 12
    assert resp.output_tokens == 7
    assert resp.model


def test_missing_token_counts(mock_transport):
    mock_transport(
        lambda r: httpx.Response(200, json={"message": {"role": "assistant", "content": "x"}})
    )
    resp = _client().complete(system="s", messages=[LLMMessage("user", "u")])
    assert resp.content == "x"
    assert resp.input_tokens is None and resp.output_tokens is None


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_bad_status(mock_transport, status):
    mock_transport(lambda r: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(LLMUnavailable):
        _client().complete(system="s", messages=[LLMMessage("user", "u")])


@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
def test_connection_errors(mock_transport, exc):
    def handler(request):
        raise exc

    mock_transport(handler)
    with pytest.raises(LLMUnavailable):
        _client().complete(system="s", messages=[LLMMessage("user", "u")])
