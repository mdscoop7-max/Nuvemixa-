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
    # Sinds 27-11-2026 vervangen door het open webonderzoek (nv_web_discovery); de oude route blijft bestaan.
    assert 'id="nv-wd-form"' in text and "Live zoeken met AI" in text and "AI-configuratie ontbreekt" in text
    assert "disabled" in text.split('id="nv-wd-submit"')[1][:80]
    assert "Regio" in text and "Webshopcategorie" in text and "Groothandels en fabrikanten" in text


def test_page_with_configuration_enables_the_button(administrator, configured):
    text = administrator.get("/dashboard?section=leveranciers").get_data(as_text=True)
    assert "AI-configuratie ontbreekt" not in text
    assert "disabled" not in text.split('id="nv-wd-submit"')[1][:40]


def test_missing_configuration_sends_nothing(administrator, monkeypatch):
    calls = install(monkeypatch, citations())
    response = post(administrator)
    assert response.status_code == 200 and response.json["code"] == "not_configured"
    assert response.json["state"] == "unavailable" and response.json["fallback_url"].startswith("/dashboard?section=onderzoek")
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
    # AI-fout = geen 503 meer: duidelijke melding plus link naar normaal zoeken.
    assert response.status_code == 200 and response.json["code"] == code and response.json["state"] == "unavailable"
    assert "Normaal zoeken werkt wel" in response.json["message"] and "research_mode=suppliers" in response.json["fallback_url"]
    assert response.json["results"] == [] and "fixture-key" not in response.get_data(as_text=True)


@pytest.mark.parametrize("body,code", [(b"", "empty"), (b"   ", "empty"), (b"{niet-json", "invalid_json")])
def test_empty_or_broken_api_answers_are_reported(administrator, configured, monkeypatch, body, code):
    install(monkeypatch, body)
    response = post(administrator)
    assert response.status_code == 200 and response.json["code"] == code and response.json["state"] == "unavailable"


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


def test_route_is_blocked_during_storage_freeze_without_any_call_or_cost(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_FREEZE", "1")
    response = post(administrator)
    assert response.status_code == 503 and calls == [] and ai.usage_snapshot()["month_used"] == 0
    if response.is_json:  # zonder PR #73 antwoordt de route zelf; met PR #73 de algemene bevriezing (platte tekst)
        assert response.json["code"] == "frozen"
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_FREEZE")
    assert post(administrator).status_code == 200 and len(calls) == 1


def test_limit_survives_a_server_restart_through_the_signed_session_counter(administrator, configured, monkeypatch):
    monkeypatch.setenv(ai.DAILY_VARIABLE, "2")
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    assert post(administrator, query="Product een").status_code == 200
    assert post(administrator, query="Product twee").status_code == 200
    monkeypatch.setattr(ai, "_usage", {"month": "", "month_count": 0, "day": "", "day_count": 0})  # herstart
    blocked = post(administrator, query="Product drie")
    assert blocked.status_code == 429 and blocked.json["code"] == "limit" and len(calls) == 2


def test_tampered_session_counter_is_ignored_safely(administrator, configured, monkeypatch):
    install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    with administrator.session_transaction() as saved:
        saved["nv_supplier_ai_usage"] = {"m": "x", "mc": "veel", "d": None, "dc": -5}
    assert post(administrator).status_code == 200


def test_route_is_listed_with_the_freeze_ai_endpoints():
    import nv_freeze
    assert "nv_manage.supplier_ai_search" in nv_freeze.AI_ENDPOINTS


def test_freeze_guard_blocks_the_route_before_it_runs(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_FREEZE", "1")
    response = post(administrator)
    assert response.status_code == 503 and response.mimetype == "text/plain" and response.headers["Retry-After"] == "120"
    assert calls == [] and ai.usage_snapshot()["month_used"] == 0


def test_missing_or_wrong_csrf_token_is_refused_for_an_admin_without_any_call(administrator, configured, monkeypatch):
    calls = install(monkeypatch, citations("https://sirocco.de/dropshipping/"))
    assert administrator.post(ROUTE, data={"query": "LED-lamp"}).status_code == 403
    assert administrator.post(ROUTE, data={"query": "LED-lamp", "_csrf_token": "fout"}).status_code == 403
    assert calls == [] and ai.usage_snapshot()["month_used"] == 0



class _ErrorBody:
    def __init__(self, payload): self.payload = payload
    def read(self, *_): return self.payload
    def close(self): pass


def test_http_400_is_logged_safely_and_retried_with_a_simpler_request(administrator, configured, monkeypatch, caplog):
    import io
    attempts = []
    body = json.dumps({"error": {"type": "invalid_request_error", "param": "tool_choice", "code": "unsupported_value",
                                 "message": "Tool choice not supported with key sk-abcdefghijklmnop"}}).encode()

    def fake(request, timeout):
        data = json.loads(request.data)
        attempts.append(data)
        if len(attempts) == 1:
            raise urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(body))
        return Reply(citations("https://www.bigbuy.eu/nl/dropshipping"))

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake)
    with caplog.at_level("WARNING"):
        response = post(administrator)
    assert response.status_code == 200 and response.json["ok"] is True
    # Tweede poging: geen domeinfilter meer, wel nog gedwongen webzoeken en de domeinen als site:-zoekvragen.
    assert "filters" in attempts[0]["tools"][0] and "filters" not in attempts[1]["tools"][0]
    assert "site:" in attempts[1]["instructions"] and "bigbuy.eu" in attempts[1]["input"]
    log = caplog.text
    assert "param=tool_choice" in log and "sk-abcdefghijklmnop" not in log and "fixture-key" not in log


def test_repeated_http_400_ends_as_ai_unavailable_with_parameter(administrator, configured, monkeypatch):
    import io
    body = json.dumps({"error": {"type": "invalid_request_error", "param": "tools[0].filters", "message": "x"}}).encode()
    attempts = []

    def fake(request, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(body))

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake)
    response = post(administrator)
    assert len(attempts) == 3 and response.status_code == 200 and response.json["state"] == "unavailable"
    assert "tools[0].filters" in response.json["message"] and response.json["detail"]["param"] == "tools[0].filters"


def test_filters_refusal_is_remembered_so_next_search_skips_it(administrator, configured, monkeypatch):
    import io
    monkeypatch.setattr(ai, "_filters_refused", set())
    body = json.dumps({"error": {"type": "invalid_request_error", "param": "tools",
                                 "message": "Parameter 'filters' not supported with model 'gpt-4.1-mini'."}}).encode()
    attempts = []

    def fake(request, timeout):
        data = json.loads(request.data)
        attempts.append(data)
        if "filters" in data["tools"][0]:
            raise urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(body))
        return Reply(citations("https://www.bigbuy.eu/nl/dropshipping"))

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake)
    first = post(administrator)
    assert first.json["ok"] is True and len(attempts) == 2
    assert first.json["meta"]["variant"] == ai.REQUEST_VARIANTS[1]
    second = post(administrator, query="Yogamat")
    assert second.json["ok"] is True and len(attempts) == 3 and "filters" not in attempts[2]["tools"][0]


def test_openai_tracking_parameter_does_not_reject_an_approved_citation():
    response = {"output": [{"type": "message", "content": [{"type": "output_text", "annotations": [
        {"type": "url_citation", "url": "https://www.bigbuy.eu/nl/dropshipping?utm_source=openai", "title": "BigBuy"},
        {"type": "url_citation", "url": "https://www.bigbuy.eu/nl/zoek?q=lamp", "title": "Zoek"},
        {"type": "url_citation", "url": "https://other.example/x?utm_source=openai", "title": "Ander"}]}]}]}
    rejected = []
    received, found = ai.extract_cited(response, ["bigbuy.eu"], rejected)
    assert received == 3 and found["bigbuy.eu"]["href"] == "https://www.bigbuy.eu/nl/dropshipping"
    assert "other.example" in rejected
    assert ai.strip_tracking("https://a.example/p?q=1&utm_source=openai") == "https://a.example/p?q=1"
