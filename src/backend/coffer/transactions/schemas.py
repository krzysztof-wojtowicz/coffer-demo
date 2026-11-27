import datetime as dt
from decimal import Decimal
from typing import Annotated

from pydantic import AliasPath, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from coffer.core.money import MAX_ABS_AMOUNT, MoneyStr

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


def _validate_amount(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("Nieprawidłowa kwota")
    if value == 0:
        raise ValueError("Kwota nie może być zerem")
    if abs(value) >= MAX_ABS_AMOUNT:
        raise ValueError("Kwota poza zakresem")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError("Maksymalnie 2 miejsca po przecinku")
    return value


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
        return _validate_amount(value)

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        if "\x00" in value:  # PostgreSQL text cannot store NUL; would be a 500
            raise ValueError("Niedozwolony znak w opisie")
        return value


class TransactionUpdate(BaseModel):
    """Partial update; omitted or null fields mean no change."""

    date: dt.date | None = None
    amount: Decimal | None = None
    description: Description | None = None
    category_id: int | None = None

    @field_validator("amount")
    @classmethod
    def _check_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return _validate_amount(value)

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise ValueError("Niedozwolony znak w opisie")
        return value


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: dt.date
    amount: MoneyStr
    description: str
    category_id: int
    category_name: str = Field(validation_alias=AliasPath("category", "name"))
    source: str
