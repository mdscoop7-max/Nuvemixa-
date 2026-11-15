"""PostgreSQL connection for dashboard data, independent of authentication."""
import os
import sqlite3

import psycopg
from contextlib import contextmanager


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


@contextmanager
def application_db(*, read_only=False):
    try:
        with connect() as db:
            if read_only:
                db.execute("SET TRANSACTION READ ONLY")
            db.execute("SET LOCAL search_path TO nuvemixa_dashboard, pg_catalog")
            db.execute("SET LOCAL statement_timeout TO '5s'")
            db.execute("SET LOCAL lock_timeout TO '3s'")
            db.row_factory = dashboard_rows
            yield DashboardQueries(db)
    except psycopg.IntegrityError:
        raise sqlite3.IntegrityError("Gegevensconflict in dashboardopslag.") from None
    except (KeyError, psycopg.Error):
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
