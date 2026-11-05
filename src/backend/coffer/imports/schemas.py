import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer


class BankOut(BaseModel):
    id: str
    name: str


class ImportRowOut(BaseModel):
    index: int
    date: dt.date | None
    amount: Decimal | None
    currency: str | None
    description: str
    category_id: int | None
    needs_review: bool
    status: Literal["new", "duplicate", "error"]
    error: str | None

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.2f}"


class ImportCounts(BaseModel):
    new: int
    duplicate: int
    error: int


class ImportPreviewOut(BaseModel):
    id: str
    bank: str
    filename: str
    expires_at: dt.datetime
    rows: list[ImportRowOut]
    counts: ImportCounts


class CommitRow(BaseModel):
    index: int
    include: bool
    category_id: int | None = None


class CommitIn(BaseModel):
    rows: list[CommitRow] = []


class CommitOut(BaseModel):
    imported: int
    skipped_duplicates: int
    skipped_errors: int
