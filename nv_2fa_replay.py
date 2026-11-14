
"""Voorkom hergebruik van een Google Authenticator-tijdstap."""

import sqlite3
from pathlib import Path

DATABASE = Path(__file__).resolve().parent / "nv_2fa_replay.sqlite3"


def registreer_eenmalig(stap):
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
