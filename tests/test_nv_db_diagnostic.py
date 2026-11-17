"""Regiovergelijking van de databasediagnose: standaard uit, alleen beheerders, alleen getallen, geen geheimen."""
import json
import sys
import types

import pytest

import nv_db_diagnostic as diag
from test_system_check import administrator  # noqa: F401  (fixture)
import app as dashboard

URL_FRA = "postgresql://gebruiker:geheim-fra@ep-fra.example.invalid/db"
URL_ORE = "postgresql://gebruiker:geheim-ore@ep-ore.example.invalid/db"
ROUTE = "/admin/nv/db-diagnose"


@pytest.fixture
def regions(monkeypatch):
    monkeypatch.setenv(diag.SWITCH, "1")
    monkeypatch.delenv(diag.URL_VARIABLE, raising=False)
    monkeypatch.setenv("NUVEMIXA_DB_DIAGNOSTIC_URL_FRANKFURT", URL_FRA)
    monkeypatch.setenv("NUVEMIXA_DB_DIAGNOSTIC_URL_OREGON", URL_ORE)


def fake_measurements(monkeypatch, seconds, calls=None, fail=None):
    def fake(dsn):
        if calls is not None:
            calls.append("frankfurt" if "geheim-fra" in dsn else "oregon")
        if fail and fail in dsn:
            raise ConnectionError(f"kan {dsn} niet bereiken")
        value = seconds["frankfurt" if "geheim-fra" in dsn else "oregon"]
        return value * 5, [value] * diag.QUERIES_PER_CONNECTION
    monkeypatch.setattr(diag, "_connect_and_query", fake)


def test_route_is_off_by_default_even_with_urls_set(administrator, monkeypatch):
    monkeypatch.delenv(diag.SWITCH, raising=False)
    monkeypatch.setenv("NUVEMIXA_DB_DIAGNOSTIC_URL_FRANKFURT", URL_FRA)
    monkeypatch.setenv("NUVEMIXA_DB_DIAGNOSTIC_URL_OREGON", URL_ORE)
    assert administrator.get(ROUTE).status_code == 404


def test_route_requires_an_administrator(regions):
    assert dashboard.app.test_client().get(ROUTE).status_code == 403


def test_both_region_urls_are_required(administrator, monkeypatch):
    monkeypatch.setenv(diag.SWITCH, "1")
    monkeypatch.delenv(diag.URL_VARIABLE, raising=False)
    monkeypatch.setenv("NUVEMIXA_DB_DIAGNOSTIC_URL_FRANKFURT", URL_FRA)
    monkeypatch.delenv("NUVEMIXA_DB_DIAGNOSTIC_URL_OREGON", raising=False)
    fake_measurements(monkeypatch, {"frankfurt": 0.001, "oregon": 0.001}, calls := [])
    response = administrator.get(ROUTE)
    assert response.status_code == 503 and calls == []
    assert "geheim" not in response.get_data(as_text=True)


def test_regions_are_measured_alternately_in_one_round_and_only_numbers_are_shown(administrator, regions, monkeypatch):
    calls = []
    fake_measurements(monkeypatch, {"frankfurt": 0.170, "oregon": 0.002}, calls)
    response = administrator.get(ROUTE)
    body = response.get_data(as_text=True)
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    per_round = diag.CONNECTIONS_PER_ROUND
    assert calls[:2 * per_round] == ["frankfurt"] * per_round + ["oregon"] * per_round  # eerst Frankfurt, dan Oregon
    assert calls.count("frankfurt") == calls.count("oregon") == diag.ROUNDS * per_round
    data = response.json
    assert set(data["regios"]) == {"frankfurt", "oregon"}
    assert data["sneller"] == "oregon" and data["querymediaan_verschil_ms"] == 168.0
    assert data["regios"]["frankfurt"]["query"]["mediaan_ms"] == 170.0
    assert data["regios"]["frankfurt"]["rondes"] == diag.ROUNDS and data["regios"]["frankfurt"]["fouten"] == {}
    for secret in ("geheim", "gebruiker", "example.invalid", "postgresql://", "ep-fra", "ep-ore"):
        assert secret not in body


def test_one_failing_region_is_reported_without_secrets_and_the_other_still_measured(administrator, regions, monkeypatch):
    fake_measurements(monkeypatch, {"frankfurt": 0.100, "oregon": 0.002}, fail="geheim-fra")
    response = administrator.get(ROUTE)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    frankfurt = response.json["regios"]["frankfurt"]
    assert frankfurt["fouten"] == {"ConnectionError": diag.ROUNDS * diag.CONNECTIONS_PER_ROUND}
    assert "query" not in frankfurt and response.json["regios"]["oregon"]["query"]["mediaan_ms"] == 2.0
    assert "sneller" not in response.json
    for secret in ("geheim", "gebruiker", "example.invalid", "kan postgresql"):
        assert secret not in body


def test_all_regions_failing_gives_a_503_with_only_the_error_class(administrator, regions, monkeypatch):
    def broken(dsn):
        raise RuntimeError(dsn)
    monkeypatch.setattr(diag, "_connect_and_query", broken)
    response = administrator.get(ROUTE)
    body = response.get_data(as_text=True)
    assert response.status_code == 503 and json.loads(body) == {"fout": "Meting mislukt.", "type": "RuntimeError"}
    assert "geheim" not in body and "example.invalid" not in body


def test_time_budget_stops_the_measurement_and_says_so(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(diag.time, "perf_counter", lambda: clock["now"])

    def slow(dsn):
        clock["now"] += 10.0
        return 10.0, [0.001] * diag.QUERIES_PER_CONNECTION
    monkeypatch.setattr(diag, "_connect_and_query", slow)
    result = diag.measure_regions({"frankfurt": URL_FRA, "oregon": URL_ORE})
    assert result["afgebroken_door_tijdsbudget"] is True
    assert sum(r.get("nieuwe_verbinding", {}).get("aantal", 0) + ("eerste_verbinding_ms" in r) for r in result["regios"].values()) == 3


def test_second_measurement_is_refused_while_one_runs(administrator, regions, monkeypatch):
    fake_measurements(monkeypatch, {"frankfurt": 0.001, "oregon": 0.001}, calls := [])
    assert diag._busy.acquire(blocking=False)
    try:
        assert administrator.get(ROUTE).status_code == 429 and calls == []
    finally:
        diag._busy.release()


def test_single_url_mode_still_works_unchanged(administrator, monkeypatch):
    monkeypatch.setenv(diag.SWITCH, "1")
    monkeypatch.delenv("NUVEMIXA_DB_DIAGNOSTIC_URL_FRANKFURT", raising=False)
    monkeypatch.delenv("NUVEMIXA_DB_DIAGNOSTIC_URL_OREGON", raising=False)
    monkeypatch.setenv(diag.URL_VARIABLE, URL_FRA)
    result = {"query": {"aantal": 1}, "totaal_ms": 1.0}
    monkeypatch.setattr(diag, "measure", lambda dsn: result)
    assert administrator.get(ROUTE).json == result


def test_connection_is_verified_tls_and_only_runs_select_one(monkeypatch):
    seen = {"statements": [], "kwargs": None}

    class Result:
        def fetchone(self):
            return (1,)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement, *args):
            seen["statements"].append(statement)
            return Result()

    def connect(dsn, **kwargs):
        seen["kwargs"] = kwargs
        return Connection()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=connect))
    connected, timings = diag._connect_and_query(URL_FRA)
    assert set(seen["statements"]) == {"SELECT 1"} and len(timings) == diag.QUERIES_PER_CONNECTION
    assert seen["kwargs"]["sslmode"] == "verify-full" and seen["kwargs"]["autocommit"] is True
    assert seen["kwargs"]["connect_timeout"] <= 8


def test_diagnostic_does_not_switch_dashboard_features_to_postgres(regions, monkeypatch):
    import nv_dashboard_postgres
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_DATABASE_URL", raising=False)
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    assert nv_dashboard_postgres.configured() is False and nv_dashboard_postgres.runtime_enabled() is False
