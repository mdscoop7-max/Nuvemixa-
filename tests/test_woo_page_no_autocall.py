"""Het openen van de WooCommerce-pagina doet GEEN externe aanroep; alleen een klik op een knop doet dat.
Alle waarden zijn fictief; er wordt niets echt benaderd."""
import pytest

import app as dashboard
import nv_woo_bridge as bridge
from test_system_check import CSRF_TOKEN, administrator  # noqa: F401  (fixture)

GEHEIM = "ck_fictief_geheim_987"
NAMES = {"URL": "https://shop.example.invalid", "KEY": GEHEIM, "SECRET": "cs_fictief_geheim", "HOST": "shop.example.invalid"}


@pytest.fixture(autouse=True)
def omgeving(monkeypatch):
    for k, v in NAMES.items():
        monkeypatch.setenv("NUVEMIXA_WOO_" + k, v)
    bridge.reset_test()
    calls = []

    def geen_netwerk(*a, **k):
        calls.append(("netwerk", a, k))
        raise AssertionError("er mag geen netwerkaanroep worden gedaan")

    monkeypatch.setattr(bridge.requests, "get", geen_netwerk)
    monkeypatch.setattr(bridge.socket, "getaddrinfo", geen_netwerk)
    yield calls
    bridge.reset_test()


def nep_fetch(monkeypatch, antwoord=None, fout=None):
    log = []

    def fetch(base, auth, path, host):
        log.append(path)
        if fout:
            raise fout
        return antwoord(path) if antwoord else []

    monkeypatch.setattr(bridge, "_fetch", fetch)
    return log


def post(client, url, **extra):
    return client.post(url, data={"_csrf_token": CSRF_TOKEN, **extra})


@pytest.mark.parametrize("url", ["/admin/commerce", "/admin/commerce?embedded=1", "/dashboard?section=woocommerce",
                                 "/dashboard?section=dashboard", "/dashboard?section=monitoring"])
def test_openen_van_pagina_doet_geen_aanroep(administrator, omgeving, url):
    assert administrator.get(url).status_code == 200
    assert omgeving == []


def test_ongetest_is_eerlijk_en_toont_geen_verbonden(administrator):
    page = administrator.get("/admin/commerce").get_data(as_text=True)
    assert "Geconfigureerd, nog niet getest" in page and "Verbonden en gecontroleerd" not in page
    assert "Verbinding testen" in page and "Gegevens vernieuwen" in page
    assert GEHEIM not in page and "cs_fictief_geheim" not in page


def test_knop_test_doet_precies_een_alleen_lezen_aanroep(administrator, monkeypatch):
    log = nep_fetch(monkeypatch)
    response = post(administrator, "/admin/commerce/test")
    assert response.status_code == 303
    assert log == ["products?per_page=1"]
    page = administrator.get("/admin/commerce").get_data(as_text=True)
    assert "Verbonden en gecontroleerd" in page and "Laatste succesvolle test:" in page
    assert log == ["products?per_page=1"]  # opnieuw openen doet niets extra's


def test_knop_vernieuwen_leest_alleen_en_bewaart_momentopname(administrator, monkeypatch):
    def antwoord(path):
        if path.startswith("products"):
            return [{"id": 1, "name": "Testproduct", "sku": "T1", "stock_status": "instock", "price": "9.95"}]
        return [{"id": 7, "status": "processing", "date_created": "2026-11-17T10:00:00", "total": "19.90",
                 "billing": {"email": "klant@example.invalid"}}]

    log = nep_fetch(monkeypatch, antwoord)
    assert post(administrator, "/admin/commerce/refresh").status_code == 303
    assert len(log) == 2 and all(p.startswith(("products", "orders")) for p in log)
    page = administrator.get("/admin/commerce").get_data(as_text=True)
    assert "Testproduct" in page and "Momentopname van" in page
    assert "klant@example.invalid" not in page  # geen klantgegevens
    assert len(log) == 2


def test_fout_is_veilig_en_laatste_succes_blijft_zichtbaar(administrator, monkeypatch):
    nep_fetch(monkeypatch)
    post(administrator, "/admin/commerce/test")
    nep_fetch(monkeypatch, fout=bridge.CommerceConnectionError("WooCommerce weigert toegang. Controleer de leesrechten van de API-sleutel."))
    post(administrator, "/admin/commerce/test")
    page = administrator.get("/admin/commerce").get_data(as_text=True)
    assert "Verbindingsfout" in page and "leesrechten" in page and "Laatste succesvolle test:" in page
    assert GEHEIM not in page and "cs_fictief_geheim" not in page


def test_knoppen_hebben_csrf_en_beheerder_nodig(administrator, monkeypatch):
    log = nep_fetch(monkeypatch)
    assert administrator.post("/admin/commerce/test", data={}).status_code in (400, 403)
    anoniem = dashboard.app.test_client()
    for url in ("/admin/commerce/test", "/admin/commerce/refresh"):
        assert anoniem.post(url, data={"_csrf_token": "x"}).status_code in (302, 303, 400, 403)
    assert log == []


def test_zonder_configuratie_geen_aanroep_en_knoppen_uit(administrator, monkeypatch, omgeving):
    monkeypatch.delenv("NUVEMIXA_WOO_KEY")
    page = administrator.get("/admin/commerce").get_data(as_text=True)
    assert "Niet ingesteld" in page and "disabled" in page
    log = nep_fetch(monkeypatch)
    post(administrator, "/admin/commerce/test")
    assert log == [] and omgeving == []


def test_er_zijn_geen_schrijfroutes_naar_woocommerce():
    verboden = ("publish", "sync", "update", "delete", "create")
    routes = [r for r in dashboard.app.url_map.iter_rules() if r.endpoint.startswith("nuvemixa_woo.")]
    assert {r.rule for r in routes} == {"/admin/commerce", "/admin/commerce/test", "/admin/commerce/refresh"} | {r.rule for r in routes if r.rule.startswith("/admin/commerce-assets")}
    assert not any(w in r.rule for r in routes for w in verboden)
    import inspect
    broncode = inspect.getsource(bridge)
    assert "requests.post" not in broncode and "requests.put" not in broncode and "requests.delete" not in broncode


SECTIES = ["dashboard", "producten", "publicatie", "categorieen", "afbeeldingen", "bestellingen", "klanten",
           "klantenservice", "kortingen", "onderzoek", "internationaal", "viral", "calculator", "statistieken", "seo",
           "rankfix", "google-shopping", "google-ads", "marketing", "leveranciers", "woocommerce", "administratie",
           "accountbeheer", "monitoring", "instellingen"]


@pytest.mark.parametrize("sectie", SECTIES)
def test_geen_enkele_dashboardpagina_doet_een_externe_aanroep(administrator, monkeypatch, omgeving, sectie):
    """Ook mét volledige (fictieve) Woo-configuratie en de oude WOOCOMMERCE_*-variabelen."""
    import urllib.request
    monkeypatch.setenv("WOOCOMMERCE_URL", "https://oud.example.invalid")
    monkeypatch.setenv("WOOCOMMERCE_KEY", "ck_oud")
    monkeypatch.setenv("WOOCOMMERCE_SECRET", "cs_oud")

    def verboden(*a, **k):
        omgeving.append("verboden")
        raise AssertionError("externe aanroep bij het openen van een pagina")

    monkeypatch.setattr(bridge, "_fetch", verboden)
    monkeypatch.setattr(dashboard, "woo_request", verboden, raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", verboden)
    assert administrator.get("/dashboard?section=" + sectie).status_code == 200
    assert omgeving == []


def test_bestellingen_tonen_de_momentopname_van_de_knop(administrator, monkeypatch):
    nep_fetch(monkeypatch, antwoord=lambda path: [{"id": 4711, "status": "processing", "date_created": "2026-11-16T10:00:00",
                                                    "total": "19.95", "billing": {"email": "geheim@klant.invalid"}}]
              if path.startswith("orders") else [{"id": 1, "name": "Testproduct", "sku": "T-1", "price": "9.95"}])
    assert "Nog niet opgehaald" in administrator.get("/dashboard?section=bestellingen").get_data(as_text=True)
    post(administrator, "/admin/commerce/refresh")
    page = administrator.get("/dashboard?section=bestellingen").get_data(as_text=True)
    assert "#4711" in page and "processing" in page and "geheim@klant.invalid" not in page
