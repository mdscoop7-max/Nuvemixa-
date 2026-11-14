"""First-party counts of browser sessions with a storefront visit on a UTC day."""
import hashlib
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from contextlib import closing

from flask import current_app, request, session

from nv_dashboard_manager import DB

STOREFRONT = {"home", "shop", "deals", "products_page", "category_page", "product_detail", "product"}


def enabled():
    return os.getenv("NUVEMIXA_VISIT_COUNTER", "").lower() == "true"


def traffic_kind():
    return "webshop" if os.getenv("NUVEMIXA_VISIT_TRAFFIC") == "webshop" else "test"


def record_visit(response):
    if (not enabled() or request.method != "GET" or response.status_code != 200
            or request.endpoint not in STOREFRONT or request.environ.get("nuvemixa.internal_check")
            or session.get("nv_admin") or session.get("nv_staff_id")
            or request.args.get("dashboard_from") or request.args.get("from_dashboard")
            or request.headers.get("Sec-Purpose") or request.headers.get("Purpose")
            or request.headers.get("Sec-GPC") == "1" or request.headers.get("DNT") == "1"):
        return response
    agent = request.user_agent.string
    if not agent or re.search(r"bot|spider|crawl|preview|headless|curl|python|wget|monitor|lighthouse", agent, re.I):
        return response
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    kind = traffic_kind()
    key = f"{kind}:{day}"
    if session.get("nv_visit_day") == key:
        return response
    # Keep one random marker for this browser session/day; it is unrelated to IP or account data.
    marker = secrets.token_urlsafe(24)
    try:
        with closing(sqlite3.connect(DB, timeout=0.3)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS storefront_visits (
                traffic TEXT NOT NULL, day TEXT NOT NULL, marker TEXT NOT NULL,
                measured_at TEXT NOT NULL, PRIMARY KEY(traffic,day,marker))""")
            db.execute("INSERT OR IGNORE INTO storefront_visits VALUES (?,?,?,?)",
                       (kind, day, hashlib.sha256(marker.encode()).hexdigest(), now.isoformat(timespec="seconds")))
    except (OSError, sqlite3.Error):
        current_app.logger.warning("Lokale bezoekmeting tijdelijk niet beschikbaar")
        return response
    session["nv_visit_day"] = key
    return response


def visit_summary():
    state = {"enabled": enabled(), "traffic": traffic_kind(), "groups": [], "error": False}
    if not DB.is_file():
        return state
    try:
        with closing(sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.3)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='storefront_visits'").fetchone():
                return state
            rows = db.execute("""SELECT traffic,
                sum(day=date('now')), sum(day=date('now','-1 day')),
                sum(day BETWEEN date('now','-6 days') AND date('now')),
                sum(day BETWEEN date('now','-29 days') AND date('now')),
                count(*), min(measured_at), max(measured_at)
                FROM storefront_visits GROUP BY traffic ORDER BY traffic""")
            state["groups"] = rows.fetchall()
    except (OSError, sqlite3.Error):
        state["error"] = True
    return state
