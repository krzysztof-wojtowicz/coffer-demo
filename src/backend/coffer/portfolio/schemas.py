import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

from coffer.analytics.allocation import AssetClass
from coffer.core import clock
from coffer.core.money import MoneyStr, PctStr, money

ValueSource = Literal["market", "manual", "cost"]

MAX_QUANTITY = Decimal("1000000000000")  # NUMERIC(20,8) limit

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

REQUIRED_ON_PATCH = ("name", "asset_class", "quantity", "purchase_price", "currency")


def fmt_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


PurchasePrice = Annotated[Decimal, money("Cena zakupu")]
CurrentValue = Annotated[Decimal, money("Wartość bieżąca")]

# Output type: quantities without trailing zeros.
QtyStr = Annotated[Decimal, PlainSerializer(fmt_quantity, return_type=str)]


class _HoldingValidators(BaseModel):
    """Validators shared by create and update; fields are declared in subclasses."""

    @field_validator("name", "symbol", "note", mode="before", check_fields=False)
    @classmethod
    def _no_nul(cls, v: object) -> object:
        if isinstance(v, str) and "\x00" in v:  # PostgreSQL text cannot store NUL; would be a 500
            raise ValueError("Niedozwolony znak w tekście")
        return v

    @field_validator("symbol", check_fields=False)
    @classmethod
    def _symbol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("Symbol może mieć maksymalnie 20 znaków")
        return v

    @field_validator("currency", check_fields=False)
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError("Waluta musi być 3-literowym kodem, np. PLN")
        return v

    @field_validator("quantity", check_fields=False)
    @classmethod
    def _quantity(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return None
        if not v.is_finite():
            raise ValueError("Nieprawidłowa ilość")
        if v <= 0:
            raise ValueError("Ilość musi być większa od zera")
        if v >= MAX_QUANTITY:
            raise ValueError("Ilość poza zakresem")
        if v != v.quantize(Decimal("0.00000001")):
            raise ValueError("Ilość: maksymalnie 8 miejsc po przecinku")
        return v

    @field_validator("purchase_date", check_fields=False)
    @classmethod
    def _date(cls, v: dt.date | None) -> dt.date | None:
        if v is not None and v > clock.today():
            raise ValueError("Data zakupu nie może być z przyszłości")
        return v

    @field_validator("note", check_fields=False)
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return v or None


class HoldingCreate(_HoldingValidators):
    name: Name
    symbol: str | None = None
    asset_class: AssetClass
    quantity: Decimal
    purchase_price: PurchasePrice
    currency: str = "PLN"
    purchase_date: dt.date | None = None
    manual_value: CurrentValue | None = None
    note: Note | None = None


class HoldingUpdate(_HoldingValidators):
    """PATCH body: only sent fields change; required columns cannot be set to null."""

    name: Name | None = None
    symbol: str | None = None
    asset_class: AssetClass | None = None
    quantity: Decimal | None = None
    purchase_price: PurchasePrice | None = None
    currency: str | None = None
    purchase_date: dt.date | None = None
    manual_value: CurrentValue | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def _no_null_required(self) -> "HoldingUpdate":
        for field in REQUIRED_ON_PATCH:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Pole {field} nie może być puste")
        return self


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    symbol: str | None
    asset_class: AssetClass
    quantity: QtyStr
    purchase_price: MoneyStr
    currency: str
    purchase_date: dt.date | None
    manual_value: MoneyStr | None
    note: str | None
    created_at: dt.datetime


class HoldingValuationOut(BaseModel):
    id: int
    name: str
    symbol: str | None
    asset_class: AssetClass
    quantity: QtyStr
    currency: str
    cost_basis: MoneyStr
    current_value: MoneyStr
    value_source: ValueSource
    market_price: MoneyStr | None
    price_currency: str | None
    gain: MoneyStr
    gain_pct: PctStr | None
    share_pct: PctStr | None
    amount_currency: str
    converted: bool
    as_of: dt.datetime | None = None


class AllocationOut(BaseModel):
    asset_class: AssetClass
    value: MoneyStr
    share_pct: PctStr


class ClassGapOut(BaseModel):
    asset_class: AssetClass
    current_pct: PctStr
    target_pct: PctStr
    gap_pp: PctStr | None


class TargetOut(BaseModel):
    classes: list[ClassGapOut]
    total_gap_pp: PctStr | None


class PortfolioSummaryOut(BaseModel):
    holdings: list[HoldingValuationOut]
    allocation: list[AllocationOut]
    total_value: MoneyStr
    total_cost: MoneyStr
    total_gain: MoneyStr
    total_gain_pct: PctStr | None
    prices_available: bool
    fx_missing: list[str]
    prices_as_of: dt.datetime | None = None
    target: TargetOut | None = None
