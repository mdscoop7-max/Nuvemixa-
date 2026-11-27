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


def test_research_page_and_separate_trends_page_with_honest_platform_labels(administrator):
    """Sinds 27-11-2026 staat trendonderzoek (zonder artikelnaam) in een eigen menu: Onderzoeksplatforms & trends."""
    html = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    assert "1</span> Product zoeken" in html and "2</span> Trends zonder artikelnaam?" in html
    assert "section=trends" in html and "nv-rblock--platforms" not in html
    trends = administrator.get("/dashboard?section=trends").get_data(as_text=True)
    form = trends.split('id="nv-tr-form"')[1].split("</form>")[0]
    assert 'type="search"' not in form and "research_term" not in form          # geen artikelzoekbalk
    for text in ("Alle categorieën", "Gadgets", "Smart Home", "Beauty &amp; Care", "Home &amp; Living",
                 "Lifestyle &amp; Sport", "Slim", "7 dagen", "14 dagen", "30 dagen", ">Zoeken<"):
        assert text in form, text
    assert trends.count("Externe zoeklink") >= 6 and "Geen trenddatum: niet als trendbewijs" in trends
    assert "Huisdieren" not in form


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


def _empty(term, **extra):
    return {"error": None, "term": term, "country_name": "Nederland", "category_name": "Gadgets",
            "products": [], "suppliers": [], "news": [], "trends": [], "links": [], "search_trends": [],
            "alternatives": [], "pending_sources": [], "unavailable_sources": [], "unavailable_reasons": {},
            "sources_checked": [], "next_steps": [], "interpretation": {"queries": [], "categories": [], "automatic": False},
            "supplier_suggestions": [], "preferred_tab": "products", "fetched_at": "-", "topic": term,
            "google_trends_checked": False, "supplier_products": 0, "all_sources_failed": False,
            "source_unavailable": False, **extra}


def test_platform_category_really_changes_the_backend_search(administrator, monkeypatch):
    seen = []
    monkeypatch.setattr(nv_ai_search, "discover", lambda term, *a, **k: seen.append(k) or _empty(term))
    base = {"section": "onderzoek", "research_run": "1", "research_block": "platforms", "research_mode": "trends",
            "research_term": "Automatische kattenvoerbak", "research_platform": ["Productcatalogi"],
            "research_country": "NL", "research_supplier_filter": "all"}
    administrator.get("/dashboard", query_string={**base, "research_category": "smart-home"})
    administrator.get("/dashboard", query_string={**base, "research_category": "overig"})
    page = administrator.get("/dashboard", query_string={**base, "research_category": "shop"})
    assert seen[0]["category"] == "smart-home" and seen[0].get("infer", True) is True
    assert seen[1]["category"] == "shop" and seen[1]["infer"] is False
    assert seen[2]["category"] == "shop" and seen[2].get("infer", True) is True
    html = page.get_data(as_text=True)
    assert "Niets gevonden" in html and "Gebruikte periode" in html


def test_overig_skips_automatic_category_narrowing():
    from nv_product_discovery import discover
    cats = {"gadgets": "Gadgets", "pets": "Huisdieren", "home-living": "Home & Living"}
    def offline(*a, **k):
        raise OSError("offline")
    narrowed = discover("kattenvoerbak", mode="products", platforms=["Productcatalogi"], fetch=offline,
                        categories=cats)
    broad = discover("kattenvoerbak", mode="products", platforms=["Productcatalogi"], fetch=offline,
                     categories=cats, infer=False)
    assert narrowed["interpretation"]["automatic"] is True
    assert broad["interpretation"]["automatic"] is False and len(broad["interpretation"]["categories"]) == 3


def test_compact_rows_show_required_fields_and_merge_duplicates():
    import nv_product_rows
    from nv_research_assessment import Fact
    products = [
        {"title": "Automatic Cat Feeder 4L", "url": "https://a.example/1", "source": "PetShop", "category": "pets",
         "facts": {"purchase": Fact("19.95", "https://a.example/1", "2026-11-18", "EUR")}, "assessment": {"status": "Nader onderzoeken", "reason": "x"}},
        {"title": "Automatic cat feeder 4l", "url": "https://a.example/2", "source": "PetShop", "category": "pets"},
        {"title": "Andere voerbak", "url": "https://b.example/1", "source": "Andere", "category": "pets"},
    ]
    suppliers = [{"name": "Echte BV", "origin_name": "Duitsland", "region": "eu", "website": "https://echt.example",
                  "dropshipping": True, "dropshipping_source": "https://echt.example/ds",
                  "products": [{"url": "https://a.example/1"}]}]
    rows = nv_product_rows.build(products, suppliers, {"pets": "Huisdieren"})
    assert len(rows) == 2 and rows[0]["duplicates"] == 1
    first = rows[0]
    assert (first["supplier"], first["origin"], first["dropship"], first["category"]) == ("Echte BV", "Duitsland", "Bevestigd", "Huisdieren")
    assert first["price"] == "Inkoop € 19,95"
    assert rows[1]["price"] is None and rows[1]["dropship"] == "Niet bevestigd" and rows[1]["origin"] == "Onbekend"


def test_results_render_as_compact_rows_with_actions(administrator, monkeypatch):
    item = {"title": "Automatic Cat Feeder 4L", "url": "https://a.example/1", "source": "PetShop", "category": "gadgets",
            "image": "", "other_sources": [],
            "assessment": {"status": "Nader onderzoeken", "reason": "Controleer eerst iets.", "facts": [], "missing": [],
                           "scenario": None, "indicative": None, "market_context": [], "safety_portal": "https://ec.europa.eu",
                           "alert": None, "safety_weeks": 0}}
    monkeypatch.setattr(nv_ai_search, "discover", lambda term, *a, **k: _empty(term, products=[item]))
    html = administrator.get("/dashboard", query_string={"section": "onderzoek", "research_run": "1",
                                                         "research_term": "kattenvoerbak"}).get_data(as_text=True)
    assert 'class="nv-prow"' in html and "nv-research-cards" not in html.split('id="nv-research-products"')[1][:400]
    for text in ("Details", "Bewaar als concept", "Bereken marge", "Niet bevestigd", "Niet beschikbaar", "Controleer eerst iets."):
        assert text in html, text


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
