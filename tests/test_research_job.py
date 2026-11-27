"""Gecombineerd onderzoeksproces (nv_research_job), valuta (nv_fx) en permanente cache (nv_research_store).

Alle bronnen, AI-antwoorden en koersen hieronder zijn nagebootst; er wordt niets echt aangeroepen."""
import sqlite3
import time
from contextlib import contextmanager
from decimal import Decimal

import pytest

import nv_fx
import nv_openai
import nv_research_job as job
import nv_research_store as store
import nv_web_discovery_view as view
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

ECB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
<Cube><Cube time="2026-11-26"><Cube currency="USD" rate="1.0975"/><Cube currency="AUD" rate="1.6540"/>
<Cube currency="GBP" rate="0.8350"/></Cube></Cube></gesmes:Envelope>"""


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
    monkeypatch.setattr(view, "_usage", {"day": "", "count": 0})
    monkeypatch.setattr(nv_fx, "_state", {"at": 0.0, "date": "", "rates": {}})

    class Reply:
        content = ECB_XML
        def raise_for_status(self): pass
    monkeypatch.setattr(nv_fx.requests, "get", lambda *a, **k: Reply())


def offer(title, supplier, amount, currency="AUD", url=None, query="kitchen organizer"):
    return {"title": title, "url": url or f"https://syncee.com/product/{supplier}/{len(title)}", "image": "",
            "supplier": supplier, "source": "Syncee", "own_website": "", "warehouse": "Australia",
            "price": {"amount": amount, "currency": currency}, "dropship": True, "shipping_nl": "Bevestigd",
            "lead_time": "", "query": query}


# ------------------------------------------------------------------ valuta ------------------------------------------
def test_ecb_conversion_shows_original_price_currency_rate_and_date():
    conversion = nv_fx.to_eur("73.59", "AUD")
    assert conversion["eur"] == 44.49 and conversion["rate"] == 1.654 and conversion["date"] == "2026-11-26"
    text = nv_fx.describe(conversion)
    assert text == "AUD 73,59 = € 44,49 (1 EUR = 1,6540 AUD, ECB-referentiekoers 26-11-2026)"
    assert nv_fx.to_eur(10, "EUR")["rate"] == 1.0
    with pytest.raises(nv_fx.RateUnavailable):
        nv_fx.to_eur(5, "XYZ")                       # geen koers = geen omrekening, nooit geschat
    with pytest.raises(ValueError):
        nv_fx.to_eur("abc", "USD")


def test_no_rate_when_ecb_unreachable(monkeypatch):
    def down(*args, **kwargs):
        raise nv_fx.requests.ConnectionError("weg")
    monkeypatch.setattr(nv_fx.requests, "get", down)
    with pytest.raises(nv_fx.RateUnavailable):
        nv_fx.to_eur(10, "USD")


def test_margin_calculator_prefills_euro_and_explains_the_conversion(administrator):
    text = administrator.get("/dashboard?section=onderzoek&margin_product=Cart&margin_amount=73.59"
                             "&margin_currency=AUD").get_data(as_text=True)
    assert 'value="44.49"' in text
    assert "AUD 73,59 = € 44,49 (1 EUR = 1,6540 AUD, ECB-referentiekoers 26-11-2026)" in text
    bad = administrator.get("/dashboard?section=onderzoek&margin_amount=5&margin_currency=XYZ").get_data(as_text=True)
    assert "Er is niet omgerekend" in bad


# ------------------------------------------------------------------ samenvoegen -------------------------------------
def test_same_product_from_two_providers_is_one_card_with_two_offers():
    """Live 27-11: Primebay en Lifebay toonden hetzelfde product tegen dezelfde prijs (AUD 73,59)."""
    rows = job.group_products([offer("Mobile Kitchen Organizer Cart with Wheels", "Primebay", 73.59),
                               offer("Mobile Kitchen Organizer Cart with Wheels", "Lifebay", 73.59),
                               offer("Foldable Dishcloth Shelf Kitchen Organizer", "zonchef", 23.99, "USD")],
                              lambda price: nv_fx.to_eur(price["amount"], price["currency"]))
    cart = next(row for row in rows if row["title"].startswith("Mobile"))
    assert len(rows) == 2 and cart["offer_count"] == 2 and "meerdere aanbieders" in cart["same_product_note"]
    assert cart["offers"][0]["eur"]["eur"] == 44.49


def test_unrelated_and_other_use_products_are_removed_with_a_reason(monkeypatch):
    """Live 27-11: een campingtas verscheen bij 'Keukenorganizer'."""
    seen = {}

    def fake_chat(task, system, payload, **kwargs):
        seen.update(task=task, payload=payload)
        return {"reject": [i for i, r in enumerate(payload["results"]) if "Camping" in r["title"]]}
    monkeypatch.setattr(nv_openai, "chat_json", fake_chat)
    items = [offer("Expandable Stainless Steel Kitchen Organizer", "CashyMart", 18.45, "USD"),
             offer("Naturehike 35L Camping Kitchen Organizer Storage Bag", "Naturexplore", 39.99),
             offer("LED Desk Lamp", "Lampco", 10)]
    kept, removed = job.relevant_products(items, "Keukenorganizer", ["kitchen organizer"], "home-living", True)
    assert [item["title"] for item in kept] == ["Expandable Stainless Steel Kitchen Organizer"]
    reasons = {item["title"]: item["reason"] for item in removed}
    assert reasons["LED Desk Lamp"].startswith("Zoekterm en vertalingen")
    assert reasons["Naturehike 35L Camping Kitchen Organizer Storage Bag"].startswith("AI: ander producttype")
    assert seen["task"] == "category_filter" and seen["payload"]["shop_category"] == "Home & Living"


def test_exact_versus_related_products():
    """Live 27-11: 'magnetische powerbank' toonde ook gewone powerbanks via het algemene woord 'power bank'."""
    phrases = ["magnetische powerbank", "magnetic power bank"]
    assert job.exact_match("UGREEN MagFlow Air Magnetic Power Bank (10000mAh, Qi2 15W)", phrases)
    assert job.exact_match("FS5 - Magnetic Powerbank - 5.000 mAh", phrases)
    assert not job.exact_match("UGREEN Nexode Power Bank 25000mAh 200W", phrases)
    assert job.exact_match("Yoga Mat 6mm TPE", ["yogamat"]) and not job.exact_match("Yoga Block", ["yogamat"])
    rows = job.group_products([{**offer("Magnetic Power Bank 5000", "A", 10), "exact": True},
                               {**offer("Power Bank 20000", "B", 12), "exact": False}], lambda price: None)
    assert {r["title"]: r["match"] for r in rows} == {"Magnetic Power Bank 5000": "exact", "Power Bank 20000": "related"}


def test_ai_filter_that_rejects_almost_everything_is_ignored(monkeypatch):
    monkeypatch.setattr(nv_openai, "chat_json", lambda *a, **k: {"reject": [0, 1, 2, 3]})
    items = [offer(f"Kitchen Organizer {n}", "S", n) for n in range(4)]
    kept, removed = job.relevant_products(items, "kitchen organizer", [], "home-living", True)
    assert len(kept) == 4 and not removed


def test_suppliers_are_deduplicated_and_split_by_region():
    catalog = [{"name": "Lifebay", "origin": "AU", "own_website": "https://www.lifebay.com.au", "website":
                "https://syncee.com/supplier/1/lifebay", "role": "Dropshippingleverancier", "dropshipping": True},
               {"name": "Primebay", "origin": "", "own_website": "", "website": "https://syncee.com/supplier/2"}]
    cards = [{"name": "Lifebay Pty", "domain": "lifebay.com.au", "home": "https://lifebay.com.au/", "url":
              "https://lifebay.com.au/wholesale", "country": "AU", "role": "Groothandel / distributeur",
              "verified": True, "signals": ["groothandel"], "facts": [{"quote": "Wholesale kitchen organizer"}]},
             {"name": "Keuken BV", "domain": "keukenbv.nl", "home": "https://keukenbv.nl/", "url": "https://keukenbv.nl/b2b",
              "country": "NL", "role": "Groothandel / distributeur", "verified": True, "signals": [], "facts": []},
             {"name": "Kuche GmbH", "domain": "kuche.de", "home": "https://kuche.de/", "url": "https://kuche.de/",
              "country": "DE", "role": "Fabrikant", "verified": False, "signals": [], "facts": []}]
    products = [{"offers": [{"supplier": "Lifebay"}, {"supplier": "Primebay"}]}]
    rows = job.merge_suppliers(catalog, cards, products)
    lifebay = [row for row in rows if row["domain"] == "lifebay.com.au"]
    assert len(lifebay) == 1 and lifebay[0]["sources"] == ["Syncee", "AI-webonderzoek"]
    split = job.sections(rows)
    assert [r["name"] for r in split["nl"]] == ["Keuken BV"] and [r["name"] for r in split["eu"]] == ["Kuche GmbH"]
    assert [r["name"] for r in split["international"]] == ["Lifebay"] and [r["name"] for r in split["unknown"]] == ["Primebay"]
    eu_only, hidden = job.apply_filter(rows, "eu")
    assert {r["name"] for r in eu_only} == {"Keuken BV", "Kuche GmbH"} and hidden == 2


def test_live_found_supplier_problems_are_fixed():
    """Live 27-11 'Keukenorganizer': Lifebay dubbel, Ferm Living/Naturexplore zonder producten, Primebay zonder land."""
    catalog = [
        {"name": "Lifebay", "origin": "AU", "own_website": "https://www.lifebay.com.au", "website": "https://syncee.com/s/1"},
        {"name": "Lifebay", "origin": "AU", "own_website": "", "website": "https://syncee.com/s/1",
         "role": "Leverancier via marktplaats"},
        {"name": "Primebay", "origin": "", "own_website": "https://primebay.com.au", "website": "https://syncee.com/s/2"},
        {"name": "Ferm Living", "origin": "DK", "own_website": "", "website": "https://fermliving.com"},
        {"name": "Naturexplore", "origin": "", "own_website": "https://naturexplore.com.au", "website": "https://syncee.com/s/3"},
    ]
    products = [{"offers": [{"supplier": "Lifebay"}, {"supplier": "Primebay"}]}]
    rows = {row["name"]: row for row in job.merge_suppliers(catalog, [], products)}
    assert sorted(rows) == ["Lifebay", "Primebay"]                       # geen dubbele Lifebay, geen lege leveranciers
    assert rows["Lifebay"]["domain"] == "lifebay.com.au"
    assert rows["Primebay"]["country"] == "AU" and rows["Primebay"]["region"] == "international"
    assert rows["Primebay"]["country_note"] == "afgeleid uit domein primebay.com.au"


def test_two_companies_with_same_name_but_different_websites_stay_apart():
    catalog = [{"name": "Home Co", "origin": "NL", "own_website": "https://homeco.nl", "website": "x"},
               {"name": "Home Co", "origin": "US", "own_website": "https://homeco.com", "website": "y"}]
    rows = job.merge_suppliers(catalog, [], [{"offers": [{"supplier": "Home Co"}]}])
    assert len(rows) == 2


def test_only_the_five_webshop_categories_and_valid_input():
    values = job.parse({"research_term": "Keukenorganizer", "research_category": "pets"})
    assert values["category"] == "" and values["mode"] == "products" and values["country"] == "NL"
    assert job.parse({"research_term": "x y", "research_category": "home-living"})["category"] == "home-living"
    for bad in ("x", "mail@example.com"):
        with pytest.raises(job.web.SearchError):
            job.parse({"research_term": bad})


# ------------------------------------------------------------------ volledige taak ----------------------------------
def fake_sources(monkeypatch, verified=4, calls=None):
    calls = [] if calls is None else calls
    monkeypatch.setattr(job, "plan", lambda values: {"ai": True, "category": "home-living", "keywords_en":
                        ["kitchen organizer"], "keywords_nl": ["keukenorganizer"], "exclude": [], "message": "",
                        "queries": ["kitchen organizer", "Keukenorganizer"]})
    monkeypatch.setattr(job, "catalog_search", lambda values, queries, category, deadline: {
        "products": [offer("Mobile Kitchen Organizer Cart with Wheels", "Primebay", 73.59, query="kitchen organizer"),
                     offer("Mobile Kitchen Organizer Cart with Wheels", "Lifebay", 73.59, query="kitchen organizer")],
        "suppliers": [], "sources": {"Syncee": {"status": "doorzocht", "count": 2},
                                     "Ferm Living": {"status": "doorzocht", "count": 0}}, "per_query": {}})

    def fake_web(term, kind, category, country, scope, exclude):
        calls.append((kind, scope, tuple(exclude)))
        n = verified if not exclude else 2
        results = [{"name": f"Bedrijf {kind} {i}", "domain": f"b{len(calls)}{i}.nl", "home": f"https://b{len(calls)}{i}.nl/",
                    "url": f"https://b{len(calls)}{i}.nl/p", "country": "NL", "role": "Groothandel / distributeur",
                    "verified": True, "signals": ["groothandel"], "facts": []} for i in range(n)]
        return {"results": results, "verified_count": n, "unique_companies": n,
                "meta": {"searches": 1, "candidates": n, "keywords": ["kitchen organiser"]}}, None
    monkeypatch.setattr(job, "_web_safe", fake_web)
    monkeypatch.setattr(job, "register_matches", lambda term, keywords, category: ([], []))
    monkeypatch.setattr(nv_openai, "chat_json", lambda *a, **k: {"reject": []})
    return calls


def test_full_job_combines_all_sources_and_is_stored_permanently(monkeypatch):
    fake_sources(monkeypatch)
    values = job.parse({"research_term": "Keukenorganizer"})
    key = job.cache_key(values)
    job.run(key, values, time.time())
    row = store.load(key)
    assert row["state"] == "done" and row["storage"] == "database"
    result = row["payload"]["result"]
    assert result["counts"]["products"] == 1 and result["counts"]["offers"] == 2
    assert result["counts"]["verified_suppliers"] == 4 and result["fallback"] == ""
    names = [s["name"] for s in result["sources"]]
    assert "Syncee" in names and "Ferm Living" in names and "AI-webonderzoek" in names
    assert any(s["name"].startswith("Partnerregister") for s in result["sources"])
    assert result["ai"]["products_via_ai_keywords"] == 1 and result["ai"]["web_suppliers"] == 4
    assert [s["text"] for s in row["payload"]["steps"]][-1] == "Klaar"


def test_too_few_verified_suppliers_triggers_a_second_strategy(monkeypatch):
    calls = fake_sources(monkeypatch, verified=1)
    values = job.parse({"research_term": "Keukenorganizer", "research_supplier_filter": "eu"})
    key = job.cache_key(values)
    job.run(key, values, time.time())
    result = store.load(key)["payload"]["result"]
    assert len(calls) == 2 and calls[1][0] == "wholesale" and calls[1][2] == ("b10.nl",)
    assert calls[0][1] == "eu" and calls[1][1] == "eu"          # filter NL/EU blijft gerespecteerd
    assert result["fallback"].startswith("Weinig gecontroleerde bedrijven (1)")
    assert any(s["name"] == "AI-webonderzoek (tweede strategie)" for s in result["sources"])


def test_routes_start_poll_and_permanent_cache(administrator, monkeypatch):
    fake_sources(monkeypatch)
    monkeypatch.setattr(nv_openai, "configured", lambda: True)
    monkeypatch.setattr(job._pool, "submit", lambda fn, *args: fn(*args))   # synchroon voor de test
    form = {"_csrf_token": CSRF_TOKEN, "research_term": "Keukenorganizer", "research_category": "shop",
            "research_mode": "products", "research_country": "NL", "research_supplier_filter": "all"}
    first = administrator.post("/dashboard/onderzoek/start", data=form)
    assert first.status_code == 200 and first.json["ok"] and first.json["state"] == "running"
    status = administrator.get("/dashboard/onderzoek/status?key=" + first.json["key"])
    assert status.json["state"] == "done" and status.json["result"]["counts"]["products"] == 1
    used = view.usage()["used"]
    again = administrator.post("/dashboard/onderzoek/start", data=form)      # uit de permanente cache, geen kosten
    assert again.json["state"] == "done" and again.json["cached"] and view.usage()["used"] == used
    assert administrator.get("/dashboard/onderzoek/status?key=nope").status_code == 400


def test_interrupted_job_is_reported_and_can_be_restarted(administrator, monkeypatch):
    values = job.parse({"research_term": "Keukenorganizer"})
    key = job.cache_key(values)
    store.save(key, "running", {"values": values, "steps": [{"t": 0, "text": "Onderzoek gestart"}]},
               time.time() - 1000)
    with store.connect() as db:
        db.execute("UPDATE research_cache SET updated_at = ? WHERE cache_key = ?", (time.time() - 1000, key))
    reply = administrator.get("/dashboard/onderzoek/status?key=" + key)
    assert reply.json["state"] == "failed" and "onderbroken" in reply.json["error"]


def test_failed_job_never_disappears_silently(monkeypatch):
    monkeypatch.setattr(job, "plan", lambda values: 1 / 0)
    values = job.parse({"research_term": "Keukenorganizer"})
    key = job.cache_key(values)
    job.run(key, values, time.time())
    row = store.load(key)
    assert row["state"] == "failed" and "ZeroDivisionError" in row["payload"]["steps"][-1]["text"]


def test_store_falls_back_to_memory_when_database_is_down(monkeypatch):
    @contextmanager
    def down():
        raise sqlite3.OperationalError("weg")
        yield
    monkeypatch.setattr(store, "connect", down)
    assert store.save("k", "done", {"result": {"a": 1}}) == "geheugen"
    assert store.load("k")["storage"] == "geheugen" and store.load("k")["payload"]["result"] == {"a": 1}


# ------------------------------------------------------------------ pagina -----------------------------------------
def test_research_page_has_one_combined_search_and_only_five_categories(administrator):
    text = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    assert 'id="nv-rj"' in text and "nv-research-job.js" in text
    assert 'id="nv-wd-form"' not in text                     # geen tweede, losse zoekfunctie meer
    assert "Huisdieren" not in text
    assert 'data-start="/dashboard/onderzoek/start"' in text and 'data-can-save="1"' in text
