"""Menu 'Extra producten': per hoofdcategorie producten toevoegen; standaard concept (niet in de webshop)."""
import pytest

import app as dashboard
import nv_catalog_manager
import nv_dashboard_manager
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401


@pytest.fixture
def local_db(tmp_path, monkeypatch):
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    monkeypatch.setattr(nv_dashboard_manager, "DB", tmp_path / "dashboard.sqlite3")
    monkeypatch.setattr(nv_catalog_manager, "DB", tmp_path / "dashboard.sqlite3")
    nv_catalog_manager.invalidate_changes()
    yield
    nv_catalog_manager.invalidate_changes()


def add(client, **fields):
    data = {"_csrf_token": CSRF_TOKEN, "section": "extra-producten", "category": "gadgets", "name": "Mini statiefhouder",
            "price": "14.95", "cost_price": "4.10", "stock_status": "unknown", "stock_quantity": "",
            "short_description": "Klein statief.", "description": "Compacte houder voor telefoon.", **fields}
    return client.post("/admin/nv/catalog", data=data)


def test_menu_shows_every_main_category_with_base_count(administrator, local_db):
    html = administrator.get("/dashboard?section=extra-producten").get_data(as_text=True)
    assert "Extra producten per categorie" in html
    for name in ("Gadgets", "Smart Home", "Beauty &amp; Care", "Home &amp; Living", "Lifestyle &amp; Sport"):
        assert f"+ Product toevoegen aan {name}" in html
    assert "20 basisproducten" in html
    assert 'href="/dashboard?section=extra-producten"' in administrator.get("/dashboard").get_data(as_text=True)


def test_new_product_is_concept_and_hidden_from_shop(administrator, local_db):
    response = add(administrator)
    assert response.status_code == 303 and "section=extra-producten" in response.location
    page = administrator.get("/dashboard?section=extra-producten").get_data(as_text=True)
    assert "Mini statiefhouder" in page and "Concept (verborgen)" in page and "inkoop €" in page.replace("\xa0", " ")
    shop = dashboard.app.test_client().get("/gadgets").get_data(as_text=True)
    assert "Mini statiefhouder" not in shop


def test_visible_product_appears_in_shop_and_can_be_hidden_again(administrator, local_db):
    add(administrator, visible="1")
    shop = dashboard.app.test_client().get("/gadgets").get_data(as_text=True)
    assert "Mini statiefhouder" in shop
    administrator.post("/admin/nv/catalog", data={"_csrf_token": CSRF_TOKEN, "section": "extra-producten", "category": "gadgets",
                                                  "slug": "mini-statiefhouder", "op": "visibility", "visible": "0"})
    assert "Mini statiefhouder" not in dashboard.app.test_client().get("/gadgets").get_data(as_text=True)


def test_invalid_input_is_refused_and_base_products_cannot_be_edited_here(administrator, local_db):
    add(administrator, cost_price="abc")
    add(administrator, name="Ander product", image="http://onveilig.example/x.jpg")
    page = administrator.get("/dashboard?section=extra-producten").get_data(as_text=True)
    assert "Mini statiefhouder" not in page and "Ander product" not in page
    with dashboard.app.test_request_context("/dashboard"):
        base = next(p for p in dashboard.catalog_items() if p["category_slug"] == "gadgets")
    response = administrator.post("/admin/nv/catalog", data={"_csrf_token": CSRF_TOKEN, "section": "extra-producten",
                                                             "category": "gadgets", "slug": base["slug"], "name": "Gewijzigd",
                                                             "price": "1", "stock_status": "unknown"})
    assert response.status_code == 404
