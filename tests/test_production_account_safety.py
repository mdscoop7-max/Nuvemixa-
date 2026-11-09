"""Launch safety: prototype account and administration must remain private."""
from app import app

def test_prototype_account_login_disabled_on_deployment(monkeypatch):
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("TRENDMIX_ACCOUNTS_ENABLED", "true")
    client=app.test_client()
    assert client.get("/registreren").status_code == 404
    assert client.get("/inloggen").status_code == 404

def test_local_accounts_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.setenv("TRENDMIX_ACCOUNTS_ENABLED", "false")
    client=app.test_client()
    assert client.get("/registreren").status_code == 404
    assert client.get("/inloggen").status_code == 404

def test_admin_workspace_disabled_on_deployment(monkeypatch):
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "admin")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "private-password-longer-than-16")
    client=app.test_client()
    assert client.get("/beheer/productconcepten").status_code == 404
    assert client.get("/beheer/klantenservice").status_code == 404
