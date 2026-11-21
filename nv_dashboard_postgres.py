"""PostgreSQL connection for dashboard data, independent of authentication."""
import atexit
import logging
import os
import sqlite3
import threading

import psycopg
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def configured():
    return runtime_enabled() or bool(os.environ.get("NUVEMIXA_DASHBOARD_DATABASE_URL", "").strip())


@contextmanager
def connect():
    import certifi
    import psycopg

    with psycopg.connect(os.environ["NUVEMIXA_DASHBOARD_DATABASE_URL"],
                         sslmode="verify-full", sslrootcert=certifi.where(),
                         connect_timeout=4, prepare_threshold=None) as db:
        yield db


def runtime_enabled():
    return os.environ.get("NUVEMIXA_DASHBOARD_BACKEND", "").strip().lower() == "postgres"


class DashboardRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def dashboard_rows(cursor):
    names = tuple(column.name for column in cursor.description or ())
    return lambda values: DashboardRow(zip(names, values, strict=True))


class DashboardQueries:
    """Use the stored queries' SQLite-style bind markers with psycopg."""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=()):
        return self.connection.execute(query.replace("?", "%s"), parameters)


# --- Optionele verbindingspool (schakelaar NUVEMIXA_DASHBOARD_POOL, standaard uit) -----------
# Zonder schakelaar blijft het gedrag exact zoals voorheen: een nieuwe verbinding per aanroep.
# Met schakelaar worden verbindingen per proces hergebruikt. Elke aanroep van application_db()
# blijft een echte, afzonderlijke transactie met dezelfde time-outs en dezelfde afhandeling van
# fouten. Er is nooit een terugval naar SQLite: bij een probleem geeft de opslag een fout.
POOL_SWITCH = "NUVEMIXA_DASHBOARD_POOL"
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 3
POOL_TIMEOUT = 4.0
POOL_MAX_LIFETIME = 300.0
POOL_MAX_IDLE = 60.0
# SET LOCAL werkt alleen binnen een transactie en blijft dus ook achter PgBouncer
# (transactiemodus) beperkt tot deze ene transactie.
_SETTINGS = ("SET LOCAL search_path TO nuvemixa_dashboard, pg_catalog; "
             "SET LOCAL statement_timeout TO '5s'; SET LOCAL lock_timeout TO '3s'")

_pool = None
_pool_key = None
_pool_lock = threading.Lock()


def pool_enabled():
    return os.environ.get(POOL_SWITCH, "").strip().lower() in {"1", "true", "yes", "on"}


def new_connection(dsn, **extra):
    """Eén verbinding met dezelfde TLS-instellingen als connect(); ook de testhaak voor de pool."""
    import certifi

    return psycopg.connect(dsn, sslmode="verify-full", sslrootcert=certifi.where(),
                           connect_timeout=4, prepare_threshold=None, **extra)


class _RedactPoolLogs(logging.Filter):
    """De pool logt verbindingsfouten met hostnaam; die tonen we nooit."""

    def filter(self, record):
        args = record.args if isinstance(record.args, tuple) else (record.args,)
        record.args = tuple(type(arg).__name__ if isinstance(arg, BaseException) else arg for arg in args)
        record.exc_info = record.exc_text = None
        return True


def _new_pool(dsn):
    from psycopg_pool import ConnectionPool

    class PoolConnection(psycopg.Connection):
        @classmethod
        def connect(cls, conninfo="", **kwargs):
            return new_connection(conninfo, autocommit=True)

    pool_logger = logging.getLogger("psycopg.pool")
    if not any(isinstance(item, _RedactPoolLogs) for item in pool_logger.filters):
        pool_logger.addFilter(_RedactPoolLogs())
    pool = ConnectionPool(
        dsn, connection_class=PoolConnection, min_size=POOL_MIN_SIZE, max_size=POOL_MAX_SIZE,
        timeout=POOL_TIMEOUT, max_lifetime=POOL_MAX_LIFETIME, max_idle=POOL_MAX_IDLE,
        max_waiting=10, num_workers=1, name="nuvemixa-dashboard", open=False,
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
    """Sluit de pool netjes (bij afsluiten van het proces en in tests)."""
    global _pool, _pool_key
    with _pool_lock:
        pool, same_process = _pool, _pool_key is not None and _pool_key[1] == os.getpid()
        _pool = _pool_key = None
    if pool is not None and same_process:
        pool.close(timeout=1)


atexit.register(reset_pool)


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


def _open_transaction(pool, read_only):
    """Haal een verbinding op en open de transactie. Alleen een dode verbinding (bijvoorbeeld na
    een slaapstand van de database) wordt vervangen; op dat moment is er nog niets gelezen of
    geschreven, dus een nieuwe poging is veilig."""
    begin = ("BEGIN READ ONLY; " if read_only else "BEGIN; ") + _SETTINGS
    for attempt in range(1, POOL_MAX_SIZE + 2):
        db = pool.getconn(timeout=POOL_TIMEOUT)
        try:
            db.execute(begin)
            return db
        except Exception:
            retry = attempt < POOL_MAX_SIZE + 1 and _dead(db)
            _release(pool, db, failed=True)
            if not retry:
                raise


@contextmanager
def _pooled_application_db(read_only):
    pool = _pool_for(os.environ["NUVEMIXA_DASHBOARD_DATABASE_URL"])
    db = _open_transaction(pool, read_only)
    finished = False
    try:
        db.row_factory = dashboard_rows
        yield DashboardQueries(db)
        db.execute("COMMIT")
        finished = True
    finally:
        _release(pool, db, failed=not finished)


@contextmanager
def _direct_application_db(read_only):
    with connect() as db:
        if read_only:
            db.execute("SET TRANSACTION READ ONLY")
        db.execute("SET LOCAL search_path TO nuvemixa_dashboard, pg_catalog")
        db.execute("SET LOCAL statement_timeout TO '5s'")
        db.execute("SET LOCAL lock_timeout TO '3s'")
        db.row_factory = dashboard_rows
        yield DashboardQueries(db)


@contextmanager
def application_db(*, read_only=False):
    try:
        opener = _pooled_application_db if pool_enabled() else _direct_application_db
        with opener(read_only) as db:
            yield db
    except psycopg.IntegrityError:
        raise sqlite3.IntegrityError("Gegevensconflict in dashboardopslag.") from None
    except (KeyError, psycopg.Error) as exc:
        logger.warning("Dashboardopslag niet beschikbaar (%s)", type(exc).__name__)
        raise sqlite3.OperationalError("PostgreSQL-dashboardopslag is niet beschikbaar.") from None


@contextmanager
def read_db(path, *, timeout=0.5):
    if runtime_enabled():
        with application_db(read_only=True) as db:
            yield db
    else:
        from contextlib import closing

        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=timeout)) as db:
            db.row_factory = sqlite3.Row
            yield db


def table_exists(db, name):
    if runtime_enabled():
        return db.execute("SELECT to_regclass(?) IS NOT NULL", (name,)).fetchone()[0]
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? COLLATE NOCASE",
                           (name,)).fetchone())


def columns_for(db, name):
    if runtime_enabled():
        return {row[0] for row in db.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema='nuvemixa_dashboard' AND table_name=?", (name,))}
    return {row[1] for row in db.execute(f"PRAGMA table_info({name})")}


def lock_staff(db):
    db.execute("LOCK TABLE staff IN SHARE ROW EXCLUSIVE MODE" if runtime_enabled() else "BEGIN IMMEDIATE")


def lock_catalog(db):
    db.execute("LOCK TABLE catalog_edits IN SHARE ROW EXCLUSIVE MODE" if runtime_enabled() else "BEGIN IMMEDIATE")
