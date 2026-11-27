"""Centraal platformregister (nv_platforms) en de platformkaarten in de onderzoeksmenu's."""
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import date

import pytest

import nv_platforms as reg
import nv_research_store as store
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

REQUIRED = {
    "social": "TikTok Instagram Facebook|YouTube / Shorts|Pinterest Reddit Threads Snapchat X",
    "trends": "Google|Google Trends|Google Shopping|Google News|TikTok Creative Center|TikTok Shop|Pinterest Trends|"
              "Meta Ad Library|Google Ads Transparency Center|Exploding Topics|Trend Hunter|Product Hunt|Kickstarter|"
              "Indiegogo",
    "markets": "Amazon|Amazon Best Sellers|Amazon Movers & Shakers|Amazon New Releases|bol.com|AliExpress|Alibaba|eBay|"
               "Etsy|Temu|SHEIN|Walmart|Kaufland|Cdiscount|1688|Rakuten|Shopee|Lazada",
    "suppliers": "Syncee|BigBuy|CJdropshipping|Hertwill|Spocket|Zendrop|Faire|Ankorstore|Orderchamp|Global Sources|"
                 "Made-in-China|Europages|Kompass|DHgate",
    "tools": "Sell The Trend|Minea|Dropship.io|Niche Scraper|Ecomhunt|Pipiads|Kalodata|FastMoss|Jungle Scout|Helium 10|"
             "Semrush|Similarweb",
}


def names(group):
    return {p["name"] for p in reg.all_platforms() if p["group"] == group}


@pytest.mark.parametrize("group", REQUIRED)
def test_every_requested_platform_is_in_the_register(group):
    text = REQUIRED[group]
    wanted = set(text.split("|")) if group != "social" else {"TikTok", "Instagram", "Facebook", "YouTube / Shorts",
                                                             "Pinterest", "Reddit", "Threads", "Snapchat", "X"}
    assert wanted <= names(group), wanted - names(group)


def test_catalogues_and_publications_come_from_the_real_sources():
    import nv_trends
    from nv_product_discovery import CATALOGUES
    sources = [p for p in reg.all_platforms() if p["group"] == "sources"]
    assert all(p["auto"] for p in sources)                                 # die raadpleegt NUVEMIXA zelf
    hosts = {p["domain"] for p in sources}
    assert "theverge.com" in hosts and "allure.com" in hosts
    assert {c.name for c in CATALOGUES} <= {p["name"] for p in sources}     # elke aangesloten catalogus één kaart
    assert len([p for p in sources if p["domain"] == "theverge.com"]) == 1    # twee feeds, één kaart


def test_only_sources_nuvemixa_really_reads_are_marked_automatic():
    auto = {p["key"] for p in reg.all_platforms() if p["auto"] and p["group"] != "sources"}
    assert auto == {"google-trends", "syncee"}
    for p in reg.all_platforms():
        if p["key"] in ("tiktok", "instagram", "pinterest-trends", "tiktok-cc", "amazon-bestsellers"):
            assert not p["auto"]


def test_every_card_has_https_links_for_all_categories_and_honest_labels():
    keys = set()
    for p in reg.all_platforms():
        c = reg.card(p)
        assert c["key"] not in keys
        keys.add(c["key"])
        assert set(c["links"]) == {"all", "term", *reg.CATEGORIES}
        for cat in ("all", *reg.CATEGORIES):
            url = reg.resolve(c["links"][cat], 7)
            assert url.startswith("https://") and "{" not in url, (p["key"], cat, url)
        assert c["cost"] in reg.COST.values() and c["account"] in reg.ACCOUNT.values()
        assert c["period_label"] in reg.PERIOD.values()
    assert sum(1 for p in reg.all_platforms() if reg.card(p)["logo_url"]) >= 85


def test_category_and_period_are_applied_where_the_platform_supports_it():
    by = {p["key"]: reg.card(p) for p in reg.all_platforms()}
    today = date(2026, 11, 27)
    assert reg.resolve(by["google-news"]["links"]["beauty-care"], 30, today=today).count("when%3A30d") == 1
    assert "since%3A2026-11-20" in reg.resolve(by["x"]["links"]["gadgets"], 7, today=today)
    assert "t=week" in reg.resolve(by["reddit"]["links"]["gadgets"], 7) and "t=month" in reg.resolve(
        by["reddit"]["links"]["gadgets"], 14)
    assert reg.resolve(by["google-trends"]["links"]["all"], 7) == "https://trends.google.com/trending?geo=NL&hours=168"
    assert "date=today%201-m" in reg.resolve(by["google-trends"]["links"]["smart-home"], 30)
    assert by["amazon-movers"]["links"]["beauty-care"] == "https://www.amazon.nl/gp/movers-and-shakers/beauty/"
    assert by["amazon-bestsellers"]["links"]["all"] == "https://www.amazon.nl/gp/bestsellers/"
    assert by["bol"]["links"]["beauty-care"].endswith("searchtext=verzorging")           # Nederlands bij bol.com
    assert by["kaufland"]["links"]["home-living"].endswith("search_value=Wohnen")
    assert by["instagram"]["links"]["smart-home"] == "https://www.instagram.com/explore/tags/smarthome/"
    assert by["aliexpress"]["links"]["home-living"] == "https://www.aliexpress.com/w/wholesale-home-decor.html"
    assert by["snapchat"]["category_link"] is False and by["snapchat"]["period"] == "none"


@pytest.mark.parametrize("section, card_id, groups", [
    ("trends", "nv-pcs-tr", ["Sociale media", "Trends en advertenties", "Internationale marktplaatsen",
                             "Leveranciers en dropshipping", "Gespecialiseerde onderzoeksplatforms",
                             "Productcatalogi en publicaties"]),
    ("onderzoek", "nv-pcs-po", ["Sociale media", "Trends en advertenties", "Internationale marktplaatsen"]),
    ("internationaal", "nv-pcs-int", ["Internationale marktplaatsen", "Leveranciers en dropshipping"]),
    ("partners", "nv-pcs-partners", ["Leveranciers en dropshipping", "Gespecialiseerde onderzoeksplatforms"]),
    ("leveranciers", "nv-pcs-lev", ["Leveranciers en dropshipping"]),
    ("viral", "nv-pcs-viral", ["Sociale media", "Trends en advertenties"]),
])
def test_platform_cards_are_back_on_the_research_pages(administrator, section, card_id, groups):
    page = administrator.get(f"/dashboard?section={section}").get_data(as_text=True)
    assert f'id="{card_id}"' in page and "nv-platforms.js" in page and "nv-platforms.css" in page
    block = page.split(f'id="{card_id}"')[1].split("</section>")[0]
    for label in groups:
        assert f"<span>{label}</span>" in block
    for name in ("TikTok", "Instagram") if "Sociale media" in groups else ("Syncee",) if "Leveranciers en dropshipping" in groups else ():
        assert f'<b class="nv-pc__name">{name}</b>' in block
    cards = re.findall(r'<a class="nv-pc" href="([^"]+)"', block)
    assert cards and all(href.startswith("https://") for href in cards)
    assert 'target="_blank" rel="noopener noreferrer nofollow"' in block
    assert "Externe snelkoppeling" in block


def test_trends_page_has_no_product_search_bar_and_cards_follow_its_own_controls(administrator):
    page = administrator.get("/dashboard?section=trends").get_data(as_text=True)
    form = page.split('id="nv-tr-form"')[1].split("</form>")[0]
    assert 'type="search"' not in form and 'type="text"' not in form and "<input name=" not in form
    assert 'name="trend_category"' in form and 'value="slim"' in form and 'value="7"' in form and 'value="30"' in form
    block = page.split('id="nv-pcs-tr"')[1][:600]
    assert "data-cat-source=\"#nv-tr-form [name=trend_category]\"" in block
    assert "data-period-source=\"#nv-tr-form [name=trend_period]\"" in block


def test_viral_page_keeps_its_own_category_and_period_controls(administrator):
    page = administrator.get("/dashboard?section=viral").get_data(as_text=True)
    block = page.split('id="nv-pcs-viral"')[1].split("</section>")[0]
    assert "data-pcs-cat" in block and block.count("data-pcs-period") == 3


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
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


def test_trend_cards_only_show_suppliers_from_an_earlier_product_research(tmp_store):
    import nv_research_job as job
    import nv_trends
    values = {"term": "Philips Hue", "category": "smart-home", "mode": "products", "country": "NL", "filter": "all"}
    store.save(job.cache_key(values), "done", {"result": {"suppliers": {
        "nl": [{"name": "Nedis"}], "eu": [{"name": "SwitchBot"}], "international": [], "unknown": []},
        "counts": {"verified_suppliers": 1}}})
    out = nv_trends.known_suppliers([{"name": "Philips Hue", "category": "smart-home"},
                                     {"name": "Treadmill", "category": "lifestyle-sport"}])
    assert out[0]["suppliers"]["count"] == 2 and out[0]["suppliers"]["names"] == ["Nedis", "SwitchBot"]
    assert "suppliers" not in out[1]                                       # niet onderzocht: niets verzonnen
