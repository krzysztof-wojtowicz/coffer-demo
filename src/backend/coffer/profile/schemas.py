import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Horizon = Literal["short", "medium", "long"]
Risk = Literal["low", "medium", "high"]
AssetClass = Literal["cash", "deposit", "stocks", "etf", "bonds", "crypto", "real_estate"]


class ProfileIn(BaseModel):
    horizon: Horizon
    risk: Risk
    preferred_classes: list[AssetClass] = Field(min_length=1)

    @field_validator("preferred_classes")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("Klasy aktywów nie mogą się powtarzać")
        return v


class ProfileOut(BaseModel):
    horizon: Horizon
    risk: Risk
    preferred_classes: list[AssetClass]
    updated_at: dt.datetime

    model_config = {"from_attributes": True}
