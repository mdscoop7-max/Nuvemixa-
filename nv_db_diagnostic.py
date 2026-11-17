"""Alleen-lezen meting van de databasesnelheid vanuit de draaiende service (standaard UIT).

Aan te zetten met NUVEMIXA_DB_DIAGNOSTIC=1 en een aparte NUVEMIXA_DB_DIAGNOSTIC_URL (bewust niet de
dashboard-DSN, want die schakelt functies naar Postgres). Alleen beheerders; de uitvoer bevat alleen getallen.
"""
import os
import statistics
import threading
import time

from flask import Blueprint, abort, jsonify

from nv_dashboard_manager import require_admin

SWITCH = "NUVEMIXA_DB_DIAGNOSTIC"
URL_VARIABLE = "NUVEMIXA_DB_DIAGNOSTIC_URL"
CONNECTIONS = 5
QUERIES = 20
BUDGET_SECONDS = 10.0
bp = Blueprint("nv_db_diagnostic", __name__)
_busy = threading.Lock()


def enabled():
    return os.getenv(SWITCH, "").strip().lower() in {"1", "true", "yes", "on"}


def _ms(value):
    return round(value * 1000, 1)


def _percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))]


def measure(dsn):
    """Meet nieuwe verbindingen en herhaalde queries; geeft alleen getallen terug."""
    import certifi
    import psycopg

    started = time.perf_counter()
    connect_times, query_times = [], []
    for _ in range(CONNECTIONS):
        if time.perf_counter() - started > BUDGET_SECONDS:
            break
        begin = time.perf_counter()
        with psycopg.connect(dsn, sslmode="verify-full", sslrootcert=certifi.where(),
                             connect_timeout=4, prepare_threshold=None, autocommit=True) as db:
            db.execute("SELECT 1").fetchone()
            connect_times.append(time.perf_counter() - begin)
            if len(query_times) < QUERIES:
                for _ in range(QUERIES - len(query_times)):
                    if time.perf_counter() - started > BUDGET_SECONDS:
                        break
                    tick = time.perf_counter()
                    db.execute("SELECT 1").fetchone()
                    query_times.append(time.perf_counter() - tick)
    if not connect_times or not query_times:
        raise RuntimeError("Geen meetwaarden")
    return {
        "nieuwe_verbinding": {"aantal": len(connect_times), "mediaan_ms": _ms(statistics.median(connect_times)),
                              "max_ms": _ms(max(connect_times))},
        "query": {"aantal": len(query_times), "mediaan_ms": _ms(statistics.median(query_times)),
                  "p95_ms": _ms(_percentile(query_times, 0.95)), "max_ms": _ms(max(query_times))},
        "totaal_ms": _ms(time.perf_counter() - started),
    }


@bp.get("/admin/nv/db-diagnose")
def diagnose():
    if not enabled():
        abort(404)
    return _diagnose_admin()


@require_admin
def _diagnose_admin():
    dsn = os.getenv(URL_VARIABLE, "").strip()
    if not dsn:
        return _answer({"fout": "Meetverbinding is niet ingesteld."}, 503)
    if not _busy.acquire(blocking=False):
        return _answer({"fout": "Er loopt al een meting."}, 429)
    try:
        return _answer(measure(dsn), 200)
    except Exception as error:  # noqa: BLE001 - alleen de klassenaam, nooit hostnamen of wachtwoorden
        return _answer({"fout": "Meting mislukt.", "type": type(error).__name__}, 503)
    finally:
        _busy.release()


def _answer(payload, status):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response
