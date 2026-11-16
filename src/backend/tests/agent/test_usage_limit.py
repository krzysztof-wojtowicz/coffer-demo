import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.agent import service
from coffer.agent.models import LlmUsageDaily


def test_parallel_reservations_one_slot(test_engine, user):
    now = datetime.now(UTC)
    barrier = threading.Barrier(8)
    results: list[bool] = []

    def worker() -> None:
        with Session(test_engine) as session:
            barrier.wait()
            results.append(service.reserve_run(session, user.id, now, 1))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False] * 7 + [True]


def test_parallel_reservations_limit_three(test_engine, user):
    now = datetime.now(UTC)
    barrier = threading.Barrier(6)
    results: list[bool] = []

    def worker() -> None:
        with Session(test_engine) as session:
            barrier.wait()
            results.append(service.reserve_run(session, user.id, now, 3))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 3


def test_counter_does_not_grow_past_limit(db, user):
    now = datetime.now(UTC)
    for _ in range(5):
        service.reserve_run(db, user.id, now, 2)
    assert db.scalars(select(LlmUsageDaily.runs)).one() == 2


def test_new_utc_day_resets(db, user):
    now = datetime(2025, 3, 1, 23, 59, tzinfo=UTC)
    assert service.reserve_run(db, user.id, now, 1) is True
    assert service.reserve_run(db, user.id, now, 1) is False
    assert service.reserve_run(db, user.id, now + timedelta(minutes=2), 1) is True


def test_limits_are_per_user(db, user, make_user):
    other = make_user(email="inny@example.com")
    now = datetime.now(UTC)
    assert service.reserve_run(db, user.id, now, 1) is True
    assert service.reserve_run(db, other.id, now, 1) is True


def test_record_usage_adds_tokens(db, user):
    now = datetime.now(UTC)
    service.reserve_run(db, user.id, now, 5)
    service.record_usage(db, user.id, now.date(), 10, 4)
    service.record_usage(db, user.id, now.date(), 5, 1)
    db.commit()
    row = db.scalars(select(LlmUsageDaily)).one()
    assert (row.input_tokens, row.output_tokens) == (15, 5)
