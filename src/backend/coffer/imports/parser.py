import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from coffer.imports.banks import BankConfig

# Same bound as manual transactions; the column is NUMERIC(14,2).
MAX_ABS_AMOUNT = Decimal("1000000000")

_SPACES = (" ", " ", " ")


class ImportFormatError(Exception):
    pass


class ImportEncodingError(Exception):
    pass


@dataclass
class ParsedRow:
    index: int
    date: date | None
    amount: Decimal | None
    currency: str | None
    description: str
    error: str | None = None


def _parse_amount(raw: str, bank: BankConfig) -> Decimal:
    text = raw.strip()
    for sp in _SPACES:
        text = text.replace(sp, "")
    if bank.thousands_separator.strip():
        text = text.replace(bank.thousands_separator, "")
    text = text.replace(bank.decimal_separator, ".")
    value = Decimal(text)
    if not value.is_finite():
        raise InvalidOperation
    return value


def parse(content: bytes, bank: BankConfig) -> list[ParsedRow]:
    try:
        text = content.decode(bank.encoding)
    except UnicodeDecodeError:
        raise ImportEncodingError("Nie udało się odczytać pliku (kodowanie)") from None
    # NUL cannot be stored in PostgreSQL text/JSONB; drop it instead of failing with a 500.
    text = text.removeprefix("﻿").replace("\x00", "")
    records = [r for r in csv.reader(io.StringIO(text), delimiter=bank.delimiter) if any(r)]
    if len(records) < bank.skip_rows or not records:
        raise ImportFormatError(
            f"Plik nie pasuje do formatu banku: brak kolumny „{bank.columns['description']}”"
        )
    header = [h.strip() for h in records[bank.skip_rows - 1]]
    missing = [name for name in bank.columns.values() if name not in header]
    if missing:
        names = ", ".join(f"„{m}”" for m in missing)
        label = "kolumny" if len(missing) == 1 else "kolumn"
        raise ImportFormatError(f"Plik nie pasuje do formatu banku: brak {label} {names}")
    pos = {key: header.index(name) for key, name in bank.columns.items()}

    def cell(rec: list[str], key: str) -> str:
        i = pos[key]
        return rec[i].strip() if i < len(rec) else ""

    rows: list[ParsedRow] = []
    for rec in records[bank.skip_rows :]:
        index = len(rows)
        description = " ".join(cell(rec, "description").split())
        currency = cell(rec, "currency").upper() or None
        errors: list[str] = []
        d: date | None = None
        amount: Decimal | None = None
        try:
            d = datetime.strptime(cell(rec, "date"), bank.date_format).date()
        except ValueError:
            errors.append("Nieprawidłowa data")
        try:
            amount = _parse_amount(cell(rec, "amount"), bank)
        except InvalidOperation:
            errors.append("Nieprawidłowa kwota")
        if amount is not None and (not amount.is_finite() or abs(amount) >= MAX_ABS_AMOUNT):
            errors.append("Kwota poza zakresem")
            amount = None
        elif amount is not None and amount != amount.quantize(Decimal("0.01")):
            errors.append("Kwota ma więcej niż 2 miejsca po przecinku")
        if not description:
            errors.append("Brak opisu")
        if currency is None:
            errors.append("Brak waluty")
        elif currency != "PLN":
            errors.append(
                f"Waluta {currency} nie jest jeszcze obsługiwana (kursy NBP w kolejnym etapie)"
            )
        rows.append(ParsedRow(index, d, amount, currency, description, "; ".join(errors) or None))
    return rows
