from datetime import date
from decimal import Decimal
from unittest.mock import patch

from coffer.transactions import service as tx_service
from coffer.transactions.models import Transaction

HEADER = "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"


def _add(db, user, day, desc, amount="-10.00"):
    db.add(
        Transaction(
            user_id=user.id,
            date=day,
            amount=Decimal(amount),
            currency="PLN",
            base_amount=Decimal(amount),
            description=desc,
            category_id=1,
            source="manual",
        )
    )
    db.commit()


def _upload(client, *lines):
    content = (HEADER + "\n".join(lines) + "\n").encode()
    return client.post(
        "/api/imports", data={"bank": "testbank"}, files={"file": ("w.csv", content, "text/csv")}
    )


def test_dedup_keys_only_requested_range(db, user):
    _add(db, user, date(2026, 2, 28), "A")
    _add(db, user, date(2026, 3, 5), "A  B")
    _add(db, user, date(2026, 4, 1), "C")
    keys = tx_service.dedup_keys(db, user.id, date(2026, 3, 1), date(2026, 4, 1))
    assert list(keys) == [(date(2026, 3, 5), Decimal("-10.00"), "a b")]


def test_import_queries_only_file_range(auth_client):
    with patch.object(tx_service, "dedup_keys", wraps=tx_service.dedup_keys) as spy:
        r = _upload(
            auth_client,
            "05.03.2026;05.03.2026;A;-10,00;PLN;0,00",
            "20.03.2026;20.03.2026;B;-5,00;PLN;0,00",
        )
    assert r.status_code == 201
    args = spy.call_args.args
    assert args[2:] == (date(2026, 3, 5), date(2026, 3, 21))


def test_case_insensitive_duplicate(auth_client, db, user):
    _add(db, user, date(2026, 3, 5), "ALLEGRO")
    body = _upload(auth_client, "05.03.2026;05.03.2026;allegro;-10,00;PLN;0,00").json()
    assert body["counts"]["duplicate"] == 1


def test_identical_rows_in_file_both_imported(auth_client):
    line = "05.03.2026;05.03.2026;KAWA;-10,00;PLN;0,00"
    assert _upload(auth_client, line, line).json()["counts"] == {
        "new": 2,
        "duplicate": 0,
        "error": 0,
    }
