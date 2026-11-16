import socket

import pytest

from coffer.agent.testing import FakeLLM
from tests.e5.conftest import ACTION_CASES, final_answer, run_action_api


def test_blocker_works(network_attempts):
    s = socket.socket()
    with pytest.raises(OSError):
        s.connect(("93.184.216.34", 80))
    s.close()
    assert network_attempts


@pytest.mark.parametrize("with_llm", [True, False])
def test_all_actions_stay_offline(anna_client, use_llm, network_attempts, with_llm):
    network_attempts.clear()
    for action, params in ACTION_CASES:
        use_llm(FakeLLM([final_answer(action)] * 3) if with_llm else None)
        assert run_action_api(anna_client, action, params).status_code == 200
    assert network_attempts == []
