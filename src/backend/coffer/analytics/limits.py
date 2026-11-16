from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from coffer.analytics.month import CategoryTotal
from coffer.core.money import ZERO, quantize

_PCT = Decimal("0.1")


@dataclass(frozen=True)
class LimitStatus:
    category_id: int
    category_name: str
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    used_pct: Decimal
    exceeded: bool


def limit_status(
    by_category: Sequence[CategoryTotal], limits: Mapping[int, tuple[str, Decimal]]
) -> list[LimitStatus]:
    spent_by_id = {c.category_id: c.expenses for c in by_category}
    result: list[LimitStatus] = []
    for cid, (name, limit) in limits.items():
        limit = quantize(limit)
        spent = quantize(spent_by_id.get(cid, ZERO))
        used = (
            (spent / limit * 100).quantize(_PCT, rounding=ROUND_HALF_UP)
            if limit > 0
            else Decimal("0.0")
        )
        result.append(
            LimitStatus(cid, name, limit, spent, quantize(limit - spent), used, spent > limit)
        )
    return sorted(result, key=lambda s: s.category_name)
