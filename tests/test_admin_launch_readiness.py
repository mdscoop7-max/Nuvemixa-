import base64
from app import app


def _auth():
    token = base64.b64encode(b"owner:test-long-secret-password-123").decode()
    return {"Authorization": "Basic " + token}


def test_launch_readiness_hidden_without_credentials(monkeypatch):
    monkeypatch.delenv("TRENDMIX_ADMIN_USER", raising=False)
    monkeypatch.delenv("TRENDMIX_ADMIN_PASSWORD", raising=False)
    assert app.test_client().get("/beheer/lancering").status_code == 404


def test_launch_readiness_requires_admin(monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "owner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "test-long-secret-password-123")
    assert app.test_client().get("/beheer/lancering").status_code == 401


def test_launch_readiness_show_unverified_gate(monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "owner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "test-long-secret-password-123")
    client = app.test_client()
    resp = client.get("/beheer/lancering", headers=_auth())
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["X-Robots-Tag"] == "noindex, nofollow"
    html = resp.get_data(as_text=True)
    assert "Nog niet verkoopklaar" in html
    assert html.count("Nog te bevestigen") == 8
    assert "EU-leveranciers" in html
    assert "Betalingen" in html
    home = client.get("/beheer", headers=_auth()).get_data(as_text=True)
    assert "/beheer/lancering" in home
