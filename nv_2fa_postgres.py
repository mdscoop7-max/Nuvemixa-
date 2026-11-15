"""PostgreSQL storage for primary administrator 2FA."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
from contextlib import contextmanager

from cryptography.fernet import Fernet, InvalidToken

from nv_2fa import gebruik_herstelcode


class StorageUnavailable(RuntimeError):
    """Safe error for authentication paths and logs."""


def enabled():
    return bool(os.getenv("NUVEMIXA_2FA_BACKEND") or os.getenv("NUVEMIXA_2FA_DATABASE_URL"))


def connect(dsn):
    import certifi
    import psycopg

    return psycopg.connect(
        dsn, sslmode="verify-full", sslrootcert=certifi.where(),
        connect_timeout=5, prepare_threshold=None,
    )


@contextmanager
def transaction():
    try:
        dsn = os.environ["NUVEMIXA_2FA_DATABASE_URL"]
        if os.getenv("NUVEMIXA_2FA_BACKEND", "postgres") != "postgres" or not dsn:
            raise ValueError("Invalid backend")
        with connect(dsn) as db:
            db.execute("SET LOCAL statement_timeout = '5s'")
            db.execute("SET LOCAL lock_timeout = '3s'")
            yield db
    except Exception:
        # Driver/configuration errors can include connection details.
        raise StorageUnavailable("Beveiligde PostgreSQL-opslag is niet beschikbaar.") from None


def key():
    return os.environ["NUVEMIXA_2FA_FERNET_KEY"].encode("ascii")


def decode(ciphertext, encryption_key):
    try:
        payload = json.loads(Fernet(encryption_key).decrypt(bytes(ciphertext)))
        secret = payload["totp_secret"]
        hashes = payload["recovery_hashes"]
        if (
            payload["enabled"] is not True
            or not isinstance(secret, str) or not secret
            or not isinstance(hashes, list)
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)
        ):
            raise ValueError("Invalid payload")
        if not base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True):
            raise ValueError("Invalid TOTP seed")
        return payload
    except (InvalidToken, ValueError, TypeError, KeyError, UnicodeError, binascii.Error):
        raise StorageUnavailable("Actieve 2FA-opslag kan niet worden gevalideerd.") from None


def _state(db, lock=False):
    sql = "SELECT required, ciphertext FROM nuvemixa_auth.state WHERE singleton"
    row = db.execute(sql + (" FOR UPDATE" if lock else "")).fetchone()
    if row is None:
        raise StorageUnavailable("Verplichte 2FA-opslag ontbreekt.")
    return row


def _active(db, lock=False):
    required, ciphertext = _state(db, lock)
    if not required:
        raise StorageUnavailable("2FA-inschrijving is nog niet voltooid.")
    return ciphertext


def is_active():
    with transaction() as db:
        required, ciphertext = _state(db)
        encryption_key = key()
        if required:
            decode(ciphertext, encryption_key)
        else:
            Fernet(encryption_key)
        return required


def store_pending(token, secret):
    with transaction() as db:
        required, _ = _state(db, lock=True)
        if required:
            raise StorageUnavailable("2FA is al actief.")
        ciphertext = Fernet(key()).encrypt(json.dumps({"token": token, "totp_secret": secret}).encode())
        db.execute(
            "UPDATE nuvemixa_auth.state SET pending = %s, "
            "pending_until = clock_timestamp() + interval '10 minutes' WHERE singleton",
            (ciphertext,),
        )


def _pending(db, token):
    row = db.execute(
        "SELECT pending FROM nuvemixa_auth.state "
        "WHERE singleton AND NOT required AND pending_until > clock_timestamp()"
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(Fernet(key()).decrypt(bytes(row[0])))
    if hmac.compare_digest(payload["token"], token):
        return payload
    return None


def load_pending(token):
    with transaction() as db:
        return _pending(db, token)


def activate_pending(token, secret, recovery_hashes, step):
    with transaction() as db:
        required, _ = _state(db, lock=True)
        pending = None if required else _pending(db, token)
        if pending is None or not hmac.compare_digest(pending["totp_secret"], secret):
            return False
        if not _register_step(db, step):
            return False
        ciphertext = Fernet(key()).encrypt(json.dumps(
            {"enabled": True, "totp_secret": secret, "recovery_hashes": recovery_hashes}
        ).encode())
        db.execute(
            "UPDATE nuvemixa_auth.state SET required = true, ciphertext = %s, "
            "pending = NULL, pending_until = NULL WHERE singleton",
            (ciphertext,),
        )
        return True



def load():
    with transaction() as db:
        return decode(_active(db), key())


def consume_recovery_code(code):
    with transaction() as db:
        encryption_key = key()
        payload = decode(_active(db, lock=True), encryption_key)
        if not gebruik_herstelcode(code, payload["recovery_hashes"]):
            return False
        ciphertext = Fernet(encryption_key).encrypt(json.dumps(payload).encode("utf-8"))
        db.execute("UPDATE nuvemixa_auth.state SET ciphertext = %s WHERE singleton", (ciphertext,))
        return True


def register_totp_step(step):
    with transaction() as db:
        _active(db)
        return _register_step(db, step)


def _register_step(db, step):
    return db.execute(
        "INSERT INTO nuvemixa_auth.replay (step) VALUES (%s) ON CONFLICT DO NOTHING RETURNING step",
        (step,),
    ).fetchone() is not None


def attempt_key(scope, identity, encryption_key):
    return hmac.digest(encryption_key, f"{scope}\0{identity}".encode(), hashlib.sha256)


def reserve_attempt(scope, identity, limit, window):
    with transaction() as db:
        # One short transaction serializes admission and cleanup across workers.
        _state(db, lock=True)
        now = db.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp())::double precision").fetchone()[0]
        db.execute(
            "DELETE FROM nuvemixa_auth.attempts WHERE occurred_at <= %s OR "
            "(scope = '2fa' AND occurred_at <= %s)",
            (now - 900, now - 300),
        )
        tag = attempt_key(scope, identity, key())
        count = db.execute(
            "SELECT count(*) FROM nuvemixa_auth.attempts WHERE scope = %s AND tag = %s AND occurred_at > %s",
            (scope, tag, now - window),
        ).fetchone()[0]
        if count >= limit:
            return None
        ticket = secrets.token_hex(16)
        db.execute(
            "INSERT INTO nuvemixa_auth.attempts (scope, tag, occurred_at, ticket) VALUES (%s, %s, %s, %s)",
            (scope, tag, now, ticket),
        )
        return ticket


def finish_password_attempt(identity, ticket):
    with transaction() as db:
        _state(db, lock=True)
        tag = attempt_key("password", identity, key())
        # Clear only this request and prior failures. Concurrent newer attempts stay counted.
        db.execute(
            """DELETE FROM nuvemixa_auth.attempts
               WHERE scope = 'password' AND tag = %s AND occurred_at <= (
                   SELECT occurred_at FROM nuvemixa_auth.attempts WHERE ticket = %s)
               AND (ticket = %s OR failed)""",
            (tag, ticket, ticket),
        )


def fail_password_attempt(ticket):
    with transaction() as db:
        db.execute("UPDATE nuvemixa_auth.attempts SET failed = true WHERE ticket = %s", (ticket,))
