from collections import Counter
from datetime import date
from decimal import Decimal

from coffer.imports.parser import ParsedRow


def dedup_key(d: date, amount: Decimal, description: str) -> tuple[date, Decimal, str]:
    return (d, amount, " ".join(description.split()))


def mark_duplicates(
    rows: list[ParsedRow], existing: Counter[tuple[date, Decimal, str]]
) -> set[int]:
    remaining = Counter(existing)
    dups: set[int] = set()
    for row in rows:
        if row.error is not None or row.date is None or row.amount is None:
            continue
        key = dedup_key(row.date, row.amount, row.description)
        if remaining[key] > 0:
            remaining[key] -= 1
            dups.add(row.index)
    return dups
