import time

from coffer.agent.llm import LLMUnavailable
from coffer.agent.testing import FakeLLM

from .conftest import MONTH
from .test_surplus import GOOD, use_llm  # noqa: F401

URL = "/api/agent/surplus"


def test_duration_ms_in_suggestion(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    body = auth_client.post(URL, json={"month": MONTH}).json()
    assert body["ai_status"] == "ok"
    d = body["suggestion"]["duration_ms"]
    assert isinstance(d, int) and not isinstance(d, bool) and d >= 0


def test_duration_reflects_llm_time(auth_client, surplus_data, use_llm, monkeypatch):  # noqa: F811
    llm = use_llm(FakeLLM([GOOD]))
    orig = llm.complete

    def slow(**kw):
        time.sleep(0.15)
        return orig(**kw)

    monkeypatch.setattr(llm, "complete", slow)
    body = auth_client.post(URL, json={"month": MONTH}).json()
    assert body["suggestion"]["duration_ms"] >= 100
    run = auth_client.get(f"/api/agent/runs/{body['run_id']}").json()
    assert run["duration_ms"] >= 100


def test_no_suggestion_when_unavailable(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([LLMUnavailable("x")]))
    body = auth_client.post(URL, json={"month": MONTH}).json()
    assert body["ai_status"] == "unavailable"
    assert body["suggestion"] is None
