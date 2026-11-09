"""Bilingual policy/support wiring and verified business-information disclosures."""
from app import app


def test_policy_and_contact_load_bilingual_controller():
    client = app.test_client()
    for path in ("/contact", "/privacy", "/retouren", "/voorwaarden"):
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "trendmix-bilingual-pages.js" in html


def test_policy_contains_real_bilingual_sections():
    html = app.test_client().get("/privacy").get_data(as_text=True)
    assert "data-tm-info-nl=" in html
    assert "data-tm-info-en=" in html


def test_contact_never_invents_business_registration():
    html = app.test_client().get("/contact").get_data(as_text=True)
    assert "Bedrijfs- en contactinformatie" in html
    assert "KvK-nummer" in html
    assert "nadat ze door de eigenaar zijn bevestigd" in html
    assert "data-tm-service-en=" in html


def test_bilingual_controller_served():
    response = app.test_client().get("/static/trendmix-bilingual-pages.js")
    assert response.status_code == 200
    assert b"data-tm-info-en" in response.data
    assert b"data-tm-service-en" in response.data
