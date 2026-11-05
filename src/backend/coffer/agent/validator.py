import re
from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from coffer.agent.drafts import SuggestionDraft
from coffer.agent.tools.registry import ToolCall

_NUM = re.compile(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for m in _NUM.finditer(text):
        raw = re.sub(r"[  ]", "", m.group(0)).replace(",", ".")
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


def _allowed(tool_calls: list[ToolCall]) -> list[Decimal]:
    nums: list[Decimal] = []
    for call in tool_calls:
        for s in _strings(call.output):
            nums.extend(extract_numbers(s))
    return nums


def _exponent(n: Decimal) -> int:
    exp = n.as_tuple().exponent
    return exp if isinstance(exp, int) else 0  # 'n'/'N'/'F' = NaN/Infinity


def _is_ok(n: Decimal, allowed: list[Decimal]) -> bool:
    if n in allowed:
        return True
    if n == n.to_integral_value() and _exponent(n) >= 0:
        for a in allowed:
            if n == a.quantize(Decimal(1), rounding=ROUND_HALF_UP) or n == int(a):
                return True
    return False


def _is_amount(n: Decimal) -> bool:
    return _exponent(n) < 0 or n >= 100


def validate(draft: SuggestionDraft, tool_calls: list[ToolCall]) -> list[str]:
    errors: list[str] = []
    if not draft.summary.strip():
        errors.append("Pole summary jest puste.")
    profile_ok = any(
        c.name == "get_investment_profile" and c.output.get("available") is True for c in tool_calls
    )
    portfolio_ok = any(c.name.startswith("get_portfolio") for c in tool_calls)
    allowed = _allowed(tool_calls)

    for n in extract_numbers(draft.summary):
        if _is_amount(n) and not _is_ok(n, allowed):
            errors.append(f"Liczba {n} w polu summary nie występuje w danych.")

    for i, risk in enumerate(draft.risks, 1):
        for n in extract_numbers(risk):
            if _is_amount(n) and not _is_ok(n, allowed):
                errors.append(f"Ryzyko {i}: liczba {n} nie występuje w danych.")

    for i, item in enumerate(draft.rationale, 1):
        if not item.claim.strip():
            errors.append(f"Uzasadnienie {i}: pole claim jest puste.")
        if item.refers_to == "profile" and not profile_ok:
            errors.append(f"Uzasadnienie {i}: odwołanie do profilu, ale profil jest niedostępny.")
        if item.refers_to == "portfolio" and not portfolio_ok:
            errors.append(f"Uzasadnienie {i}: odwołanie do portfela, ale brak danych portfela.")
        for n in extract_numbers(item.claim):
            if _is_amount(n) and not _is_ok(n, allowed):
                errors.append(f"Liczba {n} w polu claim nie występuje w danych.")
        for n in extract_numbers(item.value):
            if not _is_ok(n, allowed):
                errors.append(f"Liczba {n} w polu value nie występuje w danych.")
    return errors
