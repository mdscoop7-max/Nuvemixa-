"""Onderzoeksplatforms & trends (nv_trends) en zoekgeschiedenis (nv_search_history). Alle bronnen nagebootst."""
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

import nv_openai
import nv_research_store as store
import nv_trends as trends
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

NOW = datetime.now(timezone.utc)


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


def item(title, days, source="The Verge – Gadgets", kind="publicatie", region="VS", url=None, indicator=""):
    return {"title": title, "url": url or f"https://example.com/{abs(hash(title))}", "date": NOW - timedelta(days=days),
            "source": source, "region": region, "kind": kind, "indicator": indicator}


def test_rss_feeds_are_read_with_dates_and_undated_items_skipped():
    class Reply:
        def __init__(self, body): self.content = body
        def raise_for_status(self): pass
    rss = (b"<rss><channel><item><title>Vitamix Just Launched Its First-Ever Juicer</title>"
           b"<link>https://www.thekitchn.com/vitamix-juicer</link><pubDate>Fri, 27 Nov 2026 10:00:00 +0000</pubDate></item>"
           b"<item><title>No date</title><link>https://x.com/a</link></item></channel></rss>")
    rows = trends.read_feed("The Kitchn", "https://www.thekitchn.com/main.rss", "VS", fetch=lambda *a, **k: Reply(rss))
    assert [r["title"] for r in rows] == ["Vitamix Just Launched Its First-Ever Juicer"]
    assert rows[0]["date"].year == 2026 and rows[0]["kind"] == "publicatie"


def test_ai_names_must_literally_appear_in_the_real_headline(monkeypatch):
    items = [item("Vitamix Just Launched Its First-Ever Juicer", 1),
             item("Fabio Cannavaro nieuwe trainer", 1, "Google Trends NL", "zoekinteresse", "NL")]
    monkeypatch.setattr(nv_openai, "chat_json", lambda *a, **k: {"products": [
        {"name": "Vitamix juicer", "category": "home-living", "ids": [0]},
        {"name": "Smart blender pro", "category": "home-living", "ids": [0]},     # verzonnen: staat niet in titel
        {"name": "Cannavaro", "category": "pets", "ids": [1]}]})                   # geen toegestane categorie
    found, rejected = trends.extract_products(items, ["home-living", "gadgets"])
    assert [f["name"] for f in found] == ["Vitamix juicer"] and rejected == 2


def test_status_is_only_what_the_sources_support():
    rising = trends.status_of([item("bakfiets", 1, "Google Trends NL", "zoekinteresse", "NL", indicator="2000+")])
    assert rising[0] == "Stijgende interesse" and "2000+" in rising[1]
    assert trends.status_of([item("Vitamix Just Launched Its First-Ever Juicer", 1)])[0] == "Nieuwe productontwikkeling"
    two = [item("The robot vacuum everyone talks about", 1), item("Robot vacuum review", 2, "Engadget")]
    assert trends.status_of(two)[0] == "Veelbesproken product"
    assert trends.status_of([item("Best robot vacuum for pet hair", 1)])[0] == "Voorlopige trendindicatie"


def test_trend_job_uses_period_labels_platforms_honestly_and_ignores_catalogues(monkeypatch):
    feed = [item("Vitamix Just Launched Its First-Ever Juicer", 2, "The Kitchn"),
            item("Old juicer news", 40, "The Kitchn")]
    monkeypatch.setattr(trends, "read_feed", lambda name, url, region, fetch=None: feed if name == "The Kitchn" else [])
    monkeypatch.setattr(trends, "google_trends", lambda country, fetch=None: [])
    seen = {}

    def fake_chat(task, system, payload, **kwargs):
        seen["titles"] = [h["title"] for h in payload["headlines"]]
        return {"products": [{"name": "Vitamix juicer", "category": "home-living", "ids": [0]}]}
    monkeypatch.setattr(nv_openai, "chat_json", fake_chat)
    values = trends.parse({"trend_category": "home-living", "trend_period": "7"})
    key = trends.cache_key(values)
    trends.run(key, values, time.time())
    result = store.load(key)["payload"]["result"]
    assert seen["titles"] == ["Vitamix Just Launched Its First-Ever Juicer"]     # 40 dagen oud valt buiten 7 dagen
    assert [t["name"] for t in result["trends"]] == ["Vitamix juicer"]
    assert result["trends"][0]["status"] == "Nieuwe productontwikkeling" and result["days"] == 7
    kinds = {s["name"]: (s["kind"], s["status"]) for s in result["sources"]}
    assert kinds["TikTok"] == ("Externe handmatige zoeklink", "Niet doorzocht door NUVEMIXA")
    assert kinds["TikTok Creative Center"][0] == "Niet aangesloten bron"
    assert kinds["Productcatalogi en Syncee"][0] == "Niet als trendbron gebruikt"
    assert result["empty_categories"] == []


def test_trend_routes_and_cache_per_period(administrator, monkeypatch):
    monkeypatch.setattr(trends._pool, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(trends, "read_feed", lambda *a, **k: [])
    monkeypatch.setattr(trends, "google_trends", lambda *a, **k: [])
    form = {"_csrf_token": CSRF_TOKEN, "trend_category": "all", "trend_period": "30"}
    first = administrator.post("/dashboard/trends/start", data=form)
    status = administrator.get("/dashboard/trends/status?key=" + first.json["key"]).json
    assert status["state"] == "done" and status["result"]["trends"] == []
    assert "Gadgets" in status["result"]["empty_categories"]                      # eerlijk: onvoldoende gegevens
    again = administrator.post("/dashboard/trends/start", data=form).json
    assert again["cached"] is True and trends.CACHE_SECONDS[7] < trends.CACHE_SECONDS[30]


def test_menu_has_the_six_research_items(administrator):
    html = administrator.get("/dashboard?section=trends").get_data(as_text=True)
    menu = html.split(">Onderzoek<")[1].split(">Vindbaarheid<")[0]
    order = ["Productonderzoek", "Internationaal marktonderzoek", "Partners zoeken", "Onderzoeksplatforms &amp; trends",
             "Kandidaten &amp; concepten", "Viral Product Finder"]
    positions = [menu.index(name) for name in order]
    assert positions == sorted(positions) and "Rapportages" not in menu and "margecalculator" not in menu
    assert "Prijs- en margecalculator" in html and "Rapportages" in html            # verplaatst, niet verwijderd


def test_search_history_is_per_user_deduplicated_and_permanent(administrator):
    def post(**data):
        return administrator.post("/dashboard/zoekgeschiedenis", data={
            "_csrf_token": CSRF_TOKEN, "veld": "onderzoek:product:research_term", **data})
    post(actie="toevoegen", term="Keukenorganizer")
    post(actie="toevoegen", term="yogamat")
    items = post(actie="toevoegen", term="keukenorganizer").json["items"]
    assert items == ["keukenorganizer", "yogamat"]                                   # geen dubbele, nieuwste eerst
    assert post(actie="verwijderen", term="YOGAMAT").json["items"] == ["keukenorganizer"]
    listed = administrator.get("/dashboard/zoekgeschiedenis?veld=onderzoek:product:research_term").json
    assert listed["items"] == ["keukenorganizer"]
    assert post(actie="wissen").json["items"] == []
    assert administrator.get("/dashboard/zoekgeschiedenis?veld=x").status_code == 400
    import app as dashboard
    assert dashboard.app.test_client().get("/dashboard/zoekgeschiedenis?veld=abc").status_code in (302, 403)
