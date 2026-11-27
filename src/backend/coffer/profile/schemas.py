import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from coffer.analytics.allocation import AssetClass

Horizon = Literal["short", "medium", "long"]
Risk = Literal["low", "medium", "high"]


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


class TargetShareOut(BaseModel):
    asset_class: AssetClass
    share_pct: int


class ProfileOut(BaseModel):
    horizon: Horizon
    risk: Risk
    preferred_classes: list[AssetClass]
    updated_at: dt.datetime
    target: list[TargetShareOut]
