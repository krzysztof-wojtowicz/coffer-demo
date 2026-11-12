"""Business clock: "today" in the configured timezone (not the server's UTC)."""

import datetime as dt
from zoneinfo import ZoneInfo

from coffer.core.config import get_settings


def today() -> dt.date:
    return dt.datetime.now(ZoneInfo(get_settings().timezone)).date()
