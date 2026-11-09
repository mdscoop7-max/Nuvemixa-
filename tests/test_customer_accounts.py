"""Local customer account safety regression checks."""
import os
from pathlib import Path

def test_account_register_login_and_logout(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDMIX_ACCOUNTS_DB", str(tmp_path / "customers.sqlite3"))
    from app import app
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.get("/registreren")
    assert response.status_code == 200
    with client.session_transaction() as session:
        token = session["_tm_csrf"]
    rejected = client.post("/registreren", data={"name":"Tester","email":"test@example.com","password":"strong-password-123"})
    assert rejected.status_code == 403
    registered = client.post("/registreren", data={"_csrf_token":token,"name":"Tester","email":"test@example.com","password":"strong-password-123"})
    assert registered.status_code == 303
    account = client.get("/account")
    assert b"Tester" in account.data
    assert "no-store" in account.headers["Cache-Control"]
    with client.session_transaction() as session:
        token = session["_tm_csrf"]
    logged_out = client.post("/uitloggen", data={"_csrf_token":token})
    assert logged_out.status_code == 303
    assert b"Account aanmaken" in client.get("/account").data
    client.get("/inloggen")
    with client.session_transaction() as session:
        token = session["_tm_csrf"]
    logged_in = client.post("/inloggen", data={"_csrf_token":token,"email":"test@example.com","password":"strong-password-123"})
    assert logged_in.status_code == 303

def test_password_is_hashed_and_attempts_limited(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDMIX_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    from customer_accounts import create_account, authenticate, _db
    ident = create_account("Tester","test2@example.com","strong-password-456")
    assert ident
    with _db() as db:
        value = db.execute("SELECT password_hash FROM accounts WHERE id=?", (ident,)).fetchone()["password_hash"]
        assert "strong-password-456" not in value
        assert value.startswith("scrypt:")
    for _ in range(5):
        account, limited = authenticate("test2@example.com","wrong-password","127.0.0.1")
        assert account is None
    account, limited = authenticate("test2@example.com","strong-password-456","127.0.0.1")
    assert limited and account is None
