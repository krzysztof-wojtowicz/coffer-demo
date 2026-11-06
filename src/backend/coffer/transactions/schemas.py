import datetime as dt
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_serializer, field_validator

MAX_ABS_AMOUNT = Decimal("1000000000")

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    in_budget: bool
    is_default: bool


class TransactionCreate(BaseModel):
    date: dt.date
    amount: Decimal
    description: Description
    category_id: int | None = None

    @field_validator("amount")
    @classmethod
    def _check_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Nieprawidłowa kwota")
        if value == 0:
            raise ValueError("Kwota nie może być zerem")
        if abs(value) >= MAX_ABS_AMOUNT:
            raise ValueError("Kwota poza zakresem")
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Maksymalnie 2 miejsca po przecinku")
        return value

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        if "\x00" in value:  # PostgreSQL text cannot store NUL; would be a 500
            raise ValueError("Niedozwolony znak w opisie")
        return value


class TransactionOut(BaseModel):
    id: int
    date: dt.date
    amount: Decimal
    currency: str
    description: str
    category_id: int
    category_name: str
    source: str

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> str:
        return f"{value:.2f}"
