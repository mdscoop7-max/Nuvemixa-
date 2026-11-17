import json
import urllib.error

import pytest

import app as dashboard
import nv_supplier_ai as ai
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401  (fixture)

ROUTE = "/dashboard/leveranciers/ai-zoeken"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(ai, "_cache", {})
    monkeypatch.setattr(ai, "_usage", {"month": "", "month_count": 0, "day": "", "day_count": 0})
    monkeypatch.setattr(ai, "COOLDOWN_SECONDS", 0)
    for name in (ai.MONTHLY_VARIABLE, ai.DAILY_VARIABLE):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NUVEMIXA_SUPPLIER_SEARCH_MODEL", raising=False)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setenv("NUVEMIXA_SUPPLIER_SEARCH_MODEL", "fixture-model")


class Reply:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, _): return self.body


def citations(*urls):
    refs = [{"type": "url_citation", "url": url, "title": "Titel " + url[-6:]} for url in urls]
    return json.dumps({"output": [{"type": "message", "content": [
        {"type": "output_text", "text": "Verzonnen prijs 1 euro en bedrijf Phantom BV.", "annotations": refs}]}]}).encode()


def install(monkeypatch, body=None, error=None):
    calls = []
    def fake(request, timeout):
        calls.append(json.loads(request.data))
        assert timeout == ai.TIMEOUT_SECONDS
        if error:
            raise error
        return Reply(body)
    monkeypatch.setattr(ai.urllib.request, "urlopen", fake)
    return calls


def post(client, **values):
    form = {"_csrf_token": CSRF_TOKEN, "query": "LED-bureaulamp", "eu_only": "1"}
    form.update(values)
    return client.post(ROUTE, data=form)


def test_leveranciers_page_shows_the_search_bar_and_missing_configuration(administrator):
    page = administrator.get("/dashboard?section=leveranciers")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert 'id="nv-ai-form"' in text and "Zoeken met AI" in text and "AI-configuratie ontbreekt" in text
    assert "disabled" in text.split('id="nv-ai-submit"')[1][:80]
    assert "Alleen Europese leveranciers" in text and "Zoekwoord" in text and "Productcategorie" in text


def test_page_with_configuration_enables_the_button(administrator, configured):
    text = administrator.get("/dashboard?section=leveranciers").get_data(as_text=True)
    assert "AI-configuratie ontbreekt" not in text
    assert "disabled" not in text.split('id="nv-ai-submit"')[1][:40]


def test_missing_configuration_sends_nothing(administrator, monkeypatch):
    calls = install(monkeypatch, citations())
    response = post(administrator)
    assert response.status_code == 503 and response.json["code"] == "not_configured"
    assert "OPENAI_API_KEY" in response.json["message"] and calls == []


def test_requires_permission_and_csrf(configured, monkeypatch):
    calls = install(monkeypatch, citations())
    assert dashboard.app.test_client().post(ROUTE, data={"query": "x"}).status_code in (400, 403)
    assert calls == []


@pytest.mark.parametrize("values", [{"query": "a"}, {"query": "lamp@example.invalid"}, {"category": "Verzonnen"},
                                    {"country": "XX"}, {"keyword": "a@b"}])
def test_invalid_input_is_rejected_without_api_call(administrator, configured, monkeypatch, values):
    calls = install(monkeypatch, citations())
    response = post(administrator, **values)
    assert response.status_code == 400 and response.json["code"] == "invalid" and calls == []


def test_only_cited_approved_sources_become_results_and_unknown_fields_stay_unconfirmed(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations("https://www.ikea.com/fixture", "https://www.dropxl.com/nl/faq.html",
                                           "https://www.dropxl.com/nl/andere", "https://sirocco.de/dropshipping/"))
    response = post(administrator, category="Home & Living", keyword="dimbaar", prefer_woo="1")
    assert response.status_code == 200 and response.json["ok"]
    results = response.json["results"]
    assert [row["name"] for row in results] == ["dropXL B2B", "Sirocco"]
    sirocco = results[1]
    assert sirocco["dropshipping"] == "Bron meldt dropshipping vanuit Kleve"
    for row in results:
        assert row["woocommerce"] == row["sell_the_trend"] == row["delivery"] == row["contact"] == "Niet bevestigd"
        assert row["source"]["href"].startswith("https://") and "geciteerde bronpagina" in row["source"]["origin"]
    assert "Phantom" not in json.dumps(results) and "euro" not in json.dumps(results)
    meta = response.json["meta"]
    assert meta["citations_received"] == 4 and meta["sources_accepted"] == 2
    assert meta["persistent"] is False and meta["cached"] is False
    sent = calls[0]
    domains = sent["tools"][0]["filters"]["allowed_domains"]
    assert "avasam.com" not in domains and "cjdropshipping.com" not in domains
    assert sent["max_tool_calls"] == 3 and sent["store"] is False
    assert "WooCommerce" in sent["instructions"] and "dimbaar" in sent["input"]


def test_country_filter_limits_sources_and_unsupported_combination_costs_nothing(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    assert post(administrator, country="DE").json["results"][0]["country"] == "DE"
    assert calls[0]["tools"][0]["filters"]["allowed_domains"] == ["sirocco.de"]
    before = ai.usage_snapshot()["month_used"]
    response = post(administrator, country="GB", eu_only="1")
    assert response.json["code"] == "no_sources" and len(calls) == 1
    assert ai.usage_snapshot()["month_used"] == before


def test_no_cited_source_gives_clear_empty_message(administrator, configured, monkeypatch):
    install(monkeypatch, citations("https://www.ikea.com/fixture"))
    response = post(administrator)
    assert response.json["ok"] and response.json["results"] == []
    assert "Geen controleerbare bron" in response.json["message"]


@pytest.mark.parametrize("error,code", [
    (urllib.error.HTTPError("u", 401, "x", {}, None), "auth"),
    (urllib.error.HTTPError("u", 429, "x", {}, None), "upstream_limit"),
    (urllib.error.HTTPError("u", 500, "x", {}, None), "upstream"),
    (TimeoutError(), "timeout"),
    (urllib.error.URLError(TimeoutError()), "timeout"),
    (urllib.error.URLError("dns"), "network"),
])
def test_external_failures_get_specific_messages_without_secrets(administrator, configured, monkeypatch, error, code):
    install(monkeypatch, error=error)
    response = post(administrator)
    assert response.status_code == 503 and response.json["code"] == code
    assert response.json["results"] == [] and "fixture-key" not in response.get_data(as_text=True)


@pytest.mark.parametrize("body,code", [(b"", "empty"), (b"   ", "empty"), (b"{niet-json", "invalid_json")])
def test_empty_or_broken_api_answers_are_reported(administrator, configured, monkeypatch, body, code):
    install(monkeypatch, body)
    response = post(administrator)
    assert response.status_code == 503 and response.json["code"] == code


def test_identical_search_is_served_from_cache_without_a_second_call(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    first, second = post(administrator), post(administrator)
    assert len(calls) == 1 and second.json["meta"]["cached"] is True
    assert first.json["results"] == second.json["results"]
    assert ai.usage_snapshot()["month_used"] == 1


def test_monthly_and_daily_limits_stop_searches_before_any_call(administrator, configured, monkeypatch):
    monkeypatch.setenv(ai.MONTHLY_VARIABLE, "1")
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    assert post(administrator, query="Eerste product").status_code == 200
    blocked = post(administrator, query="Tweede product")
    assert blocked.status_code == 429 and blocked.json["code"] == "limit" and len(calls) == 1
    monkeypatch.setenv(ai.MONTHLY_VARIABLE, "50")
    monkeypatch.setenv(ai.DAILY_VARIABLE, "1")
    assert post(administrator, query="Derde product").status_code == 429
    assert len(calls) == 1


def test_failed_calls_also_count_and_cooldown_blocks_rapid_repeats(administrator, configured, monkeypatch):
    install(monkeypatch, error=TimeoutError())
    post(administrator)
    assert ai.usage_snapshot()["month_used"] == 1
    monkeypatch.setattr(ai, "COOLDOWN_SECONDS", 3600)
    assert post(administrator, query="Ander product").json["code"] == "cooldown"


def test_parallel_search_is_refused(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations())
    assert ai._busy.acquire(blocking=False)
    try:
        assert post(administrator).json["code"] == "busy" and calls == []
    finally:
        ai._busy.release()


def test_existing_supplier_search_helper_is_unchanged():
    import nv_supplier_finder
    assert nv_supplier_finder.search_configured() is False


def test_bigbuy_dropshipping_fact_is_shown_but_woocommerce_stays_unconfirmed(administrator, configured, monkeypatch):
    install(monkeypatch, citations("https://www.bigbuy.eu/public/doc/Guia_API_BigBuy_EN.pdf"))
    (row,) = post(administrator, country="ES").json["results"]
    assert "dropshipping met eigen voorraad" in row["dropshipping"] and row["woocommerce"] == "Niet bevestigd"
