"""Alleen-lezen meting van de databasesnelheid vanuit de draaiende service (standaard UIT).

Aan te zetten met NUVEMIXA_DB_DIAGNOSTIC=1 en een aparte NUVEMIXA_DB_DIAGNOSTIC_URL (bewust niet de
dashboard-DSN, want die schakelt functies naar Postgres). Alleen beheerders; de uitvoer bevat alleen getallen.

Regiovergelijking: zijn NUVEMIXA_DB_DIAGNOSTIC_URL_FRANKFURT en NUVEMIXA_DB_DIAGNOSTIC_URL_OREGON beide gezet,
dan meet de route beide fictieve testdatabases afwisselend in dezelfde meetronde (alleen `SELECT 1`). De uitvoer
noemt alleen de vaste labels "frankfurt" en "oregon", nooit hostnamen, gebruikers of wachtwoorden.
"""
import os
import statistics
import threading
import time

from flask import Blueprint, abort, jsonify

from nv_dashboard_manager import require_admin

SWITCH = "NUVEMIXA_DB_DIAGNOSTIC"
URL_VARIABLE = "NUVEMIXA_DB_DIAGNOSTIC_URL"
REGION_VARIABLES = (("frankfurt", "NUVEMIXA_DB_DIAGNOSTIC_URL_FRANKFURT"),
                    ("oregon", "NUVEMIXA_DB_DIAGNOSTIC_URL_OREGON"))
ROUNDS = 3
CONNECTIONS_PER_ROUND = 2
QUERIES_PER_CONNECTION = 10
COMPARE_BUDGET_SECONDS = 25.0
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


def _connect_and_query(dsn):
    """Eén nieuwe verbinding plus herhaalde `SELECT 1`; geeft (verbindingstijd, [querytijden]) in seconden."""
    import certifi
    import psycopg

    begin = time.perf_counter()
    with psycopg.connect(dsn, sslmode="verify-full", sslrootcert=certifi.where(),
                         connect_timeout=8, prepare_threshold=None, autocommit=True) as db:
        db.execute("SELECT 1").fetchone()
        connected = time.perf_counter() - begin
        timings = []
        for _ in range(QUERIES_PER_CONNECTION):
            tick = time.perf_counter()
            db.execute("SELECT 1").fetchone()
            timings.append(time.perf_counter() - tick)
    return connected, timings


def _summary(first, connects, queries, rounds, errors):
    result = {"rondes": rounds, "fouten": errors}
    if first is not None:
        result["eerste_verbinding_ms"] = _ms(first)  # kan een koude Neon-start bevatten
    if connects:
        result["nieuwe_verbinding"] = {"aantal": len(connects), "mediaan_ms": _ms(statistics.median(connects)),
                                       "max_ms": _ms(max(connects))}
    if queries:
        result["query"] = {"aantal": len(queries), "mediaan_ms": _ms(statistics.median(queries)),
                           "p95_ms": _ms(_percentile(queries, 0.95)), "max_ms": _ms(max(queries))}
    return result


def measure_regions(dsns):
    """Meet de regio's afwisselend in dezelfde ronde. `dsns` is {label: dsn}; de uitvoer bevat alleen getallen."""
    started = time.perf_counter()
    state = {label: {"first": None, "connects": [], "queries": [], "rounds": 0, "errors": {}} for label in dsns}
    stopped_early = False
    for _round in range(ROUNDS):
        for label, dsn in dsns.items():
            entry = state[label]
            for _ in range(CONNECTIONS_PER_ROUND):
                if time.perf_counter() - started > COMPARE_BUDGET_SECONDS:
                    stopped_early = True
                    break
                try:
                    connected, timings = _connect_and_query(dsn)
                except Exception as error:  # noqa: BLE001 - alleen de klassenaam, nooit hostnamen of wachtwoorden
                    name = type(error).__name__
                    entry["errors"][name] = entry["errors"].get(name, 0) + 1
                    continue
                if entry["first"] is None:
                    entry["first"] = connected
                else:
                    entry["connects"].append(connected)
                entry["queries"].extend(timings)
            entry["rounds"] += 1
    regions = {label: _summary(e["first"], e["connects"], e["queries"], e["rounds"], e["errors"])
               for label, e in state.items()}
    result = {"regios": regions, "totaal_ms": _ms(time.perf_counter() - started)}
    if stopped_early:
        result["afgebroken_door_tijdsbudget"] = True
    medians = {label: r["query"]["mediaan_ms"] for label, r in regions.items() if "query" in r}
    if len(medians) == 2:
        result["querymediaan_verschil_ms"] = round(abs(medians["frankfurt"] - medians["oregon"]), 1)
        result["sneller"] = min(medians, key=medians.get)
    if not medians:
        raise RuntimeError("Geen meetwaarden")
    return result


@bp.get("/admin/nv/db-diagnose")
def diagnose():
    if not enabled():
        abort(404)
    return _diagnose_admin()


@require_admin
def _diagnose_admin():
    regions = {label: os.getenv(name, "").strip() for label, name in REGION_VARIABLES}
    given = {label: dsn for label, dsn in regions.items() if dsn}
    if given and len(given) != len(REGION_VARIABLES):
        return _answer({"fout": "Voor de regiovergelijking zijn beide meetverbindingen nodig."}, 503)
    dsn = os.getenv(URL_VARIABLE, "").strip()
    if not given and not dsn:
        return _answer({"fout": "Meetverbinding is niet ingesteld."}, 503)
    if not _busy.acquire(blocking=False):
        return _answer({"fout": "Er loopt al een meting."}, 429)
    try:
        return _answer(measure_regions(given) if given else measure(dsn), 200)
    except Exception as error:  # noqa: BLE001 - alleen de klassenaam, nooit hostnamen of wachtwoorden
        return _answer({"fout": "Meting mislukt.", "type": type(error).__name__}, 503)
    finally:
        _busy.release()


def _answer(payload, status):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response
