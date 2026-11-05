from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from coffer.transactions.models import Transaction

FIXTURE = Path(__file__).resolve().parents[4] / "data/fixtures/csv/testbank-2026-10.csv"
HEADER = "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"


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


def test_auth_required(client):
    assert client.get("/api/imports/banks").status_code == 401
    assert upload(client).status_code == 401
    assert client.get("/api/imports/x").status_code == 401
    assert client.post("/api/imports/x/commit", json={}).status_code == 401
    assert client.delete("/api/imports/x").status_code == 401


def test_banks(auth_client):
    r = auth_client.get("/api/imports/banks")
    assert r.status_code == 200
    assert {"id": "testbank", "name": "Coffer Test Bank"} in r.json()


def test_preview_fixture(auth_client, category_id):
    r = upload(auth_client)
    assert r.status_code == 201
    body = r.json()
    assert body["counts"] == {"new": 17, "duplicate": 0, "error": 1}
    assert body["bank"] == "testbank"
    assert body["filename"] == "wyciag.csv"
    assert len(body["rows"]) == 18
    assert body["expires_at"]
    by_desc = {r["description"]: r for r in body["rows"]}
    biedronka = next(r for d, r in by_desc.items() if "BIEDRONKA" in d)
    assert biedronka["category_id"] == category_id("Jedzenie")
    assert biedronka["needs_review"] is False
    assert Decimal(str(biedronka["amount"])) == Decimal("-87.43")
    assert biedronka["status"] == "new"
    obiad = next(r for d, r in by_desc.items() if "ZWROT ZA OBIAD" in d)
    assert obiad["category_id"] == category_id("Inne")
    assert obiad["needs_review"] is True
    eur = next(r for r in body["rows"] if r["currency"] == "EUR")
    assert eur["status"] == "error"
    assert eur["error"] == "Waluta EUR nie jest jeszcze obsługiwana (kursy NBP w kolejnym etapie)"
    assert len([r for r in body["rows"] if "MPK" in r["description"]]) == 2


def test_get_preview(auth_client):
    pid = upload(auth_client).json()["id"]
    r = auth_client.get(f"/api/imports/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid
    assert r.json()["counts"]["new"] == 17


def test_preview_does_not_save(auth_client, db, user):
    upload(auth_client)
    assert txs(db, user) == []


def test_commit_default_and_reimport_all_duplicates(auth_client, db, user, category_id):
    pid = upload(auth_client).json()["id"]
    r = auth_client.post(f"/api/imports/{pid}/commit", json={})
    assert r.status_code == 200
    assert r.json() == {"imported": 17, "skipped_duplicates": 0, "skipped_errors": 1}
    saved = txs(db, user)
    assert len(saved) == 17
    assert all(t.source == "import" and t.currency == "PLN" for t in saved)
    assert all(t.base_amount == t.amount for t in saved)
    # preview removed
    assert auth_client.get(f"/api/imports/{pid}").status_code == 404
    # reimport
    body = upload(auth_client).json()
    assert body["counts"] == {"new": 0, "duplicate": 17, "error": 1}
    assert all(r["status"] != "new" for r in body["rows"])


def test_commit_flags_needs_review(auth_client, db, user, category_id):
    pid = upload(auth_client).json()["id"]
    auth_client.post(f"/api/imports/{pid}/commit", json={})
    saved = txs(db, user)
    obiad = next(t for t in saved if "ZWROT ZA OBIAD" in t.description)
    assert obiad.category_id == category_id("Inne") and obiad.needs_review is True
    bied = next(t for t in saved if "BIEDRONKA" in t.description)
    assert bied.needs_review is False


def test_mpk_multiset_one_in_db(auth_client, db, user, category_id):
    ticket = "03.10.2026;04.10.2026;ZAKUP KARTĄ MPK KRAKÓW BILET;-4,60;PLN;0,00"
    first = upload(auth_client, csv(ticket)).json()
    auth_client.post(f"/api/imports/{first['id']}/commit", json={})
    assert len(txs(db, user)) == 1
    body = upload(auth_client, csv(ticket, ticket)).json()
    assert body["counts"] == {"new": 1, "duplicate": 1, "error": 0}
    assert [r["status"] for r in body["rows"]] == ["duplicate", "new"]
    r = auth_client.post(f"/api/imports/{body['id']}/commit", json={})
    assert r.json() == {"imported": 1, "skipped_duplicates": 1, "skipped_errors": 0}
    assert len(txs(db, user)) == 2


def test_manual_transaction_counts_for_dedup(auth_client):
    auth_client.post(
        "/api/transactions",
        json={
            "date": "2026-10-03",
            "amount": "-4.60",
            "description": "ZAKUP KARTĄ MPK KRAKÓW BILET",
        },
    )
    body = upload(
        auth_client, csv("03.10.2026;04.10.2026;ZAKUP KARTĄ MPK KRAKÓW BILET;-4,60;PLN;0")
    ).json()
    assert body["counts"]["duplicate"] == 1


def test_commit_overrides(auth_client, db, user, category_id):
    content = csv(
        "03.10.2026;03.10.2026;COS DZIWNEGO;-10,00;PLN;0",
        "04.10.2026;04.10.2026;BIEDRONKA;-20,00;PLN;0",
        "05.10.2026;05.10.2026;ORLEN;-30,00;PLN;0",
    )
    body = upload(auth_client, content).json()
    idx = {r["description"]: r["index"] for r in body["rows"]}
    r = auth_client.post(
        f"/api/imports/{body['id']}/commit",
        json={
            "rows": [
                {
                    "index": idx["COS DZIWNEGO"],
                    "include": True,
                    "category_id": category_id("Zdrowie"),
                },
                {"index": idx["BIEDRONKA"], "include": False, "category_id": None},
            ]
        },
    )
    assert r.json() == {"imported": 2, "skipped_duplicates": 0, "skipped_errors": 0}
    saved = {t.description: t for t in txs(db, user)}
    assert set(saved) == {"COS DZIWNEGO", "ORLEN"}
    assert saved["COS DZIWNEGO"].category_id == category_id("Zdrowie")
    assert saved["COS DZIWNEGO"].needs_review is False
    assert saved["ORLEN"].category_id == category_id("Transport")


def test_commit_duplicate_only_when_included(auth_client, db, user):
    line = "03.10.2026;03.10.2026;BIEDRONKA;-20,00;PLN;0"
    first = upload(auth_client, csv(line)).json()
    auth_client.post(f"/api/imports/{first['id']}/commit", json={})
    body = upload(auth_client, csv(line)).json()
    assert body["counts"]["duplicate"] == 1
    r = auth_client.post(
        f"/api/imports/{body['id']}/commit",
        json={"rows": [{"index": body["rows"][0]["index"], "include": True, "category_id": None}]},
    )
    assert r.json()["imported"] == 1
    assert len(txs(db, user)) == 2


def test_commit_error_row_never_imported(auth_client, db, user):
    body = upload(auth_client, csv("14.10.2026;15.10.2026;BOOKING;-120,00;EUR;0")).json()
    assert body["counts"] == {"new": 0, "duplicate": 0, "error": 1}
    r = auth_client.post(
        f"/api/imports/{body['id']}/commit",
        json={"rows": [{"index": body["rows"][0]["index"], "include": True, "category_id": None}]},
    )
    assert r.status_code == 200
    assert r.json()["imported"] == 0
    assert r.json()["skipped_errors"] == 1
    assert txs(db, user) == []


def test_commit_rededuplicates_against_db(auth_client, db, user):
    line = "03.10.2026;03.10.2026;BIEDRONKA;-20,00;PLN;0"
    body = upload(auth_client, csv(line)).json()
    assert body["counts"]["new"] == 1
    auth_client.post(
        "/api/transactions",
        json={"date": "2026-10-03", "amount": "-20.00", "description": "BIEDRONKA"},
    )
    r = auth_client.post(f"/api/imports/{body['id']}/commit", json={})
    assert r.json() == {"imported": 0, "skipped_duplicates": 1, "skipped_errors": 0}
    assert len(txs(db, user)) == 1


def test_commit_unknown_category_rolls_back(auth_client, db, user):
    body = upload(
        auth_client,
        csv("03.10.2026;03.10.2026;A;-20,00;PLN;0", "04.10.2026;04.10.2026;B;-5,00;PLN;0"),
    ).json()
    r = auth_client.post(
        f"/api/imports/{body['id']}/commit",
        json={"rows": [{"index": body["rows"][1]["index"], "include": True, "category_id": 99999}]},
    )
    assert r.status_code == 422
    assert "Nieznana kategoria" in r.text
    assert txs(db, user) == []


def test_delete(auth_client):
    pid = upload(auth_client).json()["id"]
    assert auth_client.delete(f"/api/imports/{pid}").status_code == 204
    assert auth_client.get(f"/api/imports/{pid}").status_code == 404
    assert auth_client.delete(f"/api/imports/{pid}").status_code == 404


def test_not_found_message(auth_client):
    r = auth_client.get("/api/imports/nie-ma-takiego")
    assert r.status_code == 404
    assert "Nie znaleziono podglądu importu" in r.text


def test_isolation(auth_client, other_auth_client, db, user):
    pid = upload(auth_client).json()["id"]
    assert other_auth_client.get(f"/api/imports/{pid}").status_code == 404
    assert other_auth_client.post(f"/api/imports/{pid}/commit", json={}).status_code == 404
    assert other_auth_client.delete(f"/api/imports/{pid}").status_code == 404
    assert auth_client.get(f"/api/imports/{pid}").status_code == 200
    assert txs(db, user) == []


def test_expired_preview(auth_client, test_engine):
    pid = upload(auth_client).json()["id"]
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE import_drafts SET expires_at = now() - interval '1 minute'"))
    assert auth_client.get(f"/api/imports/{pid}").status_code == 404
    assert auth_client.post(f"/api/imports/{pid}/commit", json={}).status_code == 404
    assert auth_client.delete(f"/api/imports/{pid}").status_code == 404


def test_unknown_bank(auth_client):
    r = upload(auth_client, bank="nieistniejacy")
    assert r.status_code == 422
    assert "Nieobsługiwany bank" in r.text


def test_too_large(auth_client):
    big = HEADER.encode() + b"01.10.2026;01.10.2026;X;-1,00;PLN;0\n" * 40000
    assert len(big) > 1024 * 1024
    r = upload(auth_client, big)
    assert r.status_code == 422
    assert "Plik jest za duży (maks. 1 MB)" in r.text


def test_empty_file_no_transactions(auth_client):
    r = upload(auth_client, HEADER.encode())
    assert r.status_code == 422
    assert "Plik nie zawiera transakcji" in r.text


def test_missing_column(auth_client):
    r = upload(auth_client, b"Data operacji;Kwota;Waluta\n01.10.2026;-1,00;PLN\n")
    assert r.status_code == 422
    assert "Plik nie pasuje do formatu banku" in r.text
    assert "Opis" in r.text


def test_bad_encoding(auth_client):
    content = HEADER.encode() + "01.10.2026;01.10.2026;ZAŻÓŁĆ;-1,00;PLN;0\n".encode("cp1250")
    r = upload(auth_client, content)
    assert r.status_code == 422
    assert "Nie udało się odczytać pliku" in r.text


def test_bad_rows_reported_not_fatal(auth_client):
    body = upload(
        auth_client,
        csv("01.10.2026;01.10.2026;OK;-1,00;PLN;0", "01.10.2026;01.10.2026;ZLE;abc;PLN;0"),
    ).json()
    assert body["counts"] == {"new": 1, "duplicate": 0, "error": 1}
    bad = next(r for r in body["rows"] if r["status"] == "error")
    assert bad["error"]
    assert bad["amount"] is None


def test_no_import_for_other_user_dedup(auth_client, other_auth_client, db):
    line = "03.10.2026;03.10.2026;BIEDRONKA;-20,00;PLN;0"
    b = upload(other_auth_client, csv(line)).json()
    other_auth_client.post(f"/api/imports/{b['id']}/commit", json={})
    body = upload(auth_client, csv(line)).json()
    assert body["counts"]["new"] == 1


# --- regresje z przeglądu E2/E3 ---


def test_huge_amounts_are_row_errors_not_500(auth_client):
    content = csv(
        "01.10.2026;01.10.2026;OGROMNA;1E30;PLN;0,00",
        "02.10.2026;02.10.2026;ZA DUZA;99 999 999 999 999,99;PLN;0,00",
        "03.10.2026;03.10.2026;OK;-10,00;PLN;0,00",
    )
    resp = upload(auth_client, content)
    assert resp.status_code == 201
    statuses = [r["status"] for r in resp.json()["rows"]]
    assert statuses == ["error", "error", "new"]
    assert "zakresem" in resp.json()["rows"][0]["error"]


def test_second_commit_of_same_draft_is_404(auth_client):
    draft_id = upload(auth_client).json()["id"]
    assert auth_client.post(f"/api/imports/{draft_id}/commit", json={"rows": []}).status_code == 200
    resp = auth_client.post(f"/api/imports/{draft_id}/commit", json={"rows": []})
    assert resp.status_code == 404


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
