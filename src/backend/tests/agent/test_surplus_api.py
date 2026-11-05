import pytest

from coffer.agent.llm import LLMUnavailable
from coffer.agent.schemas import DISCLAIMER
from coffer.agent.testing import FakeLLM

from .conftest import DESCRIPTION, MONTH
from .test_surplus import GOOD, GOOD_PROFILE, use_llm  # noqa: F401

URL = "/api/agent/surplus"


def test_requires_auth(client, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    assert client.post(URL, json={"month": MONTH}).status_code == 401


def test_success(auth_client, surplus_data, use_llm):  # noqa: F811
    llm = use_llm(FakeLLM([GOOD]))
    r = auth_client.post(URL, json={"month": MONTH})
    assert r.status_code == 200
    body = r.json()
    assert body["ai_status"] == "ok"
    assert body["summary"]["surplus"] == "3765.44"
    assert body["summary"]["income"] == "5000.00"
    s = body["suggestion"]
    assert s["disclaimer"] == DISCLAIMER and s["model"] == "fake"
    assert s["rationale"][0]["refers_to"] == "budget"
    assert s["rationale"][0]["value"] == "3765.44"
    assert s["risks"] and s["profile_used"] is False
    assert isinstance(s["id"], int) and "generated_at" in s
    assert isinstance(body["run_id"], int)
    blob = "".join(m.content for m in llm.calls[0]["messages"])
    assert DESCRIPTION not in blob and "user@example.com" not in blob


def test_no_surplus(auth_client, use_llm):  # noqa: F811
    llm = use_llm(FakeLLM([GOOD]))
    body = auth_client.post(URL, json={"month": MONTH}).json()
    assert body["ai_status"] == "no_surplus"
    assert body["suggestion"] is None
    assert body["summary"]["surplus"] == "0.00"
    assert llm.calls == []


def test_llm_none(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(None)
    r = auth_client.post(URL, json={"month": MONTH})
    assert r.status_code == 200
    assert r.json()["ai_status"] == "unavailable"
    assert r.json()["summary"]["surplus"] == "3765.44"


@pytest.mark.parametrize(
    "responses",
    [
        [LLMUnavailable("x")],
        ["nie json", "nadal nie json"],
        ['{"summary":"a","rationale":[]}', '{"summary":"a","rationale":[]}'],
        [GOOD_PROFILE, GOOD_PROFILE],
    ],
)
def test_llm_failures_never_5xx(auth_client, surplus_data, use_llm, responses):  # noqa: F811
    use_llm(FakeLLM(responses))
    r = auth_client.post(URL, json={"month": MONTH})
    assert r.status_code == 200
    assert r.json()["ai_status"] == "unavailable"
    assert r.json()["suggestion"] is None


@pytest.mark.parametrize("month", ["2025-13", "2025-3", "marzec", "", "2025-00", "9999-12"])
def test_invalid_month_422(auth_client, use_llm, month):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    assert auth_client.post(URL, json={"month": month}).status_code == 422


def test_missing_month_422(auth_client, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    assert auth_client.post(URL, json={}).status_code == 422


def test_user_isolation(other_auth_client, surplus_data, use_llm):  # noqa: F811
    llm = use_llm(FakeLLM([GOOD]))
    body = other_auth_client.post(URL, json={"month": MONTH}).json()
    assert body["ai_status"] == "no_surplus"
    assert body["summary"]["income"] == "0.00"
    assert llm.calls == []
