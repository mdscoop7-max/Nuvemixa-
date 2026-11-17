"""Partnerzoeker: drie modellen gescheiden, feit/aanwijzing/onbekend, geen verzonnen gegevens, geen automatische acties."""
import pytest
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401

import nv_partners as np_


def names(args):
    return [r["name"] for r in np_.search(args)]


def test_register_heeft_alle_drie_modellen_en_ongeschikte_bedrijven():
    rows = np_.search({})
    models = {m for r in rows for m in r["models"]}
    assert models == {"A", "B", "C"}
    assert {r["status"] for r in rows} == {"aantoonbaar", "mogelijk", "affiliate", "ongeschikt"}


def test_elk_bedrijf_heeft_alle_criteria_met_geldige_status():
    for p in np_.all_partners():
        assert set(p["facts"]) >= {k for k, _, _ in np_.CRITERIA}, p["name"]
        for k, _, _ in np_.CRITERIA:
            assert p["facts"][k]["status"] in (np_.FACT, np_.HINT, np_.UNKNOWN)
            assert p["facts"][k]["text"]


def test_affiliate_is_nooit_dropshipping():
    for p in np_.all_partners():
        if "C" in p["models"]:
            assert "A" not in p["models"] and p["status"] == "affiliate"
            assert p["facts"]["ondersteuning"]["text"].lower().startswith("alleen commissie") or "alleen affiliate" in p["facts"]["ondersteuning"]["text"].lower()
    assert "123Wonen" in names({"model": "C"}) and "123Wonen" not in names({"model": "A"})


def test_aantoonbaar_dropshipping_vereist_een_gelezen_feit():
    for p in np_.all_partners():
        if p["status"] == "aantoonbaar" and p["name"] in {"Beautinow", "Hertwill", "BigBuy", "Syncee", "CJdropshipping"}:
            assert any(x["status"] == np_.FACT for x in p["facts"].values())


def test_onderzocht_bedrijf_met_bron_en_niet_gelezen_bedrijf_zonder_feiten():
    versa = next(p for p in np_.PARTNERS if p["name"] == "Versa Group")
    assert all(x["status"] == np_.UNKNOWN for x in versa["facts"].values())
    assert np_.score(versa)["fit"] == 0 and np_.score(versa)["label"] == "Vooral onbekend"
    assert np_.score(next(p for p in np_.PARTNERS if p["name"] == "Beautinow"))["fit"] > 50


def test_score_telt_aanwijzing_minder_dan_feit():
    a = {"facts": {k: np_.f("x", np_.FACT) for k, _, _ in np_.CRITERIA}, "favorable": {"levering"}}
    b = {"facts": {k: np_.f("x", np_.HINT) for k, _, _ in np_.CRITERIA}, "favorable": {"levering"}}
    assert np_.score(a)["fit"] > np_.score(b)["fit"] > 0


def test_filters_categorie_land_type_kosten_integratie():
    assert "Beautinow" in names({"cat": "beauty-care", "land": "NL"})
    assert "Beautinow" not in names({"cat": "beauty-care", "land": "US"})
    assert "Avasam" not in names({"land": "NL"}) and "Avasam" in names({"land": "GB"})
    assert set(names({"type": "netwerk"})) >= {"Awin (Nederland)", "Daisycon", "TradeTracker"}
    assert "Hertwill" in names({"kosten": "gratis"}) and "Nuki" in names({"kosten": "gratis"})
    assert "Beautinow" in names({"integratie": "feed"}) and "BigBuy" in names({"integratie": "api"})
    assert "Beautinow" in names({"q": "parfum"}) and "Nuki" in names({"q": "slimme sloten"})


def test_gadgets_niet_alleen_opladers():
    types = {t for r in np_.search({"cat": "gadgets"}) for t in r["products"]}
    assert len(types) >= 6 and not types <= {"usb", "kabels", "powerbanks"}


def test_home_living_heeft_meer_dan_een_merk():
    assert len([n for n in names({"cat": "home-living"})]) >= 6


def test_ontdekkingslinks_hangen_van_filters_af_en_halen_niets_op():
    nl = np_.discovery_links("yogamat", "lifestyle-sport", "NL")
    de = np_.discovery_links("yogamat", "lifestyle-sport", "DE")
    assert nl != de and all(x["url"].startswith("https://www.google.com/search?q=") for x in nl)
    assert any("site%3A.nl" in x["url"] for x in nl)


def test_pagina_toont_resultaten_zonder_netwerk_en_zonder_verzendknop(administrator):
    html = administrator.get("/dashboard?section=partners").get_data(as_text=True)
    assert "Partners zoeken" in html and "Gecontroleerd feit" in html and "Bewaar op kandidatenlijst" in html
    assert "Beautinow" in html and "Aqara" in html
    assert "Stuur aanvraag" not in html and "mailto:" not in html
    gefilterd = administrator.get("/dashboard?section=partners&model=C&land=NL").get_data(as_text=True)
    assert "123Wonen" in gefilterd and "Beautinow" not in gefilterd


def test_kandidaat_bewaren_schrijft_alleen_naar_leverancierslijst(administrator, monkeypatch):
    saved = []
    import nuvemixa_admin_store as store
    monkeypatch.setattr(store, "add_supplier", lambda *a, **k: saved.append(a))
    r = administrator.post("/dashboard/partners/kandidaat", data={"_csrf_token": CSRF_TOKEN, "name": "Beautinow"})
    assert r.status_code == 303 and len(saved) == 1
    assert saved[0][0] == "Beautinow" and saved[0][1] == "" and saved[0][3].startswith("[Kandidaat")
    assert "Nog geen overeenkomst" in saved[0][3]


def test_kandidaat_eigen_vondst_is_gemarkeerd_als_ongecontroleerd(administrator, monkeypatch):
    saved = []
    import nuvemixa_admin_store as store
    monkeypatch.setattr(store, "add_supplier", lambda *a, **k: saved.append(a))
    administrator.post("/dashboard/partners/kandidaat", data={"_csrf_token": CSRF_TOKEN, "name": "Kleine Yogawinkel",
                       "url": "https://example.invalid", "model": "B", "notes": "wil ik vragen"})
    assert "ongecontroleerd" in saved[0][3]


def test_kandidaat_route_vereist_inlog_en_csrf(administrator):
    import app
    assert app.app.test_client().post("/dashboard/partners/kandidaat", data={"name": "X"}).status_code in (302, 303, 400, 401, 403)
    assert administrator.post("/dashboard/partners/kandidaat", data={"name": "Beautinow"}).status_code in (400, 403)


def test_geen_enkele_aanvraag_functie_bestaat():
    import inspect
    source = inspect.getsource(np_)
    assert "smtplib" not in source and "requests." not in source and "send_mail" not in source
