from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

import app
import nv_dashboard_manager
import nv_dashboard_postgres
from nv_supplier_finder import POINTS, assess, directories, rank_offers, search_supplier_sources
from test_dashboard_workspace import isolated_research
from test_nv_2fa_postgres import databases, pg_state, seed
from test_system_check import administrator, CSRF_TOKEN


BASE = {
    "name": "Fixture supplier", "kind": "distributor", "identifier": "gtin", "match_value": "123",
    "company_country": "NL", "warehouse_country": "NL", "warehouse_location": "Fixture warehouse",
    "return_country": "NL", "return_address": "Fixture return desk", "processing": 1, "transport": 2,
    "deliveries": 10, "on_time": 10, "buy": "10", "shipping": "2", "duty": "0",
    "exact_match": True, "stock": True, "dropship": True, "tracking": True, "safe": True,
    "quality": True, "service": True,
    **{key: "https://fixture.invalid/" + key for key in ("warehouse_url", "offer_url", "safety_url", "history_url", "returns_url", "business_url")},
}
DOSSIER = dict(gross="50", tax="8", payment="1", returns="2", warranty="0", fx="0", other="0", ads="5")


def test_ranking_requires_real_warehouse_and_verified_dropshipping():
    eu = dict(BASE, name="EU")
    foreign = dict(BASE, name="Outside", warehouse_country="CN", buy="5", transport=6)
    blocked = dict(BASE, name="Unverified", dropship=False, safe=False)
    retailer = dict(BASE, name="Retailer", kind="retailer")
    ranked = rank_offers([foreign, blocked, eu, retailer], "NL", DOSSIER)
    assert [r["name"] for r in ranked[:2]] == ["EU", "Outside"]
    assert ranked[0]["score"] == sum(maximum for _, maximum in POINTS.values()) == 100
    assert ranked[0]["days"] == 3 and ranked[0]["total"] == Decimal("12")
    assert ranked[1]["region"] == 0 and ranked[1]["days"] == 7
    assert all(not row["ready"] for row in ranked[2:])
    assert assess(dict(BASE, warehouse_url=""), "NL", DOSSIER)["region"] == 0
    assert [row[0] for row in directories("NL")[:3]] == ["NL", "BE", "DE"]


def test_only_evidence_of_better_terms_can_override_eu_order():
    eu = dict(BASE, name="EU", on_time=9)
    outside = dict(BASE, name="Verified", warehouse_country="CN", buy="9")
    unknown = dict(BASE, name="No history", warehouse_country="CN", buy="3", history_url="")
    assert [r["name"] for r in rank_offers([eu, outside, unknown], "BE", DOSSIER)] == ["Verified","EU","No history"]
    assert rank_offers([eu, outside], "NL", {})[0]["name"] == "EU"
    us = dict(BASE, name="US", warehouse_country="US", return_country="US")
    assert rank_offers([eu, us], "US", DOSSIER)[0]["name"] == "US"


def test_comparison_saved_in_existing_dossier(isolated_research):
    client, candidate = isolated_research
    def form(name, origin):
        values = {key: str(value) if type(value) is not bool else str(int(value)) for key,value in BASE.items()}
        return dict(values, _csrf_token=CSRF_TOKEN, candidate=candidate, market="NL", name=name,
                    warehouse_country=origin, checked="2024-01-01")
    for name, origin in (("Fixture Alpha", "NL"), ("Fixture Beta", "DE"), ("Fixture Gamma", "CN")):
        assert client.post("/dashboard/viral/supplier", data=form(name, origin)).status_code == 303
    page = client.get(f"/dashboard?section=viral&detail={candidate}")
    assert b"3 aanbiedingen met bevestigde basisgegevens" in page.data
    assert b"Fixture Alpha" in page.data and b"Fixture Gamma" in page.data and b"3 werkdagen" in page.data
    assert client.post("/dashboard/viral/supplier", data={"candidate": candidate}).status_code == 403


def test_ai_supplier_search_accepts_only_cited_approved_organisations(monkeypatch):
    monkeypatch.setenv("NUVEMIXA_SUPPLIER_SEARCH_MODEL", "fixture-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    import json
    import nv_supplier_finder
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, _):
            urls = ["https://www.ikea.com/fixture", "https://www.dropxl.com/nl/faq.html",
                    "https://www.dropxl.com/nl/other", "https://sirocco.de/dropshipping/"]
            references = [{"url": url, "type": "url_citation"} for url in urls]
            return json.dumps({"output": [{"type": "message", "content": [
                {"type": "output_text", "text": "Pretend price or lead time.", "annotations": references}
            ]}]}).encode()
    def response(request, timeout):
        data = json.loads(request.data)
        allowed = data["tools"][0]["filters"]["allowed_domains"]
        assert allowed[:3] == ["dropxl.com", "versagroup.be", "sirocco.de"]
        assert "Pretend" not in str(data) and "GTIN-TEST" in data["input"]
        return Reply()
    monkeypatch.setattr(nv_supplier_finder.urllib.request, "urlopen", response)
    assert [row["name"] for row in search_supplier_sources("Fixture", "GTIN-TEST", "NL")] == ["dropxl.com", "sirocco.de"]


def test_postgres_runtime_keeps_route_data_and_staff_login(databases, administrator, monkeypatch, tmp_path):
    monkeypatch.setenv("NUVEMIXA_STAFF_LOGIN", "on")
    import psycopg
    target = databases()
    from uuid import uuid4
    from psycopg import sql
    role = sql.Identifier("dashboard_test_" + uuid4().hex)
    with psycopg.connect(target, autocommit=True) as db:
        db.execute(Path("nv_dashboard_postgres.sql").read_text(encoding="utf-8"))
        db.execute("CREATE SCHEMA nuvemixa_auth")
        db.execute("CREATE TABLE nuvemixa_auth.state (fixture text)")
        db.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA nuvemixa_dashboard TO {}").format(role))
        db.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA nuvemixa_dashboard TO {}").format(role))
        db.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA nuvemixa_dashboard TO {}").format(role))
    @contextmanager
    def db_connection():
        with psycopg.connect(target) as db:
            db.execute(sql.SQL("SET ROLE {}").format(role))
            yield db
    monkeypatch.setattr(nv_dashboard_postgres, "connect", db_connection)
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    monkeypatch.setattr(app, "_CUSTOMER_DB", tmp_path / "forbidden-local.sqlite3")
    monkeypatch.setattr(nv_dashboard_manager, "DB", tmp_path / "forbidden-dashboard.sqlite3")
    def submit(route, **fields):
        response = administrator.post(route, data={"_csrf_token": CSRF_TOKEN, **fields})
        assert response.status_code == 303, (route, response.status_code)
        return response
    assert "toegevoegd" in submit("/admin/customers/create", name="Pg Client", email="client@example.invalid", password="fixture-long-war").location
    assert "toegevoegd" in submit("/admin/suppliers", name="Pg Supplier", website="https://supplier.example.invalid").location
    submit("/admin/nv/coupons", percentage="10")
    submit("/admin/nv/catalog", section="categorieen", name="Fixture Pg Category")
    submit("/dashboard/internationaal", market="NL", product="kabels", sales="45")
    submit("/dashboard/viral", country="NL", niche="Huis en wonen", title="Pg Trend")
    with psycopg.connect(target) as db:
        candidate = db.execute("SELECT id FROM nuvemixa_dashboard.viral_candidates").fetchone()[0]
    submit("/dashboard/viral", candidate=candidate, action="observation", platform="pinterest",
           source="https://www.pinterest.com/fixture", observed="2024-01-01", window="7", metric="interest", value="11")
    submit("/dashboard/viral/dossier", candidate=candidate, market="NL", gross="50")
    comparison = {key: str(value) if type(value) is not bool else str(int(value)) for key,value in BASE.items()}
    submit("/dashboard/viral/supplier", candidate=candidate, market="NL", checked="2024-01-01", **comparison)
    submit("/admin/nv/team", op="create", username="fixture-staff", email="staff@example.invalid",
           name="Pg Staff", role="employee", password="fixture-long-password",
           permissions_present="1", permission="merchant_view")
    with app.app.test_request_context("/"):
        product = next(iter(app.catalog_items()))
    submit("/admin/nv/seo-scan", product_url=product["product_url"])
    for name, text in (("klanten", b"Pg Client"), ("leveranciers", b"Pg Supplier"),
                       ("categorieen", b"Fixture Pg Category"), ("kortingen", b"10%"),
                       ("viral&detail=1", b"Fixture supplier"), ("seo", b"Laatste rapport")):
        assert text in administrator.get("/dashboard?section=" + name).data
    staff = app.app.test_client()
    staff.get("/admin/login")
    with staff.session_transaction() as saved:
        token = saved["_tm_csrf"]
    result = staff.post("/admin/login", data={"email":"fixture-staff","password":"fixture-long-password","_csrf_token":token})
    assert result.location == "/dashboard"
    assert staff.get("/admin/merchant-preview").status_code == 200
    assert staff.get("/admin/monitoring/check").status_code == 403
    assert not app._CUSTOMER_DB.exists() and not nv_dashboard_manager.DB.exists()
    assert administrator.get("/admin/monitoring/check").json["summary"]["error"] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db_connection() as db:
        db.execute("SELECT * FROM nuvemixa_auth.state")
    def unavailable():
        raise psycopg.OperationalError("fixture details")
    monkeypatch.setattr(nv_dashboard_postgres, "connect", unavailable)
    assert b"Klantdatabase kan niet worden gelezen" in administrator.get("/dashboard?section=klanten").data
    assert not app._CUSTOMER_DB.exists()


def test_primary_admin_and_totp_with_isolated_dashboard_database(databases, pg_state, monkeypatch):
    import psycopg
    import pyotp
    from werkzeug.security import generate_password_hash

    target = databases()
    with psycopg.connect(target, autocommit=True) as db:
        db.execute(Path("nv_dashboard_postgres.sql").read_text(encoding="utf-8"))
    @contextmanager
    def dashboard_db():
        with psycopg.connect(target) as db:
            yield db
    seed(pg_state[-1])
    monkeypatch.setattr(nv_dashboard_postgres, "connect", dashboard_db)
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_DATABASE_URL", target)
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "fixture-primary@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", generate_password_hash("fixture dashboard password"))
    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_SECURE", False)
    admin = app.app.test_client()
    def post(route, **fields):
        admin.get(route)
        with admin.session_transaction() as saved:
            token = saved["_tm_csrf"]
        return admin.post(route, data={"_csrf_token": token, **fields})
    assert post("/admin/login", email="fixture-primary@example.invalid",
                password="fixture dashboard password").location == "/admin/2fa"
    assert admin.get("/dashboard").status_code == 302
    assert post("/admin/2fa", code=pyotp.TOTP(pg_state[2]).now()).status_code == 302
    assert admin.get("/dashboard?section=kortingen").status_code == 200
    with psycopg.connect(target) as db:
        assert db.execute("SELECT to_regclass('nuvemixa_auth.state')").fetchone() == (None,)
