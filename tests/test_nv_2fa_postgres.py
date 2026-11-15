"""Opt-in integration tests for a disposable, loopback PostgreSQL server."""

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import time
from uuid import uuid4

from cryptography.fernet import Fernet
import pyotp
import pytest
from werkzeug.security import generate_password_hash

import nv_2fa_postgres as store
from nv_2fa import maak_herstelcodes
from migrate_nuvemixa_2fa_postgres import REQUIRED_FILES, restore_backup


@pytest.fixture
def databases():
    dsn = os.getenv("NUVEMIXA_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Loopback PostgreSQL-testserver niet opgegeven.")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    options = conninfo_to_dict(dsn)
    assert options.get("host") == "127.0.0.1"
    assert not options.get("hostaddr") and not options.get("service")
    admin_dsn = make_conninfo(dsn, dbname="postgres")
    created = []

    def new_database():
        name = "nv_fixture_" + uuid4().hex
        with psycopg.connect(admin_dsn, autocommit=True) as db:
            db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        created.append(name)
        return make_conninfo(dsn, dbname=name, sslmode="disable")

    yield new_database

    if created and os.getenv("NUVEMIXA_TEST_POSTGRES_KEEP_DATABASES") != "1":
        with psycopg.connect(admin_dsn, autocommit=True) as db:
            for name in created:
                db.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def pg_state(databases, monkeypatch):
    import psycopg

    dsn = databases()
    with psycopg.connect(dsn, autocommit=True) as db:
        for script in ("nv_2fa_postgres.sql", "nv_2fa_postgres_enrollment.sql"):
            db.execute(Path(script).read_text(encoding="utf-8"))
    monkeypatch.setenv("NUVEMIXA_2FA_DATABASE_URL", dsn)
    monkeypatch.setenv("NUVEMIXA_2FA_BACKEND", "postgres")
    monkeypatch.setattr(store, "connect", psycopg.connect)
    key = Fernet.generate_key()
    monkeypatch.setenv("NUVEMIXA_2FA_FERNET_KEY", key.decode("ascii"))
    codes, hashes = maak_herstelcodes(2)
    secret = pyotp.random_base32()
    ciphertext = Fernet(key).encrypt(json.dumps(
        {"enabled": True, "totp_secret": secret, "recovery_hashes": hashes}
    ).encode())
    return dsn, key, secret, codes, ciphertext


def seed(ciphertext):
    with store.transaction() as db:
        db.execute("INSERT INTO nuvemixa_auth.state (ciphertext) VALUES (%s)", (ciphertext,))


def parallel(n, operation):
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(lambda _: operation(), range(n)))


def test_replay_recovery_and_limits_concurrently(pg_state):
    _, _, _, codes, ciphertext = pg_state
    seed(ciphertext)
    assert sum(parallel(8, lambda: store.register_totp_step(999))) == 1
    assert sum(parallel(8, lambda: store.consume_recovery_code(codes[0]))) == 1
    assert len(store.load()["recovery_hashes"]) == 1
    assert sum(ticket is not None for ticket in parallel(
        8, lambda: store.reserve_attempt("2fa", "fixture", 5, 300))) == 5
    tickets = parallel(9, lambda: store.reserve_attempt("password", "fixture", 6, 900))
    assert sum(ticket is not None for ticket in tickets) == 6
    with store.transaction() as db:
        db.execute("UPDATE nuvemixa_auth.attempts SET occurred_at = occurred_at - 901")
    assert store.reserve_attempt("password", "fixture", 6, 900)
    assert store.reserve_attempt("2fa", "fixture", 5, 300)


def test_password_success_preserves_newer_parallel_attempts(pg_state):
    seed(pg_state[-1])
    earlier = store.reserve_attempt("password", "fixture", 6, 900)
    store.fail_password_attempt(earlier)
    current = store.reserve_attempt("password", "fixture", 6, 900)
    newer = store.reserve_attempt("password", "fixture", 6, 900)
    store.fail_password_attempt(newer)
    store.finish_password_attempt("fixture", current)
    with store.transaction() as db:
        assert db.execute("SELECT ticket FROM nuvemixa_auth.attempts").fetchall() == [(newer,)]


def test_flask_login_csrf_totp_and_database_outage(pg_state, monkeypatch):
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
    assert post(a, "/admin/2fa", codes, csrf=False).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: post(c, "/admin/2fa", codes), (a, b)))
    assert sorted(result.status_code for result in results) == [200, 302]
    winner = a if results[0].status_code == 302 else b
    assert winner.get("/dashboard").status_code == 200
    def offline(_):
        raise OSError("sensitive connection details")
    monkeypatch.setattr(store, "connect", offline)
    result = post(app.test_client(), "/admin/login", data)
    assert result.status_code == 503 and b"sensitive" not in result.data
    assert winner.get("/dashboard").status_code == 302
    loser = b if winner is a else a
    assert loser.get("/admin/2fa").status_code == 503


def test_missing_record_and_wrong_key_fail_closed(pg_state, monkeypatch):
    from nv_2fa_login import is_2fa_actief

    with pytest.raises(store.StorageUnavailable):
        is_2fa_actief()
    seed(pg_state[-1])
    monkeypatch.setenv("NUVEMIXA_2FA_FERNET_KEY", Fernet.generate_key().decode("ascii"))
    with pytest.raises(store.StorageUnavailable):
        is_2fa_actief()


def fixture_bundle(root, encryption_key, ciphertext):
    bundle = root / "bundle"
    bundle.mkdir()
    (bundle / "nv_2fa.key").write_bytes(encryption_key)
    (bundle / "nv_2fa_secrets.json").write_bytes(ciphertext)
    (bundle / "nv_2fa_verplicht.flag").write_bytes(b"2FA_REQUIRED\n")
    with closing(sqlite3.connect(bundle / "nv_2fa_replay.sqlite3")) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE gebruikte_stappen (stap INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO gebruikte_stappen VALUES (123)")
        db.commit()
    with closing(sqlite3.connect(bundle / "nv_2fa_attempts.sqlite3")) as db:
        db.execute("CREATE TABLE pogingen (sleutel TEXT, tijdstip REAL)")
        db.executemany("INSERT INTO pogingen VALUES (?, ?)", [
            ("old", time.time() - 400), ("recent", time.time()),
        ])
        db.commit()
    entries = []
    for name in REQUIRED_FILES:
        content = (bundle / name).read_bytes()
        entries.append({"name": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    manifest = json.dumps({"format": 1, "entries": entries}).encode()
    (bundle / "manifest.json").write_bytes(manifest)
    checksum = root / "independent.sha256"
    checksum.write_text(hashlib.sha256(manifest).hexdigest() + "\n", encoding="ascii")
    return bundle, checksum


def test_verified_import_and_dump_restore(pg_state, databases, monkeypatch, tmp_path):
    dsn, key, secret, codes, ciphertext = pg_state
    bundle, checksum = fixture_bundle(tmp_path, key, ciphertext)
    assert (bundle / "nv_2fa_replay.sqlite3").read_bytes()[18:20] == b"\x02\x02"
    restore_backup(bundle, checksum)
    with pytest.raises(store.StorageUnavailable):
        store.load()
    bad_file = bundle / "nv_2fa_verplicht.flag"
    original = bad_file.read_bytes()
    bad_file.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        restore_backup(bundle, checksum, apply=True)
    bad_file.write_bytes(original)
    restore_backup(bundle, checksum, apply=True)
    with pytest.raises(store.StorageUnavailable):
        restore_backup(bundle, checksum, apply=True)
    with store.transaction() as db:
        assert db.execute("SELECT ciphertext FROM nuvemixa_auth.state").fetchone()[0] == ciphertext
        assert db.execute("SELECT count(*) FROM nuvemixa_auth.attempts").fetchone()[0] == 1
    assert not store.register_totp_step(123)
    assert store.consume_recovery_code(codes[0])
    assert not store.consume_recovery_code(codes[0])

    # Fixture DSNs have no secrets. Production dump credentials belong in libpq's secret input.
    dump = subprocess.run(["pg_dump", "--schema=nuvemixa_auth", "-Fc", "--dbname", dsn],
                          check=True, capture_output=True).stdout
    restored = databases()
    subprocess.run(["pg_restore", "--exit-on-error", "--single-transaction", "--dbname", restored],
                   input=dump, check=True, capture_output=True)
    monkeypatch.setenv("NUVEMIXA_2FA_DATABASE_URL", restored)
    assert store.load()["totp_secret"] == secret
    assert not store.consume_recovery_code(codes[0])
    assert not store.register_totp_step(123)
    assert store.consume_recovery_code(codes[1])

def test_postgres_enrollment_qr_and_atomic_activation(pg_state, monkeypatch):
    import base64
    import re

    from app import app

    _, key, secret, _, _ = pg_state
    with store.transaction() as db:
        db.execute("INSERT INTO nuvemixa_auth.state (required) VALUES (false)")
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "new-fixture@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", generate_password_hash("fixture-only"))
    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setitem(app.config, "SECRET_KEY", Fernet.generate_key())
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr("nv_2fa.maak_geheime_sleutel", lambda: secret)

    client = app.test_client()
    setup = "/admin/2fa/setup"

    def post(path, **data):
        with client.session_transaction() as session:
            data["_csrf_token"] = session["_tm_csrf"]
        return client.post(path, data=data, headers={"Origin": "http://localhost"})

    client.get("/admin/login")
    assert post("/admin/login", email="new-fixture@example.invalid", password="fixture-only").location == setup
    assert client.post(setup, data={"action": "start", "password": "fixture-only"}).status_code == 403
    assert client.get(setup).status_code == 200
    assert post(setup, action="start", password="wrong").status_code == 200
    assert post(setup, action="start", password="fixture-only").status_code == 303
    qr = client.get(setup)
    assert qr.headers["Cache-Control"] == "no-store"
    match = re.search(rb"data:image/png;base64,([A-Za-z0-9+/=]+)", qr.data)
    assert match and base64.b64decode(match[1]).startswith(b"\x89PNG\r\n\x1a\n")
    assert post(setup, action="activate", code="123").status_code == 200
    totp = pyotp.TOTP(secret)
    assert post(setup, action="activate", code=totp.now()).status_code == 200
    assert client.get("/dashboard").status_code == 200
    with store.transaction() as db:
        active, pending, encrypted = db.execute(
            "SELECT required, pending, ciphertext FROM nuvemixa_auth.state"
        ).fetchone()
        assert active and pending is None and secret.encode() not in encrypted
        assert db.execute("SELECT count(*) FROM nuvemixa_auth.replay").fetchone() == (1,)
    assert len(store.decode(encrypted, key)["recovery_hashes"]) == 10
    assert not store.activate_pending("expired", secret, [], int(time.time()) // 30 + 1)
