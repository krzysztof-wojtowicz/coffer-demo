import httpx
import pytest

from coffer.agent.llm import LLMStatus, OllamaClient, get_llm_client
from coffer.agent.testing import FakeLLM
from coffer.main import app

URL = "/api/agent/status"


@pytest.fixture
def mock_transport(monkeypatch):
    def install(handler):
        orig = httpx.Client.__init__

        def init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            orig(self, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "__init__", init)

    return install


@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


def _client(model="qwen3:8b"):
    return OllamaClient("http://ollama.test:11434", model, 5.0)


def _tags(*names):
    return httpx.Response(200, json={"models": [{"name": n} for n in names]})


def test_ollama_available(mock_transport):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["timeout"] = request.extensions.get("timeout")
        return _tags("llama3:8b", "qwen3:8b")

    mock_transport(handler)
    st = _client().status()
    assert st == LLMStatus(available=True, model="qwen3:8b")
    assert seen["method"] == "GET"
    assert seen["url"] == "http://ollama.test:11434/api/tags"
    if seen["timeout"]:
        assert max(v for v in seen["timeout"].values() if v is not None) <= 2.0


def test_ollama_latest_suffix(mock_transport):
    mock_transport(lambda r: _tags("qwen3:latest"))
    assert _client("qwen3").status().available is True


def test_ollama_model_missing(mock_transport):
    mock_transport(lambda r: _tags("llama3:8b"))
    st = _client().status()
    assert st.available is False
    assert st.model == "qwen3:8b"


def test_ollama_empty_list(mock_transport):
    mock_transport(lambda r: _tags())
    assert _client().status().available is False


def test_ollama_non_200(mock_transport):
    mock_transport(lambda r: httpx.Response(500, text="boom"))
    assert _client().status().available is False


def test_ollama_connection_error(mock_transport):
    def handler(request):
        raise httpx.ConnectError("refused")

    mock_transport(handler)
    assert _client().status().available is False


def test_ollama_timeout(mock_transport):
    def handler(request):
        raise httpx.ReadTimeout("slow")

    mock_transport(handler)
    assert _client().status().available is False


def test_ollama_garbage_body(mock_transport):
    mock_transport(lambda r: httpx.Response(200, text="not json"))
    assert _client().status().available is False


def test_fake_llm_status():
    assert FakeLLM([]).status() == LLMStatus(True, "fake")
    assert FakeLLM([], available=False).status() == LLMStatus(False, "fake")


def test_endpoint_requires_auth(client, use_llm):
    use_llm(FakeLLM([]))
    assert client.get(URL).status_code == 401


def test_endpoint_available(auth_client, use_llm):
    use_llm(FakeLLM([]))
    r = auth_client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"provider": "ollama", "model": "fake", "available": True}


def test_endpoint_model_unavailable(auth_client, use_llm):
    use_llm(FakeLLM([], available=False))
    r = auth_client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"provider": "ollama", "model": "fake", "available": False}


def test_endpoint_provider_none(auth_client, use_llm):
    use_llm(None)
    r = auth_client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"provider": "none", "model": None, "available": False}
