import datetime as dt
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator

from coffer.core.clock import today

MAX_ABS_AMOUNT = Decimal("1000000000")


class OpeningBalanceIn(BaseModel):
    amount: Decimal
    as_of: dt.date

    @field_validator("amount", mode="before")
    @classmethod
    def _no_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("Nieprawidłowa kwota")
        return value

    @field_validator("amount")
    @classmethod
    def _amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Nieprawidłowa kwota")
        if abs(value) >= MAX_ABS_AMOUNT:
            raise ValueError("Kwota poza zakresem")
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Maksymalnie 2 miejsca po przecinku")
        return value

    @model_validator(mode="after")
    def _date(self) -> "OpeningBalanceIn":
        if self.as_of > today():
            raise ValueError("Data salda nie może być z przyszłości")
        return self


class OpeningBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount: Decimal
    as_of: dt.date

    @field_serializer("amount")
    def _ser(self, value: Decimal) -> str:
        return f"{value:.2f}"
