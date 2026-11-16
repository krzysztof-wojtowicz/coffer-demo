from datetime import UTC, datetime

import pytest

from coffer.agent.actions.base import ActionContext
from coffer.agent.actions.common import ASSET_CLASSES, load_profile_target, plural
from coffer.agent.tools.registry import ToolContext, default_registry


@pytest.mark.parametrize(
    ("n", "word"),
    [
        (0, "m"),
        (1, "o"),
        (2, "f"),
        (4, "f"),
        (5, "m"),
        (12, "m"),
        (14, "m"),
        (22, "f"),
        (25, "m"),
        (101, "m"),
        (112, "m"),
    ],
)
def test_plural(n, word):
    assert plural(n, "o", "f", "m") == word


def _ctx(db, user_id):
    tool_ctx = ToolContext(db=db, user_id=user_id, now=datetime.now(UTC))
    registry = default_registry()

    def call(name, args):
        return registry.call(name, args, tool_ctx).output

    return ActionContext(db, user_id, tool_ctx.now, call)


def test_profile_target_default_and_user(db, user, profile):
    pt = load_profile_target(_ctx(db, user.id))
    assert pt.has_profile and (pt.risk, pt.horizon) == ("high", "long")
    assert pt.profile_snapshot["risk"] == "high"
    assert sum(float(c["target_pct"]) for c in pt.target["classes"]) == pytest.approx(100)


def test_profile_target_without_profile(db, user):
    pt = load_profile_target(_ctx(db, user.id))
    assert not pt.has_profile and (pt.risk, pt.horizon) == ("medium", "medium")
    assert pt.profile_snapshot is None


def test_try_call_returns_none_on_tool_error(db, user):
    ctx = _ctx(db, user.id)
    from coffer.agent.actions.base import ToolCallFailed

    def failing(name, args):
        raise ToolCallFailed("x")

    bad = ActionContext(db, user.id, ctx.now, failing)
    assert bad.try_call("anything", {}) is None
    assert ctx.try_call("get_investment_profile", {}) is not None
    assert "etf" in ASSET_CLASSES
