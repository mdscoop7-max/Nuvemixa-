import re

import pytest

import app as dashboard
import nv_administratie as adm
from test_system_check import administrator

MENU = ["dashboard", "producten", "categorieen", "afbeeldingen", "bestellingen", "klanten", "klantenservice",
        "kortingen", "onderzoek", "internationaal", "viral", "calculator", "statistieken", "seo", "rankfix",
        "google-shopping", "google-ads", "marketing", "talen", "leveranciers", "woocommerce", "accountbeheer",
        "monitoring", "instellingen"]


def test_test_overview_calculates_from_paid_orders_only():
    o = adm.test_overview()
    assert o["omzet"] == 12390 and o["kosten"] == 10175 and o["winst"] == 2215
    assert str(o["marge"]) == "17.9"
    assert [p["aantal"] for p in o["producten"]] == [2, 1, 1]
    assert {x["id"]: x["betaald"] for x in o["orders"]} == {"T-1001": True, "T-1002": True, "T-1003": False, "T-1004": False}


def test_euro_format():
    assert adm.euro(123456) == "€1.234,56" and adm.euro(-5) == "-€0,05"


def test_real_orders_has_no_customer_fields():
    summary = adm.real_orders([{"id": 7, "date": "2026-11-01", "status": "completed", "currency": "EUR", "total": "10.00",
                                "billing": {"email": "x@example.invalid"}}])
    assert "x@example.invalid" not in repr(summary) and summary["aantal"] == 1
    assert adm.real_orders(None) is None


def test_administration_page_labels_testdata_and_hides_real_figures(administrator, monkeypatch):
    monkeypatch.setattr(dashboard, "recent_woo_orders", lambda: (None, "WooCommerce niet gekoppeld."))
    page = administrator.get("/dashboard?section=administratie")
    text = page.get_data(as_text=True)
    assert page.status_code == 200 and text.count("TESTDATA") >= 4
    assert "ECHT" in text and "WooCommerce niet gekoppeld." in text


def test_administration_shows_real_orders_separately(administrator, monkeypatch):
    monkeypatch.setattr(dashboard, "recent_woo_orders", lambda: ([{"id": 757, "date": "d", "status": "processing",
                                                                   "currency": "EUR", "total": "9.99"}], None))
    text = administrator.get("/dashboard?section=administratie").get_data(as_text=True)
    assert "#757" in text and "Betaald, in behandeling" in text


def test_administration_requires_owner_login():
    client = dashboard.app.test_client()
    assert client.get("/dashboard?section=administratie").status_code in (302, 303, 401, 403)


def test_all_menu_sections_and_single_home(administrator):
    for section in MENU + ["administratie"]:
        assert administrator.get(f"/dashboard?section={section}").status_code == 200, section
    home = administrator.get("/dashboard?section=dashboard").get_data(as_text=True)
    assert home.count('aria-label="NUVEMIXA hoofdscherm"') == 1 and "nv26-home" not in home
    for label in ("Producten", "Productonderzoek", "Niches", "Leveranciers", "WooCommerce", "Bestellingen", "Klantberichten", "Administratie"):
        assert label in home
    assert re.search(r"€\s?\d[\d.,]*\s*</strong><small>Geen verkoopcijfer", home)
    menu = home[home.index('id="tmAdminNavigation"'):]
    for section in MENU:
        assert f"section={section}" in menu, section


def test_languages_page_lists_real_shop_languages(administrator):
    import nv_talen
    codes = [row["code"] for row in nv_talen.winkel_talen()]
    assert codes == ["nl", "en", "fr", "it", "es", "de"]
    text = administrator.get("/dashboard?section=talen").get_data(as_text=True)
    assert "Nog niet gekoppeld" in text and "Niet gekoppeld" in text
    for name in ("Nederlands", "Engels", "Frans", "Italiaans", "Spaans", "Duits"):
        assert name in text


def test_languages_page_handles_missing_files(tmp_path):
    import nv_talen
    assert nv_talen.winkel_talen(tmp_path) == []
