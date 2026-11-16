from datetime import date
from decimal import Decimal

from coffer.imports.categorize import categorize
from coffer.transactions.models import Transaction

CSV = (
    "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"
    "01.03.2026;01.03.2026;SKLEP U ZOSI;-10,00;PLN;0,00\n"
)


def test_hint_beats_rules_and_falls_back():
    assert categorize("SKLEP U ZOSI") is None
    assert categorize("sklep  u zosi", {"sklep u zosi": "Jedzenie"}) == "Jedzenie"
    assert categorize("BIEDRONKA 1", {"sklep u zosi": "Jedzenie"}) == "Jedzenie"
    assert categorize("LIDL", {"lidl": "Rozrywka"}) == "Rozrywka"


def test_user_correction_proposed_on_next_import(auth_client, db, user, category_id):
    def upload():
        r = auth_client.post(
            "/api/imports",
            data={"bank": "testbank"},
            files={"file": ("w.csv", CSV.encode(), "text/csv")},
        )
        assert r.status_code == 201, r.text
        return r.json()

    first = upload()
    assert first["rows"][0]["needs_review"] is True
    zakupy = category_id("Zakupy")
    r = auth_client.post(
        f"/api/imports/{first['id']}/commit",
        json={
            "rows": [{"index": first["rows"][0]["index"], "include": True, "category_id": zakupy}]
        },
    )
    assert r.status_code == 200, r.text
    db.add(
        Transaction(
            user_id=user.id,
            date=date(2026, 4, 1),
            amount=Decimal("-1.00"),
            currency="PLN",
            base_amount=Decimal("-1.00"),
            description="x",
            category_id=zakupy,
            source="manual",
        )
    )
    db.commit()
    second = upload()
    row = second["rows"][0]
    assert row["category_id"] == zakupy and row["needs_review"] is False
