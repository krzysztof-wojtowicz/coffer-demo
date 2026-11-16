import csv
from pathlib import Path

from coffer.imports.categorize import RULES, categorize

FIXTURE = Path(__file__).resolve().parents[4] / "data/fixtures/categorization/n05-200.csv"


def _rows() -> list[tuple[str, str]]:
    with FIXTURE.open(encoding="utf-8", newline="") as f:
        return [(r["Opis"], r["Oczekiwana kategoria"]) for r in csv.DictReader(f, delimiter=";")]


def test_n05_accuracy_at_least_80_percent():
    rows = _rows()
    assert len(rows) == 200
    hits = sum(categorize(desc) == expected for desc, expected in rows)
    assert hits / len(rows) >= 0.80, f"N05 accuracy {hits / len(rows):.1%}"


def test_n05_set_not_tuned_to_rules():
    keywords = [k for _, kws in RULES for k in kws]
    outside = [d for d, _ in _rows() if not any(k in d.upper() for k in keywords)]
    assert len(outside) >= 30
