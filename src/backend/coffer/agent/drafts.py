from typing import Literal

from pydantic import BaseModel, Field


class RationaleItem(BaseModel):
    claim: str = Field(min_length=1)
    refers_to: Literal["budget", "profile", "portfolio"]
    value: str


class SuggestionDraft(BaseModel):
    summary: str = Field(min_length=1)
    rationale: list[RationaleItem] = Field(min_length=1, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=5)
