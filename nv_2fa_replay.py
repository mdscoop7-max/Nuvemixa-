
"""Voorkom hergebruik van een Google Authenticator-tijdstap."""

import sqlite3
from nv_2fa_rate_limit import _beveilig_databasebestanden
import nv_2fa_postgres as postgres
from nv_storage_paths import TWO_FA_DIR

DATABASE = TWO_FA_DIR / "nv_2fa_replay.sqlite3"


def registreer_eenmalig(stap):
    if postgres.enabled():
        return postgres.register_totp_step(int(stap))

    _beveilig_databasebestanden(DATABASE)
    db = sqlite3.connect(DATABASE, timeout=10)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""
            CREATE TABLE IF NOT EXISTS gebruikte_stappen (
                stap INTEGER PRIMARY KEY
            )
        """)
        resultaat = db.execute(
            "INSERT OR IGNORE INTO gebruikte_stappen (stap) VALUES (?)",
            (int(stap),)
        )
        toegestaan = resultaat.rowcount == 1
        db.commit()
        return toegestaan
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
