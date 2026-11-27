"""Open webonderzoek: AI vindt kandidaten, de server controleert elke pagina, één resultaat per bedrijf.

Alle AI-antwoorden en webpagina's hieronder zijn nagebootst; er wordt niets echt aangeroepen."""
import json

import pytest

import nv_openai
import nv_web_discovery as wd
import nv_web_discovery_view as view
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

ROUTE = "/dashboard/onderzoek/webzoeken"
REAL_FETCH, REAL_PUBLIC_HOST = wd.fetch_page, wd.public_host

PAGES = {
    "https://www.powerhandel.de/b2b": "<title>PowerHandel GmbH</title><p>Großhandel für Powerbank und Ladegeräte. "
                                      "Händler werden – B2B-Preise, Dropshipping möglich, WooCommerce Plugin.</p>"
                                      "<a href='/kontakt'>Kontakt</a>",
    "https://shop.powerhandel.de/powerbank": "<p>Powerbank wholesale</p>",
    "https://www.chargefactory.cn/oem": "<p>We are a factory for power bank OEM and ODM orders, MOQ 500.</p>",
    "https://www.blog-tech.nl/beste-powerbanks": "<p>De beste powerbanks van 2026 getest.</p>",
    "https://www.lampen.fr/": "<p>Lampes design pour la maison.</p>",
    "https://grossiste-energie.fr/powerbank": "<p>Grossiste powerbank pour revendeurs.</p>",
}


def response(results, cited=()):
    text = json.dumps({"results": results})
    refs = [{"type": "url_citation", "url": url, "title": "T"} for url in cited]
    return {"output": [{"type": "web_search_call"}, {"type": "web_search_call"},
                       {"type": "message", "content": [{"type": "output_text", "text": text, "annotations": refs}]}]}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(wd, "_cache", {})
    monkeypatch.setattr(view, "_usage", {"day": "", "count": 0})
    monkeypatch.setattr(view, "COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(wd, "public_host", lambda host: host not in {"127.0.0.1", "intern.local"})
    monkeypatch.delenv(view.DAILY_VARIABLE, raising=False)

    def fake_fetch(url, deadline):
        if "blocked" in url:
            raise ValueError("HTTP 403")
        if url not in PAGES:
            raise ValueError("HTTP 404")
        return url, PAGES[url]
    monkeypatch.setattr(wd, "fetch_page", fake_fetch)


@pytest.fixture
def ai(monkeypatch):
    calls = []
    state = {"reply": response([])}

    def fake_post(path, data, **kwargs):
        calls.append(data)
        return state["reply"]
    monkeypatch.setattr(nv_openai, "post", fake_post)
    monkeypatch.setattr(nv_openai, "configured", lambda: True)
    return calls, state


def row(url, name="", country=""):
    return {"name": name, "url": url, "country": country, "type": "wholesale"}


def test_open_search_verifies_pages_dedupes_companies_and_skips_retail(ai):
    calls, state = ai
    state["reply"] = response([
        row("https://www.powerhandel.de/b2b", "PowerHandel"),
        row("https://shop.powerhandel.de/powerbank", "PowerHandel Shop"),   # zelfde bedrijf, ander subdomein
        row("https://www.amazon.de/s?k=powerbank", "Amazon"),               # consumentenwinkel
        row("https://www.blog-tech.nl/beste-powerbanks", "Blog"),           # geen zakelijk signaal
        row("https://www.chargefactory.cn/oem", "ChargeFactory", "CN"),
        row("https://verzonnen-leverancier.nl/x", "Phantom BV"),           # bestaat niet (404)
    ])
    result = wd.search("powerbank", "suppliers", "gadgets")
    names = [card["name"] for card in result["results"]]
    assert names.count("PowerHandel") == 1 and "PowerHandel Shop" not in names
    assert "Amazon" not in names and "Phantom BV" not in names
    assert result["unique_companies"] == len({card["domain"] for card in result["results"]})
    verified = {card["domain"] for card in result["results"] if card["verified"]}
    assert verified == {"powerhandel.de", "chargefactory.cn"}
    blog = next(card for card in result["results"] if card["domain"] == "blog-tech.nl")
    assert not blog["verified"] and blog["status"].startswith("Aanwijzing")
    power = next(card for card in result["results"] if card["domain"] == "powerhandel.de")
    assert power["country"] == "DE" and "WooCommerce" in power["integrations"]
    assert power["contact"] == "https://www.powerhandel.de/kontakt"
    quotes = [fact["quote"] for fact in power["facts"] if fact.get("quote")]
    assert any("Großhandel" in quote for quote in quotes)   # bewijs is een citaat van de pagina zelf
    assert any("niet bereikbaar" in reason for reason in result["skipped"])
    assert any("consumentenwinkel" in reason for reason in result["skipped"])
    # Geen domeinfilter meer: dat weigert OpenAI met gpt-4.1-mini (HTTP 400 param=tools).
    assert "filters" not in calls[0]["tools"][0]


def test_prompt_uses_language_of_target_country_and_category(ai):
    calls, _ = ai
    wd.search("slimme stekker", "dropship", "smart-home", "DE")
    data = calls[0]
    assert "German" in data["instructions"] and "smart home" in data["instructions"]
    assert data["tools"][0]["user_location"] == {"type": "approximate", "country": "DE"}
    assert json.loads(data["input"])["target_country"] == "DE"


def test_country_filter_and_exclude_list_give_other_companies(ai):
    _, state = ai
    state["reply"] = response([row("https://www.powerhandel.de/b2b"), row("https://grossiste-energie.fr/powerbank")])
    only_fr = wd.search("powerbank", "wholesale", "gadgets", "FR")
    assert [card["domain"] for card in only_fr["results"]] == ["grossiste-energie.fr"]
    assert only_fr["outside_scope"] == 1
    more = wd.search("powerbank", "wholesale", "gadgets", exclude=["grossiste-energie.fr"])
    assert [card["domain"] for card in more["results"]] == ["powerhandel.de"]


def test_blocked_site_is_shown_as_not_verifiable_never_as_verified(ai):
    _, state = ai
    state["reply"] = response([row("https://blocked-one.com/a"), row("https://blocked-two.com/b")],
                              cited=["https://blocked-one.com/a"])
    result = wd.search("powerbank", "suppliers", "gadgets")
    assert sorted(card["domain"] for card in result["results"]) == ["blocked-one.com", "blocked-two.com"]
    for card in result["results"]:
        assert card["verified"] is False and "blokkeert" in card["status"]


def test_translated_keywords_from_ai_count_for_relevance_only(ai):
    _, state = ai
    PAGES["https://earbud-wholesale.com/tws"] = "<p>TWS earbuds wholesale for retailers, MOQ 100.</p>"
    reply = response([row("https://earbud-wholesale.com/tws", "Earbud Wholesale")])
    text = json.loads(reply["output"][2]["content"][0]["text"])
    text["keywords"] = ["wireless earbuds", "TWS earbuds", "<script>"]
    reply["output"][2]["content"][0]["text"] = json.dumps(text)
    state["reply"] = reply
    result = wd.search("draadloze oordopjes", "wholesale", "gadgets")
    card = result["results"][0]
    assert card["verified"] and card["relevant"]               # Nederlandse term staat er niet, de vertaling wel
    assert "<script>" not in result["meta"]["keywords"] and "tws earbuds" in result["meta"]["keywords"]


def test_products_need_the_term_on_the_page(ai):
    _, state = ai
    PAGES["https://www.lampen.fr/"] = "<p>Grossiste lampes design, vente en gros pour revendeurs.</p>"
    state["reply"] = response([row("https://www.lampen.fr/"), row("https://www.powerhandel.de/b2b")])
    result = wd.search("bureaulamp", "products", "home-living")
    lampen = next(card for card in result["results"] if card["domain"] == "lampen.fr")
    assert lampen["verified"] is False   # categorie past, maar het product zelf staat er niet


def test_urls_are_normalised_and_internal_addresses_refused():
    assert wd.normal_url("https://user:pw@example.com/") is None
    assert wd.normal_url("ftp://example.com/") is None
    assert wd.normal_url("https://x.nl/p?utm_source=openai&id=3#top") == "https://x.nl/p?id=3"
    assert wd.registrable("shop.example.co.uk") == "example.co.uk"
    for host in ("127.0.0.1", "localhost", "10.0.0.8", "192.168.1.1", "printer.local"):
        assert REAL_PUBLIC_HOST(host) is False
    with pytest.raises(ValueError):
        REAL_FETCH("https://127.0.0.1/admin", 10**9)


def test_only_the_five_webshop_categories_are_accepted():
    assert set(wd.CATEGORIES.values()) == {"Gadgets", "Smart Home", "Beauty & Care", "Home & Living",
                                           "Lifestyle & Sport"}
    for bad in ("pets", "pc-componenten"):
        with pytest.raises(wd.SearchError):
            wd.prepare("powerbank", "suppliers", bad)


def test_identical_search_comes_from_cache_without_ai_call(ai):
    calls, state = ai
    state["reply"] = response([row("https://www.powerhandel.de/b2b")])
    first = wd.search("powerbank", "suppliers", "gadgets")
    second = wd.search("Powerbank", "suppliers", "gadgets")
    assert len(calls) == 1 and second["cached"] is True and second["results"] == first["results"]


# ------------------------------------------------------------------ dashboard -----------------------------------
@pytest.mark.parametrize("section", ["onderzoek", "leveranciers", "partners", "internationaal"])
def test_component_is_on_each_research_section(administrator, section):
    page = administrator.get(f"/dashboard?section={section}")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert 'id="nv-wd-form"' in text and "nv-web-discovery.js" in text
    form = text.split('id="nv-wd-form"')[1].split("</form>")[0]
    assert "Huisdieren" not in form and "PC" not in form
    for name in ("Gadgets", "Smart Home", "Beauty &amp; Care", "Home &amp; Living", "Lifestyle &amp; Sport"):
        assert name in form


def test_route_without_key_sends_nothing(administrator, monkeypatch):
    called = []
    monkeypatch.setattr(nv_openai, "configured", lambda: False)
    monkeypatch.setattr(nv_openai, "post", lambda *a, **k: called.append(1))
    reply = administrator.post(ROUTE, data={"_csrf_token": CSRF_TOKEN, "term": "powerbank"})
    assert reply.status_code == 200 and reply.json["code"] == "not_configured" and not called


def test_route_returns_checked_results_and_counts_only_real_calls(administrator, ai, monkeypatch):
    calls, state = ai
    monkeypatch.setenv(view.DAILY_VARIABLE, "1")
    state["reply"] = response([row("https://www.powerhandel.de/b2b", "PowerHandel")])
    form = {"_csrf_token": CSRF_TOKEN, "term": "powerbank", "kind": "suppliers", "category": "gadgets"}
    first = administrator.post(ROUTE, data=form)
    assert first.status_code == 200 and first.json["ok"] and first.json["results"][0]["name"] == "PowerHandel"
    again = administrator.post(ROUTE, data=form)            # cache: telt niet mee voor de daglimiet
    assert again.json["ok"] and again.json["cached"] and len(calls) == 1
    other = administrator.post(ROUTE, data={**form, "term": "yogamat"})
    assert other.status_code == 429 and other.json["code"] == "limit" and len(calls) == 1


def test_route_rejects_invalid_input_and_requires_login(administrator, ai):
    calls, _ = ai
    bad = administrator.post(ROUTE, data={"_csrf_token": CSRF_TOKEN, "term": "x"})
    assert bad.status_code == 400 and not calls
    import app as dashboard
    anonymous = dashboard.app.test_client().post(ROUTE, data={"term": "powerbank"})
    assert anonymous.status_code in (302, 400, 403)


def test_ai_unavailable_gives_clear_message(administrator, monkeypatch):
    monkeypatch.setattr(nv_openai, "configured", lambda: True)

    def refuse(*args, **kwargs):
        raise nv_openai.AIUnavailable("budget", "Intern maandbudget voor AI in NUVEMIXA bereikt.")
    monkeypatch.setattr(nv_openai, "post", refuse)
    reply = administrator.post(ROUTE, data={"_csrf_token": CSRF_TOKEN, "term": "powerbank"})
    assert reply.status_code == 200 and reply.json["code"] == "budget" and "maandbudget" in reply.json["message"]
