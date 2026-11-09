import base64
from app import app


def test_admin_is_hidden_without_credentials(monkeypatch):
    monkeypatch.delenv("TRENDMIX_ADMIN_USER", raising=False)
    monkeypatch.delenv("TRENDMIX_ADMIN_PASSWORD", raising=False)
    assert app.test_client().get("/beheer").status_code == 404


def test_admin_requires_auth_with_credentials(monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "owner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "test-long-secret-password-123")
    assert app.test_client().get("/beheer").status_code == 401
    invalid = base64.b64encode(b"owner:bad").decode()
    assert app.test_client().get("/beheer", headers={"Authorization": "Basic " + invalid}).status_code == 401


def test_admin_authenticated_read_only(monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "owner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "test-long-secret-password-123")
    valid = base64.b64encode(b"owner:test-long-secret-password-123").decode()
    response = app.test_client().get("/beheer", headers={"Authorization": "Basic " + valid})
    assert response.status_code == 200
    assert "Beheerdashboard" in response.get_data(as_text=True)
    assert "alleen-lezen" in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_dashboard_sales_visitors_and_media_are_unmeasured(monkeypatch):
    """Do not represent test checkouts as paid orders or invented visitors."""
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "owner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "test-long-secret-password-123")
    valid = base64.b64encode(b"owner:test-long-secret-password-123").decode()
    response = app.test_client().get("/beheer", headers={"Authorization": "Basic " + valid})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Bevestigd verkocht" in body
    assert "Bestellingen en verkochte producten" in body
    assert "Bezoekersstatistieken" in body
    assert "Hoofdmenu en categorieën" in body
    assert "Producten en afbeeldingen" in body
    assert "Nog geen geverifieerde betaalde bestellingen beschikbaar" in body
    assert "Anonieme paginaweergaven" in body
    assert "Bewerkfunctie in voorbereiding" in body
