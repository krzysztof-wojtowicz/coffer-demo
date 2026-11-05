import requests

URL = "/api/market/quotes"


def test_requires_auth(client):
    assert client.get(URL, params={"symbols": "AAPL"}).status_code == 401


def test_quotes(auth_client):
    r = auth_client.get(URL, params={"symbols": "AAPL,MSFT,NOPE"})
    assert r.status_code == 200
    quotes = {q["symbol"]: q for q in r.json()["quotes"]}
    assert set(quotes) == {"AAPL", "MSFT"}
    assert quotes["AAPL"]["price"] == "190.13"
    assert quotes["AAPL"]["change_pct"] == "2.77"
    assert quotes["MSFT"]["change_pct"] is None
    assert quotes["AAPL"]["currency"] == "USD" and quotes["AAPL"]["as_of"]


def test_unavailable_503(auth_client, fake_yf):
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    r = auth_client.get(URL, params={"symbols": "AAPL"})
    assert r.status_code == 503
    assert "niedostępne" in r.json()["detail"]
