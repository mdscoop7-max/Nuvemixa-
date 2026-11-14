"""Minimalistische logregistratie van succesvolle klantacties (geen IP/wachtwoorden)."""
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def record_customer_activity(database_path, customer_id, event_type):
    """Best effort: mag de klantlogin nooit tegenhouden."""
    if event_type not in ("registered", "logged_in") or not isinstance(customer_id, int):
        return
    try:
        with sqlite3.connect(str(database_path), timeout=5) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS nv_customer_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('registered','logged_in')),
                occurred_at TEXT NOT NULL
            )""")
            conn.execute("INSERT INTO nv_customer_activity(customer_id,event_type,occurred_at) VALUES(?,?,?)",
                         (customer_id, event_type, datetime.now(timezone.utc).isoformat(timespec="seconds")))
    except (sqlite3.Error, OSError):
        logger.warning("Customer activity unavailable")


def read_customer_activity(database_path):
    """Alleen voor afgeschermde beheerdersroute; geen e-mails of wachtwoorden."""
    try:
        uri = Path(database_path).resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            try:
                rows = conn.execute("""SELECT a.customer_id, a.event_type, a.occurred_at
                    FROM nv_customer_activity AS a ORDER BY a.id DESC LIMIT 50""").fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc):
                    raise
                rows = []
        return int(count), [dict(row) for row in rows], None
    except (sqlite3.Error, OSError, ValueError):
        return None, [], "Klantactiviteiten zijn lokaal niet beschikbaar."
