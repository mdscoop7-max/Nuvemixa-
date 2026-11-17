"""Leveranciersdekking per categorie en land; geen netwerk, geen automatische aanroepen."""
import pytest
from test_system_check import administrator  # noqa: F401

import nv_supplier_sources as ns
from zoek_fixture import maak_fetch


def namen(rows):
    return [r["name"] for r in rows]


def test_suggesties_hangen_van_categorie_en_land_af():
    beauty = namen(ns.sources_for(("beauty-care",), "NL"))
    wonen = namen(ns.sources_for(("home-living",), "NL"))
    assert "Hertwill" in beauty and "dropXL (vidaXL)" not in beauty
    assert "dropXL (vidaXL)" in wonen and beauty != wonen
    assert "Avasam" not in namen(ns.sources_for(("gadgets",), "NL"))
    assert "Avasam" in namen(ns.sources_for(("gadgets",), "GB"))


def test_elke_suggestie_heeft_toegangsklasse_en_eerlijke_status():
    for row in ns.sources_for(("gadgets", "home-living", "beauty-care"), "NL", "yogamat", limit=20):
        assert row["access_label"] and row["type_label"] and row["search_link"].startswith("https://www.google.com/search?q=")
        assert "yogamat" in row["search_link"]
        if not row["onderzocht"]:
            assert row["evidence"] == () and row["cost"] == "Onbekend."
        else:
            assert row["evidence"], "onderzochte bron moet een bewijslink hebben"


def test_bigbuy_en_cj_worden_niet_als_doorzoekbaar_getoond():
    connected = namen(ns.connected_sources())
    assert "BigBuy" not in connected and "CJdropshipping" not in connected


def test_dekking_per_categorie_en_land():
    nl = ns.coverage("NL")
    assert set(nl) == set(ns.CATEGORIES)
    assert all(nl[c]["connected"] for c in ("gadgets", "beauty-care", "home-living"))
    assert "Hama" not in [s["name"] for s in ns.coverage("FR")["gadgets"]["connected"]]


def test_geen_usb_voorkeur_meer_zonder_zoekterm():
    import nv_product_discovery as npd
    assert "power" not in " ".join(npd.SEEDS.values()).lower()
    assert all("power" not in c.seed.lower() for c in npd.CATALOGUES)


def test_hama_voegt_geen_vast_model_toe_zonder_passende_term():
    import nv_research_sources as src
    aanroepen = []

    def fetch(*a, **k):
        aanroepen.append(a)
        raise OSError("geen netwerk")
    rows = src.hama_products(fetch, "", "NL", lambda f, url, params=None, **k: f(url) , lambda *a: True,
                             lambda *a: True, lambda *a: True)
    assert rows == []
    assert all("00201752" not in str(a) for a in aanroepen)


def test_bronnentest_is_alleen_lezen_en_markeert_fouten():
    ns.reset_test()
    rows = ns.run_source_test(fetch=maak_fetch())
    assert rows and {r["status"] for r in rows} <= {"ok", "leeg", "fout"}
    assert ns.test_state()["at"]


def test_bronnentest_route_vereist_inlog_en_csrf(administrator):
    from flask import Flask  # noqa: F401
    import app
    anoniem = app.app.test_client()
    assert anoniem.post("/dashboard/onderzoek/bronnen-testen").status_code in (302, 303, 400, 401, 403)


def test_pagina_opent_zonder_netwerkaanroep_en_toont_dekking(administrator, monkeypatch):
    def verbied(*a, **k):
        raise AssertionError("de pagina mag niets aanroepen")
    monkeypatch.setattr(ns, "run_source_test", verbied)
    pagina = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    assert "Bronnen en dekking" in pagina and "Bronnen testen" in pagina
    assert "Nog niet getest" in pagina or "Live gemeten" in pagina
