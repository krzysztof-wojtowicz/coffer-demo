"""Target allocation from an investment profile, and the gap from it. Pure functions.

The tables are an illustrative model (not advice), fixed in code so nothing is rounded at
runtime. See openspec/changes/ui-upgrades/design.md D2 for how they were built.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, get_args

from coffer.analytics.portfolio import TENTH, ClassAllocation

# Order is used for output sorting and tie-breaks.
AssetClass = Literal["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"]
ASSET_CLASSES: tuple[str, ...] = get_args(AssetClass)

# (risk, horizon) -> percents by class; every row sums to 100.
_BASE: dict[tuple[str, str], dict[str, int]] = {
    ("low", "short"): {"stock": 1, "etf": 9, "bond": 70, "cash": 20},
    ("low", "medium"): {"stock": 3, "etf": 22, "bond": 60, "cash": 10, "commodity": 5},
    ("low", "long"): {"stock": 4, "etf": 31, "bond": 55, "cash": 5, "commodity": 5},
    ("medium", "short"): {"stock": 6, "etf": 19, "bond": 55, "cash": 20},
    ("medium", "medium"): {"stock": 11, "etf": 34, "bond": 40, "cash": 10, "commodity": 5},
    ("medium", "long"): {
        "stock": 15,
        "etf": 45,
        "bond": 22,
        "cash": 5,
        "crypto": 3,
        "commodity": 5,
        "real_estate": 5,
    },  # fmt: skip
    ("high", "short"): {"stock": 16, "etf": 24, "bond": 40, "cash": 20},
    ("high", "medium"): {
        "stock": 26,
        "etf": 39,
        "bond": 15,
        "cash": 10,
        "crypto": 5,
        "commodity": 5,
    },  # fmt: skip
    ("high", "long"): {
        "stock": 30,
        "etf": 45,
        "bond": 3,
        "cash": 5,
        "crypto": 7,
        "commodity": 5,
        "real_estate": 5,
    },  # fmt: skip
}

# Where the share of an unselected class goes: the first selected class in its chain.
_CHAINS: dict[str, tuple[str, ...]] = {
    "stock": ("etf", "bond", "cash"),
    "etf": ("stock", "bond", "cash"),
    "crypto": ("etf", "stock", "bond", "cash"),
    "real_estate": ("etf", "bond", "cash"),
    "commodity": ("bond", "cash"),
    "bond": ("cash", "etf", "stock"),
    "cash": ("bond", "etf", "stock"),
}


@dataclass(frozen=True)
class TargetShare:
    asset_class: str
    share_pct: int


@dataclass(frozen=True)
class ClassGap:
    asset_class: str
    current_pct: Decimal
    target_pct: Decimal
    gap_pp: Decimal | None  # None when there is no valued portfolio to compare


@dataclass(frozen=True)
class AllocationGap:
    classes: list[ClassGap]
    total_gap_pp: Decimal | None


def target_allocation(horizon: str, risk: str, preferred: Sequence[str]) -> list[TargetShare]:
    selected = set(preferred)
    base = _BASE[(risk, horizon)]
    result = dict.fromkeys(ASSET_CLASSES, 0)
    # Fallback: the selected class with the largest base share, ties by list order.
    fallback = max(
        (c for c in ASSET_CLASSES if c in selected),
        key=lambda c: (base.get(c, 0), -ASSET_CLASSES.index(c)),
        default=None,
    )
    for cls, pct in base.items():
        if cls in selected:
            dest: str | None = cls
        else:
            dest = next((c for c in _CHAINS[cls] if c in selected), fallback)
        if dest is not None:
            result[dest] += pct
    return [TargetShare(c, result[c]) for c in ASSET_CLASSES if result[c] > 0]


def allocation_gap(
    current: Sequence[ClassAllocation], target: Sequence[TargetShare]
) -> AllocationGap:
    """Current minus target per class, in percentage points; total = half the sum of |gap|."""
    cur = {a.asset_class: a.share_pct for a in current}
    tgt = {t.asset_class: Decimal(t.share_pct) for t in target}
    compare = any(a.value > 0 or a.share_pct > 0 for a in current)
    classes = []
    for c in ASSET_CLASSES:
        if c not in cur and c not in tgt:
            continue
        cp = cur.get(c, Decimal(0)).quantize(TENTH)
        tp = tgt.get(c, Decimal(0))
        classes.append(ClassGap(c, cp, tp, (cp - tp).quantize(TENTH) if compare else None))
    total = (
        (sum((abs(g.gap_pp) for g in classes if g.gap_pp is not None), Decimal(0)) / 2).quantize(
            TENTH
        )
        if compare
        else None
    )
    return AllocationGap(classes, total)
