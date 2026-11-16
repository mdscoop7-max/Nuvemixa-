"""PostgreSQL storage for primary administrator 2FA."""

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
from contextlib import contextmanager

from cryptography.fernet import Fernet, InvalidToken

from nv_2fa import gebruik_herstelcode


class StorageUnavailable(RuntimeError):
    """Safe error for authentication paths and logs."""


def enabled():
    return bool(os.getenv("NUVEMIXA_2FA_BACKEND") or os.getenv("NUVEMIXA_2FA_DATABASE_URL"))


def connect(dsn, **extra):
    import certifi
    import psycopg

    return psycopg.connect(
        dsn, sslmode="verify-full", sslrootcert=certifi.where(),
        connect_timeout=5, prepare_threshold=None, **extra,
    )


# --- Optionele verbindingspool (schakelaar NUVEMIXA_2FA_POOL, standaard uit) ---------------
# Zonder schakelaar blijft het gedrag exact zoals voorheen: een nieuwe verbinding per
# transactie. Met schakelaar worden verbindingen per proces hergebruikt. Elke transactie
# blijft een echte, afzonderlijke databasetransactie met dezelfde time-outs. Er wordt niets
# onthouden over de 2FA-status: elke aanroep leest die opnieuw uit de database.
POOL_SWITCH = "NUVEMIXA_2FA_POOL"
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 3
POOL_TIMEOUT = 4.0
POOL_MAX_LIFETIME = 300.0
POOL_MAX_IDLE = 60.0
# SET LOCAL werkt alleen binnen een transactie en blijft dus ook achter PgBouncer
# (transactiemodus) beperkt tot deze ene transactie.
_BEGIN = "BEGIN; SET LOCAL statement_timeout = '5s'; SET LOCAL lock_timeout = '3s'"
_STATE_SQL = "SELECT required, ciphertext FROM nuvemixa_auth.state WHERE singleton"

_pool = None
_pool_key = None
_pool_lock = threading.Lock()


def pool_enabled():
    return os.getenv(POOL_SWITCH, "").strip().lower() in {"1", "true", "yes", "on"}


class _RedactPoolLogs(logging.Filter):
    """De pool logt verbindingsfouten met hostnaam; die tonen we nooit."""

    def filter(self, record):
        args = record.args if isinstance(record.args, tuple) else (record.args,)
        record.args = tuple(type(arg).__name__ if isinstance(arg, BaseException) else arg for arg in args)
        record.exc_info = record.exc_text = None
        return True


def _new_pool(dsn):
    import psycopg
    from psycopg_pool import ConnectionPool

    class PoolConnection(psycopg.Connection):
        @classmethod
        def connect(cls, conninfo="", **kwargs):
            # Via de module-functie, zodat dezelfde TLS-instellingen en testhaken gelden.
            return connect(conninfo, autocommit=True)

    logger = logging.getLogger("psycopg.pool")
    if not any(isinstance(item, _RedactPoolLogs) for item in logger.filters):
        logger.addFilter(_RedactPoolLogs())
    pool = ConnectionPool(
        dsn, connection_class=PoolConnection, min_size=POOL_MIN_SIZE, max_size=POOL_MAX_SIZE,
        timeout=POOL_TIMEOUT, max_lifetime=POOL_MAX_LIFETIME, max_idle=POOL_MAX_IDLE,
        max_waiting=10, num_workers=1, name="nuvemixa-2fa", open=False,
    )
    pool.open(wait=False)
    return pool


def _pool_for(dsn):
    global _pool, _pool_key
    key_now = (dsn, os.getpid())
    with _pool_lock:
        if _pool is not None and _pool_key != key_now:
            stale, same_process = _pool, _pool_key[1] == key_now[1]
            _pool = None
            if same_process:
                stale.close(timeout=1)
            # Een pool geërfd na een fork wordt niet gesloten: de verbindingen zijn van de ouder.
        if _pool is None:
            _pool, _pool_key = _new_pool(dsn), key_now
        return _pool


def reset_pool():
    """Sluit de pool (bij afsluiten van het proces en in tests)."""
    global _pool, _pool_key
    with _pool_lock:
        pool, same_process = _pool, _pool_key is not None and _pool_key[1] == os.getpid()
        _pool = _pool_key = None
    if pool is not None and same_process:
        pool.close(timeout=1)


def _release(pool, db, *, failed):
    """Geef de verbinding terug; na een fout eerst terugdraaien, anders weggooien."""
    try:
        if failed:
            try:
                db.rollback()
            except Exception:
                db.close()
    finally:
        pool.putconn(db)


def _dead(db):
    return bool(db.closed or getattr(db, "broken", False))


def _attempts():
    # Na bijvoorbeeld een herstart van de database kunnen alle poolverbindingen dood zijn.
    # Elke dode verbinding wordt weggegooid; daarna volgt een nieuwe.
    return range(1, POOL_MAX_SIZE + 2)


def _open_transaction(pool):
    """Haal een verbinding op en open de transactie. Alleen een dode verbinding wordt
    vervangen; op dat moment is er nog niets gelezen of geschreven."""
    for attempt in _attempts():
        db = pool.getconn(timeout=POOL_TIMEOUT)
        try:
            db.execute(_BEGIN)
            return db
        except Exception:
            retry = attempt < POOL_MAX_SIZE + 1 and _dead(db)
            _release(pool, db, failed=True)
            if not retry:
                raise


def _first_rows(cursor):
    for _ in range(8):
        if cursor.description is not None:
            return cursor.fetchone()
        if not cursor.nextset():
            return None
    return None


def _read_state_pooled(dsn):
    """Eén heen-en-weer-verkeer: BEGIN, time-outs, lezen en COMMIT in één bericht.
    Alleen lezen, dus bij een dode verbinding is een nieuwe poging veilig."""
    pool = _pool_for(dsn)
    for attempt in _attempts():
        db = pool.getconn(timeout=POOL_TIMEOUT)
        failed = True
        try:
            row = _first_rows(db.execute(f"{_BEGIN}; {_STATE_SQL}; COMMIT"))
            failed = False
            return row
        except Exception:
            if not (attempt < POOL_MAX_SIZE + 1 and _dead(db)):
                raise
        finally:
            _release(pool, db, failed=failed)


def _database_url():
    dsn = os.environ["NUVEMIXA_2FA_DATABASE_URL"]
    if os.getenv("NUVEMIXA_2FA_BACKEND", "postgres") != "postgres" or not dsn:
        raise ValueError("Invalid backend")
    return dsn


@contextmanager
def _pooled_transaction(dsn):
    pool = _pool_for(dsn)
    db = _open_transaction(pool)
    finished = False
    try:
        yield db
        db.execute("COMMIT")
        finished = True
    finally:
        _release(pool, db, failed=not finished)


@contextmanager
def transaction():
    try:
        dsn = _database_url()
        if pool_enabled():
            with _pooled_transaction(dsn) as db:
                yield db
        else:
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


def _checked_state(required, ciphertext):
    encryption_key = key()
    if required:
        decode(ciphertext, encryption_key)
    else:
        Fernet(encryption_key)
    return required


def is_active():
    if pool_enabled():
        try:
            row = _read_state_pooled(_database_url())
            if row is None:
                raise StorageUnavailable("Verplichte 2FA-opslag ontbreekt.")
            return _checked_state(*row)
        except Exception:
            # Zelfde afhandeling als transaction(): nooit verbindingsdetails naar buiten.
            raise StorageUnavailable("Beveiligde PostgreSQL-opslag is niet beschikbaar.") from None
    with transaction() as db:
        return _checked_state(*_state(db))


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
