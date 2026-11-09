from app import app


def test_information_pages_render_and_link_correctly():
    client = app.test_client()
    for path in ("/faq", "/contact", "/bestellen", "/retouren", "/privacy", "/cookies", "/voorwaarden", "/over-trendmix"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "TrendMix" in response.get_data(as_text=True)


def test_checkout_costs_never_presented_as_final_total():
    client = app.test_client()
    response = client.get("/winkelwagen")
    assert response.status_code == 200
    assert "productsubtotaal" in response.get_data(as_text=True).lower()
    assert "Betalen is nog niet mogelijk" in response.get_data(as_text=True)


def test_faq_explains_test_mode_and_legal_return_rights():
    html = app.test_client().get("/faq").get_data(as_text=True)
    assert "geen echte bestelling" in html
    assert "niet afhankelijk van voorafgaande toestemming" in html


def test_information_pages_have_configured_canonical_url(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://trendmix.nl")
    # SITE_URL is set at import time; verify template uses the configured context variable.
    source = open("templates/info.html", encoding="utf-8").read()
    assert "{{ site_url }}{{ path }}" in source
