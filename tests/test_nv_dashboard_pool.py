"""Tests voor de optionele dashboard-verbindingspool (NUVEMIXA_DASHBOARD_POOL).

Alle tests draaien tegen een echte PostgreSQL-server met uitsluitend fictieve gegevens. Dezelfde
tests draaien ook via PgBouncer in transactiemodus wanneer NUVEMIXA_TEST_PGBOUNCER_DSN is ingesteld.
Rechtentests draaien alleen direct, omdat een sessierol niet door PgBouncer heen blijft staan.
"""
import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import nv_dashboard_postgres as store
from test_nv_2fa_postgres import databases  # noqa: F401  (fixture)

SECRET_HOST = "geheime-host.example.invalid"
SECRET_PASSWORD = "fixture-geheim-wachtwoord"


@pytest.fixture(params=["postgres", "pgbouncer"])
def backend(request, databases, monkeypatch):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    bouncer = os.getenv("NUVEMIXA_TEST_PGBOUNCER_DSN")
    if request.param == "pgbouncer":
        if not bouncer:
            if os.getenv("NUVEMIXA_REQUIRE_PGBOUNCER") == "1":
                pytest.fail("NUVEMIXA_REQUIRE_PGBOUNCER=1, maar NUVEMIXA_TEST_PGBOUNCER_DSN ontbreekt.")
            pytest.skip("Geen PgBouncer-testserver opgegeven.")
        assert conninfo_to_dict(bouncer).get("host") == "127.0.0.1"
    direct = databases()
    dbname = conninfo_to_dict(direct)["dbname"]
    role = "dashboard_pool_" + uuid4().hex[:12]
    with psycopg.connect(direct, autocommit=True) as db:
        db.execute(Path("nv_dashboard_postgres.sql").read_text(encoding="utf-8"))
        db.execute("CREATE SCHEMA nuvemixa_auth")
        db.execute("CREATE TABLE nuvemixa_auth.state (fixture text)")
        db.execute("INSERT INTO nuvemixa_auth.state VALUES ('onaangeroerd')")
        db.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA nuvemixa_dashboard TO {}").format(sql.Identifier(role)))
        db.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA nuvemixa_dashboard TO {}")
                   .format(sql.Identifier(role)))
        db.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA nuvemixa_dashboard TO {}")
                   .format(sql.Identifier(role)))
    dsn = make_conninfo(bouncer, dbname=dbname, sslmode="disable") if request.param == "pgbouncer" else direct
    opened = []

    def connect(target, **extra):
        db = psycopg.connect(target, prepare_threshold=None, **extra)
        if request.param == "postgres":
            with db.cursor() as cursor:
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        opened.append(db)
        return db

    monkeypatch.setenv("NUVEMIXA_DASHBOARD_DATABASE_URL", dsn)
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    monkeypatch.setenv(store.POOL_SWITCH, "1")
    monkeypatch.setattr(store, "new_connection", connect)
    store.reset_pool()
    yield SimpleNamespace(via=request.param, dsn=dsn, direct=direct, dbname=dbname, opened=opened, role=role)
    store.reset_pool()
    with psycopg.connect(make_conninfo(direct, dbname="postgres"), autocommit=True) as db:
        db.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (dbname,))


def admin(backend):
    import psycopg
    return psycopg.connect(backend.direct, autocommit=True)


def add_visit(marker, day="2026-01-01"):
    with store.application_db() as db:
        db.execute("INSERT INTO storefront_visits(traffic, day, marker, measured_at) VALUES (?,?,?,?)",
                   ("test", day, marker, "fixture"))


def visits(backend):
    with admin(backend) as db:
        return {row[0] for row in db.execute("SELECT marker FROM nuvemixa_dashboard.storefront_visits")}


def test_switch_values(monkeypatch):
    for value in ("1", "true", "YES", " on "):
        monkeypatch.setenv(store.POOL_SWITCH, value)
        assert store.pool_enabled() is True
    for value in ("", "0", "false", "uit"):
        monkeypatch.setenv(store.POOL_SWITCH, value)
        assert store.pool_enabled() is False
    monkeypatch.delenv(store.POOL_SWITCH)
    assert store.pool_enabled() is False


def test_pool_is_off_by_default_and_old_path_is_used(backend, monkeypatch):
    monkeypatch.delenv(store.POOL_SWITCH)
    calls = []
    from contextlib import contextmanager

    @contextmanager
    def old_connect():
        import psycopg
        calls.append(1)
        with psycopg.connect(backend.direct) as db:
            yield db

    monkeypatch.setattr(store, "connect", old_connect)
    with store.application_db() as db:
        assert db.execute("SHOW search_path").fetchone()[0].startswith("nuvemixa_dashboard")
    assert calls == [1] and backend.opened == [] and store._pool is None


def test_pool_reuses_connections_and_stays_within_limits(backend):
    for number in range(12):
        add_visit(f"seq-{number}")
    assert len(backend.opened) <= store.POOL_MAX_SIZE
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda number: add_visit(f"par-{number}"), range(40)))
    assert len(backend.opened) <= store.POOL_MAX_SIZE
    assert len(visits(backend)) == 52


def test_committed_writes_are_not_lost_and_visible_elsewhere(backend):
    with store.application_db() as db:
        db.execute("INSERT INTO customers(name, email, password_hash) VALUES (?,?,?)",
                   ("Fictieve Klant", "klant@example.invalid", "fixture-hash"))
    with admin(backend) as db:
        assert db.execute("SELECT name FROM nuvemixa_dashboard.customers").fetchone()[0] == "Fictieve Klant"
    with store.application_db(read_only=True) as db:
        row = db.execute("SELECT name, email FROM customers").fetchone()
        assert row["name"] == "Fictieve Klant" and row[1] == "klant@example.invalid"


def test_concurrent_writers_lose_nothing(backend):
    with admin(backend) as db:
        db.execute("INSERT INTO nuvemixa_dashboard.webshop_daily_visitors(day,visitor,first_seen,pageviews) "
                   "VALUES ('2026-01-01','v','x',0)")

    def bump(_):
        with store.application_db() as db:
            db.execute("UPDATE webshop_daily_visitors SET pageviews = pageviews + 1 WHERE visitor = ?", ("v",))

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(bump, range(60)))
    with admin(backend) as db:
        assert db.execute("SELECT pageviews FROM nuvemixa_dashboard.webshop_daily_visitors").fetchone()[0] == 60


def test_failed_transaction_rolls_back_completely_and_connection_stays_usable(backend):
    with pytest.raises(RuntimeError):
        with store.application_db() as db:
            db.execute("INSERT INTO storefront_visits VALUES ('t','2026-01-01','half','x')")
            raise RuntimeError("fixture")
    assert "half" not in visits(backend)
    add_visit("daarna")
    assert visits(backend) == {"daarna"} and len(backend.opened) <= store.POOL_MAX_SIZE


def test_integrity_and_sql_errors_are_mapped_and_roll_back(backend):
    add_visit("dubbel")
    with pytest.raises(sqlite3.IntegrityError):
        add_visit("dubbel")
    with pytest.raises(sqlite3.OperationalError):
        with store.application_db() as db:
            db.execute("INSERT INTO storefront_visits VALUES ('t','2026-01-01','voor','x')")
            db.execute("SELECT * FROM bestaat_niet")
    assert visits(backend) == {"dubbel"}
    add_visit("nog-steeds-bruikbaar")


def test_read_only_transactions_cannot_write(backend):
    with pytest.raises(sqlite3.OperationalError):
        with store.application_db(read_only=True) as db:
            db.execute("INSERT INTO storefront_visits VALUES ('t','2026-01-01','verboden','x')")
    assert visits(backend) == set()
    add_visit("schrijven-werkt-weer")


def test_settings_are_local_to_each_transaction(backend):
    with store.application_db() as db:
        assert db.execute("SHOW statement_timeout").fetchone()[0] == "5s"
        assert db.execute("SHOW lock_timeout").fetchone()[0] == "3s"
    for pooled in backend.opened:
        assert pooled.execute("SHOW statement_timeout").fetchone()[0] in ("0", "0ms")
        assert "nuvemixa_dashboard" not in pooled.execute("SHOW search_path").fetchone()[0]


def test_dead_connection_is_replaced_for_reads_and_writes(backend):
    add_visit("eerst")
    with admin(backend) as db:
        db.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                   "WHERE datname=%s AND pid<>pg_backend_pid()", (backend.dbname,))
    time.sleep(0.3)
    with store.application_db(read_only=True) as db:
        assert db.execute("SELECT count(*) FROM storefront_visits").fetchone()[0] == 1
    with admin(backend) as db:
        db.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                   "WHERE datname=%s AND pid<>pg_backend_pid()", (backend.dbname,))
    time.sleep(0.3)
    add_visit("tweede")
    assert visits(backend) == {"eerst", "tweede"}


def test_pool_recovers_after_process_restart_and_database_sleep(backend):
    add_visit("voor-herstart")
    store.reset_pool()  # nieuw proces na een Render-herstart: er bestaat nog geen pool
    assert store._pool is None
    add_visit("na-herstart")
    assert visits(backend) == {"voor-herstart", "na-herstart"}


def test_reset_pool_closes_every_connection(backend):
    add_visit("een")
    with admin(backend) as db:
        before = db.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                            (backend.dbname,)).fetchone()[0]
    assert before >= 1
    store.reset_pool()
    time.sleep(0.5)
    assert all(db.closed for db in backend.opened)


def test_exhausted_pool_fails_fast_instead_of_hanging(backend, monkeypatch):
    store.reset_pool()
    monkeypatch.setattr(store, "POOL_TIMEOUT", 0.5)
    release, entered = threading.Event(), threading.Barrier(store.POOL_MAX_SIZE + 1)

    def hold():
        with store.application_db():
            entered.wait(timeout=5)
            release.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=store.POOL_MAX_SIZE) as executor:
        holders = [executor.submit(hold) for _ in range(store.POOL_MAX_SIZE)]
        entered.wait(timeout=5)
        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match="niet beschikbaar"):
            add_visit("geen-plek")
        assert time.monotonic() - started < 3
        release.set()
        for holder in holders:
            holder.result(timeout=10)
    add_visit("weer-ruimte")
    assert visits(backend) == {"weer-ruimte"}


def test_database_offline_blocks_without_fallback_and_leaks_no_connection_details(monkeypatch, caplog):
    sqlite_touched = []
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: sqlite_touched.append(a) or pytest.fail("SQLite-terugval"))
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    monkeypatch.setenv(store.POOL_SWITCH, "1")
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_DATABASE_URL",
                       f"postgresql://gebruiker:{SECRET_PASSWORD}@127.0.0.1:9/db?sslmode=disable")
    monkeypatch.setattr(store, "POOL_TIMEOUT", 1.0)
    import psycopg
    monkeypatch.setattr(store, "new_connection", lambda dsn, **extra: psycopg.connect(
        dsn, connect_timeout=1, prepare_threshold=None, **extra))
    store.reset_pool()
    caplog.set_level(logging.DEBUG)
    started = time.monotonic()
    try:
        with pytest.raises(sqlite3.OperationalError, match="PostgreSQL-dashboardopslag is niet beschikbaar"):
            add_visit("offline")
        assert time.monotonic() - started < 5
        time.sleep(0.3)
    finally:
        store.reset_pool()
    assert sqlite_touched == []
    logged = caplog.text
    assert SECRET_PASSWORD not in logged and "gebruiker" not in logged and SECRET_HOST not in logged
    assert "127.0.0.1" not in logged


def test_missing_database_url_is_blocked_not_replaced(monkeypatch):
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    monkeypatch.setenv(store.POOL_SWITCH, "1")
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_DATABASE_URL", raising=False)
    with pytest.raises(sqlite3.OperationalError):
        add_visit("zonder-url")


def test_restricted_role_has_only_the_needed_rights(backend):
    if backend.via != "postgres":
        pytest.skip("Een sessierol blijft niet staan door PgBouncer in transactiemodus.")
    add_visit("rechten")
    for statement in ("DELETE FROM storefront_visits", "TRUNCATE storefront_visits",
                      "CREATE TABLE nieuw(a int)", "DROP TABLE storefront_visits",
                      "ALTER TABLE storefront_visits ADD COLUMN extra text"):
        with pytest.raises(sqlite3.OperationalError):
            with store.application_db() as db:
                db.execute(statement)
    for statement in ("SELECT * FROM nuvemixa_auth.state", "UPDATE nuvemixa_auth.state SET fixture='x'",
                      "INSERT INTO nuvemixa_auth.state VALUES ('x')"):
        with pytest.raises(sqlite3.OperationalError):
            with store.application_db() as db:
                db.execute(statement)
    with admin(backend) as db:
        assert db.execute("SELECT fixture FROM nuvemixa_auth.state").fetchall() == [("onaangeroerd",)]
    assert visits(backend) == {"rechten"}
    with store.application_db() as db:  # wel toegestaan: lezen, invoegen en wijzigen
        db.execute("UPDATE storefront_visits SET measured_at = ? WHERE marker = ?", ("nieuw", "rechten"))
        db.execute("INSERT INTO customers(name,email,password_hash) VALUES ('Fictief','a@example.invalid','h')")


def test_flask_routes_use_the_pool_without_touching_sqlite(backend, monkeypatch, tmp_path):
    import app
    import nv_dashboard_manager
    from test_system_check import administrator, CSRF_TOKEN  # noqa: F401
    monkeypatch.setattr(app, "_CUSTOMER_DB", tmp_path / "verboden-klanten.sqlite3")
    monkeypatch.setattr(nv_dashboard_manager, "DB", tmp_path / "verboden-dashboard.sqlite3")
    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "admin@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", "fixture-only")
    import nv_2fa_login
    monkeypatch.setattr(nv_2fa_login, "is_2fa_actief", lambda: True)
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_SECURE", False)
    client = app.app.test_client()
    with client.session_transaction() as saved:
        saved["nv_admin"] = True
        saved["_tm_csrf"] = CSRF_TOKEN

    def submit(route, **fields):
        response = client.post(route, data={"_csrf_token": CSRF_TOKEN, **fields})
        assert response.status_code == 303, (route, response.status_code)
        return response

    assert "toegevoegd" in submit("/admin/customers/create", name="Pool Klant", email="pool@example.invalid",
                                  password="fixture-lang-wachtwoord").location
    assert "toegevoegd" in submit("/admin/suppliers", name="Pool Leverancier",
                                  website="https://leverancier.example.invalid").location
    submit("/admin/nv/coupons", percentage="10")
    for section, text in (("klanten", b"Pool Klant"), ("leveranciers", b"Pool Leverancier"), ("kortingen", b"10%")):
        assert text in client.get("/dashboard?section=" + section).data
    assert not (tmp_path / "verboden-klanten.sqlite3").exists()
    assert not (tmp_path / "verboden-dashboard.sqlite3").exists()
    assert len(backend.opened) <= store.POOL_MAX_SIZE


def test_application_code_needs_no_delete_truncate_or_ddl_rights():
    """De beperkte rol krijgt alleen SELECT, INSERT en UPDATE; de code mag nooit meer vragen."""
    import re
    forbidden = re.compile(r"\b(DELETE\s+FROM|TRUNCATE|DROP\s+(TABLE|SCHEMA)|ALTER\s+TABLE\s+\w+\s+(ADD|DROP))", re.I)
    modules = ("app.py", "nv_dashboard_manager.py", "nuvemixa_admin_store.py", "nv_customer_activity.py",
               "nv_product_dossier.py", "nv_supplier_finder.py", "nv_viral_research.py", "nv_visits.py",
               "nv_webshop_visits.py", "nv_international.py", "nv_catalog_manager.py", "nv_seo_scan.py")
    for name in modules:
        text = Path(name).read_text(encoding="utf-8")
        if name == "nv_dashboard_manager.py":  # alleen de SQLite-migratie van de personeelstabel, niet in PostgreSQL
            text = re.sub(r'db\.execute\("ALTER TABLE staff ADD COLUMN [^\n]*\n', "", text)
        assert not forbidden.search(text), name
