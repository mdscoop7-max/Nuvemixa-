"""Alle onderzoeks-, niche-, leveranciers-, partner- en publicatiemenu's: bereikbaar, eerlijk over de gegevensbron,
alleen voor de eigenaar."""
import pytest
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401

import app as dashboard

MENUS = [
    "dashboard", "producten", "categorieen", "onderzoek", "internationaal", "viral", "leveranciers", "partners",
    "concepten", "publicatie", "woocommerce", "calculator", "afbeeldingen", "bestellingen", "klanten",
    "accountbeheer", "kortingen", "marketing", "seo", "rankfix", "statistieken", "instellingen", "google-ads",
    "google-shopping", "talen", "klantenservice", "monitoring", "administratie",
]


@pytest.mark.parametrize("sectie", MENUS)
def test_menu_laadt_voor_eigenaar_zonder_fout(administrator, sectie):
    r = administrator.get(f"/dashboard?section={sectie}")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Traceback" not in html and "UndefinedError" not in html


@pytest.mark.parametrize("sectie", MENUS)
@pytest.mark.parametrize("klant", [False, True])
def test_menu_geweigerd_voor_anoniem_en_klant(sectie, klant):
    client = dashboard.app.test_client()
    if klant:
        with client.session_transaction() as saved:
            saved.update(customer_id=1, nv_customer_id=1)
    assert client.get(f"/dashboard?section={sectie}").status_code in (302, 303, 403)


def test_productonderzoek_toont_eerlijke_ai_status(administrator, monkeypatch):
    html = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    assert "AI Productonderzoek" not in html
    assert "AI niet beschikbaar" in html and "normaal zoeken is actief" in html
    assert "Geen verzonnen verkoopcijfers" in html
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    html = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    assert "AI actief" in html and "fixture-key" not in html


def test_viral_toont_vaste_notities_als_niet_live(administrator):
    html = administrator.get("/dashboard?section=viral").get_data(as_text=True)
    assert "Vaste handmatige notities, niet live" in html and "geen live trendresultaten" in html


def test_publicatie_beweert_niet_dat_alles_werkt(administrator):
    html = administrator.get("/dashboard?section=publicatie").get_data(as_text=True)
    assert "Google Trends en eigen waarnemingen" in html and "Sociale populariteitscijfers ontbreken" in html
    assert "nog niet gekoppeld" in html and "TESTDATA" not in html and "Testfase" not in html


def test_bronnentest_alleen_eigenaar(administrator, monkeypatch):
    import nv_supplier_sources as ns
    called = []
    monkeypatch.setattr(ns, "run_source_test", lambda *a, **k: called.append(1))
    monkeypatch.setattr(ns, "admin", lambda: False)
    r = administrator.post("/dashboard/onderzoek/bronnen-testen", data={"_csrf_token": CSRF_TOKEN})
    assert r.status_code == 403 and called == []


@pytest.mark.parametrize(("sectie", "uitleg"), [
    ("viral", ("Google Trends toont zoekinteresse", "Verkoopcijfers en sociale populariteitscijfers ontbreken")),
    ("internationaal", ("Verkoopcijfers en marktprijzen ontbreken",)),
])
def test_onderzoeksmenus_vermelden_welke_data_beschikbaar_zijn(administrator, sectie, uitleg):
    html = administrator.get(f"/dashboard?section={sectie}").get_data(as_text=True)
    for tekst in uitleg:
        assert tekst in html
