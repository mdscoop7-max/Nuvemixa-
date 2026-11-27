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
    "https://www.chargefactory.cn/oem": "<p>We are a factory for powerbank OEM and ODM orders, MOQ 500.</p>",
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


def test_more_button_tells_ai_to_skip_shown_companies_and_counts_repeats(ai):
    """Live 27-11: de tweede ronde gaf dezelfde bedrijven terug en toonde niets nieuws zonder uitleg."""
    calls, state = ai
    state["reply"] = response([row("https://www.powerhandel.de/b2b"), row("https://www.chargefactory.cn/oem")])
    result = wd.search("powerbank", "wholesale", "gadgets", exclude=["powerhandel.de"])
    assert "never return those domains" in calls[0]["instructions"]
    assert json.loads(calls[0]["input"])["exclude_domains"] == ["powerhandel.de"]
    assert result["meta"]["repeated"] == 1 and [c["domain"] for c in result["results"]] == ["chargefactory.cn"]
    first = wd.search("powerbank", "wholesale", "gadgets")
    assert "never return those domains" not in calls[-1]["instructions"] and first["meta"]["repeated"] == 0


def test_china_is_searched_in_english_with_factory_queries(ai):
    calls, _ = ai
    wd.search("powerbank", "wholesale", "gadgets", "CN", "international")
    text = calls[0]["instructions"]
    assert "Search in English." in text and "Chinese" not in text and "manufacturer China" in text


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


def test_weak_footer_words_do_not_make_a_shop_verified(ai):
    """Live 27-11: kantoorwinkels met 'B2B' of 'affiliate' in de voettekst kregen ten onrechte 'Gecontroleerd'."""
    _, state = ai
    PAGES["https://www.kantoorwinkel.nl/opbergbox"] = ("<p>Opbergbox met deksel 20 liter, op voorraad.</p>"
                                                       "<footer>Zakelijk bestellen (B2B) · Affiliate · Reseller</footer>")
    state["reply"] = response([row("https://www.kantoorwinkel.nl/opbergbox", "Kantoorwinkel")])
    card = wd.search("opbergbox", "suppliers", "home-living")["results"][0]
    assert card["verified"] is False and card["status"].startswith("Aanwijzing: alleen zwakke signalen")
    weak = [fact for fact in card["facts"] if fact["value"].startswith("Alleen los genoemd")]
    assert weak and all(fact["status"] == "aanwijzing" for fact in weak)


def test_retailer_with_affiliate_footer_or_oem_part_number_is_no_supplier(ai):
    """Live 27-11: Viking Direct ('Affiliate Partnerprogramma' in voettekst) en XtremeOffice ('OEM nummer')."""
    _, state = ai
    PAGES["https://www.viking-test.nl/opbergbox"] = ("<p>Opbergbox met deksel 5,6 l.</p><footer>Viking Shop · Affiliate "
                                                     "Partnerprogramma · Herroepingsrecht</footer>")
    PAGES["https://www.xoffice-test.nl/opbergbox"] = "<p>Opbergbox met deksel. EAN 3086960265977 OEM nummer 010438</p>"
    PAGES["https://www.oem-factory-test.cn/box"] = "<p>Opbergbox / storage box with lid. OEM/ODM service, MOQ 1000.</p>"
    state["reply"] = response([row("https://www.viking-test.nl/opbergbox", "Viking"),
                               row("https://www.xoffice-test.nl/opbergbox", "XOffice"),
                               row("https://www.oem-factory-test.cn/box", "OEM Factory")])
    cards = {card["name"]: card for card in wd.search("opbergbox", "suppliers", "home-living")["results"]}
    assert cards["Viking"]["verified"] is False and cards["XOffice"]["verified"] is False
    assert cards["OEM Factory"]["verified"] is True and cards["OEM Factory"]["role"] == "Groothandel / distributeur"
    as_partner = wd.search("opbergbox", "partners", "home-living")["results"]
    assert next(c for c in as_partner if c["name"] == "Viking")["verified"] is True   # affiliate = partner (model C)


def test_partners_need_a_real_partner_programme_and_wholesalers_get_a_clear_reason(ai):
    _, state = ai
    PAGES["https://serumbrand.eu/partners"] = "<p>Face serum. Join our affiliate program or become a stockist.</p>"
    PAGES["https://serum-wholesale.de/"] = "<p>Face serum wholesale for retailers, MOQ 50.</p>"
    state["reply"] = response([row("https://serumbrand.eu/partners", "SerumBrand"),
                               row("https://serum-wholesale.de/", "Serum Wholesale")])
    cards = {card["domain"]: card for card in wd.search("face serum", "partners", "beauty-care")["results"]}
    assert cards["serumbrand.eu"]["verified"] is True
    wholesale = cards["serum-wholesale.de"]
    assert wholesale["verified"] is False
    assert wholesale["status"] == ("Aanwijzing: wel groothandel, maar partner-/resellerprogramma niet bevestigd "
                                   "op deze pagina")


def test_relevance_ignores_spacing_and_generic_ai_words():
    """Live 27-11 (DE): 'yogamat' stond als 'Yoga Mats' op de pagina en AI gaf 'yogamatte grosshandel deutschland'."""
    page = "wholesale yoga mats for studios. sticky yoga-mat 4.5 mm".casefold()
    assert wd.matching_terms(page, wd.term_tokens("yogamat"), []) == ["yogamat"]
    assert wd.matching_terms(page, [], ["yoga mat wholesale germany"]) == ["yoga mat"]
    assert wd.matching_terms("wholesale germany only", [], ["yoga mat wholesale germany"]) == []
    assert wd.matching_terms("power banks", wd.term_tokens("mat"), []) == []      # te kort: geen toevalstreffer


def test_quote_is_found_when_article_matches_only_without_spaces(ai):
    """Live 27-11: deze combinatie gaf 'controle mislukt' (citaat zocht 'yogamat' letterlijk)."""
    _, state = ai
    PAGES["https://yoga-wholesale.de/"] = "<p>Wholesale Yoga Mats für Studios, MOQ 20.</p>"
    state["reply"] = response([row("https://yoga-wholesale.de/", "Yoga Wholesale")])
    result = wd.search("yogamat", "wholesale", "lifestyle-sport", "DE")
    card = result["results"][0]
    assert card["verified"] and not result["skipped"]
    assert "Yoga Mats" in next(fact["quote"] for fact in card["facts"] if fact["label"] == "Past bij zoekopdracht")


def test_cache_period_depends_on_research_type():
    assert wd.cache_seconds("products") == 12 * 3600
    for kind in ("suppliers", "dropship", "wholesale", "partners"):
        assert wd.cache_seconds(kind) == 24 * 3600


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
    assert lampen["status"].endswith("het gezochte artikel staat niet op deze pagina")
    supplier = wd.search("bureaulamp", "suppliers", "home-living")["results"]
    assert next(c for c in supplier if c["domain"] == "lampen.fr")["verified"] is False   # ook bij Leveranciers


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
# Productonderzoek gebruikt sinds 27-11 het gecombineerde proces (test_research_job.py), geen los blok.
@pytest.mark.parametrize("section", ["leveranciers", "partners", "internationaal"])
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


def test_owner_can_save_a_live_result_to_the_permanent_candidate_list(administrator, monkeypatch):
    text = administrator.get("/dashboard?section=partners").get_data(as_text=True)
    assert 'data-save-url="/dashboard/partners/kandidaat"' in text
    assert "geen live, automatische internetzoekmachine" not in text   # verouderde uitleg is aangepast
    saved = []
    import nuvemixa_admin_store
    monkeypatch.setattr(nuvemixa_admin_store, "add_supplier", lambda *args: saved.append(args))
    reply = administrator.post("/dashboard/partners/kandidaat", data={
        "_csrf_token": CSRF_TOKEN, "name": "PowerHandel", "url": "https://www.powerhandel.de/b2b", "model": "A",
        "notes": "Live webonderzoek: Gecontroleerd"})
    assert reply.status_code == 303 and saved and saved[0][0] == "PowerHandel"
    assert saved[0][3].startswith("[Kandidaat · model A · eigen vondst")
