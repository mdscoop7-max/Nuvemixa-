"""Minimalistische logregistratie van succesvolle klantacties (geen IP/wachtwoorden)."""
from contextlib import closing, contextmanager
import sqlite3
import nv_dashboard_postgres
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@contextmanager
def activity_db(path):
    if nv_dashboard_postgres.runtime_enabled():
        with nv_dashboard_postgres.application_db() as conn:
            yield conn
    else:
        with closing(sqlite3.connect(str(path), timeout=5)) as conn, conn:
            yield conn


def record_customer_activity(database_path, customer_id, event_type):
    """Best effort: mag de klantlogin nooit tegenhouden."""
    if event_type not in ("registered", "logged_in") or not isinstance(customer_id, int):
        return
    try:
        with activity_db(database_path) as conn:
            if not nv_dashboard_postgres.runtime_enabled():
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
        with nv_dashboard_postgres.read_db(Path(database_path), timeout=5) as conn:
            count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            rows = []
            if nv_dashboard_postgres.table_exists(conn, "nv_customer_activity"):
                rows = conn.execute("""SELECT a.customer_id, a.event_type, a.occurred_at
                    FROM nv_customer_activity AS a ORDER BY a.id DESC LIMIT 50""").fetchall()
        return int(count), [dict(row) for row in rows], None
    except (sqlite3.Error, OSError, ValueError):
        return None, [], "Klantactiviteiten zijn lokaal niet beschikbaar."
