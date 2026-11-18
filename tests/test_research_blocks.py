"""Productonderzoek in drie blokken, tijdsfilter 7/14/30/Slim en eerlijke platformlabels."""
from datetime import date, timedelta

from test_system_check import administrator  # noqa: F401

import nv_ai_search
import nv_research_period as period


def article(days_ago, url):
    return {"title": "Artikel", "url": url, "date": (date.today() - timedelta(days=days_ago)).isoformat(),
            "date_label": "Publicatie", "kind": "Markt en niche"}


def test_smart_period_depends_on_search_type():
    assert period.resolve("slim", "trends")[0] == 14
    assert period.resolve("slim", "niche")[0] == 30
    assert period.resolve("slim", "suppliers")[0] is None
    assert period.resolve("7", "suppliers") == (7, "7 dagen (zelf gekozen)")
    assert period.resolve("onzin", "products")[0] == 30


def test_period_only_filters_dated_publications_never_products_or_suppliers():
    result = {"news": [article(3, "a"), article(20, "b"), {"title": "x", "url": "c", "date": ""}],
              "trends": [article(3, "a"), article(20, "b")],
              "products": [{"title": "Product zonder datum"}], "suppliers": [{"name": "Echte BV"}]}
    summary = period.apply(result, 14)
    assert [i["url"] for i in result["news"]] == ["a"] and [i["url"] for i in result["trends"]] == ["a"]
    assert result["products"] and result["suppliers"]
    assert summary["removed"] == 1 and summary["undated"] == 1
    untouched = {"news": [article(400, "z")]}
    period.apply(untouched, None)
    assert untouched["news"]


def test_three_blocks_and_honest_platform_labels(administrator):
    html = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    for text in ("1</span> Product zoeken", "2</span> Onderzoeksplatforms", "3</span> Tijdsfilter",
                 "Bronnen doorzoeken", 'name="research_period"', "Slim", "14 dagen"):
        assert text in html, text
    assert html.count("Alleen bronlink") >= 6 and "niet live gekoppeld" in html
    assert "Live doorzocht" in html


def test_platform_block_searches_selected_sources_with_period(administrator, monkeypatch):
    seen = {}

    def fake(term, *args, **kwargs):
        seen.update(kwargs, term=term)
        return {"error": None, "term": term, "country_name": "Nederland", "category_name": "All products",
                "products": [], "suppliers": [], "news": [article(2, "nieuw"), article(25, "oud")],
                "trends": [], "links": [], "search_trends": [], "alternatives": [], "pending_sources": [],
                "unavailable_sources": [], "unavailable_reasons": {}, "sources_checked": [], "next_steps": [],
                "interpretation": {"queries": [], "categories": [], "automatic": False}, "supplier_suggestions": [],
                "preferred_tab": "news", "fetched_at": "18-11-2026 23:00", "topic": term, "google_trends_checked": False,
                "supplier_products": 0, "all_sources_failed": False, "source_unavailable": False}

    monkeypatch.setattr(nv_ai_search, "discover", fake)
    page = administrator.get("/dashboard", query_string={
        "section": "onderzoek", "research_run": "1", "research_block": "platforms", "research_mode": "trends",
        "research_term": "yogamat", "research_platform": ["Publicaties", "TikTok"], "research_period": "7",
        "research_country": "NL", "research_category": "shop", "research_supplier_filter": "all"})
    html = page.get_data(as_text=True)
    assert page.status_code == 200 and seen["term"] == "yogamat"
    assert seen["platforms"] == ["Publicaties", "TikTok"] and seen["mode"] == "trends"
    assert "7 dagen (zelf gekozen)" in html and "1 oudere publicaties weggelaten" in html


def test_ai_switch_off_uses_plain_search(administrator, monkeypatch):
    import app as dashboard
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setattr(nv_ai_search, "ai_discover", lambda *a, **k: calls.append("ai") or {"error": "x"})
    monkeypatch.setattr("nv_product_discovery.discover", lambda *a, **k: calls.append("plain") or {"error": "x"})
    administrator.get("/dashboard", query_string={"section": "onderzoek", "research_run": "1", "research_ai": "0",
                                                  "research_term": "lamp"})
    assert calls == ["plain"]
    assert dashboard is not None
