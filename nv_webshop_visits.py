"""Cookievrije bezoekersteller voor de publieke NUVEMIXA-webshop.

Telregels (ook getoond in het dashboard):
- De webshop stuurt per paginaweergave één klein bericht naar /api/webshop-visit.
- Een bezoeker is een dagelijkse pseudoniem (HMAC van IP + browser, met een zout dat
  elke Nederlandse kalenderdag wisselt). Er wordt niets op het apparaat opgeslagen en
  het IP-adres wordt niet bewaard. Dezelfde persoon is op een andere dag niet herkenbaar.
- Week, maand en totaal tellen bezoekersdagen: iemand die op twee dagen terugkomt telt twee keer.
- Een paginaweergave telt niet opnieuw wanneer dezelfde bezoeker binnen 30 minuten
  dezelfde pagina opnieuw laadt (herladen).
"""
import hashlib
import hmac
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import psycopg
from flask import Blueprint, Response, current_app, request

import nv_dashboard_postgres
import nv_freeze
from nv_dashboard_manager import DB

TIMEZONE = ZoneInfo("Europe/Amsterdam")
DEFAULT_ORIGINS = ("https://nuvemixa.alwaysdata.net",)
RELOAD_WINDOW = timedelta(minutes=30)
STORAGE_ERRORS = (OSError, ValueError, KeyError, sqlite3.Error, psycopg.Error)
BOTS = re.compile(
    r"bot|spider|crawl|slurp|preview|headless|curl|python|wget|monitor|lighthouse|uptime|health|"
    r"render|pingdom|statuscake|facebookexternalhit|bingpreview|phantom|selenium|puppeteer|playwright",
    re.I)
EXCLUDED_PATHS = ("/dashboard", "/control", "/admin", "/wp-admin", "/wp-login", "/api/", "/static/", "/healthz")
DAILY_COLUMNS = "day,visitor,first_seen,pageviews,last_path,last_at"

bp = Blueprint("webshop_visits", __name__)


def tracking_enabled():
    return os.getenv("NUVEMIXA_WEBSHOP_TRACKING", "").strip().lower() == "true"


def allowed_origins():
    extra = [item.strip().rstrip("/") for item in os.getenv("NUVEMIXA_WEBSHOP_ORIGINS", "").split(",") if item.strip()]
    return tuple(dict.fromkeys((*DEFAULT_ORIGINS, *extra)))


def persistent_backend():
    return nv_dashboard_postgres.configured()


@contextmanager
def visits_db(write=False):
    if nv_dashboard_postgres.configured():
        with nv_dashboard_postgres.connect() as db:
            yield db, "nuvemixa_dashboard.webshop_daily_visitors", "%s"
        return
    if write:
        with closing(sqlite3.connect(DB, timeout=0.5)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS webshop_daily_visitors (
                day TEXT NOT NULL, visitor TEXT NOT NULL, first_seen TEXT NOT NULL,
                pageviews INTEGER NOT NULL DEFAULT 0, last_path TEXT NOT NULL DEFAULT '',
                last_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(day, visitor))""")
            yield db, "webshop_daily_visitors", "?"
        return
    with closing(sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)) as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='webshop_daily_visitors'").fetchone()
        yield db, "webshop_daily_visitors" if exists else None, "?"


def client_address():
    for header in ("CF-Connecting-IP", "True-Client-IP"):
        value = request.headers.get(header, "").strip()
        if value:
            return value
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded or request.remote_addr or "unknown"


def visitor_hash(day, address, agent, secret):
    daily_salt = hmac.new(secret.encode(), f"nv-visits:{day}".encode(), hashlib.sha256).digest()
    return hmac.new(daily_salt, f"{address}|{agent}".encode(), hashlib.sha256).hexdigest()[:32]


def clean_path(raw):
    if not isinstance(raw, str) or not raw.startswith("/") or raw.startswith("//") or len(raw) > 300:
        return None
    path = urlsplit(raw).path or "/"
    if any(path.lower().startswith(prefix) for prefix in EXCLUDED_PATHS):
        return None
    return path[:200]


def register_hit(path, address, agent, secret, now=None):
    """Registreer één geldige paginaweergave. Geeft True terug als die is opgeslagen."""
    now = now or datetime.now(TIMEZONE)
    day = now.date().isoformat()
    stamp = now.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()
    cutoff = (now.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0) - RELOAD_WINDOW).isoformat()
    visitor = visitor_hash(day, address, agent, secret)
    with visits_db(write=True) as (db, table, mark):
        db.execute(
            f"INSERT INTO {table} ({DAILY_COLUMNS}) VALUES ({','.join([mark] * 6)})"
            " ON CONFLICT(day,visitor) DO NOTHING", (day, visitor, stamp, 0, "", ""))
        db.execute(
            f"UPDATE {table} SET pageviews = pageviews + CASE WHEN last_path = {mark} AND last_at >= {mark}"
            f" THEN 0 ELSE 1 END, last_path = {mark}, last_at = {mark} WHERE day = {mark} AND visitor = {mark}",
            (path, cutoff, path, stamp, day, visitor))
    return True


def cors_headers(response, origin):
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


@bp.route("/api/webshop-visit", methods=["POST", "OPTIONS"])
def webshop_visit():
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin not in allowed_origins():
        return Response(status=403)
    response = Response(status=204)
    cors_headers(response, origin)
    response.headers["Cache-Control"] = "no-store"
    if request.method == "OPTIONS" or not tracking_enabled() or nv_freeze.frozen():
        return response
    agent = request.headers.get("User-Agent", "")
    if (not agent or BOTS.search(agent) or request.headers.get("Sec-GPC") == "1"
            or request.headers.get("DNT") == "1" or request.headers.get("Sec-Purpose")
            or request.headers.get("Purpose")):
        return response
    payload = request.get_json(silent=True, force=True) or {}
    path = clean_path(payload.get("p") if isinstance(payload, dict) else None)
    if not path:
        return response
    try:
        register_hit(path, client_address(), agent, current_app.secret_key)
    except STORAGE_ERRORS:
        current_app.logger.warning("Webshopbezoek kon niet worden opgeslagen")
    return response


def summary(today=None):
    """Telresultaten voor het dashboard. Bevat nooit voorbeeld- of testgegevens."""
    now = datetime.now(TIMEZONE)
    today = today or now.date()
    state = {
        "enabled": tracking_enabled(), "origins": allowed_origins(), "persistent": persistent_backend(),
        "backend": "PostgreSQL" if persistent_backend() else "SQLite (niet permanent op Render)",
        "error": False, "has_data": False, "last_seen": None, "periods": [], "chart": [],
        "script_url": f"{request.host_url.rstrip('/')}/static/nv-webshop-visit.js" if request else "",
    }
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    if not persistent_backend() and not DB.is_file():
        return state
    try:
        with visits_db() as (db, table, mark):
            if not table:
                return state
            def totals(start):
                row = db.execute(f"SELECT count(*), coalesce(sum(pageviews),0) FROM {table} WHERE day >= {mark}"
                                 f" AND day <= {mark}", (start.isoformat(), today.isoformat())).fetchone()
                return int(row[0]), int(row[1])
            everything = db.execute(f"SELECT count(*), coalesce(sum(pageviews),0), max(last_at) FROM {table}").fetchone()
            state["periods"] = [
                ("Vandaag", *totals(today)), ("Deze week", *totals(week)), ("Deze maand", *totals(month)),
                ("Totaal", int(everything[0]), int(everything[1])),
            ]
            state["has_data"] = int(everything[0]) > 0
            state["last_seen"] = everything[2] or None
            start = today - timedelta(days=29)
            rows = {row[0]: (int(row[1]), int(row[2])) for row in db.execute(
                f"SELECT day, count(*), coalesce(sum(pageviews),0) FROM {table} WHERE day >= {mark} AND day <= {mark}"
                " GROUP BY day", (start.isoformat(), today.isoformat())).fetchall()}
            state["chart"] = [((start + timedelta(days=i)).strftime("%d-%m"),
                               *rows.get((start + timedelta(days=i)).isoformat(), (0, 0))) for i in range(30)]
    except STORAGE_ERRORS:
        state["error"] = True
    return state
