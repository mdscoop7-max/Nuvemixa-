"""Leverancierskoppelingen (CJdropshipping, EPROLO, SaleHoo), margecategorieën en GPSR-controle.
CJ-antwoorden zijn nagebootst volgens de officiële API-documentatie; er gaat nooit iets naar CJ."""
import json
import sqlite3
from contextlib import contextmanager

import pytest

import nv_product_margin as margin
import nv_research_store as store
import nv_supplier_integrations as links
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

KEY = "CJUserNum@api@TESTSLEUTEL-niet-echt-1234567890"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    path = tmp_path / "cache.sqlite3"

    @contextmanager
    def connect():
        db = sqlite3.connect(path)
        try:
            yield db
            db.commit()
        finally:
            db.close()
    monkeypatch.setattr(store, "connect", connect)
    monkeypatch.setattr(store, "_memory", {})
    monkeypatch.delenv("NUVEMIXA_CJ_API_KEY", raising=False)
    monkeypatch.setattr(links.CJ, "_wait", classmethod(lambda cls: None))
    monkeypatch.setattr(links.CJ, "_token", {"value": "", "expires": 0.0})
    yield path


class Reply:
    def __init__(self, data, status=200):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


def fake_cj(calls, *, token_ok=True):
    def request(method, url, params=None, json=None, headers=None, timeout=None):
        path = url.split("/api2.0/v1/")[1]
        calls.append((method, path, params, json, dict(headers or {})))
        if path == "authentication/getAccessToken":
            if not token_ok:
                return Reply({"code": 1600001, "result": False, "message": "Invalid API key"}, 200)
            return Reply({"code": 200, "result": True, "data": {"accessToken": "TOKEN-123",
                                                                 "accessTokenExpiryDate": "2099-01-01T00:00:00+08:00"}})
        if path == "product/listV2":
            return Reply({"code": 200, "result": True, "data": {"content": [{"productList": [
                {"id": "PID-1", "nameEn": "Magnetic Power Bank 10000mAh", "sku": "CJDS1", "bigImage": "https://cf.cj/p.jpg",
                 "sellPrice": "11.85", "nowPrice": "9.50", "oneCategoryName": "Electronics", "warehouseInventoryNum": 500,
                 "hasCECertification": 1, "deliveryCycle": "3-5", "addMarkStatus": 0}]}]}})
        if path == "product/stock/queryBySku":
            return Reply({"code": 200, "result": True, "data": [
                {"countryCode": "CN", "areaEn": "China Warehouse", "totalInventoryNum": 777},
                {"countryCode": "DE", "areaEn": "Germany Warehouse", "totalInventoryNum": 12}]})
        if path == "product/query":
            return Reply({"code": 200, "result": True, "data": {"variants": [{"vid": "VID-1", "variantNameEn": "Black"}]}})
        if path == "logistic/freightCalculate":
            return Reply({"code": 200, "result": True, "data": [
                {"logisticName": "CJPacket Ordinary", "logisticPrice": 4.71, "logisticAging": "7-12"}]})
        raise AssertionError("onverwacht endpoint " + path)
    return request


def test_default_status_is_honest_and_disabled():
    assert links.status("cj") == "API-sleutel vereist"
    assert links.status("eprolo") == "Account vereist" and links.status("salehoo") == "Account vereist"
    assert not any(links.active(slug) for slug in links.SUPPLIERS)


def test_salehoo_is_a_directory_not_a_dropshipping_supplier():
    s = links.SUPPLIERS["salehoo"]
    assert s["kind"] == "directory" and not s["env"]
    assert all(state != "gebouwd" for state, _ in s["capabilities"].values())
    assert s["facts"]["dropshipping"]["value"].startswith("Nee")
    assert "Betaald" in s["facts"]["subscription"]["value"]


def test_every_fact_has_a_source_or_says_not_confirmed():
    for slug, s in links.SUPPLIERS.items():
        assert set(s["facts"]) == set(links.FACT_LABELS), slug
        for key, fact in s["facts"].items():
            if fact["confirmed"]:
                assert fact["url"].startswith("https://"), (slug, key)
            else:
                assert fact["value"].startswith(links.NB), (slug, key)
        assert set(s["capabilities"]) == set(links.CAPABILITIES)
    # Bestellen en retour aanmelden plaatsen iets bij de leverancier: alleen voorbereid, nooit gebouwd
    cj = links.SUPPLIERS["cj"]["capabilities"]
    assert cj["order"][0] == cj["return_create"][0] == "voorbereid"
    assert {k for k, (state, _) in cj.items() if state == "gebouwd"} == {
        "search", "import", "images", "price", "stock", "shipping_cost", "lead_time", "tracking"}
    eprolo = links.SUPPLIERS["eprolo"]
    assert all(state == "onbekend" for state, _ in eprolo["capabilities"].values())
    assert "Hong Kong Eprolo Technology Limited" in eprolo["facts"]["country"]["value"]


def test_connect_test_activate_deactivate_flow(administrator, monkeypatch, isolated):
    calls = []
    monkeypatch.setattr(links.requests, "request", fake_cj(calls))
    url = "/dashboard/leveranciers/koppeling/cj/"
    # Zonder sleutel: niets aangeroepen
    administrator.post(url + "test", data={"_csrf_token": CSRF_TOKEN})
    assert calls == [] and links.status("cj") == "API-sleutel vereist"
    monkeypatch.setenv("NUVEMIXA_CJ_API_KEY", KEY)
    assert links.status("cj") == "Niet gekoppeld"
    # Activeren vóór een geslaagde test kan niet
    administrator.post(url + "activeren", data={"_csrf_token": CSRF_TOKEN})
    assert links.status("cj") == "Niet gekoppeld"
    reply = administrator.post(url + "test", data={"_csrf_token": CSRF_TOKEN})
    assert reply.status_code == 303 and links.status("cj") == "Uitgeschakeld"       # verbonden, nog niet actief
    assert calls[0][1] == "authentication/getAccessToken" and calls[0][3] == {"apiKey": KEY}
    administrator.post(url + "activeren", data={"_csrf_token": CSRF_TOKEN})
    assert links.status("cj") == "Verbonden" and links.active("cj")
    administrator.post(url + "deactiveren", data={"_csrf_token": CSRF_TOKEN})
    assert links.status("cj") == "Uitgeschakeld"
    # De sleutel en het token staan nooit in de database of in de pagina
    raw = sqlite3.connect(isolated).execute("SELECT payload FROM research_cache").fetchall()
    assert raw and all(KEY not in r[0] and "TOKEN-123" not in r[0] for r in raw)
    page = administrator.get("/dashboard?section=leveranciers").get_data(as_text=True)
    assert KEY not in page and "TOKEN-123" not in page and "NUVEMIXA_CJ_API_KEY" in page


def test_failed_test_shows_connection_error(administrator, monkeypatch):
    calls = []
    monkeypatch.setattr(links.requests, "request", fake_cj(calls, token_ok=False))
    monkeypatch.setenv("NUVEMIXA_CJ_API_KEY", KEY)
    administrator.post("/dashboard/leveranciers/koppeling/cj/test", data={"_csrf_token": CSRF_TOKEN})
    assert links.status("cj") == "Verbindingsfout"
    administrator.post("/dashboard/leveranciers/koppeling/cj/activeren", data={"_csrf_token": CSRF_TOKEN})
    assert links.status("cj") == "Verbindingsfout"


def test_eprolo_and_salehoo_cannot_be_tested_or_activated(administrator):
    for slug in ("eprolo", "salehoo"):
        for action in ("test", "activeren"):
            administrator.post(f"/dashboard/leveranciers/koppeling/{slug}/{action}", data={"_csrf_token": CSRF_TOKEN})
        assert links.status(slug) == "Account vereist"


def test_queries_need_an_active_connection_and_call_nothing_otherwise(administrator, monkeypatch):
    monkeypatch.setattr(links.requests, "request", lambda *a, **k: pytest.fail("geen netwerk zonder actieve koppeling"))
    reply = administrator.post("/dashboard/leveranciers/cj/zoeken", data={"_csrf_token": CSRF_TOKEN, "q": "powerbank"})
    assert reply.status_code == 409 and "API-sleutel vereist" in reply.json["message"]


def _activate(administrator, monkeypatch, calls):
    monkeypatch.setattr(links.requests, "request", fake_cj(calls))
    monkeypatch.setenv("NUVEMIXA_CJ_API_KEY", KEY)
    for action in ("test", "activeren"):
        administrator.post(f"/dashboard/leveranciers/koppeling/cj/{action}", data={"_csrf_token": CSRF_TOKEN})
    assert links.active("cj")


def test_search_stock_and_shipping_map_the_documented_fields(administrator, monkeypatch):
    calls = []
    _activate(administrator, monkeypatch, calls)
    found = administrator.post("/dashboard/leveranciers/cj/zoeken",
                               data={"_csrf_token": CSRF_TOKEN, "q": "powerbank", "category": "gadgets"}).json
    product = found["products"][0]
    assert product["price_usd"] == 9.5 and product["ce"] is True and product["inventory"] == 500
    assert "margin_amount=9.50" in product["margin_url"] and "margin_currency=USD" in product["margin_url"]
    assert "margin_category=gadgets" in product["margin_url"]
    search = [c for c in calls if c[1] == "product/listV2"][0]
    assert search[2]["keyWord"] == "powerbank" and search[4]["CJ-Access-Token"] == "TOKEN-123"
    stock = administrator.post("/dashboard/leveranciers/cj/voorraad", data={"_csrf_token": CSRF_TOKEN, "q": "CJDS1"}).json
    assert {s["country"]: s["total"] for s in stock["stock"]} == {"CN": 777, "DE": 12}
    ship = administrator.post("/dashboard/leveranciers/cj/verzending", data={"_csrf_token": CSRF_TOKEN, "q": "PID-1"}).json
    assert ship["options"] == [{"name": "CJPacket Ordinary", "days": "7-12", "price_usd": 4.71}]
    freight = [c for c in calls if c[1] == "logistic/freightCalculate"][0]
    assert freight[3]["endCountryCode"] == "NL" and freight[3]["products"] == [{"quantity": 1, "vid": "VID-1"}]
    # Er is nooit een bestel-, betaal- of geschil-endpoint aangeroepen
    assert not any(c[1].startswith(("shopping/", "disputes/")) for c in calls)


def test_research_job_includes_cj_only_when_active(administrator, monkeypatch):
    import nv_research_job as job
    found = {"products": [], "suppliers": [], "sources": {}}
    job.cj_products(found, ["powerbank"])
    assert found["products"] == [] and "api-sleutel vereist" in found["sources"]["CJdropshipping API"]["status"]
    calls = []
    _activate(administrator, monkeypatch, calls)
    job.cj_products(found, ["magnetische powerbank", "magnetic power bank"])
    assert [p["supplier"] for p in found["products"]] == ["CJdropshipping"]
    assert found["products"][0]["price"] == {"amount": 9.5, "currency": "USD"}
    assert found["sources"]["CJdropshipping API"] == {"status": "doorzocht", "count": 1}


def test_leveranciers_page_shows_management_and_honest_texts(administrator):
    page = administrator.get("/dashboard?section=leveranciers").get_data(as_text=True)
    block = page.split('id="nv-koppelingen"')[1].split("</section>")[0]
    for text in ("CJdropshipping", "EPROLO", "SaleHoo", "Leveranciersgids, geen leverancier", "Verbinding instellen",
                 "Verbinding testen", "Activeren", "Deactiveren", "Producten vergelijken", "Website bezoeken",
                 "Voorwaarden bekijken", "Nog niet bevestigd", "Laatste broncontrole 28-11-2026",
                 "wettelijke terugbetaling"):
        assert text in block, text
    assert block.count("API-sleutel vereist") >= 1 and block.count("Account vereist") >= 2
    assert "Zoeken bij CJ</button>" in block and "Zoeken kan zodra de koppeling verbonden" in block


def test_margin_presets_formula_and_markup():
    assert {k: v[1] for k, v in margin.MARGIN_PRESETS.items()} == {
        "gadgets": 35, "beauty-care": 40, "smart-home": 30, "lifestyle-sport": 35, "home-living": 35, "pc-components": 20}
    r = margin.unified_margin({"purchase_cost": "10", "target_margin": "40", "vat_rate": "21", "shipping_choice": "own",
                               "shipping_cost": "4", "advertising_cost": "2", "returns_reserve": "0.5",
                               "transaction_fee": "0.3", "transaction_pct": "0", "platform_fee": "0", "other_cost": "1"})
    a = r["advice"]
    costs = 1000 + 400 + 200 + 50 + 30 + 100
    assert abs(a["revenue"] - costs / (1 - 0.40)) <= 1                      # verkoopprijs excl. btw = kosten / (1 − marge)
    assert abs(a["margin"] - 40) < 0.1 and abs(a["markup"] - 100 * a["profit"] / a["costs"]) < 0.01
    assert a["markup"] > a["margin"]                                        # prijsopslag ≠ winstmarge


def test_calculator_category_dropdown_preselects_the_margin(administrator):
    page = administrator.get("/dashboard?section=calculator&margin_category=beauty-care").get_data(as_text=True)
    assert 'data-margin-category' in page and "PC-componenten (20%)" in page
    assert '<option value="40" selected>40%</option>' in page
    assert "Prijsopslag = winst ÷ totale kosten" in page


def test_concept_checks_include_gpsr_ce_and_documentation():
    import nv_concepts
    assert {"gpsr", "ce", "docs"} <= set(nv_concepts.CHECKS)
    assert "GPSR" in nv_concepts.CHECKS["gpsr"] and "CE" in nv_concepts.CHECKS["ce"]


def test_platform_register_has_eprolo_and_salehoo():
    import nv_platforms
    by = {p["key"]: p for p in nv_platforms.all_platforms()}
    assert by["eprolo"]["cost"] == "free" and by["salehoo"]["cost"] == "paid"
    assert not by["eprolo"]["auto"] and not by["salehoo"]["auto"]


def test_research_without_ai_is_cached_at_most_one_hour():
    import nv_research_job as job
    values = {"term": "powerbank", "category": "gadgets", "mode": "products", "country": "NL", "filter": "all"}
    full = {"payload": {"result": {"ai": {"used": True, "message": ""}}}}
    missing = {"payload": {"result": {"ai": {"used": False, "message": "AI niet beschikbaar: Daglimiet bereikt"}}}}
    assert job.fresh_seconds(values, full) > 3600 and job.fresh_seconds(values, missing) == 3600
    assert job.fresh_seconds(values) == job.fresh_seconds(values, full)
    web_only = {"payload": {"result": {"ai": {"message": ""}, "sources": [
        {"name": "AI-webonderzoek", "status": "AI niet beschikbaar: Daglimiet voor AI-aanroepen bereikt"}]}}}
    assert job.fresh_seconds(values, web_only) == 3600


def test_eprolo_eu_warehouses_are_3pl_for_own_stock():
    fact = links.SUPPLIERS["eprolo"]["facts"]["eu_warehouses"]
    assert "3PL" in fact["value"] and "NL" in fact["value"] and "eigen ingekochte voorraad" in fact["value"]
    assert fact["url"] == "https://eprolo.com/warehousing-and-fulfillment/"
