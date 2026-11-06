import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from coffer.imports.banks import BANKS
from coffer.imports.categorize import categorize
from coffer.imports.dedup import dedup_key, mark_duplicates
from coffer.imports.models import ImportDraft
from coffer.imports.parser import ParsedRow, parse
from coffer.imports.schemas import (
    CommitIn,
    CommitOut,
    ImportCounts,
    ImportPreviewOut,
    ImportRowOut,
)
from coffer.transactions import service as tx_service
from coffer.transactions.models import Transaction

MAX_FILE_BYTES = 1024 * 1024
DRAFT_TTL = timedelta(hours=1)


class UnsupportedBankError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


class EmptyImportError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class UnknownCategoryError(Exception):
    pass


def _existing(db: Session, user_id: int) -> Counter[tuple[date, Decimal, str]]:
    counter: Counter[tuple[date, Decimal, str]] = Counter()
    for d, amount, description in db.execute(
        select(Transaction.date, Transaction.amount, Transaction.description).where(
            Transaction.user_id == user_id
        )
    ):
        counter[dedup_key(d, amount, description)] += 1
    return counter


def _to_parsed(raw: dict[str, Any]) -> ParsedRow:
    return ParsedRow(
        index=raw["index"],
        date=date.fromisoformat(raw["date"]) if raw["date"] else None,
        amount=Decimal(raw["amount"]) if raw["amount"] is not None else None,
        currency=raw["currency"],
        description=raw["description"],
        error=raw["error"],
    )


def _preview(draft: ImportDraft) -> ImportPreviewOut:
    rows = [
        ImportRowOut(
            index=r["index"],
            date=r["date"],
            amount=r["amount"],
            currency=r["currency"],
            description=r["description"],
            category_id=r["category_id"],
            needs_review=r["needs_review"],
            status=r["status"],
            error=r["error"],
        )
        for r in draft.rows
    ]
    counts = Counter(r.status for r in rows)
    return ImportPreviewOut(
        id=draft.id,
        bank=draft.bank,
        filename=draft.filename,
        expires_at=draft.expires_at,
        rows=rows,
        counts=ImportCounts(
            new=counts["new"], duplicate=counts["duplicate"], error=counts["error"]
        ),
    )


def create_preview(
    db: Session, user_id: int, bank_id: str, filename: str, content: bytes
) -> ImportPreviewOut:
    bank = BANKS.get(bank_id)
    if bank is None:
        raise UnsupportedBankError
    if len(content) > MAX_FILE_BYTES:
        raise FileTooLargeError
    parsed = parse(content, bank)
    if not parsed:
        raise EmptyImportError
    dups = mark_duplicates(parsed, _existing(db, user_id))
    categories = {c.name: c.id for c in tx_service.list_categories(db)}
    default_id = next(c.id for c in tx_service.list_categories(db) if c.is_default)
    rows: list[dict[str, Any]] = []
    for p in parsed:
        if p.error is not None:
            status, category_id, review = "error", None, False
        else:
            name = categorize(p.description)
            category_id = categories.get(name) if name else None
            review = category_id is None
            if category_id is None:
                category_id = default_id
            status = "duplicate" if p.index in dups else "new"
        rows.append(
            {
                "index": p.index,
                "date": p.date.isoformat() if p.date else None,
                "amount": str(p.amount) if p.amount is not None else None,
                "currency": p.currency,
                "description": p.description,
                "category_id": category_id,
                "needs_review": review,
                "status": status,
                "error": p.error,
            }
        )
    now = datetime.now(UTC)
    db.execute(
        delete(ImportDraft).where(ImportDraft.user_id == user_id, ImportDraft.expires_at <= now)
    )
    draft = ImportDraft(
        id=str(uuid.uuid4()),
        user_id=user_id,
        bank=bank_id,
        filename=filename.replace("\x00", "")[:255],
        rows=rows,
        created_at=now,
        expires_at=now + DRAFT_TTL,
    )
    db.add(draft)
    db.commit()
    return _preview(draft)


def _get_draft(
    db: Session, user_id: int, draft_id: str, *, for_update: bool = False
) -> ImportDraft:
    try:
        uuid.UUID(draft_id)
    except ValueError:  # e.g. NUL bytes would otherwise crash the query with a 500
        raise DraftNotFoundError from None
    query = select(ImportDraft).where(
        ImportDraft.id == draft_id,
        ImportDraft.user_id == user_id,
        ImportDraft.expires_at > datetime.now(UTC),
    )
    if for_update:
        # A second concurrent commit waits here; when it proceeds the draft is gone -> 404.
        query = query.with_for_update()
    draft = db.scalar(query)
    if draft is None:
        raise DraftNotFoundError
    return draft


def get_preview(db: Session, user_id: int, draft_id: str) -> ImportPreviewOut:
    return _preview(_get_draft(db, user_id, draft_id))


def discard(db: Session, user_id: int, draft_id: str) -> None:
    db.delete(_get_draft(db, user_id, draft_id, for_update=True))
    db.commit()


def commit(db: Session, user_id: int, draft_id: str, data: CommitIn) -> CommitOut:
    draft = _get_draft(db, user_id, draft_id, for_update=True)
    valid_ids = {c.id for c in tx_service.list_categories(db)}
    overrides = {r.index: r for r in data.rows}
    if any(r.category_id is not None and r.category_id not in valid_ids for r in data.rows):
        raise UnknownCategoryError

    parsed = [_to_parsed(r) for r in draft.rows]
    dups = mark_duplicates(parsed, _existing(db, user_id))
    items: list[tx_service.BulkItem] = []
    skipped_duplicates = 0
    skipped_errors = 0
    for raw, p in zip(draft.rows, parsed, strict=True):
        if p.error is not None or p.date is None or p.amount is None:
            skipped_errors += 1
            continue
        override = overrides.get(p.index)
        if p.index in dups:
            if override is None or not override.include:
                skipped_duplicates += 1
                continue
        elif override is not None and not override.include:
            continue
        explicit = override.category_id if override else None
        items.append(
            tx_service.BulkItem(
                date=p.date,
                amount=p.amount,
                description=p.description,
                category_id=explicit if explicit is not None else raw["category_id"],
                needs_review=False if explicit is not None else raw["needs_review"],
            )
        )
    tx_service.bulk_create(db, user_id, items, source="import")
    db.delete(draft)
    db.commit()
    return CommitOut(
        imported=len(items), skipped_duplicates=skipped_duplicates, skipped_errors=skipped_errors
    )
