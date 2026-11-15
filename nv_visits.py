"""Opt-in, pseudonymous browser visits, at most one per Dutch calendar day."""
import hashlib
import os
import re
import secrets
import sqlite3
from collections import Counter
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg
from flask import current_app, request, session
from itsdangerous import BadData, URLSafeTimedSerializer

import nv_dashboard_postgres
from nv_dashboard_manager import DB

STOREFRONT = {"home", "shop", "deals", "products_page", "category_page", "product_detail", "product"}
TIMEZONE = ZoneInfo("Europe/Amsterdam")
COOKIE = "nv_measurement"
COOKIE_AGE = 30 * 24 * 60 * 60
STORAGE_ERRORS = (OSError, ValueError, sqlite3.Error, psycopg.Error)


def enabled():
    return os.getenv("NUVEMIXA_VISIT_COUNTER", "").strip().lower() == "true"


def traffic_kind():
    return "webshop" if os.getenv("NUVEMIXA_VISIT_TRAFFIC") == "webshop" else "test"


@contextmanager
def measurement_db(write=False):
    if nv_dashboard_postgres.configured():
        with nv_dashboard_postgres.connect() as db:
            yield db, "nuvemixa_dashboard.storefront_visits", "%s"
    elif write:
        with closing(sqlite3.connect(DB, timeout=0.3)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS storefront_visits (
                traffic TEXT NOT NULL, day TEXT NOT NULL, marker TEXT NOT NULL,
                measured_at TEXT NOT NULL, PRIMARY KEY(traffic,day,marker))""")
            yield db, "storefront_visits", "?"
    else:
        with closing(sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.3)) as db:
            table = db.execute("SELECT 1 FROM sqlite_master WHERE name='storefront_visits'").fetchone()
            yield db, "storefront_visits" if table else None, "?"


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
    signer = URLSafeTimedSerializer(current_app.secret_key, salt="nuvemixa-visitor")
    try:
        marker = signer.loads(request.cookies.get(COOKIE, ""), max_age=COOKIE_AGE)
    except BadData:
        # Wait for the browser to return its cookie. First requests without
        # an identifier cannot safely be deduplicated across workers.
        response.set_cookie(COOKIE, signer.dumps(secrets.token_urlsafe(24)),
                            max_age=COOKIE_AGE, httponly=True, samesite="Lax",
                            secure=current_app.config["SESSION_COOKIE_SECURE"])
        response.cache_control.public = False
        response.cache_control.private = True
        return response
    now = datetime.now(TIMEZONE)
    kind, day = traffic_kind(), now.date().isoformat()
    counted = f"{kind}:{day}"
    if session.get("nv_measurement_day") == counted:
        return response
    try:
        with measurement_db(write=True) as (db, table, mark):
            values = ",".join([mark] * 4)
            db.execute(f"INSERT INTO {table} (traffic,day,marker,measured_at) VALUES ({values})"
                       " ON CONFLICT(traffic,day,marker) DO NOTHING",
                       (kind, day, hashlib.sha256(marker.encode()).hexdigest(), now.isoformat(timespec="seconds")))
    except STORAGE_ERRORS:
        current_app.logger.warning("Bezoekmeting tijdelijk niet beschikbaar")
        return response
    session["nv_measurement_day"] = counted
    return response


def chart_buckets(daily, today):
    calendar = {"day": Counter(), "week": Counter(), "month": Counter()}
    for day, count in daily:
        day = date.fromisoformat(day)
        calendar["day"][day] += count
        calendar["week"][day - timedelta(days=day.weekday())] += count
        calendar["month"][day.replace(day=1)] += count
    formats = {"day": "%d-%m", "week": "%d-%m", "month": "%m-%Y"}
    return {period: [(day.strftime(formats[period]), count) for day, count in sorted(rows.items())[-12:]
                     if day <= today] for period, rows in calendar.items()}


def visit_summary():
    state = {"enabled": enabled(), "traffic": traffic_kind(), "groups": [], "charts": {},
             "error": False, "backend": "PostgreSQL" if nv_dashboard_postgres.configured() else "SQLite"}
    if state["backend"] == "SQLite" and not DB.is_file():
        return state
    today = datetime.now(TIMEZONE).date()
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    try:
        with measurement_db() as (db, table, mark):
            if not table:
                return state
            state["groups"] = db.execute(
                f"""SELECT traffic, sum(CASE WHEN day={mark} THEN 1 ELSE 0 END),
                   sum(CASE WHEN day={mark} THEN 1 ELSE 0 END),
                   sum(CASE WHEN day BETWEEN {mark} AND {mark} THEN 1 ELSE 0 END),
                   sum(CASE WHEN day BETWEEN {mark} AND {mark} THEN 1 ELSE 0 END),
                   count(*), min(measured_at), max(measured_at)
                   FROM {table} GROUP BY traffic ORDER BY traffic""",
                (today.isoformat(), (today-timedelta(days=1)).isoformat(), week.isoformat(), today.isoformat(),
                 month.isoformat(), today.isoformat())).fetchall()
            for traffic, *_ in state["groups"]:
                rows = db.execute(
                    f"SELECT day,count(*) FROM {table} WHERE traffic={mark} AND day BETWEEN {mark} AND {mark}"
                    " GROUP BY day ORDER BY day",
                    (traffic, (today-timedelta(days=366)).isoformat(), today.isoformat())).fetchall()
                state["charts"][traffic] = chart_buckets(rows, today)
    except STORAGE_ERRORS:
        state["error"] = True
    return state
