import json

from coffer.agent.llm import LLMUnavailable
from coffer.agent.testing import FakeLLM

from .conftest import MONTH
from .test_surplus import BAD_NUMBER, GOOD, use_llm  # noqa: F401

URL = "/api/agent/surplus/stream"


def parse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if name:
            events.append((name, data))
    return events


def post(client, month=MONTH):
    return client.post(URL, json={"month": month})


def test_requires_auth(client, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    assert post(client).status_code == 401


def test_headers(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    r = post(auth_client)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"


def test_event_order_success(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    events = parse(post(auth_client).text)
    names = [n for n, _ in events]
    assert names[0] == "status"
    assert names.index("summary") > names.index("status")
    assert names[-1] == "result" and names.count("result") == 1
    assert names.count("summary") == 1
    assert all(n in {"status", "summary", "result"} for n in names)
    summary = dict(events)["summary"]
    assert summary["surplus"] == "3765.44"
    result = events[-1][1]
    assert result["ai_status"] == "ok"
    assert result["suggestion"]["rationale"][0]["value"] == "3765.44"
    assert result["run_id"] is not None


def test_status_messages(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    msgs = [d["message"] for n, d in parse(post(auth_client).text) if n == "status"]
    assert any("Liczę podsumowanie" in m for m in msgs)
    assert any("profil" in m for m in msgs)
    assert any("analizuje" in m for m in msgs)


def test_retry_status(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([BAD_NUMBER, GOOD]))
    events = parse(post(auth_client).text)
    assert any("Poprawiam" in d["message"] for n, d in events if n == "status")
    assert events[-1][1]["ai_status"] == "ok"


def test_no_surplus_ends_with_result(auth_client, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    events = parse(post(auth_client).text)
    assert [n for n, _ in events][-1] == "result"
    assert events[-1][1]["ai_status"] == "no_surplus"


def test_llm_failure_still_result(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([LLMUnavailable("x")]))
    r = post(auth_client)
    assert r.status_code == 200
    events = parse(r.text)
    assert events[-1][0] == "result" and events[-1][1]["ai_status"] == "unavailable"


def test_llm_none(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(None)
    events = parse(post(auth_client).text)
    assert events[-1][1]["ai_status"] == "unavailable"


def test_stream_persists_run_and_suggestion(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    result = parse(post(auth_client).text)[-1][1]
    runs = auth_client.get("/api/agent/runs").json()
    assert [r["id"] for r in runs] == [result["run_id"]]
    sid = result["suggestion"]["id"]
    assert auth_client.get(f"/api/agent/suggestions/{sid}").status_code == 200


def test_invalid_month_422(auth_client, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    assert post(auth_client, "2025-13").status_code == 422
