from collections import Counter
from datetime import date
from decimal import Decimal

from coffer.imports.parser import ParsedRow
from coffer.transactions.service import normalize_description


def dedup_key(d: date, amount: Decimal, description: str) -> tuple[date, Decimal, str]:
    return (d, amount, normalize_description(description))


def mark_duplicates(
    rows: list[ParsedRow], existing: Counter[tuple[date, Decimal, str]]
) -> set[int]:
    """Mark rows already stored (same date, amount, description ignoring case and spacing).

    Each stored transaction cancels at most one row, so identical rows within one file
    (e.g. two coffees) are all imported unless the same number already exists.
    """
    remaining: Counter[tuple[date, Decimal, str]] = Counter()
    for (d, amount, description), count in existing.items():
        remaining[dedup_key(d, amount, description)] += count  # tolerate raw descriptions
    dups: set[int] = set()
    for row in rows:
        if row.error is not None or row.date is None or row.amount is None:
            continue
        key = dedup_key(row.date, row.amount, row.description)
        if remaining[key] > 0:
            remaining[key] -= 1
            dups.add(row.index)
    return dups
