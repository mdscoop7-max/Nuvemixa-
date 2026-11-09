"""Minimal first-party aggregate page-view counter, without user identifiers.

Only total/daily GET page views are stored. No IP, cookies, fingerprints,
URLs, or customer information. Not a unique-person visitor count.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _db_file():
    configured = os.getenv("TRENDMIX_METRICS_DB", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "instance" / "trendmix-metrics.sqlite3"


def _connect():
    path = _db_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=1)
    db.execute("CREATE TABLE IF NOT EXISTS page_views (day TEXT PRIMARY KEY, views INTEGER NOT NULL DEFAULT 0)")
    return db


def record_page_view():
    """Record one anonymous HTML page load; never use for sales or unique users."""
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        with _connect() as db:
            db.execute(
                "INSERT INTO page_views(day, views) VALUES(?, 1) "
                "ON CONFLICT(day) DO UPDATE SET views=views+1",
                (day,),
            )
            cutoff = (datetime.now(timezone.utc).date() - timedelta(days=90)).isoformat()
            db.execute("DELETE FROM page_views WHERE day < ?", (cutoff,))
    except (OSError, sqlite3.Error):
        # Metrics are optional. A read-only filesystem cannot break the store.
        return


def summary():
    """Return aggregate page views and today views, or None when unavailable."""
    try:
        with _connect() as db:
            total = db.execute("SELECT COALESCE(SUM(views), 0) FROM page_views").fetchone()[0]
            today = db.execute("SELECT COALESCE(views, 0) FROM page_views WHERE day=?",
                               (datetime.now(timezone.utc).date().isoformat(),)).fetchone()
        return {"total": int(total), "today": int(today[0] if today else 0)}
    except (OSError, sqlite3.Error):
        return None
