"""Gedeelde beveiliging tegen herhaalde 2FA-pogingen."""

import os
import stat
import sqlite3
import time
from pathlib import Path

import nv_2fa_postgres as postgres
from nv_storage_paths import TWO_FA_DIR

DATABASE = TWO_FA_DIR / "nv_2fa_attempts.sqlite3"

MAX_POGINGEN = 5
VENSTER = 300


def _beveilig_databasebestanden(database):
    database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if database.is_symlink():
        raise PermissionError("2FA-database mag geen symbolische link zijn.")
    try:
        descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(descriptor)
    if os.name != "nt":
        paths = (database, Path(str(database) + "-wal"), Path(str(database) + "-shm"))
        for path in paths:
            if path.is_symlink():
                raise PermissionError(f"SQLite-sidecar mag geen symbolische link zijn: {path}")
            if path.exists():
                os.chmod(path, 0o600)
                if stat.S_IMODE(path.stat().st_mode) != 0o600:
                    raise PermissionError(f"Onvoldoende bestandsrechten: {path}")


def verbinding():
    _beveilig_databasebestanden(DATABASE)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.execute("PRAGMA busy_timeout = 10000")
    db.execute("""
        CREATE TABLE IF NOT EXISTS pogingen (
            sleutel TEXT NOT NULL,
            tijdstip REAL NOT NULL
        )
    """)
    return db


def registreer_en_controleer(sleutel):
    """Reserveer een poging voordat een 2FA-code wordt gecontroleerd."""
    if postgres.enabled():
        return postgres.reserve_attempt("2fa", sleutel, MAX_POGINGEN, VENSTER) is not None

    nu = time.time()

    db = verbinding()
    try:
        db.execute("BEGIN IMMEDIATE")

        db.execute(
            "DELETE FROM pogingen WHERE tijdstip < ?",
            (nu - VENSTER,)
        )

        aantal = db.execute(
            "SELECT COUNT(*) FROM pogingen WHERE sleutel = ?",
            (sleutel,)
        ).fetchone()[0]

        if aantal >= MAX_POGINGEN:
            db.rollback()
            return False

        db.execute(
            "INSERT INTO pogingen (sleutel, tijdstip) VALUES (?, ?)",
            (sleutel, nu)
        )

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        _beveilig_databasebestanden(DATABASE)
