"""Helpers shared by actions: asset classes, profile + target allocation, Polish plurals."""

from dataclasses import dataclass
from typing import Any, Literal, get_args

from coffer.agent.actions.base import ActionContext

AssetClass = Literal["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"]
ASSET_CLASSES: tuple[str, ...] = get_args(AssetClass)
CLASS_PL = {
    "stock": "akcje",
    "etf": "fundusze ETF",
    "bond": "obligacje",
    "real_estate": "nieruchomości",
    "commodity": "surowce",
    "crypto": "kryptowaluty",
    "cash": "gotówka",
}
DEFAULT_RISK = DEFAULT_HORIZON = "medium"


@dataclass(frozen=True)
class ProfileTarget:
    profile: dict[str, Any]  # output of get_investment_profile
    has_profile: bool
    risk: str  # the profile's, or the default when there is none
    horizon: str
    target: dict[str, Any]  # output of target_allocation for risk/horizon

    @property
    def profile_snapshot(self) -> dict[str, Any] | None:
        if not self.has_profile:
            return None
        return {
            "risk": self.risk,
            "horizon": self.horizon,
            "preferred_classes": list(self.profile.get("preferred_classes") or []),
        }


def load_profile_target(ctx: ActionContext) -> ProfileTarget:
    """Profile -> default risk/horizon when missing -> target allocation (3 tool calls)."""
    profile = ctx.call("get_investment_profile", {})
    has_profile = bool(profile.get("available"))
    risk = profile["risk"] if has_profile else DEFAULT_RISK
    horizon = profile["horizon"] if has_profile else DEFAULT_HORIZON
    target = ctx.call("target_allocation", {"risk": risk, "horizon": horizon})
    return ProfileTarget(profile, has_profile, risk, horizon, target)


def plural(n: int, one: str, few: str, many: str) -> str:
    """Polish noun form for a count: 1 propozycja, 2 propozycje, 5 propozycji."""
    if n == 1:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many
