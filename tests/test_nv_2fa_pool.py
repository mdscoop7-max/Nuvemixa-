"""Tests voor de optionele 2FA-verbindingspool (NUVEMIXA_2FA_POOL).

Alle tests draaien tegen een echte PostgreSQL-server. Dezelfde tests draaien ook via PgBouncer in
transactiemodus wanneer NUVEMIXA_TEST_PGBOUNCER_DSN is ingesteld (in CI altijd). Zonder PostgreSQL
worden ze overgeslagen, net als de bestaande 2FA-tests.
"""
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pyotp
import pytest
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash

import nv_2fa_postgres as store
from nv_2fa import maak_herstelcodes

# De bestaande 2FA-tests draaien hieronder opnieuw, nu met de pool aan (en via PgBouncer).
from test_nv_2fa_postgres import (  # noqa: F401  (databases is een fixture)
    databases,
    parallel,
    seed,
    test_missing_record_and_wrong_key_fail_closed,
    test_password_success_preserves_newer_parallel_attempts,
    test_postgres_enrollment_qr_and_atomic_activation,
    test_replay_recovery_and_limits_concurrently,
)


@pytest.fixture(params=["postgres", "pgbouncer"])
def backend(request, databases, monkeypatch):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    bouncer = os.getenv("NUVEMIXA_TEST_PGBOUNCER_DSN")
    if request.param == "pgbouncer":
        if not bouncer:
            if os.getenv("NUVEMIXA_REQUIRE_PGBOUNCER") == "1":  # CI: nooit stilzwijgend overslaan
                pytest.fail("NUVEMIXA_REQUIRE_PGBOUNCER=1, maar NUVEMIXA_TEST_PGBOUNCER_DSN ontbreekt.")
            pytest.skip("Geen PgBouncer-testserver opgegeven.")
        assert conninfo_to_dict(bouncer).get("host") == "127.0.0.1"
    direct = databases()
    dbname = conninfo_to_dict(direct)["dbname"]
    with psycopg.connect(direct, autocommit=True) as db:
        for script in ("nv_2fa_postgres.sql", "nv_2fa_postgres_enrollment.sql"):
            db.execute(Path(script).read_text(encoding="utf-8"))
    dsn = make_conninfo(bouncer, dbname=dbname, sslmode="disable") if request.param == "pgbouncer" else direct
    opened = []

    def connect(target, **extra):
        opened.append(target)
        return psycopg.connect(target, prepare_threshold=None, **extra)

    monkeypatch.setenv("NUVEMIXA_2FA_DATABASE_URL", dsn)
    monkeypatch.setenv("NUVEMIXA_2FA_BACKEND", "postgres")
    monkeypatch.setenv(store.POOL_SWITCH, "1")
    monkeypatch.setattr(store, "connect", connect)
    store.reset_pool()
    yield SimpleNamespace(via=request.param, dsn=dsn, direct=direct, dbname=dbname, opened=opened)
    store.reset_pool()
    # PgBouncer houdt serververbindingen open; sluit ze zodat de testdatabase weg kan.
    with psycopg.connect(make_conninfo(direct, dbname="postgres"), autocommit=True) as db:
        db.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (dbname,))


@pytest.fixture
def pg_state(backend, monkeypatch):
    """Zelfde opzet als de fixture in test_nv_2fa_postgres, maar met de pool aan."""
    key = Fernet.generate_key()
    monkeypatch.setenv("NUVEMIXA_2FA_FERNET_KEY", key.decode("ascii"))
    codes, hashes = maak_herstelcodes(2)
    secret = pyotp.random_base32()
    ciphertext = Fernet(key).encrypt(json.dumps(
        {"enabled": True, "totp_secret": secret, "recovery_hashes": hashes}
    ).encode())
    return backend.dsn, key, secret, codes, ciphertext


def admin(backend):
    import psycopg
    return psycopg.connect(backend.direct, autocommit=True)


def test_switch_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on", " on "):
        monkeypatch.setenv(store.POOL_SWITCH, value)
        assert store.pool_enabled()
    for value in ("", "0", "false", "off", "no", "pool"):
        monkeypatch.setenv(store.POOL_SWITCH, value)
        assert not store.pool_enabled()
    monkeypatch.delenv(store.POOL_SWITCH)
    assert not store.pool_enabled()


def test_pool_is_off_by_default_and_old_behaviour_is_unchanged(pg_state, backend, monkeypatch):
    seed(pg_state[-1])
    store.reset_pool()
    backend.opened.clear()
    monkeypatch.delenv(store.POOL_SWITCH)
    assert [store.is_active() for _ in range(3)] == [True, True, True]
    assert store._pool is None
    assert len(backend.opened) == 3  # zonder schakelaar: een verbinding per controle, zoals altijd


def test_pool_reuses_connections_and_stays_within_limits(pg_state, backend):
    seed(pg_state[-1])
    store.reset_pool()
    backend.opened.clear()
    assert all(store.is_active() for _ in range(10))
    assert len(backend.opened) <= 2  # bij de start mag de pool één extra verbinding opbouwen
    settled = len(backend.opened)
    assert all(store.is_active() for _ in range(20))
    assert len(backend.opened) == settled  # daarna geen nieuwe verbindingen meer
    assert all(parallel(12, store.is_active))
    assert len(backend.opened) <= store.POOL_MAX_SIZE
    assert store._pool.get_stats()["pool_size"] <= store.POOL_MAX_SIZE


def test_state_is_read_live_on_every_call(pg_state, backend):
    _, key, _, _, ciphertext = pg_state
    seed(ciphertext)
    assert store.is_active() is True
    with admin(backend) as db:
        db.execute("DELETE FROM nuvemixa_auth.state")
    with pytest.raises(store.StorageUnavailable):  # geen onthouden "actief": direct weigeren
        store.is_active()
    with admin(backend) as db:
        db.execute("INSERT INTO nuvemixa_auth.state (ciphertext) VALUES (%s)", (b"niet-versleuteld",))
    with pytest.raises(store.StorageUnavailable):
        store.is_active()
    with admin(backend) as db:
        db.execute("UPDATE nuvemixa_auth.state SET ciphertext = %s", (ciphertext,))
    assert store.is_active() is True


def test_missing_key_and_wrong_key_fail_closed_with_pool(pg_state, monkeypatch):
    seed(pg_state[-1])
    monkeypatch.setenv("NUVEMIXA_2FA_FERNET_KEY", Fernet.generate_key().decode("ascii"))
    with pytest.raises(store.StorageUnavailable):
        store.is_active()
    monkeypatch.delenv("NUVEMIXA_2FA_FERNET_KEY")
    with pytest.raises(store.StorageUnavailable):
        store.is_active()
    monkeypatch.setenv("NUVEMIXA_2FA_BACKEND", "sqlite")
    with pytest.raises(store.StorageUnavailable):
        store.is_active()


def test_unfinished_enrollment_is_still_not_active(pg_state):
    with store.transaction() as db:
        db.execute("INSERT INTO nuvemixa_auth.state (required) VALUES (false)")
    assert store.is_active() is False  # inschrijving nog niet voltooid: niet actief, wel live gelezen


def test_database_offline_fails_closed_quickly_without_details(pg_state, monkeypatch, caplog):
    seed(pg_state[-1])
    assert store.is_active()
    store.reset_pool()

    def offline(*_args, **_kwargs):
        raise OSError("sensitive connection details")

    monkeypatch.setattr(store, "connect", offline)
    monkeypatch.setattr(store, "POOL_TIMEOUT", 0.5)
    caplog.set_level(logging.DEBUG, logger="psycopg.pool")
    for operation in (store.is_active, store.load, lambda: store.reserve_attempt("password", "x", 5, 60)):
        started = time.monotonic()
        with pytest.raises(store.StorageUnavailable) as caught:
            operation()
        assert time.monotonic() - started < 3
        assert "sensitive" not in str(caught.value)
    time.sleep(0.3)
    assert "sensitive" not in caplog.text


def test_dead_connection_is_replaced_once_for_reads_and_writes(pg_state, backend):
    seed(pg_state[-1])
    assert store.is_active()
    for operation in (store.is_active, lambda: store.register_totp_step(41)):
        with admin(backend) as db:
            db.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                       "WHERE datname = %s AND pid <> pg_backend_pid()", (backend.dbname,))
        time.sleep(0.1)
        assert operation() is True


def test_failed_transaction_is_rolled_back_and_connection_stays_usable(pg_state):
    seed(pg_state[-1])
    with pytest.raises(store.StorageUnavailable):
        with store.transaction() as db:
            db.execute("INSERT INTO nuvemixa_auth.replay (step) VALUES (77)")
            raise ValueError("fout in de aanroeper")
    with pytest.raises(store.StorageUnavailable):
        with store.transaction() as db:
            db.execute("SELECT 1/0")
    with store.transaction() as db:
        assert db.execute("SELECT count(*) FROM nuvemixa_auth.replay").fetchone() == (0,)
    assert store.register_totp_step(77) is True
    assert store.register_totp_step(77) is False
    assert store.is_active()


def test_settings_are_local_to_each_transaction(pg_state):
    seed(pg_state[-1])
    with store.transaction() as db:
        assert db.execute("SHOW statement_timeout").fetchone()[0] == "5s"
        assert db.execute("SHOW lock_timeout").fetchone()[0] == "3s"
    pool = store._pool_for(os.environ["NUVEMIXA_2FA_DATABASE_URL"])
    with pool.connection() as raw:  # buiten onze transactie mag er niets zijn achtergebleven
        assert raw.execute("SHOW statement_timeout").fetchone()[0] == "0"
        assert raw.execute("SHOW lock_timeout").fetchone()[0] == "0"


def test_exhausted_pool_fails_closed_instead_of_hanging(pg_state, monkeypatch):
    seed(pg_state[-1])
    monkeypatch.setattr(store, "POOL_TIMEOUT", 0.3)
    holders = [store.transaction() for _ in range(store.POOL_MAX_SIZE)]
    for holder in holders:
        holder.__enter__()
    try:
        started = time.monotonic()
        with pytest.raises(store.StorageUnavailable):
            store.is_active()
        with pytest.raises(store.StorageUnavailable):
            store.reserve_attempt("password", "x", 5, 60)
        assert time.monotonic() - started < 3
    finally:
        for holder in reversed(holders):
            holder.__exit__(None, None, None)
    assert store.is_active()


def test_row_locks_still_serialize_writers_through_the_pool(pg_state):
    _, _, _, codes, ciphertext = pg_state
    seed(ciphertext)
    release = threading.Event()
    entered = threading.Event()

    def holder():
        with store.transaction() as db:
            store._state(db, lock=True)
            entered.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(5)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(store.consume_recovery_code, codes[0])
        time.sleep(0.4)
        assert not pending.done()  # wacht op de vergrendeling (lock_timeout is 3 s)
        release.set()
        assert pending.result(timeout=5) is True
    thread.join()
    assert time.monotonic() - started < 3
    assert store.consume_recovery_code(codes[0]) is False


def test_flask_login_totp_and_outage_with_pool(pg_state, monkeypatch):
    from app import app
    _, _, secret, _, ciphertext = pg_state
    seed(ciphertext)
    password = "Fixture password only!"
    email = "fixture-admin@example.invalid"
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", email)
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", generate_password_hash(password))
    monkeypatch.setenv("SECRET_KEY", "only-for-test-env-presence")
    monkeypatch.setitem(app.config, "SECRET_KEY", Fernet.generate_key())
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setenv("NUVEMIXA_VISIT_COUNTER", "false")
    base = "http://localhost"

    def post(client, url, fields, csrf=True):
        if csrf:
            client.get(url)
            with client.session_transaction() as session:
                fields = dict(fields, _csrf_token=session["_tm_csrf"])
        return client.post(url, data=fields, headers={"Origin": base})

    a, b = app.test_client(), app.test_client()
    data = {"email": email, "password": password}
    assert post(a, "/admin/login", data, csrf=False).status_code == 403
    for client in (a, b):
        result = post(client, "/admin/login", data)
        assert (result.status_code, result.location) == (302, "/admin/2fa")
        assert client.get("/dashboard").status_code == 302
    codes = {"code": pyotp.TOTP(secret).now()}
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda c: post(c, "/admin/2fa", codes), (a, b)))
    assert sorted(result.status_code for result in results) == [200, 302]
    winner = a if results[0].status_code == 302 else b
    assert winner.get("/dashboard").status_code == 200
    assert winner.get("/dashboard").status_code == 200  # tweede aanvraag: opnieuw live gecontroleerd

    def offline(*_args, **_kwargs):
        raise OSError("sensitive connection details")

    store.reset_pool()
    monkeypatch.setattr(store, "connect", offline)
    monkeypatch.setattr(store, "POOL_TIMEOUT", 0.5)
    result = post(app.test_client(), "/admin/login", data)
    assert result.status_code == 503 and b"sensitive" not in result.data
    assert winner.get("/dashboard").status_code == 302  # fail-closed: geen toegang bij databasefout
    loser = b if winner is a else a
    assert loser.get("/admin/2fa").status_code == 503
