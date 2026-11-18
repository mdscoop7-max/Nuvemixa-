import hashlib
import json
import sqlite3
import subprocess
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

import pytest

import app as dashboard
import migrate_dashboard_postgres as migration
import nuvemixa_admin_store
import nv_dashboard_manager
import nv_dashboard_postgres
import nv_product_dossier
import nv_research_assistant
import nv_visits
from nv_seo_scan import canonical_matches
from test_nv_2fa_postgres import databases
from test_system_check import administrator, CSRF_TOKEN


def test_coupon_dates_are_optional_and_inclusive(administrator, monkeypatch, tmp_path):
    monkeypatch.setattr(nv_dashboard_manager, "DB", tmp_path / "discounts.sqlite3")
    monkeypatch.setattr(nv_dashboard_manager, "coupon_today", lambda: "2026-12-01")
    form = {"_csrf_token": CSRF_TOKEN, "percentage": "12"}
    def submit(starts, ends):
        return administrator.post("/admin/nv/coupons", data=dict(form, starts=starts, ends=ends))
    for invalid in (("2026-02-30", ""), ("20261201", ""), ("2026-12-02", "2026-12-01")):
        assert submit(*invalid).status_code == 303
        assert nv_dashboard_manager.coupon_rows() == []
    for valid in (("2026-12-01", "2026-12-01"), ("2026-12-02", ""), ("", "2026-11-30")):
        assert submit(*valid).status_code == 303
    rows = nv_dashboard_manager.coupon_rows()
    assert [r["status"] for r in rows] == ["Verlopen", "Gepland", "Actief"]
    assert nv_dashboard_manager.test_checkout_discount(rows[-1]["code"], 1000) == 120
    assert all(r["used"] == 0 for r in rows)


def test_dashboard_woo_uses_protected_read_path(administrator, monkeypatch):
    """Pagina openen doet geen aanroep; na een bewuste klik toont Bestellingen alleen veilige velden."""
    import nv_woo_bridge
    for k, v in {"URL": "https://shop.example.invalid", "KEY": "ck_x", "SECRET": "cs_x", "HOST": "shop.example.invalid"}.items():
        monkeypatch.setenv("NUVEMIXA_WOO_" + k, v)
    nv_woo_bridge.reset_test()
    monkeypatch.setattr(dashboard, "woo_request", lambda *a: pytest.fail("Legacy call"))
    monkeypatch.setattr(nv_woo_bridge, "_fetch", lambda *a: pytest.fail("Aanroep bij openen van de pagina"))
    assert administrator.get("/dashboard?section=bestellingen").status_code == 200
    monkeypatch.setattr(nv_woo_bridge, "_fetch", lambda b, a, path, h: [{
        "id": 757, "status": "processing", "billing": {"email": "private@example.invalid"},
    }])
    administrator.post("/admin/commerce/refresh", data={"_csrf_token": CSRF_TOKEN})
    monkeypatch.setattr(nv_woo_bridge, "_fetch", lambda *a: pytest.fail("Aanroep bij openen van de pagina"))
    response = administrator.get("/dashboard?section=bestellingen")
    assert response.status_code == 200
    assert b"#757" in response.data
    assert b"private@example.invalid" not in response.data
    nv_woo_bridge.reset_test()


def test_canonical_uses_the_expected_origin(monkeypatch):
    monkeypatch.setenv("NUVEMIXA_CANONICAL_URL", "https://shop.example.invalid")
    path = "/gadgets/product"
    assert canonical_matches("https://shop.example.invalid" + path, path, "http://localhost/")
    for url in ("https://other.example.invalid", "http://shop.example.invalid", "https://shop.example.invalid:8080"):
        assert not canonical_matches(url + path, path, "http://localhost/")


def test_visits_deduplicate_requests_and_report_calendar_periods(administrator, monkeypatch, tmp_path):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 9, 0, 15, tzinfo=tz)
    path = tmp_path / "visits.sqlite3"
    monkeypatch.setattr(nv_visits, "DB", path)
    monkeypatch.setattr(nv_visits, "datetime", Clock)
    monkeypatch.setenv("NUVEMIXA_VISIT_COUNTER", "true")
    monkeypatch.setenv("NUVEMIXA_VISIT_TRAFFIC", "test")
    browser = {"User-Agent": "Mozilla Chrome"}
    first = dashboard.app.test_client()
    first.get("/", headers=browser)
    assert not path.exists()
    cookie = first.get_cookie(nv_visits.COOKIE)
    assert cookie is not None
    second = dashboard.app.test_client()
    second.set_cookie(nv_visits.COOKIE, cookie.value)
    for client in (first, second):
        client.get("/", headers=browser)
    assert nv_visits.visit_summary()["groups"][0][1:6] == (1, 0, 1, 1, 1)
    with closing(sqlite3.connect(path)) as db, db:
        db.executemany("INSERT INTO storefront_visits VALUES ('test', ?, 'historic', ?)",
                       [(day, day) for day in ("2026-11-08", "2026-11-01", "2026-10-31")])
    summary = nv_visits.visit_summary()
    assert summary["groups"][0][1:6] == (1, 1, 1, 3, 4)
    chart = summary["charts"]["test"]
    assert chart["day"][-1] == ("09-11", 1)
    assert chart["week"][-1] == ("09-11", 1)
    assert chart["month"][-1] == ("11-2026", 3)
    page = administrator.get("/dashboard?section=statistieken")
    assert b"Deze week" in page.data and b"Maandelijks" in page.data


@pytest.fixture
def isolated_research(administrator, monkeypatch, tmp_path):
    monkeypatch.setattr(nuvemixa_admin_store, "ADMIN_DB", tmp_path / "research.sqlite3")
    form = {"_csrf_token": CSRF_TOKEN, "title": "Fixture organizer", "country": "NL",
            "niche": "Huis en wonen"}
    assert administrator.post("/dashboard/viral", data=form).status_code == 303
    with nuvemixa_admin_store.connect() as db:
        candidate = db.execute("SELECT id FROM viral_candidates").fetchone()[0]
    return administrator, candidate


def test_saved_viral_search_opens_results(isolated_research):
    admin, _ = isolated_research
    result = admin.get("/dashboard?section=viral&candidate_q=organizer").get_data(as_text=True)
    assert 'class="panel nv-manual-block" open' in result and "Fixture organizer" in result
    unmatched = admin.get("/dashboard?section=viral&candidate_q=yogamat").get_data(as_text=True)
    assert "Fixture organizer" not in unmatched


def test_dossier_retains_offers_and_never_approves_retailer(isolated_research):
    admin, candidate = isolated_research
    form = {"_csrf_token": CSRF_TOKEN, "candidate": candidate, "market": "NL",
            "demand_url": "https://example.invalid/demand", "demand_date": "2024-01-01",
            "offer_url": "https://example.invalid/offer", "offer_date": "2024-01-01",
            "demand_confirmed": "1", "dropship": "1", "supplier_name": "Example",
            "supplier_kind": "retailer", "stock": "in_stock", "delivery": "Demo",
            "returns_terms": "Demo", "gross": "100", "tax": "10", "buy": "20",
            **{k: "0" for k in ("shipping","duty","payment","returns","warranty","fx","other","ads")}}
    assert admin.post("/dashboard/viral/dossier", data=form).status_code == 303
    page = admin.get(f"/dashboard?section=viral&detail={candidate}")
    assert b"Vraag bevestigd" in page.data and b"Leverancier bevestigd" not in page.data
    assert b"70.00" in page.data and b"Onbekend" in page.data
    second = dict(form, market="GB", offer_amount="10", offer_currency="EUR")
    invalid = admin.post("/dashboard/viral/dossier", data=second, follow_redirects=True)
    assert b"Vul wisselkoers" in invalid.data
    second.update(exchange_rate="0.8", exchange_url="https://example.invalid/rate", exchange_date="2024-01-01")
    assert admin.post("/dashboard/viral/dossier", data=second).status_code == 303
    with nuvemixa_admin_store.connect() as db:
        rows = db.execute("SELECT market,payload FROM product_dossier_offers ORDER BY market").fetchall()
    assert [row[0] for row in rows] == ["GB", "NL"]
    assert json.loads(rows[0][1])["buy"] == "8.00"


def test_research_ai_only_emits_a_known_action_with_evidence(isolated_research, monkeypatch):
    admin, candidate = isolated_research
    with nuvemixa_admin_store.connect() as db:
        db.execute("INSERT INTO viral_observations VALUES (?, 'pinterest', ?, '2024-01-01', 7, 'interest', 42, 0)",
                   (candidate, "https://www.pinterest.com/private-fixture"))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture")
    monkeypatch.setenv("NUVEMIXA_RESEARCH_AI", "true")
    class ModelResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, _):
            answer = json.dumps({"action": "supplier", "evidence": [1]})
            return json.dumps({"choices": [{"message": {"content": answer}}]}).encode()
    def model(request, timeout):
        assert b"42" in request.data and b"private-fixture" not in request.data
        assert request.full_url == "https://api.openai.com/v1/chat/completions"
        return ModelResponse()
    monkeypatch.setattr(nv_research_assistant.urllib.request, "urlopen", model)
    page = admin.post("/dashboard/viral/assistant",
                      data={"_csrf_token": CSRF_TOKEN, "candidate": candidate}, follow_redirects=True)
    assert b"schriftelijke dropshippingofferte" in page.data and b"pinterest 2024-01-01" in page.data


def test_postgres_visits_and_verified_snapshot_import(databases, monkeypatch, tmp_path):
    import psycopg
    dsn = databases()
    with psycopg.connect(dsn, autocommit=True) as target:
        target.execute(Path("nv_dashboard_postgres.sql").read_text(encoding="utf-8"))
    hashes = {}
    rows = {}
    for filename, tables in migration.FILES.items():
        path = tmp_path / filename
        with closing(sqlite3.connect(path)) as source, source:
            for table, (fields, keys) in tables.items():
                columns = fields.split()
                source.execute(f'CREATE TABLE "{table}" (' + ", ".join(f'"{col}"' for col in columns) + ")")
                numbers = {"id": 7, "candidate": 7, "candidate_id": 7, "supplier_id": 7, "customer_id": 7,
                           "used": 2, "active": 1, "usage_limit": 9, "amount": 4.35, "views": 3, "window": 7,
                           "value": 40, "estimate": 0, "purchase_cost_cents": 9, "shipping_cost_cents": 8,
                           "selling_price_cents": 20, "pageviews": 3}
                record = tuple(numbers.get(col, f"{table}-{col}") for col in columns)
                if table == "storefront_visits":
                    record = ("test", datetime.now(nv_visits.TIMEZONE).date().isoformat(), "historic", "measured-fixture")
                source.execute(f'INSERT INTO "{table}" VALUES (' + ",".join("?" for _ in columns) + ")", record)
                rows[table] = record
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    data = migration.source_rows(tmp_path, hashes)
    broken = dict(data)
    fields, keys, records = broken["coupons"]
    broken["coupons"] = (fields, keys, records + records)
    with pytest.raises(psycopg.errors.UniqueViolation), psycopg.connect(dsn) as db:
        migration.import_rows(db, broken)
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM nuvemixa_dashboard.staff").fetchone() == (0,)
        migration.import_rows(db, data)
    with pytest.raises(ValueError, match="bevat gegevens"), psycopg.connect(dsn) as db:
        migration.import_rows(db, data)
    @contextmanager
    def test_connection():
        with psycopg.connect(dsn) as db:
            yield db
    monkeypatch.setattr(nv_dashboard_postgres, "connect", test_connection)
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_DATABASE_URL", dsn)
    summary = nv_visits.visit_summary()
    assert len(data) == 16
    assert summary["backend"] == "PostgreSQL" and summary["groups"][0][1] == 1
    monkeypatch.setenv("NUVEMIXA_VISIT_COUNTER", "true")
    monkeypatch.setenv("NUVEMIXA_VISIT_TRAFFIC", "test")
    monkeypatch.setattr(nv_visits, "DB", tmp_path / "no-sqlite-fallback.sqlite3")
    monkeypatch.setitem(dashboard.app.config, "SESSION_COOKIE_SECURE", False)
    visitor = dashboard.app.test_client()
    for _ in range(3):
        assert visitor.get("/", headers={"User-Agent": "Mozilla Chrome"}).status_code == 200
    assert nv_visits.visit_summary()["groups"][0][1] == 2
    assert not nv_visits.DB.exists()
    restored = databases()
    dump = subprocess.run(["pg_dump", "--schema=nuvemixa_dashboard", "-Fc", "--dbname", dsn],
                          check=True, capture_output=True).stdout
    subprocess.run(["pg_restore", "--exit-on-error", "--single-transaction", "--dbname", restored],
                   input=dump, check=True, capture_output=True)
    with psycopg.connect(restored) as db:
        for table in data:
            # Identifiers come from the fixed migration manifest.
            expected_count = 2 if table == "storefront_visits" else 1
            assert db.execute(f"SELECT count(*) FROM nuvemixa_dashboard.{table}").fetchone() == (expected_count,)
        assert db.execute("SELECT nextval(pg_get_serial_sequence('nuvemixa_dashboard.staff','id'))").fetchone() == (8,)
        assert db.execute("SELECT to_regclass('nuvemixa_auth.state')").fetchone() == (None,)
