"""Pure parser, de-duplication and categorizer tests (no HTTP)."""

import csv
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.imports.banks import BANKS
from coffer.imports.categorize import RULES, categorize
from coffer.imports.dedup import mark_duplicates
from coffer.imports.parser import ImportFormatError, ParsedRow, parse

BANK = BANKS["testbank"]
HEADER = "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"
N05_FIXTURE = Path(__file__).resolve().parents[4] / "data/fixtures/categorization/n05-200.csv"


def _csv(*lines: str) -> bytes:
    return (HEADER + "\n".join(lines) + "\n").encode()


# --- Parser ---


def test_parse_amount_with_space_and_nbsp():
    rows = parse(
        _csv(
            "01.10.2026;01.10.2026;A;-1 234,56;PLN;0,00",
            "01.10.2026;01.10.2026;B;-1 234,56;PLN;0,00",
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
    assert [r.index for r in rows] == [0, 1, 2, 3]


def test_parse_missing_column():
    with pytest.raises(ImportFormatError) as e:
        parse(b"Data operacji;Kwota;Waluta\n01.10.2026;-1,00;PLN\n", BANK)
    assert "Opis" in str(e.value)


@given(cents=st.integers(-(10**11) + 1, 10**11 - 1).filter(lambda c: c != 0))
def test_parse_amount_roundtrip(cents):
    whole, frac = divmod(abs(cents), 100)
    text = f"{whole:,}".replace(",", " ") + f",{frac:02d}"
    if cents < 0:
        text = "-" + text
    rows = parse(_csv(f"01.10.2026;01.10.2026;X;{text};PLN;0"), BANK)
    assert rows[0].error is None
    assert rows[0].amount == Decimal(cents) / 100


# --- Categorizer ---


@pytest.mark.parametrize(
    ("desc", "cat"),
    [
        ("ZAKUP KARTĄ BIEDRONKA 1234", "Jedzenie"),
        ("zakup lidl krakow", "Jedzenie"),
        ("ŻABKA Z1234", "Jedzenie"),
        ("ZAKUP KARTĄ MPK KRAKÓW BILET", "Transport"),
        ("ORLEN STACJA 55", "Transport"),
        ("PRZELEW WYCHODZĄCY CZYNSZ PAŹDZIERNIK", "Mieszkanie"),
        ("RACHUNEK ZA PRĄD TAURON", "Rachunki"),
        ("APTEKA DOZ", "Zdrowie"),
        ("PŁATNOŚĆ BLIK NETFLIX.COM", "Rozrywka"),
        ("ALLEGRO.PL", "Zakupy"),
        ("PRZELEW PRZYCHODZĄCY WYNAGRODZENIE 09/2026", "Wynagrodzenie"),
        ("PRZELEW WŁASNY NA RACHUNEK OSZCZĘDNOŚCIOWY", "Przelewy własne"),
        ("PRZELEW WYCHODZĄCY DOM MAKLERSKI TESTOWY", "Inwestycje"),
        ("ZWROT ZA OBIAD JAN TESTOWY", None),
        ("", None),
    ],
)
def test_categorize_rules(desc, cat):
    assert categorize(desc) == cat


def test_hint_beats_rules_and_falls_back():
    assert categorize("SKLEP U ZOSI") is None
    assert categorize("sklep  u zosi", {"sklep u zosi": "Jedzenie"}) == "Jedzenie"
    assert categorize("BIEDRONKA 1", {"sklep u zosi": "Jedzenie"}) == "Jedzenie"
    assert categorize("LIDL", {"lidl": "Rozrywka"}) == "Rozrywka"


def _n05_rows() -> list[tuple[str, str]]:
    with N05_FIXTURE.open(encoding="utf-8", newline="") as f:
        return [(r["Opis"], r["Oczekiwana kategoria"]) for r in csv.DictReader(f, delimiter=";")]


def test_n05_accuracy_at_least_80_percent():
    rows = _n05_rows()
    assert len(rows) == 200
    hits = sum(categorize(desc) == expected for desc, expected in rows)
    assert hits / len(rows) >= 0.80, f"N05 accuracy {hits / len(rows):.1%}"


def test_n05_set_not_tuned_to_rules():
    keywords = [k for _, kws in RULES for k in kws]
    outside = [d for d, _ in _n05_rows() if not any(k in d.upper() for k in keywords)]
    assert len(outside) >= 30


# --- De-duplication ---

D = date(2026, 10, 3)


def _row(i, d, amount, desc):
    return ParsedRow(i, d, Decimal(amount), "PLN", desc, None)


def test_dedup_multiset():
    rows = [_row(0, D, "-4.60", "MPK"), _row(1, D, "-4.60", "MPK"), _row(2, D, "-1.00", "X")]
    key = (D, Decimal("-4.60"), "mpk")
    assert mark_duplicates(rows, Counter({key: 1})) == {0}
    assert mark_duplicates(rows, Counter({key: 2})) == {0, 1}
    assert mark_duplicates(rows, Counter({key: 5})) == {0, 1}
    assert mark_duplicates(rows, Counter()) == set()


def test_dedup_normalizes_whitespace_and_needs_same_amount_and_date():
    rows = [_row(0, D, "-4.60", "MPK   KRAKÓW  BILET")]
    assert mark_duplicates(rows, Counter({(D, Decimal("-4.60"), "mpk kraków bilet"): 1})) == {0}
    other = [_row(0, D, "-4.61", "MPK"), _row(1, date(2026, 10, 4), "-4.60", "MPK")]
    assert mark_duplicates(other, Counter({(D, Decimal("-4.60"), "mpk"): 1})) == set()


@given(k=st.integers(0, 6), n=st.integers(0, 6))
def test_dedup_property_min_k_n(k, n):
    rows = [_row(i, D, "-4.60", "MPK") for i in range(k)]
    result = mark_duplicates(rows, Counter({(D, Decimal("-4.60"), "mpk"): n}) if n else Counter())
    assert result == set(range(min(k, n)))
