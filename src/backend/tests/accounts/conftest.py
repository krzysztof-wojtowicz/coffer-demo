from collections.abc import Iterator

import pytest

from coffer.accounts.ratelimit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()
