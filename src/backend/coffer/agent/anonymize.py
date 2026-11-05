"""PII scrubber for free text that may reach a model (planned: AI categorization, F07).

Not on the current surplus path: its tools send only aggregates and category names.
"""

import re

_IBAN = re.compile(r"(?:PL[  ]*)?(?:\d[  ]*){25}\d", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NUMBER = re.compile(r"\d(?:[  ]?\d)*(?:[.,]\d+)?")


def _number(m: re.Match[str]) -> str:
    text = m.group(0)
    if re.search(r"[.,]\d+$", text):
        return text
    if sum(ch.isdigit() for ch in text) >= 6:
        return "[NUMER]"
    return text


def scrub(text: str) -> str:
    text = _IBAN.sub("[RACHUNEK]", text)
    text = _EMAIL.sub("[EMAIL]", text)
    return _NUMBER.sub(_number, text)
