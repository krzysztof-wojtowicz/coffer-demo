"""Estimated LLM cost in USD per call (the UI labels it as an estimate)."""

from decimal import ROUND_HALF_UP, Decimal

# USD per 1M tokens (input, output) by model-name prefix; the longest matching prefix wins.
# Approximate, as of 2026-11-16: list prices change, unknown models give None (not 0).
_PRICES: dict[str, dict[str, tuple[str, str]]] = {
    "openai": {
        "gpt-4o-mini": ("0.15", "0.60"),
        "gpt-4o": ("2.50", "10.00"),
        "gpt-4.1-mini": ("0.40", "1.60"),
        "gpt-4.1": ("2.00", "8.00"),
        "gpt-5-mini": ("0.25", "2.00"),
        "gpt-5": ("1.25", "10.00"),
    },
    "gemini": {
        "gemini-3.8-flash": ("0.30", "2.50"),
        "gemini-2.5-flash": ("0.30", "2.50"),
        "gemini-2.5-pro": ("1.25", "10.00"),
    },
    "anthropic": {
        "claude-haiku": ("1.00", "5.00"),
        "claude-sonnet": ("3.00", "15.00"),
        "claude-opus": ("5.00", "25.00"),
    },
}
_PER = Decimal(1_000_000)
_MICRO = Decimal("0.000001")


def estimate_cost(
    provider: str | None, model: str | None, input_tokens: int | None, output_tokens: int | None
) -> Decimal | None:
    """Estimated cost in USD (6 places), 0 for Ollama, None when it cannot be estimated.

    Estimate only, based on list prices as of 2026-11-16 (see `_PRICES`).
    """
    if provider == "ollama":
        return Decimal(0)
    if provider is None or model is None or input_tokens is None or output_tokens is None:
        return None
    table = _PRICES.get(provider, {})
    prefixes = sorted((p for p in table if model.startswith(p)), key=len, reverse=True)
    if not prefixes:
        return None
    price_in, price_out = table[prefixes[0]]
    cost = (
        Decimal(input_tokens) * Decimal(price_in) + Decimal(output_tokens) * Decimal(price_out)
    ) / _PER
    return cost.quantize(_MICRO, rounding=ROUND_HALF_UP)
