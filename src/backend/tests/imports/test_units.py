from collections import Counter
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.imports.banks import BANKS
from coffer.imports.categorize import categorize
from coffer.imports.dedup import mark_duplicates
from coffer.imports.parser import ImportFormatError, ParsedRow, parse

BANK = BANKS["testbank"]
HEADER = "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"


def _csv(*lines: str) -> bytes:
    return (HEADER + "\n".join(lines) + "\n").encode()


def test_parse_amount_with_space_and_nbsp():
    rows = parse(
        _csv(
            "01.10.2026;01.10.2026;A;-1 234,56;PLN;0,00",
            "01.10.2026;01.10.2026;B;-1 234,56;PLN;0,00",
            "02.10.2026;02.10.2026;C;8 500,00;PLN;0,00",
            "02.10.2026;02.10.2026;D;-0,01;PLN;0,00",
        ),
        BANK,
    )
    assert [r.amount for r in rows] == [
        Decimal("-1234.56"),
        Decimal("-1234.56"),
        Decimal("8500.00"),
        Decimal("-0.01"),
    ]
    assert rows[0].date == date(2026, 10, 1)
    assert rows[0].currency == "PLN"
    assert rows[0].description == "A"
    assert all(r.error is None for r in rows)


def test_parse_bad_rows_do_not_abort():
    rows = parse(
        _csv(
            "01.10.2026;01.10.2026;OK;-1,00;PLN;0",
            "01.10.2026;01.10.2026;ZLA KWOTA;abc;PLN;0",
            "31.02.2026;01.10.2026;ZLA DATA;-1,00;PLN;0",
            "02.10.2026;02.10.2026;OK2;-2,00;PLN;0",
        ),
        BANK,
    )
    assert len(rows) == 4
    assert rows[0].error is None and rows[3].error is None
    assert rows[1].error and rows[2].error
    assert rows[1].amount is None
    assert rows[2].date is None
    assert [r.index for r in rows] == sorted(r.index for r in rows)
    assert len({r.index for r in rows}) == 4


def test_parse_missing_column():
    content = b"Data operacji;Kwota;Waluta\n01.10.2026;-1,00;PLN\n"
    with pytest.raises(ImportFormatError) as e:
        parse(content, BANK)
    assert "Opis" in str(e.value)


def test_parse_fixture_file():
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "data/fixtures/csv/testbank-2026-10.csv"
    rows = parse(path.read_bytes(), BANK)
    assert len(rows) == 18
    assert sum(1 for r in rows if r.currency == "EUR") == 1


@pytest.mark.parametrize(
    ("desc", "cat"),
    [
        ("ZAKUP KARTĄ BIEDRONKA 1234", "Jedzenie"),
        ("zakup lidl krakow", "Jedzenie"),
        ("ŻABKA Z1234", "Jedzenie"),
        ("AUCHAN", "Jedzenie"),
        ("ZAKUP KARTĄ MPK KRAKÓW BILET", "Transport"),
        ("ORLEN STACJA 55", "Transport"),
        ("UBER TRIP", "Transport"),
        ("PRZELEW WYCHODZĄCY CZYNSZ PAŹDZIERNIK", "Mieszkanie"),
        ("RACHUNEK ZA PRĄD TAURON", "Rachunki"),
        ("INTERNET ORANGE", "Rachunki"),
        ("APTEKA DOZ", "Zdrowie"),
        ("PŁATNOŚĆ BLIK NETFLIX.COM", "Rozrywka"),
        ("KINO CINEMA TEST", "Rozrywka"),
        ("ALLEGRO.PL", "Zakupy"),
        ("PRZELEW PRZYCHODZĄCY WYNAGRODZENIE 09/2026", "Wynagrodzenie"),
        ("PRZELEW WŁASNY NA RACHUNEK OSZCZĘDNOŚCIOWY", "Przelewy własne"),
        ("PRZELEW WYCHODZĄCY DOM MAKLERSKI TESTOWY", "Inwestycje"),
    ],
)
def test_categorize_rules(desc, cat):
    assert categorize(desc) == cat


def test_categorize_unknown_is_none():
    assert categorize("ZWROT ZA OBIAD JAN TESTOWY") is None
    assert categorize("") is None


def _row(i, d, amount, desc):
    return ParsedRow(i, d, Decimal(amount), "PLN", desc, None)


def test_dedup_multiset():
    d = date(2026, 10, 3)
    rows = [_row(0, d, "-4.60", "MPK"), _row(1, d, "-4.60", "MPK"), _row(2, d, "-1.00", "X")]
    assert mark_duplicates(rows, Counter({(d, Decimal("-4.60"), "MPK"): 1})) == {0}
    assert mark_duplicates(rows, Counter({(d, Decimal("-4.60"), "MPK"): 2})) == {0, 1}
    assert mark_duplicates(rows, Counter({(d, Decimal("-4.60"), "MPK"): 5})) == {0, 1}
    assert mark_duplicates(rows, Counter()) == set()


def test_dedup_normalizes_whitespace():
    d = date(2026, 10, 3)
    rows = [_row(0, d, "-4.60", "MPK   KRAKÓW  BILET")]
    assert mark_duplicates(rows, Counter({(d, Decimal("-4.60"), "MPK KRAKÓW BILET"): 1})) == {0}


def test_dedup_different_amount_or_date_not_duplicate():
    d = date(2026, 10, 3)
    rows = [_row(0, d, "-4.61", "MPK"), _row(1, date(2026, 10, 4), "-4.60", "MPK")]
    assert mark_duplicates(rows, Counter({(d, Decimal("-4.60"), "MPK"): 1})) == set()


@given(k=st.integers(0, 6), n=st.integers(0, 6))
def test_dedup_property_min_k_n(k, n):
    d = date(2026, 10, 3)
    rows = [_row(i, d, "-4.60", "MPK") for i in range(k)]
    result = mark_duplicates(rows, Counter({(d, Decimal("-4.60"), "MPK"): n}) if n else Counter())
    assert result == set(range(min(k, n)))


@given(cents=st.integers(-(10**11) + 1, 10**11 - 1).filter(lambda c: c != 0))
def test_parse_amount_roundtrip(cents):
    amount = Decimal(cents) / 100
    whole, frac = divmod(abs(cents), 100)
    text = f"{whole:,}".replace(",", " ") + f",{frac:02d}"
    if cents < 0:
        text = "-" + text
    rows = parse(_csv(f"01.10.2026;01.10.2026;X;{text};PLN;0"), BANK)
    assert rows[0].error is None
    assert rows[0].amount == amount
