from contextlib import closing
import sqlite3

import pytest

import app as dashboard
import nv_2fa_login
import nv_visits

CSRF_TOKEN = "system-test-csrf-" + "x" * 32


@pytest.fixture
def administrator(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "admin@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", "fixture-only")
    monkeypatch.setattr(nv_2fa_login, "is_2fa_actief", lambda: True)
    monkeypatch.setitem(dashboard.app.config, "SESSION_COOKIE_SECURE", False)
    client = dashboard.app.test_client()
    with client.session_transaction() as saved:
        saved["nv_admin"] = True
        saved["_tm_csrf"] = CSRF_TOKEN
    return client


def check(response, name):
    assert response.status_code == 200
    return next(row for row in response.json["checks"] if row["name"] == name)


def test_customer_scan_and_explicit_initialization(administrator, monkeypatch, tmp_path):
    path = tmp_path / "customers.sqlite3"
    monkeypatch.setattr(dashboard, "_CUSTOMER_DB", path)
    route = "/admin/monitoring/check"
    initialize = {"action": "initialize_customers", "_csrf_token": CSRF_TOKEN}

    assert check(administrator.get(route), "Klantdatabase")["status"] == "attention"
    assert b"Lege klanttabel initialiseren" in administrator.get("/dashboard?section=monitoring&scan=1").data
    assert administrator.get("/dashboard?section=klanten").status_code == 200
    assert administrator.post(route, data={"action": initialize["action"]}).status_code == 403
    assert not path.exists()
    staff = dashboard.app.test_client()
    with staff.session_transaction() as saved:
        saved["_tm_csrf"] = CSRF_TOKEN
    assert staff.post(route, data=initialize).status_code == 403
    assert administrator.post(route, data=initialize).status_code == 303
    assert check(administrator.get(route), "Klantdatabase")["status"] == "works"
    created = administrator.post("/admin/customers/create", data={
        "_csrf_token": CSRF_TOKEN, "name": "Fixture klant", "email": "buyer@example.invalid",
        "password": "fixture-password",
    })
    assert created.status_code == 303 and "toegevoegd" in created.location
    assert administrator.post(route, data=initialize).status_code == 303
    assert b"Fixture klant" in administrator.get("/dashboard?section=klanten").data


def test_customer_scan_preserves_other_tables_and_incompatible_schema(administrator, monkeypatch, tmp_path):
    path = tmp_path / "customers.sqlite3"
    monkeypatch.setattr(dashboard, "_CUSTOMER_DB", path)
    route = "/admin/monitoring/check"
    initialize = {"action": "initialize_customers", "_csrf_token": CSRF_TOKEN}
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE preserved (value TEXT)")
        db.execute("INSERT INTO preserved VALUES ('existing')")
    assert "klanttabel ontbreekt" in check(administrator.get(route), "Klantdatabase")["result"]
    assert administrator.post(route, data=initialize).status_code == 303
    with closing(sqlite3.connect(path)) as db, db:
        assert db.execute("SELECT value FROM preserved").fetchone() == ("existing",)
        db.execute("DROP TABLE customers")
        db.execute("CREATE TABLE customers (id INTEGER)")
    assert "password_hash" in check(administrator.get(route), "Klantdatabase")["result"]
    assert administrator.post(route, data=initialize).status_code == 409
    with closing(sqlite3.connect(path)) as db:
        assert [row[1] for row in db.execute("PRAGMA table_info(customers)")] == ["id"]


def test_merchant_previews_share_eligibility(administrator, monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard.app, "static_folder", str(tmp_path))
    photo = tmp_path / "photo.jpg"
    photo.touch()
    item = {
        "id": "eligible", "name": "Fixture", "description": "Fixture product", "price": "1.00",
        "stock_status": "in_stock", "brand": "Fixture", "mpn": "fixture", "product_url": "/gadgets/test",
        "image": "/static/photo.jpg", **{key: True for key in (
            "merchant_verified", "supplier_verified", "product_data_verified",
            "price_verified", "image_verified", "delivery_verified")},
    }
    items = [item, {**item, "id": "duplicate"}, {**item, "id": "duplicate"},
             {**item, "id": "a" * 51, "image": "/img/product/gadgets/test.svg"},
             {**item, "id": "broken", "image": "/static/missing.jpg"},
             {**item, "id": "broken-absolute", "image": "https://nuvemixa.alwaysdata.net/static/missing.jpg"},
             {**item, "id": "placeholder", "image": "/%69mg/product/gadgets/test.svg"},
             {**item, "id": "blank-identifiers", "brand": " ", "mpn": "\t"},
             {**item, "id": "sub-cent", "price": "0.001"},
             {**item, "id": "other-port", "product_url": "https://nuvemixa.alwaysdata.net:8443/gadgets/test"}]
    monkeypatch.setattr(dashboard, "catalog_items", lambda: items)
    report = administrator.get("/admin/merchant-preview").json
    assert report["ready"] == 1
    assert report["reason_counts"] == {
        "dubbele product-ID": 2, "gegenereerde tijdelijke afbeelding": 2,
        "product-ID": 1, "lokaal afbeeldingsbestand ontbreekt": 2, "prijs": 1, "productlink": 1,
        "merk en GTIN of MPN": 1,
    }
    assert "51 tekens" in report["products"][3]["issues"][0]["detail"]
    feed = administrator.get("/admin/merchant-feed-preview.xml")
    assert feed.headers["X-NUVEMIXA-Eligible-Count"] == "1"
    assert b"<g:id>eligible</g:id>" in feed.data


def test_seo_report_is_run_locally_stored_and_read_back(administrator, monkeypatch, tmp_path):
    import nv_dashboard_manager as manager
    import nv_seo_scan

    path = tmp_path / "seo.sqlite3"
    monkeypatch.setattr(manager, "DB", path)
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    monkeypatch.delenv("NUVEMIXA_CANONICAL_URL", raising=False)
    url = "/dashboard?section=seo"
    assert b"Nog geen lokaal SEO-rapport" in administrator.get(url).data
    assert not path.exists()
    product = next(dashboard.catalog_items())
    action = "/admin/nv/seo-scan"
    assert administrator.post(action, data={"product_url": product["product_url"]}).status_code == 403
    assert administrator.post(action, data={
        "_csrf_token": CSRF_TOKEN, "product_url": product["product_url"],
    }).status_code == 303
    _, report = nv_seo_scan.last_scan()
    assert report["path"] == product["product_url"]
    assert [check[1] for check in report["checks"]] == [True, True, True, True]
    assert b"Laatste rapport" in administrator.get(url).data
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE seo_scans SET payload = '[]'")
    assert b"Het laatste scanrapport kan tijdelijk niet worden geladen." in administrator.get(url).data


def test_visitor_count_opt_in_and_exclusions(administrator, monkeypatch, tmp_path):
    path = tmp_path / "visits.sqlite3"
    monkeypatch.setattr(nv_visits, "DB", path)
    monkeypatch.setenv("NUVEMIXA_VISIT_TRAFFIC", "test")
    monkeypatch.delenv("NUVEMIXA_VISIT_COUNTER", raising=False)
    route = "/admin/monitoring/check"
    browser = {"User-Agent": "Mozilla/5.0 Chrome/120"}
    client = dashboard.app.test_client()
    assert client.get("/", headers=browser).status_code == 200
    assert not path.exists()
    assert check(administrator.get(route), "Bezoekersteller")["status"] == "disabled"
    monkeypatch.setenv("NUVEMIXA_VISIT_COUNTER", "true")
    assert check(administrator.get(route), "Bezoekersteller")["status"] == "unchecked"
    client.get("/", headers={**browser, "Sec-GPC": "1"})
    client.get("/", headers={**browser, "DNT": "1"})
    client.get("/", headers={"User-Agent": "Googlebot"})
    administrator.get("/", headers=browser)
    assert not path.exists()
    client.get("/", headers=browser)
    client.get("/shop", headers=browser)
    assert nv_visits.visit_summary()["groups"][0][4] == 1
    assert check(administrator.get(route), "Bezoekersteller")["status"] == "works"
    monkeypatch.setenv("NUVEMIXA_VISIT_TRAFFIC", "webshop")
    assert check(administrator.get(route), "Bezoekersteller")["status"] == "unchecked"


def test_monitoring_only_probes_an_explicitly_requested_connection(administrator, monkeypatch):
    route = "/admin/monitoring/check"
    monkeypatch.delenv("MOLLIE_API_KEY", raising=False)
    calls = []

    def probe():
        calls.append(True)
        return {"state": "connected_test" if len(calls) == 1 else "unavailable", "message": "Fixture"}

    monkeypatch.setattr(dashboard, "mollie_readonly_check", probe)
    form = {"action": "Betalingen", "_csrf_token": CSRF_TOKEN}
    assert check(administrator.post(route, data=form), "Betalingen")["status"] == "unconfigured"
    monkeypatch.setenv("MOLLIE_API_KEY", "test_fixture")
    assert check(administrator.get(route), "Betalingen")["status"] == "unchecked"
    assert calls == []
    assert check(administrator.post(route, data=form), "Betalingen")["status"] == "works"
    assert check(administrator.post(route, data=form), "Betalingen")["status"] == "failed"
    assert len(calls) == 2


def test_monitoring_woocommerce_needs_the_safe_read_configuration(administrator, monkeypatch):
    route = "/admin/monitoring/check"
    monkeypatch.setattr(dashboard, "woo_configured", lambda: True)
    monkeypatch.setattr(dashboard, "read_configuration_present", lambda: False)
    fetches = []

    def read_orders():
        fetches.append(True)
        if len(fetches) == 2:
            raise dashboard.CommerceConnectionError("fixture connection failure")
        return []

    monkeypatch.setattr(dashboard, "read_recent_orders", read_orders)
    form = {"action": "WooCommerce", "_csrf_token": CSRF_TOKEN}
    assert check(administrator.post(route, data=form), "WooCommerce")["status"] == "unchecked"
    assert fetches == []
    monkeypatch.setattr(dashboard, "read_configuration_present", lambda: True)
    assert check(administrator.post(route, data=form), "WooCommerce")["status"] == "works"
    assert check(administrator.post(route, data=form), "WooCommerce")["status"] == "failed"
