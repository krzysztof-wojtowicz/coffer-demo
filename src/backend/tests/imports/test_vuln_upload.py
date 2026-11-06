"""Exploit regressions for the import endpoints (NUL bytes, malformed draft ids, IDOR)."""

from tests.imports.test_api import csv, upload

ROW = "01.10.2026;01.10.2026;KAWA;-5,00;PLN;0"


def test_nul_in_filename_does_not_crash(auth_client):
    # Raw multipart: httpx would percent-encode the NUL, an attacker does not.
    body = (
        b'--B\r\nContent-Disposition: form-data; name="bank"\r\n\r\ntestbank\r\n'
        b'--B\r\nContent-Disposition: form-data; name="file"; filename="a\x00b.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n" + csv(ROW) + b"\r\n--B--\r\n"
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


def test_malformed_draft_id_is_404(auth_client):
    for bad in ("%00", "x" * 100):
        assert auth_client.get(f"/api/imports/{bad}").status_code == 404
        assert auth_client.post(f"/api/imports/{bad}/commit", json={}).status_code == 404
        assert auth_client.delete(f"/api/imports/{bad}").status_code == 404


def test_other_users_draft_is_404(auth_client, other_auth_client):
    draft_id = upload(auth_client, csv(ROW)).json()["id"]
    assert other_auth_client.get(f"/api/imports/{draft_id}").status_code == 404
    assert other_auth_client.post(f"/api/imports/{draft_id}/commit", json={}).status_code == 404
    assert other_auth_client.delete(f"/api/imports/{draft_id}").status_code == 404
    assert auth_client.get(f"/api/imports/{draft_id}").status_code == 200
