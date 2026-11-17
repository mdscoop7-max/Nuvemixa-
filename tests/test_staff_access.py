"""Toegangstests: alleen de eigenaar (met 2FA) heeft beheerderstoegang; medewerkers staan standaard uit."""
import pytest
from werkzeug.security import generate_password_hash

import app as dashboard
import nv_2fa_login
import nv_dashboard_manager as manager
from test_system_check import administrator, CSRF_TOKEN

PUBLIC_ENDPOINTS = {"static", "admin_login", "admin_2fa", "admin_2fa_setup", "admin_logout"}


@pytest.fixture
def staffdb(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "DB", tmp_path / "staff.sqlite3")
    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "admin@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", generate_password_hash("fixture-owner-password"))
    monkeypatch.setattr(nv_2fa_login, "is_2fa_actief", lambda: True)
    monkeypatch.setitem(dashboard.app.config, "SESSION_COOKIE_SECURE", False)
    dashboard._ADMIN_LOGIN_ATTEMPTS.clear()      # pogingenteller per IP mag testen niet beïnvloeden
    ids = {}
    with manager.connect() as db:
        for name, role in (("medewerker", "employee"), ("beheerder", "admin")):
            db.execute("INSERT INTO staff(username,email,name,role,password_hash,session_version,active,permissions) VALUES(?,?,?,?,?,?,1,NULL)",
                       (name, f"{name}@example.invalid", name, role, generate_password_hash("fixture-staff-password"), "v1"))
            ids[name] = db.execute("SELECT id FROM staff WHERE username=?", (name,)).fetchone()["id"]
    return ids


def staff_client(staffdb, who):
    client = dashboard.app.test_client()
    with client.session_transaction() as saved:
        saved["nv_staff_id"], saved["nv_staff_version"], saved["_tm_csrf"] = staffdb[who], "v1", CSRF_TOKEN
    return client


def login(identity, password):
    client = dashboard.app.test_client()
    client.get("/admin/login")
    with client.session_transaction() as saved:
        token = saved["_tm_csrf"]
    return client, client.post("/admin/login", data={"email": identity, "password": password, "_csrf_token": token})


def admin_rules():
    for rule in dashboard.app.url_map.iter_rules():
        if rule.endpoint in PUBLIC_ENDPOINTS or "<" in rule.rule:
            continue
        if rule.rule.startswith(("/admin", "/dashboard", "/catalogus-overzicht")):
            yield rule


def test_staff_login_is_off_by_default(staffdb, monkeypatch):
    monkeypatch.delenv(manager.STAFF_SWITCH, raising=False)
    for who in ("medewerker", "beheerder"):
        client, response = login(who, "fixture-staff-password")
        assert response.status_code == 200 and b"klopt niet" in response.data, who
        with client.session_transaction() as saved:
            assert "nv_staff_id" not in saved
    assert manager.staff_auth("medewerker", "fixture-staff-password") is None


def test_existing_staff_session_is_ignored_when_off(staffdb, monkeypatch):
    monkeypatch.delenv(manager.STAFF_SWITCH, raising=False)
    for who in ("medewerker", "beheerder"):
        client = staff_client(staffdb, who)
        assert client.get("/dashboard").status_code in (302, 303)
        assert client.get("/dashboard?section=accountbeheer").status_code in (302, 303)
        assert client.get("/admin/merchant-preview").status_code in (302, 303, 403)


def test_staff_accounts_are_kept_when_off(staffdb, monkeypatch):
    monkeypatch.delenv(manager.STAFF_SWITCH, raising=False)
    assert {row["username"] for row in manager.team_rows()} == {"medewerker", "beheerder"}


def test_staff_with_admin_role_is_not_owner_even_when_on(staffdb, monkeypatch):
    monkeypatch.setenv(manager.STAFF_SWITCH, "on")
    client, response = login("beheerder", "fixture-staff-password")
    assert response.location == "/dashboard"          # inloggen kan, maar zonder eigenaarsrechten
    for section in ("accountbeheer", "instellingen", "monitoring", "woocommerce"):
        assert client.get(f"/dashboard?section={section}").status_code == 403, section
    post = client.post("/admin/nv/team", data={"_csrf_token": CSRF_TOKEN, "op": "create", "username": "nieuw",
                       "email": "n@example.invalid", "name": "N", "role": "admin", "password": "fixture-long-password"})
    assert post.status_code == 403
    assert client.get("/admin/integrations").status_code in (302, 303, 403)


def test_route_audit_anonymous_and_every_kind_of_staff(staffdb, monkeypatch):
    rules = list(admin_rules())
    assert len(rules) >= 10
    for switch in (None, "on"):
        if switch:
            monkeypatch.setenv(manager.STAFF_SWITCH, switch)
        else:
            monkeypatch.delenv(manager.STAFF_SWITCH, raising=False)
        clients = {"anoniem": dashboard.app.test_client()}
        for who in ("medewerker", "beheerder"):
            clients[who] = staff_client(staffdb, who)
        for name, client in clients.items():
            for rule in rules:
                for method in sorted(rule.methods & {"GET", "POST"}):
                    data = {"_csrf_token": CSRF_TOKEN} if method == "POST" else None
                    response = client.open(rule.rule, method=method, data=data)
                    owner_only = rule.rule.startswith(("/admin/nv/team", "/admin/integrations", "/admin/suppliers",
                                                        "/admin/research", "/admin/monitoring", "/admin/mollie", "/admin/rankfix",
                                                        "/admin/customers", "/admin/supplier-feed", "/admin/nv/db-diagnose",
                                                        "/admin/commerce", "/admin/merchant-feed"))
                    ok = response.status_code in (301, 302, 303, 307, 308, 400, 401, 403, 404, 405, 429)
                    if not ok and (name == "anoniem" or owner_only):
                        pytest.fail(f"{name}/{switch}: {method} {rule.rule} -> {response.status_code}")
                    assert response.status_code < 500, (name, method, rule.rule, response.status_code)


def test_customer_session_gives_no_dashboard_access(staffdb):
    client = dashboard.app.test_client()
    with client.session_transaction() as saved:
        saved["customer_id"] = 1
        saved["nv_customer_id"] = 1
    assert client.get("/dashboard").status_code in (302, 303)
    assert client.get("/dashboard?section=accountbeheer").status_code in (302, 303)


def test_owner_cannot_be_locked_out(staffdb, administrator, monkeypatch):
    monkeypatch.delenv(manager.STAFF_SWITCH, raising=False)
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", generate_password_hash("fixture-owner-password"))
    assert administrator.get("/dashboard?section=accountbeheer").status_code == 200
    assert administrator.get("/dashboard?section=dashboard").status_code == 200
    client, response = login("admin@example.invalid", "fixture-owner-password")
    assert response.location == "/admin/2fa"           # eigenaar loopt nog door de tweede stap
    client, response = login("admin@example.invalid", "verkeerd-wachtwoord")
    assert response.status_code == 200 and b"klopt niet" in response.data
    # Accounts uitschakelen blijft mogelijk, nieuwe aanmaken niet
    off = administrator.post("/admin/nv/team", data={"_csrf_token": CSRF_TOKEN, "op": "create", "username": "x1y",
                             "email": "x@example.invalid", "name": "X", "role": "employee", "password": "fixture-long-password"})
    assert off.status_code == 303
    assert "x1y" not in {row["username"] for row in manager.team_rows()}
    disable = administrator.post("/admin/nv/team", data={"_csrf_token": CSRF_TOKEN, "op": "disable", "id": str(staffdb["medewerker"])})
    assert disable.status_code == 303


@pytest.mark.parametrize("value", ["", "off", "0", "false", "ON ", "aan", "yes", "1", "true", "onn"])
def test_switch_fails_closed_on_missing_or_wrong_values(staffdb, monkeypatch, value):
    if value.strip().lower() == "on":
        monkeypatch.setenv(manager.STAFF_SWITCH, value)
        assert manager.staff_login_enabled() is True      # alleen exact "on" (hoofdletters en spaties genegeerd)
        return
    monkeypatch.setenv(manager.STAFF_SWITCH, value)
    assert manager.staff_login_enabled() is False
    assert manager.staff_auth("medewerker", "fixture-staff-password") is None
    client, response = login("beheerder", "fixture-staff-password")
    assert b"klopt niet" in response.data
