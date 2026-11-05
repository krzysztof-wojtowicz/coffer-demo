import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

AssetClass = Literal["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"]
ValueSource = Literal["market", "manual", "cost"]

MAX_MONEY = Decimal("1000000000000")  # NUMERIC(14,2) limit
MAX_QUANTITY = Decimal("1000000000000")  # NUMERIC(20,8) limit

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

REQUIRED_ON_PATCH = ("name", "asset_class", "quantity", "purchase_price", "currency")


def _money(value: Decimal | None, label: str) -> Decimal | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError(f"Nieprawidłowa wartość: {label}")
    if value < 0:
        raise ValueError(f"{label} nie może być ujemna")
    if value >= MAX_MONEY:
        raise ValueError(f"{label} poza zakresem")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError(f"{label}: maksymalnie 2 miejsca po przecinku")
    return value


def _pct(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.1f}"


def _money_str(value: Decimal) -> str:
    return f"{value:.2f}"


def fmt_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


class _HoldingValidators(BaseModel):
    """Validators shared by create and update; fields are declared in subclasses."""

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

    @field_validator("purchase_price", check_fields=False)
    @classmethod
    def _price(cls, v: Decimal | None) -> Decimal | None:
        return _money(v, "Cena zakupu")

    @field_validator("manual_value", check_fields=False)
    @classmethod
    def _manual(cls, v: Decimal | None) -> Decimal | None:
        return _money(v, "Wartość bieżąca")

    @field_validator("purchase_date", check_fields=False)
    @classmethod
    def _date(cls, v: dt.date | None) -> dt.date | None:
        if v is not None and v > dt.date.today():
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
    purchase_price: Decimal
    currency: str = "PLN"
    purchase_date: dt.date | None = None
    manual_value: Decimal | None = None
    note: Note | None = None


class HoldingUpdate(_HoldingValidators):
    """PATCH body: only sent fields change; required columns cannot be set to null."""

    name: Name | None = None
    symbol: str | None = None
    asset_class: AssetClass | None = None
    quantity: Decimal | None = None
    purchase_price: Decimal | None = None
    currency: str | None = None
    purchase_date: dt.date | None = None
    manual_value: Decimal | None = None
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
    quantity: Decimal
    purchase_price: Decimal
    currency: str
    purchase_date: dt.date | None
    manual_value: Decimal | None
    note: str | None
    created_at: dt.datetime

    @field_serializer("quantity")
    def _ser_qty(self, v: Decimal) -> str:
        return fmt_quantity(v)

    @field_serializer("purchase_price")
    def _ser_price(self, v: Decimal) -> str:
        return _money_str(v)

    @field_serializer("manual_value")
    def _ser_manual(self, v: Decimal | None) -> str | None:
        return None if v is None else _money_str(v)


class HoldingValuationOut(BaseModel):
    id: int
    name: str
    symbol: str | None
    asset_class: AssetClass
    quantity: Decimal
    currency: str
    cost_basis: Decimal
    current_value: Decimal
    value_source: ValueSource
    market_price: Decimal | None
    price_currency: str | None
    gain: Decimal
    gain_pct: Decimal | None
    share_pct: Decimal | None
    amount_currency: str
    converted: bool

    @field_serializer("quantity")
    def _ser_qty(self, v: Decimal) -> str:
        return fmt_quantity(v)

    @field_serializer("cost_basis", "current_value", "gain")
    def _ser_money(self, v: Decimal) -> str:
        return _money_str(v)

    @field_serializer("market_price")
    def _ser_price(self, v: Decimal | None) -> str | None:
        return None if v is None else _money_str(v)

    @field_serializer("gain_pct")
    def _ser_gain_pct(self, v: Decimal | None) -> str | None:
        return _pct(v)

    @field_serializer("share_pct")
    def _ser_share(self, v: Decimal | None) -> str | None:
        return _pct(v)


class AllocationOut(BaseModel):
    asset_class: AssetClass
    value: Decimal
    share_pct: Decimal

    @field_serializer("value")
    def _ser_value(self, v: Decimal) -> str:
        return _money_str(v)

    @field_serializer("share_pct")
    def _ser_pct(self, v: Decimal) -> str:
        return f"{v:.1f}"


class PortfolioSummaryOut(BaseModel):
    holdings: list[HoldingValuationOut]
    allocation: list[AllocationOut]
    total_value: Decimal
    total_cost: Decimal
    total_gain: Decimal
    total_gain_pct: Decimal | None
    prices_available: bool
    fx_missing: list[str]

    @field_serializer("total_value", "total_cost", "total_gain")
    def _ser_money(self, v: Decimal) -> str:
        return _money_str(v)

    @field_serializer("total_gain_pct")
    def _ser_pct(self, v: Decimal | None) -> str | None:
        return _pct(v)
