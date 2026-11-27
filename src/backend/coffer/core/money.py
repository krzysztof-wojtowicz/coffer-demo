from decimal import ROUND_HALF_UP, Context, Decimal
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("1000000000000")  # NUMERIC(14,2) limit
MAX_ABS_AMOUNT = Decimal("1000000000")  # signed transaction / balance amounts
# Wide enough that quantizing quantity x price products never overflows the default 28 digits.
_WIDE = Context(prec=60)


def quantize(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP, context=_WIDE)


def money(label: str) -> AfterValidator:
    """Input validator: non-negative amount that fits NUMERIC(14,2), at most 2 decimals.

    The label is part of the Polish error message so a form can tell which field is wrong.
    Use as `Annotated[Decimal, money("Cena")]`.
    """

    def check(value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError(f"Nieprawidłowa wartość: {label}")
        if value < 0:
            raise ValueError(f"{label} nie może być ujemna")
        if value >= MAX_MONEY:
            raise ValueError(f"{label} poza zakresem")
        if value != value.quantize(CENT):
            raise ValueError(f"{label}: maksymalnie 2 miejsca po przecinku")
        return value

    return AfterValidator(check)


# Output: always a two-decimal string in JSON ("10.50"), never a float.
MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: f"{quantize(v)}", return_type=str)]
# Output: percentage as a one-decimal string ("12.5"), rounded ROUND_HALF_UP.
PctStr = Annotated[
    Decimal,
    PlainSerializer(
        lambda v: f"{v.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP, context=_WIDE)}",
        return_type=str,
    ),
]
