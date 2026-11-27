"""Trendcategorieën, perioden, afleiden uit de cache, afbeeldingen en de koppeling met Viral Product Finder.
Alle bronnen en AI nagebootst; de namen komen uit het echte live trendonderzoek van 27-11-2026 (Neon-cache)."""
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


def item(title, days, source="Allure", kind="publicatie", region="VS", image="", indicator=""):
    return {"title": title, "url": f"https://example.com/{abs(hash(title))}", "date": NOW - timedelta(days=days),
            "source": source, "region": region, "kind": kind, "image": image, "indicator": indicator}


@pytest.mark.parametrize("name, expected", [
    ("Electric Toothbrushes", "beauty-care"), ("Dyson Airwrap", "beauty-care"), ("Curling Irons", "beauty-care"),
    ("Retinol Hand Creams", "beauty-care"), ("Korean Skin-Care Products", "beauty-care"),
    ("Philips Hue", "smart-home"), ("Tapo’s new indoor security camera", "smart-home"),
    ("Treadmill", "lifestyle-sport"), ("Garmin Forerunner 265S", "lifestyle-sport"),
    ("Smartwool Gloves", "lifestyle-sport"), ("Asics Running Shoes", "lifestyle-sport"),
    ("Coffee Maker", "home-living"), ("Lola Blankets", "home-living"), ("Bedding", "home-living"),
    ("Zepath’s rechargeable AA batteries", "gadgets"), ("Oura Ring 5", "gadgets"), ("Anker power bank", "gadgets"),
])
def test_product_rules_put_real_trend_names_in_the_right_shop_category(name, expected):
    assert trends.rule_category(name) == expected


def test_rules_correct_old_cache_without_ai_and_move_other_categories_out():
    old = [{"name": "Electric Toothbrushes", "category": "gadgets", "status": "Voorlopige trendindicatie",
            "evidence": [item("9 Best Electric Toothbrushes & Oral Care Gadgets 2026", 1)]},
           {"name": "Airversa Humelle v2 Humidifier", "category": "smart-home", "status": "x",
            "evidence": [item("Airversa Humelle v2 Humidifier with HomeKit over Thread (video)", 1, "HomeKit News")]},
           {"name": "Oura Ring 5", "category": "gadgets", "status": "Seizoensgebonden interesse",
            "evidence": [item("The Oura Ring 5 just got its biggest discount ever for Black Friday", 1)]}]
    shown = trends.present({"trends": old}, {"category": "gadgets"})
    assert [t["name"] for t in shown["trends"]] == ["Oura Ring 5"]
    assert {"name": "Electric Toothbrushes", "category": "Beauty & Care"} in shown["moved"]
    # Black Friday-korting is geen seizoensinteresse en geen trendbewijs
    assert shown["trends"][0]["status"] == "Alleen aanbieding"
    every = trends.present({"trends": old}, {"category": "all"})
    by_name = {t["name"]: t for t in every["trends"]}
    assert by_name["Electric Toothbrushes"]["category"] == "beauty-care"
    assert "AI koos Gadgets" in by_name["Electric Toothbrushes"]["category_note"]
    assert by_name["Airversa Humelle v2 Humidifier"]["category"] == "smart-home"     # HomeKit in de titel
    assert every["trends"][-1]["status"] == "Alleen aanbieding"                       # aanbiedingen achteraan


def test_periods_7_14_30_only_send_items_inside_the_period(monkeypatch):
    feed = [item("Vitamix Just Launched Its First-Ever Juicer", 3, "The Kitchn"),
            item("Ninja unveils new blender", 10, "The Kitchn"), item("Smeg kettle review", 20, "The Kitchn"),
            item("Ancient toaster", 45, "The Kitchn")]
    monkeypatch.setattr(trends, "read_feed", lambda name, url, region, fetch=None: feed if name == "The Kitchn" else [])
    monkeypatch.setattr(trends, "google_trends", lambda country, fetch=None: [])
    sent = {}

    def fake_chat(task, system, payload, **kwargs):
        sent.setdefault("calls", []).append([h["title"] for h in payload["headlines"]])
        return {"products": []}
    monkeypatch.setattr(nv_openai, "chat_json", fake_chat)
    for period, expected in (("7", 1), ("14", 2), ("30", 3), ("slim", 2)):
        values = {"category": "home-living", "period": period}
        trends.run(trends.cache_key(values), values, time.time())
        assert len(sent["calls"][-1]) == expected, period
        result = store.load(trends.cache_key(values))["payload"]["result"]
        assert result["days"] == trends.PERIODS[period][1]
        assert result["since"] == (NOW - timedelta(days=result["days"])).date().isoformat()


def test_shorter_period_and_single_category_are_derived_from_todays_cache_without_ai(administrator, monkeypatch):
    feed = [item("Philips Hue launches new smart bulb", 2, "The Verge – Smart Home"),
            item("Sonos debuts new speaker", 12, "The Verge – Gadgets")]
    monkeypatch.setattr(trends._pool, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(trends, "read_feed", lambda name, url, region, fetch=None:
                        feed if name in ("The Verge – Smart Home",) else [])
    monkeypatch.setattr(trends, "google_trends", lambda *a, **k: [])
    calls = []

    def fake_chat(task, system, payload, **kwargs):
        calls.append(1)
        return {"products": [{"name": "Philips Hue", "category": "smart-home", "ids": [0]},
                             {"name": "Sonos speaker", "category": "gadgets", "ids": [1]}]}
    monkeypatch.setattr(nv_openai, "chat_json", fake_chat)
    first = administrator.post("/dashboard/trends/start", data={"_csrf_token": CSRF_TOKEN, "trend_category": "all",
                                                                "trend_period": "30"}).json
    assert administrator.get("/dashboard/trends/status?key=" + first["key"]).json["state"] == "done"
    assert len(calls) == 1
    short = administrator.post("/dashboard/trends/start", data={"_csrf_token": CSRF_TOKEN,
                                                                "trend_category": "smart-home", "trend_period": "7"}).json
    assert len(calls) == 1                                    # geen tweede AI-aanroep
    assert short["state"] == "done" and short["cached"] is True
    assert [t["name"] for t in short["result"]["trends"]] == ["Philips Hue"]
    assert "Alle categorieën · 30 dagen" in short["result"]["derived_from"]
    assert "Geen nieuwe AI-aanroep" in short["steps"][0]["text"]
    # De afgeleide versie wordt bewaard: later opnieuw opvragen komt uit de cache
    again = administrator.post("/dashboard/trends/start", data={"_csrf_token": CSRF_TOKEN,
                                                                "trend_category": "smart-home", "trend_period": "7"}).json
    assert again["cached"] is True and len(calls) == 1
    # Een langere periode kan niet uit een kortere worden afgeleid
    assert trends.reusable({"category": "all", "period": "30"}) == (None, None)


def test_feed_image_only_https_images_from_the_publisher():
    import xml.etree.ElementTree as ET
    node = ET.fromstring('<item xmlns:media="http://search.yahoo.com/mrss/"><title>x</title>'
                         '<media:content url="http://insecure.example/a.jpg" medium="image"/>'
                         '<media:thumbnail url="https://cdn.example/a.svg"/>'
                         '<enclosure url="https://cdn.example/toothbrush.jpg" type="image/jpeg"/></item>')
    assert trends.feed_image(node, "https://example.com/a") == "https://cdn.example/toothbrush.jpg"
    assert trends.feed_image(ET.fromstring("<item><title>x</title></item>"), "") == ""


def test_card_image_only_when_the_article_is_about_this_one_product():
    own = item("Tapo’s new indoor security camera includes a touchscreen", 1, image="https://cdn.example/tapo.jpg")
    own["products_named"] = 1
    roundup = item("39 Best Korean Skin-Care Products on Amazon to Shop Black Friday", 1, image="https://cdn.example/k.jpg")
    roundup["products_named"] = 1
    shared = item("Garmin and Oura cut prices", 1, image="https://cdn.example/g.jpg")
    shared["products_named"] = 2
    google = item("bakfiets", 1, "Google Trends NL", "zoekinteresse", image="https://cdn.example/news.jpg")
    google["products_named"] = 1
    assert trends.card_image([own])["url"] == "https://cdn.example/tapo.jpg"
    assert trends.card_image([roundup]) is None and trends.card_image([shared]) is None
    assert trends.card_image([google]) is None


def test_extract_counts_products_per_article(monkeypatch):
    items = [item("Garmin Forerunner and Oura Ring get price cuts", 1), item("Tapo launches camera", 1)]
    monkeypatch.setattr(nv_openai, "chat_json", lambda *a, **k: {"products": [
        {"name": "Garmin Forerunner", "category": "lifestyle-sport", "ids": [0]},
        {"name": "Oura Ring", "category": "gadgets", "ids": [0]},
        {"name": "Tapo camera", "category": "smart-home", "ids": [1]}]})
    trends.extract_products(items, list(trends.CATS))
    assert items[0]["products_named"] == 2 and items[1]["products_named"] == 1


def _saved(values, trends_list, checked="2026-11-27 16:27 UTC"):
    result = {"category": values["category"], "period": values["period"], "period_label": "7 dagen",
              "category_label": "Alle categorieën", "checked": checked, "trends": trends_list, "sources": [],
              "empty_categories": []}
    store.save(trends.cache_key(values), "done", {"values": values, "steps": [], "result": result})


def test_viral_finder_reads_saved_trends_splits_rising_and_never_calls_ai(administrator, monkeypatch):
    monkeypatch.setattr(nv_openai, "chat_json", lambda *a, **k: pytest.fail("Viral Product Finder mag geen AI gebruiken"))
    day = NOW.date().isoformat()
    rising = {"name": "Bakfiets", "category": "lifestyle-sport", "status": "Stijgende interesse", "reason": "x",
              "evidence": [{"title": "bakfiets", "url": "https://trends.google.com/x", "date": day,
                            "source": "Google Trends NL", "kind": "zoekinteresse", "region": "NL", "indicator": "2000+"}]}
    normal = {"name": "Electric Toothbrushes", "category": "gadgets", "status": "Voorlopige trendindicatie",
              "reason": "x", "evidence": [{"title": "9 Best Electric Toothbrushes", "url": "https://allure.com/a",
                                           "date": day, "source": "Allure", "kind": "publicatie", "region": "VS"}]}
    deal = {"name": "Oura Ring 5", "category": "gadgets", "status": "Seizoensgebonden interesse", "reason": "x",
            "evidence": [{"title": "The Oura Ring 5 just got its biggest discount ever for Black Friday",
                          "url": "https://theverge.com/o", "date": day, "source": "The Verge", "kind": "publicatie",
                          "region": "VS"}]}
    _saved({"category": "all", "period": "7"}, [rising, normal, deal])
    _saved({"category": "gadgets", "period": "30"}, [normal])          # zelfde product in tweede onderzoek
    view = trends.viral_view()
    assert [t["name"] for t in view["rising"]] == ["Bakfiets"]
    assert [t["name"] for t in view["trends"]] == ["Electric Toothbrushes"]          # één keer, niet twee
    assert view["trends"][0]["category"] == "beauty-care" and view["trends"][0]["niche"].startswith("Beauty")
    assert [t["name"] for t in view["deals"]] == ["Oura Ring 5"]
    page = administrator.get("/dashboard?section=viral").get_data(as_text=True)
    assert "Aantoonbaar snel stijgende belangstelling" in page and "Bakfiets" in page
    assert "Leg vast als viral-kandidaat" in page and "viral_title=Bakfiets" in page
    assert "virale score" not in page.split("nv-vt-title")[1].split("</section>")[0].replace("geen verkoopcijfers, views of virale scores", "")
    prefilled = administrator.get("/dashboard?section=viral&viral_title=Bakfiets&viral_niche=Fitness+en+sport").get_data(as_text=True)
    assert 'value="Bakfiets"' in prefilled and "<option selected>Fitness en sport</option>" in prefilled


def test_viral_finder_without_saved_trends_says_so_honestly(administrator):
    page = administrator.get("/dashboard?section=viral").get_data(as_text=True)
    assert "Geen product met aantoonbaar snel stijgende belangstelling" in page
    assert "Nog geen bewaarde trends" in page


@pytest.mark.parametrize("section", ["onderzoek", "internationaal", "partners", "concepten", "viral", "leveranciers"])
def test_every_research_search_bar_has_the_search_history(administrator, section):
    """Elke onderzoekszoekbalk krijgt de Google-achtige zoekgeschiedenis: data-history of een form[data-research-search]
    (dan koppelt nv-search-history.js hem automatisch). Geen oude 'Recent'-knoppen of datalists."""
    from html.parser import HTMLParser

    class Inputs(HTMLParser):
        def __init__(self):
            super().__init__()
            self.form, self.bad, self.good = None, [], []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "form":
                self.form = attrs
            if tag == "datalist":
                self.bad.append("datalist")
            if tag == "input" and (attrs.get("type") == "search" or "data-history" in attrs):
                name = attrs.get("name") or attrs.get("id")
                if name in ("nvMenuFilter",) or (self.form or {}).get("class", "").startswith("top-search"):
                    return
                ok = "data-history" in attrs or "data-research-search" in (self.form or {})
                (self.good if ok else self.bad).append(name)

        def handle_endtag(self, tag):
            if tag == "form":
                self.form = None
    page = administrator.get(f"/dashboard?section={section}").get_data(as_text=True)
    parser = Inputs()
    parser.feed(page)
    assert parser.bad == [] and parser.good, (section, parser.bad)
    assert "nv-search-history.js" in page and ">Recent<" not in page


def test_internationaal_offers_handoff_to_productonderzoek(administrator):
    page = administrator.get("/dashboard?section=internationaal").get_data(as_text=True)
    assert 'data-section="internationaal"' in page and 'id="nv-wd-handoff"' in page
    assert 'data-research-url="/dashboard?section=onderzoek"' in page


def test_both_daily_limits_are_shown_separately(administrator, monkeypatch):
    import nv_web_discovery_view as view
    monkeypatch.setattr(nv_openai, "usage", lambda wait=0.0: {"month_usd": 1.567, "month_limit_usd": 3.0, "day_calls": 81,
                                                              "day_limit": 80, "persistent": True, "blocked": False,
                                                              "last_error": ""})
    page = administrator.get("/dashboard?section=partners").get_data(as_text=True)
    assert "van 60 live zoekopdrachten" in page or "live zoekopdrachten via deze knop" in page
    assert "AI-aanroepen vandaag 81 van 80" in page and "US$ 1,57 van US$ 3,00" in page
    assert "De AI-daggrens is bereikt" in page
    assert view.ai_usage()["reached"] is True
