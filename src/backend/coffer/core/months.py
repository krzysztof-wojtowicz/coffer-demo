import re
from datetime import date
from typing import Annotated

from pydantic import StringConstraints

MonthStr = Annotated[str, StringConstraints(pattern=r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")]

_MONTH_RE = re.compile(r"^((?:19|20)\d{2})-(0[1-9]|1[0-2])$")


def parse_month(value: str) -> tuple[date, date]:
    match = _MONTH_RE.match(value)
    if match is None:
        raise ValueError(f"Invalid month: {value!r}")
    year, month = int(match.group(1)), int(match.group(2))
    if year < 1:
        raise ValueError(f"Invalid month: {value!r}")
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end
