from decimal import Decimal

import pytest

from coffer.agent.pricing import estimate_cost


def test_ollama_is_free():
    assert estimate_cost("ollama", "llama3.1", None, None) == Decimal(0)
    assert estimate_cost("ollama", "llama3.1", 1000, 1000) == Decimal(0)


def test_known_model_prefix():
    assert estimate_cost("openai", "gpt-4o-mini-2024-07-18", 1_000_000, 1_000_000) == Decimal(
        "0.750000"
    )


def test_longest_prefix_wins():
    mini = estimate_cost("openai", "gpt-4o-mini", 1_000_000, 0)
    full = estimate_cost("openai", "gpt-4o", 1_000_000, 0)
    assert mini == Decimal("0.150000") and full == Decimal("2.500000")


def test_rounding_half_up_to_micro_dollars():
    # 5 tokens * 0.15 / 1e6 = 0.00000075 -> 0.000001
    assert estimate_cost("openai", "gpt-4o-mini", 5, 0) == Decimal("0.000001")


@pytest.mark.parametrize(
    ("provider", "model", "tin", "tout"),
    [
        ("openai", "unknown-model", 10, 10),
        ("openai", "gpt-4o-mini", None, 10),
        ("openai", "gpt-4o-mini", 10, None),
        (None, "gpt-4o-mini", 10, 10),
        ("gemini", None, 10, 10),
        ("mystery", "gpt-4o-mini", 10, 10),
    ],
)
def test_unknown_is_none(provider, model, tin, tout):
    assert estimate_cost(provider, model, tin, tout) is None
