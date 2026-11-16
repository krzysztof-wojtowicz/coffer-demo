"""Validation of model answers against what the tools actually returned (D3).

Numbers in the narrative must occur in the data the model saw, and URLs and symbols must come
from tool results; otherwise the answer is rejected and retried (then the rule-based fallback).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from coffer.agent.schemas import ReportDraft

_NUM = re.compile(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
_URL_KEYS = ("url", "source_url", "link")
_TITLE_KEYS = ("title", "name")


def extract_numbers(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for m in _NUM.finditer(text):
        raw = re.sub(r"[  ]", "", m.group(0)).replace(",", ".")
        out.append(Decimal(raw))
    return out


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, bool) or value is None:
        return
    else:
        yield str(value)


@dataclass
class Seen:
    """Everything the model was shown: numbers, URLs (with titles) and symbols."""

    urls: set[str] = field(default_factory=set)
    titles: dict[str, str] = field(default_factory=dict)
    symbols: set[str] = field(default_factory=set)
    numbers: list[Decimal] = field(default_factory=list)

    def add(self, data: Any) -> None:
        """Collect from a tool output or context (any JSON-like value)."""
        for s in _strings(data):
            self.numbers.extend(extract_numbers(s))
        self._walk(data)

    def _walk(self, node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _URL_KEYS and isinstance(value, str):
                    self.urls.add(value)
                    title = next(
                        (node[t] for t in _TITLE_KEYS if isinstance(node.get(t), str)), None
                    )
                    if title:
                        self.titles.setdefault(value, title)
                elif key == "symbol" and isinstance(value, str):
                    self.symbols.add(value.upper())
                elif key == "symbols" and isinstance(value, list):
                    self.symbols.update(v.upper() for v in value if isinstance(v, str))
                else:
                    self._walk(value)
        elif isinstance(node, list):
            for v in node:
                self._walk(v)


def _exponent(n: Decimal) -> int:
    exp = n.as_tuple().exponent
    return exp if isinstance(exp, int) else 0  # 'n'/'N'/'F' = NaN/Infinity


# Models round and rescale freely ("5177380175872.0 USD" -> "5.18 bln USD", "0.125" -> "12.5%").
_SCALES = tuple(Decimal(10) ** e for e in (0, 2, -2, 3, 6, 9, 12))
_REL_TOL = Decimal("0.02")  # 2% covers rounding to 2-3 significant digits
_NARRATIVE_UNKNOWN_MAX = 0  # raise to tolerate derived numbers (sums, differences) in prose


def _close(n: Decimal, a: Decimal) -> bool:
    if a == 0:
        return n == 0
    return abs(n - a) <= abs(a) * _REL_TOL


def _is_ok(n: Decimal, allowed: list[Decimal]) -> bool:
    if not n.is_finite():
        return False
    for a in allowed:
        if not a.is_finite():
            continue
        # Rescaling ("5.18 bln", "12.5%") applies only to short numbers; long ones must match as-is.
        for scale in _SCALES if abs(n) < 10000 else _SCALES[:1]:
            if _close(n * scale, a) or _close(n * scale, -a):
                return True
    return False


def _is_amount(n: Decimal) -> bool:
    """Small whole numbers ("3 pozycje", "5/5") and years are narration, not data."""
    if _exponent(n) >= 0 and (n < 100 or 1900 <= n <= 2100):
        return False
    return True


def _check_numbers(text: str, where: str, seen: Seen, errors: list[str], strict: bool) -> None:
    for n in extract_numbers(text):
        if (strict or _is_amount(n)) and not _is_ok(n, seen.numbers):
            errors.append(f"Liczba {n} w polu {where} nie występuje w danych.")


def _narrative(text: str, where: str, seen: Seen, unknown: list[str]) -> None:
    _check_numbers(text, where, seen, unknown, strict=False)


def validate_draft(draft: ReportDraft, seen: Seen) -> list[str]:
    """Generic checks of a model draft; action-specific ones live in `Action.check`."""
    errors: list[str] = []
    unknown: list[str] = []
    if not draft.headline.strip():
        errors.append("Pole headline jest puste.")
    _narrative(draft.headline, "headline", seen, unknown)

    for i, f in enumerate(draft.findings, 1):
        if not f.title.strip():
            errors.append(f"Wniosek {i}: pole title jest puste.")
        _narrative(f.title, f"findings[{i}].title", seen, unknown)
        _narrative(f.detail, f"findings[{i}].detail", seen, unknown)
        if f.value:
            _check_numbers(f.value, f"findings[{i}].value", seen, errors, strict=True)

    for i, r in enumerate(draft.recommendations, 1):
        _narrative(r.title, f"recommendations[{i}].title", seen, unknown)
        _narrative(r.detail, f"recommendations[{i}].detail", seen, unknown)
        if r.amount:
            _check_numbers(r.amount, f"recommendations[{i}].amount", seen, errors, strict=True)
        if r.symbol and r.symbol.strip().upper() not in seen.symbols:
            errors.append(f"Rekomendacja {i}: symbol {r.symbol} nie pochodzi z wyników narzędzi.")
        if r.source_url and r.source_url not in seen.urls:
            errors.append(f"Rekomendacja {i}: adres URL nie pochodzi z wyników narzędzi.")

    for i, risk in enumerate(draft.risks, 1):
        _narrative(risk, f"risks[{i}]", seen, unknown)

    for url in draft.source_urls:
        if url not in seen.urls:
            errors.append(f"Adres URL {url} w polu source_urls nie pochodzi z wyników narzędzi.")
    if len(unknown) > _NARRATIVE_UNKNOWN_MAX:
        errors.extend(unknown)
    return errors
