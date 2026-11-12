import datetime as dt

import coffer.core.clock as clock


def _freeze(monkeypatch, utc: dt.datetime) -> None:
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz)

    monkeypatch.setattr(clock.dt, "datetime", FakeDT)


def test_today_is_next_day_in_warsaw_after_utc_evening(monkeypatch):
    _freeze(monkeypatch, dt.datetime(2026, 6, 10, 23, 30, tzinfo=dt.UTC))
    assert clock.today() == dt.date(2026, 6, 11)


def test_today_winter_offset(monkeypatch):
    _freeze(monkeypatch, dt.datetime(2026, 1, 10, 22, 59, tzinfo=dt.UTC))
    assert clock.today() == dt.date(2026, 1, 10)
    _freeze(monkeypatch, dt.datetime(2026, 1, 10, 23, 0, tzinfo=dt.UTC))
    assert clock.today() == dt.date(2026, 1, 11)
