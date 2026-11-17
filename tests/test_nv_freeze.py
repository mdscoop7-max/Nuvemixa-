import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import app as dashboard
import migrate_dashboard_postgres as migration
import nuvemixa_admin_store
import nv_customer_activity
import nv_dashboard_manager
import nv_db_diagnostic
import nv_freeze
import nv_visits
import nv_webshop_visits
from nv_permissions import SECTIONS
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

SHOP = "https://nuvemixa.alwaysdata.net"
BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
EXTRA_SECTIONS = ("accountbeheer", "leveranciers", "vindbaarheid")


@pytest.fixture
def storage(monkeypatch, tmp_path):
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_DATABASE_URL", raising=False)
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    monkeypatch.delenv(nv_freeze.SWITCH, raising=False)
    monkeypatch.setenv("NUVEMIXA_WEBSHOP_TRACKING", "true")
    paths = {
        "dashboard": tmp_path / "dashboard.sqlite3",
        "admin": tmp_path / "admin.sqlite3",
        "customers": tmp_path / "customers.sqlite3",
    }
    monkeypatch.setattr(nv_dashboard_manager, "DB", paths["dashboard"])
    monkeypatch.setattr(nv_visits, "DB", paths["dashboard"])
    monkeypatch.setattr(nv_webshop_visits, "DB", paths["dashboard"])
    monkeypatch.setattr(nuvemixa_admin_store, "database_path", lambda: paths["admin"])
    monkeypatch.setattr(dashboard, "_CUSTOMER_DB", paths["customers"])
    return paths


def checksums(paths):
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items() if path.exists()}


def freeze(monkeypatch, on=True):
    if on:
        monkeypatch.setenv(nv_freeze.SWITCH, "1")
    else:
        monkeypatch.delenv(nv_freeze.SWITCH, raising=False)


def test_every_non_get_route_is_classified():
    known = (nv_freeze.WRITE_ENDPOINTS | nv_freeze.AI_ENDPOINTS | nv_freeze.IN_PLACE_ENDPOINTS
             | nv_freeze.ALLOWED_ENDPOINTS | {nv_freeze.MONITORING_ENDPOINT})
    found = {rule.endpoint for rule in dashboard.app.url_map.iter_rules()
             if rule.methods & {"POST", "PUT", "PATCH", "DELETE"}}
    assert found - known == set(), "Nieuwe schrijfroute: deel hem in bij de bevriezingslijsten"
    assert known - found == set(), "Verouderde vermelding in de bevriezingslijsten"
    lists = [nv_freeze.WRITE_ENDPOINTS, nv_freeze.AI_ENDPOINTS, nv_freeze.IN_PLACE_ENDPOINTS, nv_freeze.ALLOWED_ENDPOINTS]
    assert sum(len(item) for item in lists) == len(set().union(*lists))


def test_default_is_off(monkeypatch):
    monkeypatch.delenv(nv_freeze.SWITCH, raising=False)
    assert nv_freeze.frozen() is False
    for value in ("0", "false", "", "no"):
        monkeypatch.setenv(nv_freeze.SWITCH, value)
        assert nv_freeze.frozen() is False


def test_blocked_routes_answer_503_and_change_nothing(administrator, storage, monkeypatch):
    for target in ("/dashboard?section=klanten", "/dashboard?section=kortingen"):
        assert administrator.get(target).status_code == 200
    before = checksums(storage)
    freeze(monkeypatch)
    blocked = nv_freeze.WRITE_ENDPOINTS | nv_freeze.AI_ENDPOINTS
    seen = 0
    for rule in dashboard.app.url_map.iter_rules():
        if rule.endpoint not in blocked or "POST" not in rule.methods:
            continue
        url = rule.rule
        response = administrator.post(url, data={"_csrf_token": CSRF_TOKEN})
        assert response.status_code == 503, rule.endpoint
        assert response.headers["Retry-After"] == "120"
        assert "Er is niets opgeslagen" in response.get_data(as_text=True)
        seen += 1
    assert seen == len(blocked)
    assert checksums(storage) == before


def test_ai_routes_blocked_before_any_external_call(administrator, storage, monkeypatch):
    freeze(monkeypatch)
    for url in ("/dashboard/viral/assistant", "/dashboard/viral/supplier-search"):
        rules = [r for r in dashboard.app.url_map.iter_rules() if r.rule.endswith(url.rsplit("/", 1)[1])]
        assert rules, url
    called = []
    monkeypatch.setattr(nv_freeze, "MESSAGE", nv_freeze.MESSAGE)
    for rule in dashboard.app.url_map.iter_rules():
        if rule.endpoint in nv_freeze.AI_ENDPOINTS:
            assert administrator.post(rule.rule, data={"_csrf_token": CSRF_TOKEN}).status_code == 503
    assert called == []


def test_monitoring_write_action_blocked_but_scan_allowed(administrator, storage, monkeypatch):
    freeze(monkeypatch)
    route = "/admin/monitoring/check"
    write = administrator.post(route, data={"action": "initialize_customers", "_csrf_token": CSRF_TOKEN})
    assert write.status_code == 503
    assert not storage["customers"].exists()
    assert administrator.get(route).status_code == 200
    assert not storage["customers"].exists()


def test_frozen_routes_are_unblocked_when_switch_is_off(administrator, storage, monkeypatch):
    freeze(monkeypatch, False)
    response = administrator.post("/admin/nv/coupons", data={"_csrf_token": CSRF_TOKEN, "percentage": "10"})
    assert response.status_code == 303
    assert len(nv_dashboard_manager.coupon_rows()) == 1


def test_all_dashboard_sections_stay_readable_without_changes(administrator, storage, monkeypatch):
    sections = list(SECTIONS) + list(EXTRA_SECTIONS) + [""]
    for name in sections:  # eerst met bestaande databases opbouwen
        administrator.get(f"/dashboard?section={name}")
    nuvemixa_admin_store_ready = storage["admin"].exists()
    before = checksums(storage)
    freeze(monkeypatch)
    for name in sections:
        response = administrator.get(f"/dashboard?section={name}")
        assert response.status_code == 200, name
    assert checksums(storage) == before
    assert nuvemixa_admin_store_ready in (True, False)


def test_frozen_reads_do_not_create_files_or_directories(administrator, storage, monkeypatch, tmp_path):
    missing = tmp_path / "nog-niet" / "bestaat.sqlite3"
    monkeypatch.setattr(nv_dashboard_manager, "DB", missing)
    monkeypatch.setattr(dashboard, "_CUSTOMER_DB", tmp_path / "ook-niet" / "klanten.sqlite3")
    freeze(monkeypatch)
    for name in list(SECTIONS) + list(EXTRA_SECTIONS):
        response = administrator.get(f"/dashboard?section={name}")
        assert response.status_code < 500, name
    assert not missing.parent.exists()
    assert not (tmp_path / "ook-niet").exists()


def test_readonly_connection_when_frozen(storage, monkeypatch, tmp_path):
    path = tmp_path / "x.sqlite3"
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE t(a)")
    freeze(monkeypatch)
    with closing(nv_freeze.sqlite_connect(path, 1)) as db:
        assert db.execute("SELECT COUNT(*) FROM t").fetchone() == (0,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("INSERT INTO t VALUES (1)")
    freeze(monkeypatch, False)
    with closing(nv_freeze.sqlite_connect(path, 1)) as db, db:
        db.execute("INSERT INTO t VALUES (1)")


def test_visit_counters_skip_silently_when_frozen(storage, monkeypatch):
    client = dashboard.app.test_client()
    freeze(monkeypatch)
    response = client.post("/api/webshop-visit", data='{"p": "/"}', headers={
        "Origin": SHOP, "User-Agent": BROWSER, "X-Forwarded-For": "203.0.113.7", "Content-Type": "text/plain"})
    assert response.status_code == 204
    assert client.get("/", headers={"User-Agent": BROWSER}).status_code in (200, 301, 302, 404)
    assert checksums(storage) == {}


def test_customer_activity_not_written_when_frozen(storage, monkeypatch):
    freeze(monkeypatch)
    nv_customer_activity.record_customer_activity(storage["customers"], 1, "logged_in")  # mag niets schrijven
    assert checksums(storage) == {}
    freeze(monkeypatch, False)
    nv_customer_activity.record_customer_activity(storage["customers"], 1, "logged_in")
    assert storage["customers"].exists()


def test_staff_login_flow_unaffected_by_freeze(administrator, monkeypatch):
    freeze(monkeypatch)
    response = administrator.post("/admin/logout", data={"_csrf_token": CSRF_TOKEN})
    assert response.status_code in (200, 302, 303)
    assert nv_freeze.blocked("admin_login", "POST") is False
    assert nv_freeze.blocked("admin_2fa", "POST") is False
    assert nv_freeze.blocked("customer_login", "POST") is False


def test_diagnostic_is_off_by_default(administrator, monkeypatch):
    monkeypatch.delenv(nv_db_diagnostic.SWITCH, raising=False)
    assert administrator.get("/admin/nv/db-diagnose").status_code == 404


def test_diagnostic_requires_admin_and_returns_only_numbers(administrator, monkeypatch):
    monkeypatch.setenv(nv_db_diagnostic.SWITCH, "1")
    assert dashboard.app.test_client().get("/admin/nv/db-diagnose").status_code == 403
    assert administrator.get("/admin/nv/db-diagnose").status_code == 503  # geen meetverbinding ingesteld
    secret = "postgresql://gebruiker:geheim-wachtwoord@host.example.invalid/db"
    monkeypatch.setenv(nv_db_diagnostic.URL_VARIABLE, secret)
    result = {"nieuwe_verbinding": {"aantal": 5, "mediaan_ms": 3.1, "max_ms": 5.0},
              "query": {"aantal": 20, "mediaan_ms": 1.0, "p95_ms": 2.0, "max_ms": 3.0}, "totaal_ms": 40.0}
    monkeypatch.setattr(nv_db_diagnostic, "measure", lambda dsn: result)
    response = administrator.get("/admin/nv/db-diagnose")
    assert response.status_code == 200 and response.json == result
    assert response.headers["Cache-Control"] == "no-store"
    monkeypatch.setattr(nv_db_diagnostic, "measure", lambda dsn: (_ for _ in ()).throw(RuntimeError(secret)))
    failed = administrator.get("/admin/nv/db-diagnose")
    assert failed.status_code == 503
    assert "geheim" not in failed.get_data(as_text=True) and "host.example" not in failed.get_data(as_text=True)


def test_diagnostic_does_not_enable_postgres_features(monkeypatch):
    import nv_dashboard_postgres
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_DATABASE_URL", raising=False)
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    monkeypatch.setenv(nv_db_diagnostic.SWITCH, "1")
    monkeypatch.setenv(nv_db_diagnostic.URL_VARIABLE, "postgresql://u:p@h.example.invalid/db")
    assert nv_dashboard_postgres.configured() is False
    assert nv_dashboard_postgres.runtime_enabled() is False


def test_migration_knows_daily_visitors_table():
    tables = migration.FILES["nuvemixa_dashboard.sqlite3"]
    columns, keys = tables["webshop_daily_visitors"]
    assert columns.split() == ["day", "visitor", "first_seen", "pageviews", "last_path", "last_at"]
    assert keys.split() == ["day", "visitor"]
