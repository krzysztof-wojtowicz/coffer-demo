import re

from fastapi.testclient import TestClient

from coffer.main import app

PUBLIC = {
    "/api/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/logout",
}
METHODS = {"get", "post", "put", "patch", "delete"}


def _fill(path: str) -> str:
    def repl(m: re.Match) -> str:
        name = m.group(1).lower()
        return "2026-10" if "month" in name or "period" in name else "1"

    return re.sub(r"\{([^}]+)\}", repl, path)


def test_all_protected_routes_require_login(client: TestClient) -> None:
    checked = []
    for path, item in app.openapi()["paths"].items():
        if path in PUBLIC:
            continue
        for method in item:
            if method not in METHODS:
                continue
            response = client.request(method.upper(), _fill(path))
            checked.append((method, path))
            assert response.status_code == 401, f"{method.upper()} {path} -> {response.status_code}"
    assert ("get", "/api/auth/me") in checked
