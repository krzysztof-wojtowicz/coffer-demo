from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text

from coffer.transactions import service as tx_service
from coffer.transactions.models import Transaction

FIXTURE = Path(__file__).resolve().parents[4] / "data/fixtures/csv/testbank-2026-10.csv"
HEADER = "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"
MPK = "03.10.2026;04.10.2026;ZAKUP KARTĄ MPK KRAKÓW BILET;-4,60;PLN;0,00"
BIEDRONKA = "03.10.2026;03.10.2026;BIEDRONKA;-20,00;PLN;0"


def upload(client, content: bytes | None = None, bank="testbank", name="wyciag.csv"):
    if content is None:
        content = FIXTURE.read_bytes()
    return client.post(
        "/api/imports", files={"file": (name, content, "text/csv")}, data={"bank": bank}
    )


def csv(*lines: str) -> bytes:
    return (HEADER + "\n".join(lines) + "\n").encode()


def txs(db, user):
    db.expire_all()
    return db.query(Transaction).filter(Transaction.user_id == user.id).all()


def commit(client, draft_id, rows=None):
    return client.post(
        f"/api/imports/{draft_id}/commit", json={} if rows is None else {"rows": rows}
    )


# --- Requirement: CSV import with preview ---


def test_banks(auth_client):
    r = auth_client.get("/api/imports/banks")
    assert r.status_code == 200
    assert {"id": "testbank", "name": "Coffer Test Bank"} in r.json()


def test_preview_fixture_saves_nothing(auth_client, db, user, category_id):
    r = upload(auth_client)
    assert r.status_code == 201
    body = r.json()
    assert body["counts"] == {"new": 17, "duplicate": 0, "error": 1}
    assert body["bank"] == "testbank"
    assert body["filename"] == "wyciag.csv"
    assert len(body["rows"]) == 18
    assert body["expires_at"]
    biedronka = next(r for r in body["rows"] if "BIEDRONKA" in r["description"])
    assert biedronka["category_id"] == category_id("Jedzenie")
    assert biedronka["needs_review"] is False
    assert Decimal(str(biedronka["amount"])) == Decimal("-87.43")
    assert biedronka["status"] == "new"
    eur = next(r for r in body["rows"] if r["currency"] == "EUR")
    assert eur["status"] == "error"
    assert eur["error"] == "Waluta EUR nie jest jeszcze obsługiwana (kursy NBP w kolejnym etapie)"
    assert txs(db, user) == []
    got = auth_client.get(f"/api/imports/{body['id']}")
    assert got.status_code == 200
    assert got.json()["counts"]["new"] == 17


def test_commit_saves_new_rows_once_then_reimport_is_all_duplicates(
    auth_client, db, user, category_id
):
    pid = upload(auth_client).json()["id"]
    r = commit(auth_client, pid)
    assert r.status_code == 200
    assert r.json() == {"imported": 17, "skipped_duplicates": 0, "skipped_errors": 1}
    saved = txs(db, user)
    assert len(saved) == 17
    assert all(t.source == "import" for t in saved)
    obiad = next(t for t in saved if "ZWROT ZA OBIAD" in t.description)
    assert obiad.category_id == category_id("Inne") and obiad.needs_review is True
    assert next(t for t in saved if "BIEDRONKA" in t.description).needs_review is False
    # double commit: the draft is gone, nothing is saved twice
    assert commit(auth_client, pid).status_code == 404
    assert len(txs(db, user)) == 17
    # re-import of the same file
    body = upload(auth_client).json()
    assert body["counts"] == {"new": 0, "duplicate": 17, "error": 1}


@pytest.mark.parametrize(
    ("kwargs", "content", "message"),
    [
        ({"bank": "nieistniejacy"}, None, "Nieobsługiwany bank"),
        (
            {},
            HEADER.encode() + b"01.10.2026;01.10.2026;X;-1,00;PLN;0\n" * 40000,
            "Plik jest za duży (maks. 1 MB)",
        ),
        ({}, HEADER.encode(), "Plik nie zawiera transakcji"),
        (
            {},
            b"Data operacji;Kwota;Waluta\n01.10.2026;-1,00;PLN\n",
            "Plik nie pasuje do formatu banku",
        ),
        (
            {},
            HEADER.encode() + "01.10.2026;01.10.2026;ZAŻÓŁĆ;-1,00;PLN;0\n".encode("cp1250"),
            "Nie udało się odczytać pliku",
        ),
    ],
    ids=["unknown-bank", "too-large", "empty", "missing-column", "bad-encoding"],
)
def test_invalid_file_422_saves_nothing(auth_client, db, user, kwargs, content, message):
    r = upload(auth_client, content, **kwargs)
    assert r.status_code == 422
    assert message in r.text
    assert txs(db, user) == []


def test_invalid_rows_listed_and_not_imported(auth_client, db, user):
    body = upload(
        auth_client,
        csv(
            "01.10.2026;01.10.2026;OK;-1,00;PLN;0",
            "01.10.2026;01.10.2026;ZLE;abc;PLN;0",
            "14.10.2026;15.10.2026;BOOKING;-120,00;EUR;0",
        ),
    ).json()
    assert body["counts"] == {"new": 1, "duplicate": 0, "error": 2}
    bad = [r for r in body["rows"] if r["status"] == "error"]
    assert [r["index"] for r in bad] == [1, 2]
    assert all(r["error"] for r in bad)
    assert bad[0]["amount"] is None
    # forcing an error row to be included still does not import it
    forced = [{"index": r["index"], "include": True, "category_id": None} for r in bad]
    r = commit(auth_client, body["id"], forced)
    assert r.status_code == 200
    assert r.json() == {"imported": 1, "skipped_duplicates": 0, "skipped_errors": 2}
    assert len(txs(db, user)) == 1


def test_huge_amounts_are_row_errors_not_500(auth_client):
    content = csv(
        "01.10.2026;01.10.2026;OGROMNA;1E30;PLN;0,00",
        "02.10.2026;02.10.2026;ZA DUZA;99 999 999 999 999,99;PLN;0,00",
        "03.10.2026;03.10.2026;OK;-10,00;PLN;0,00",
    )
    resp = upload(auth_client, content)
    assert resp.status_code == 201
    assert [r["status"] for r in resp.json()["rows"]] == ["error", "error", "new"]
    assert "zakresem" in resp.json()["rows"][0]["error"]


def test_cancel_saves_nothing_and_missing_draft_is_polish_404(auth_client, db, user):
    pid = upload(auth_client).json()["id"]
    assert auth_client.delete(f"/api/imports/{pid}").status_code == 204
    r = auth_client.get(f"/api/imports/{pid}")
    assert r.status_code == 404
    assert "Nie znaleziono podglądu importu" in r.text
    assert auth_client.delete(f"/api/imports/{pid}").status_code == 404
    assert txs(db, user) == []


def test_expired_draft_is_gone(auth_client, test_engine):
    pid = upload(auth_client).json()["id"]
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE import_drafts SET expires_at = now() - interval '1 minute'"))
    assert auth_client.get(f"/api/imports/{pid}").status_code == 404
    assert commit(auth_client, pid).status_code == 404
    assert auth_client.delete(f"/api/imports/{pid}").status_code == 404


def test_new_upload_removes_users_expired_drafts(auth_client, db):
    old_id = upload(auth_client).json()["id"]
    db.execute(
        text("UPDATE import_drafts SET expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": old_id},
    )
    db.commit()
    upload(auth_client)
    left = db.execute(text("SELECT count(*) FROM import_drafts WHERE id = :i"), {"i": old_id})
    assert left.scalar() == 0


def test_commit_overrides(auth_client, db, user, category_id):
    content = csv(
        "03.10.2026;03.10.2026;COS DZIWNEGO;-10,00;PLN;0",
        "04.10.2026;04.10.2026;BIEDRONKA;-20,00;PLN;0",
        "05.10.2026;05.10.2026;ORLEN;-30,00;PLN;0",
    )
    body = upload(auth_client, content).json()
    idx = {r["description"]: r["index"] for r in body["rows"]}
    r = commit(
        auth_client,
        body["id"],
        [
            {"index": idx["COS DZIWNEGO"], "include": True, "category_id": category_id("Zdrowie")},
            {"index": idx["BIEDRONKA"], "include": False, "category_id": None},
        ],
    )
    assert r.json() == {"imported": 2, "skipped_duplicates": 0, "skipped_errors": 0}
    saved = {t.description: t for t in txs(db, user)}
    assert set(saved) == {"COS DZIWNEGO", "ORLEN"}
    assert saved["COS DZIWNEGO"].category_id == category_id("Zdrowie")
    assert saved["COS DZIWNEGO"].needs_review is False
    assert saved["ORLEN"].category_id == category_id("Transport")


def test_commit_unknown_category_rolls_back(auth_client, db, user):
    body = upload(
        auth_client,
        csv("03.10.2026;03.10.2026;A;-20,00;PLN;0", "04.10.2026;04.10.2026;B;-5,00;PLN;0"),
    ).json()
    r = commit(
        auth_client,
        body["id"],
        [{"index": body["rows"][1]["index"], "include": True, "category_id": 99999}],
    )
    assert r.status_code == 422
    assert "Nieznana kategoria" in r.text
    assert txs(db, user) == []


# --- Requirement: Import de-duplication ---


def test_identical_rows_in_file_with_one_in_db(auth_client, db, user):
    first = upload(auth_client, csv(MPK)).json()
    commit(auth_client, first["id"])
    assert len(txs(db, user)) == 1
    body = upload(auth_client, csv(MPK, MPK)).json()
    assert body["counts"] == {"new": 1, "duplicate": 1, "error": 0}
    assert [r["status"] for r in body["rows"]] == ["duplicate", "new"]
    r = commit(auth_client, body["id"])
    assert r.json() == {"imported": 1, "skipped_duplicates": 1, "skipped_errors": 0}
    assert len(txs(db, user)) == 2


def test_manual_transaction_counts_case_insensitively(auth_client):
    auth_client.post(
        "/api/transactions",
        json={"date": "2026-10-03", "amount": "-20.00", "description": "BIEDRONKA"},
    )
    body = upload(auth_client, csv("03.10.2026;03.10.2026;biedronka;-20,00;PLN;0")).json()
    assert body["counts"]["duplicate"] == 1


def test_duplicate_imported_only_when_included(auth_client, db, user):
    first = upload(auth_client, csv(BIEDRONKA)).json()
    commit(auth_client, first["id"])
    body = upload(auth_client, csv(BIEDRONKA)).json()
    assert body["counts"]["duplicate"] == 1
    rows = [{"index": body["rows"][0]["index"], "include": True, "category_id": None}]
    assert commit(auth_client, body["id"], rows).json()["imported"] == 1
    assert len(txs(db, user)) == 2


def test_commit_rededuplicates_against_db(auth_client, db, user):
    body = upload(auth_client, csv(BIEDRONKA)).json()
    assert body["counts"]["new"] == 1
    auth_client.post(
        "/api/transactions",
        json={"date": "2026-10-03", "amount": "-20.00", "description": "BIEDRONKA"},
    )
    r = commit(auth_client, body["id"])
    assert r.json() == {"imported": 0, "skipped_duplicates": 1, "skipped_errors": 0}
    assert len(txs(db, user)) == 1


def test_dedup_ignores_other_users_transactions(auth_client, other_auth_client):
    b = upload(other_auth_client, csv(BIEDRONKA)).json()
    commit(other_auth_client, b["id"])
    assert upload(auth_client, csv(BIEDRONKA)).json()["counts"]["new"] == 1


# --- Requirement: Automatic categorization (learned category) ---


def test_user_correction_proposed_on_next_import(auth_client, category_id):
    line = "01.03.2026;01.03.2026;SKLEP U ZOSI;-10,00;PLN;0,00"
    first = upload(auth_client, csv(line)).json()
    assert first["rows"][0]["needs_review"] is True
    zakupy = category_id("Zakupy")
    rows = [{"index": first["rows"][0]["index"], "include": True, "category_id": zakupy}]
    assert commit(auth_client, first["id"], rows).status_code == 200
    # the same description in another month is no longer a duplicate and is categorized
    second = upload(auth_client, csv(line.replace("01.03", "01.04"))).json()
    row = second["rows"][0]
    assert row["category_id"] == zakupy and row["needs_review"] is False


# --- Exploit regressions: NUL bytes in filename and cells ---


def test_nul_in_filename_does_not_crash(auth_client):
    # Raw multipart: httpx would percent-encode the NUL, an attacker does not.
    body = (
        b'--B\r\nContent-Disposition: form-data; name="bank"\r\n\r\ntestbank\r\n'
        b'--B\r\nContent-Disposition: form-data; name="file"; filename="a\x00b.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n" + csv(MPK) + b"\r\n--B--\r\n"
    )
    r = auth_client.post(
        "/api/imports",
        content=body,
        headers={"Content-Type": "multipart/form-data; boundary=B"},
    )
    assert r.status_code == 201
    assert "\x00" not in r.json()["filename"]


def test_nul_in_csv_cell_does_not_crash(auth_client):
    r = upload(auth_client, csv("01.10.2026;01.10.2026;KA\x00WA;-5,00;PLN;0"))
    assert r.status_code == 201
    assert "\x00" not in r.json()["rows"][0]["description"]


def test_dedup_keys_only_requested_range(db, user):
    for day, desc in [
        (date(2026, 2, 28), "A"),
        (date(2026, 3, 5), "A  B"),
        (date(2026, 4, 1), "C"),
    ]:
        db.add(
            Transaction(
                user_id=user.id,
                date=day,
                amount=Decimal("-10.00"),
                description=desc,
                category_id=1,
                source="manual",
            )
        )
    db.commit()
    keys = tx_service.dedup_keys(db, user.id, date(2026, 3, 1), date(2026, 4, 1))
    assert list(keys) == [(date(2026, 3, 5), Decimal("-10.00"), "a b")]


def test_import_queries_only_file_range(auth_client):
    with patch.object(tx_service, "dedup_keys", wraps=tx_service.dedup_keys) as spy:
        r = upload(
            auth_client,
            csv(
                "05.03.2026;05.03.2026;A;-10,00;PLN;0,00", "20.03.2026;20.03.2026;B;-5,00;PLN;0,00"
            ),
        )
    assert r.status_code == 201
    assert spy.call_args.args[2:] == (date(2026, 3, 5), date(2026, 3, 21))
