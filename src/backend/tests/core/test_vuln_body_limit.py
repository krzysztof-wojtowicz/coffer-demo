"""Exploit: an oversized upload must be refused (413) before the body is buffered.

Starlette spools the whole multipart body to disk before /api/imports checks its 1 MB cap,
so a client could stream hundreds of MB per request (disk/CPU DoS on Render free).
"""

from collections.abc import Iterator

from fastapi.testclient import TestClient

from coffer.core.config import get_settings

BOUNDARY = "xBOUNDARYx"
HEADERS = {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}


def _multipart(size: int) -> bytes:
    head = (
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="bank"\r\n\r\nmbank\r\n'
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode()
    return head + b"a" * size + f"\r\n--{BOUNDARY}--\r\n".encode()


def test_oversized_content_length_rejected_413(auth_client: TestClient) -> None:
    body = _multipart(get_settings().max_request_bytes + 1)
    response = auth_client.post("/api/imports", content=body, headers=HEADERS)
    assert response.status_code == 413
    assert response.json()["detail"] == "Żądanie jest za duże"


def test_oversized_chunked_body_rejected_413(auth_client: TestClient) -> None:
    body = _multipart(get_settings().max_request_bytes + 1)

    def chunks() -> Iterator[bytes]:  # no Content-Length: Transfer-Encoding: chunked
        for i in range(0, len(body), 64 * 1024):
            yield body[i : i + 64 * 1024]

    response = auth_client.post("/api/imports", content=chunks(), headers=HEADERS)
    assert response.status_code == 413
    assert response.json()["detail"] == "Żądanie jest za duże"


def test_small_body_passes(auth_client: TestClient) -> None:
    response = auth_client.post("/api/imports", content=_multipart(10), headers=HEADERS)
    assert response.status_code != 413
