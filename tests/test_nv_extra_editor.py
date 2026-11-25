"""Exercise the editor through its real form endpoint and public catalogue."""
import json
from datetime import date, timedelta

import pytest
import app
import nv_extra_pricing as pricing
import nv_catalog_manager as catalog
from test_extra_producten import administrator, local_db, _png
from test_system_check import CSRF_TOKEN


def submit(client, **fields):
    data = dict(_csrf_token=CSRF_TOKEN, section="extra-producten", editor="2", category="gadgets",
                name="Fotoproef", stock_status="unknown", margin="30", vat="21",
                cost_price="8.50", shipping_cost="3.95", packaging_cost=".50", payment_cost=".35",
                advertising_cost="1.00", visible="1")
    return client.post("/admin/nv/extra-producten", data={**data, **fields}, headers={"Accept":"application/json"})


def product():
    catalog.invalidate_changes()
    with app.app.test_request_context("/dashboard"):
        return next(p for p in app.catalog_items() if p["name"] == "Fotoproef")


def test_eight_photos_round_trip_and_reorder(administrator, local_db):
    files = [(_png((50+i,40)), f"{i}.png") for i in range(8)]
    assert submit(administrator, image_file=files, gallery=json.dumps(list(range(8)))).status_code == 200
    saved = product()
    assert saved["price"] == 24.72 and len(set(saved["images"])) == 8
    sku = saved["sku"]
    assert all(administrator.get(url).mimetype=="image/webp" for url in saved["images"])
    images = saved["images"][::-1][:-1]
    assert submit(administrator, slug=saved["slug"], gallery=json.dumps(images)).status_code == 200
    assert product()["image"] == images[0] and product()["images"] == images and product()["sku"] == sku
    assert submit(administrator, name="Duplicaat",sku=sku).status_code == 422
    assert submit(administrator, sku="UNIEK").status_code == 422


def test_offer_uses_same_product_and_expires(administrator, local_db, monkeypatch):
    start = date(2026,11,1)
    monkeypatch.setattr(pricing, "today", lambda:start - timedelta(days=40))
    assert submit(administrator).status_code == 200
    monkeypatch.setattr(pricing, "today", lambda:start - timedelta(days=1))
    settings = dict(slug="fotoproef", offer_enabled="1",offer_shop="1",offer_list="1",sale_price="19.95",
                    offer_start=start.isoformat(),offer_end=(start+timedelta(days=2)).isoformat())
    assert submit(administrator, **settings).status_code == 200
    public=app.app.test_client()
    for offset, active in [(-1,False),(0,True),(2,True),(3,False)]:
        monkeypatch.setattr(pricing, "today", lambda:start + timedelta(days=offset))
        with app.app.test_request_context("/gadgets"):
            items=[p for p in app.catalog_items() if p['slug']=="fotoproef"]
            assert len(items)==1 and items[0]["price"]==(19.95 if active else 24.72)
            assert items[0]["old_price"]==(24.72 if active else None)
        assert ("Fotoproef" in public.get("/aanbiedingen").get_data(as_text=True))==active
        assert public.get("/gadgets/fotoproef").status_code==200


@pytest.mark.parametrize("fields", [
    {"margin":"100"}, {"sale_price":"30","offer_enabled":"1"}, {"vat":"50"}, {"stock_quantity":"-1"},
    {"stock_status":"out_of_stock","stock_quantity":"2"}, {"gallery":"[99]"}, {"minimum_stock":"-2"},
    {"image_file":(_png(), "foto.png"), "gallery":"[{},1]"},
])
def test_invalid_values_leave_no_product(administrator, local_db, fields):
    assert submit(administrator, **fields).status_code==422
    assert app.app.test_client().get("/gadgets/fotoproef").status_code==404


def test_private_draft_manual_edits_and_sanitization(administrator, local_db):
    assert submit(administrator, intent="draft",price_mode="manual",price="21.45",
                  sku="MANUAL-1",description_html='<b>Tekst</b><script>bad()</script>').status_code==200
    stored=product()
    assert stored["price"]==21.45 and stored["sku"]=="MANUAL-1" and stored["description_html"]=="<b>Tekst</b>"
    assert app.app.test_client().get("/gadgets/fotoproef").status_code==404
    assert "Fotoproef" in administrator.get("/dashboard?section=extra-producten&view=drafts").get_data(as_text=True)


@pytest.mark.parametrize("vat,expected", [("0",20.43),("9",22.27),("21",24.72)])
def test_supported_vat(administrator,local_db,vat,expected):
    assert submit(administrator,vat=vat).status_code==200
    assert product()["price"]==expected


def test_gallery_persists_across_postgres_connections(administrator, monkeypatch):
    import os
    from pathlib import Path
    from uuid import uuid4
    from contextlib import contextmanager
    import psycopg
    import nv_dashboard_postgres as pg

    url = os.getenv("NUVEMIXA_TEST_PG_URL")
    if not url:
        pytest.skip("Alleen met lokale PostgreSQL-testdatabase.")
    with psycopg.connect(url, autocommit=True) as db:
        db.execute(Path("nv_dashboard_postgres.sql").read_text())

    @contextmanager
    def connection():
        with psycopg.connect(url) as db:
            yield db

    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND","postgres")
    monkeypatch.setattr(pg,"connect",connection)
    catalog.invalidate_changes()
    name="Postgres fotoproef "+uuid4().hex[:8]
    try:
        response=submit(administrator,name=name,intent="draft",image_file=[(_png((50+i,40)), f"{i}.png") for i in range(8)])
        assert response.status_code==200,response.data
        catalog.invalidate_changes()
        with app.app.test_request_context("/dashboard"):
            saved=next(p for p in app.catalog_items() if p["name"]==name)
        assert saved["hidden"] and saved["price"]==24.72 and len(saved["images"])==8
        assert all(catalog.stored_image(url.split("/")[-1][:-5]) for url in saved["images"])
    finally:
        catalog.invalidate_changes()


def test_uploads_at_limit_and_above_it(administrator,local_db):
    import io
    png = _png((30,30)).getvalue()
    full = png.ljust(catalog.IMAGE_MAX_BYTES, b'\0')
    assert submit(administrator, image_file=[(io.BytesIO(full),f"{i}.png") for i in range(8)]).status_code==200
    response=submit(administrator, slug="fotoproef", image_file=(io.BytesIO(full+b'x'),"te-groot.png"))
    assert response.status_code==422 and "5 MB" in response.json["error"]
    assert product()["image"].endswith(".webp")
