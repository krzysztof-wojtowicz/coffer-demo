from decimal import Decimal

from pydantic import BaseModel, Field

DISCLAIMER = (
    "To nie jest porada inwestycyjna, tylko informacja edukacyjna. Inwestowanie wiąże się "
    "z ryzykiem utraty kapitału; decyzję podejmujesz samodzielnie."
)


class HoldingIn(BaseModel):
    symbol: str | None = Field(default=None, max_length=20)
    asset_class: str = Field(max_length=30)
    quantity: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    current_value: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=2)


class AdviceRequest(BaseModel):
    holdings: list[HoldingIn] = Field(default_factory=list, max_length=200)


class TopPickOut(BaseModel):
    name: str
    asset_class: str
    symbol: str | None
    rationale: str
    risk_level: int
    source_url: str | None


class TipOut(BaseModel):
    title: str
    summary: str
    source: str
    url: str | None


class AdviceOut(BaseModel):
    top_picks: list[TopPickOut]
    tips: list[TipOut]
    llm_used: bool
    disclaimer: str = DISCLAIMER
