"""Vier WooCommerce-statussen. Geen netwerk, alleen fictieve waarden."""
import pytest

import app as dashboard
import nv_woo_bridge as bridge
from test_system_check import administrator  # noqa: F401  (fixture)

NAMES = ("URL", "KEY", "SECRET", "HOST")
GEHEIM = "ck_fictief_geheim_123"


@pytest.fixture(autouse=True)
def schoon(monkeypatch):
    for n in NAMES:
        monkeypatch.delenv("NUVEMIXA_WOO_" + n, raising=False)
    for n in ("WOOCOMMERCE_URL", "WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET"):
        monkeypatch.delenv(n, raising=False)
    bridge.reset_test()
    yield
    bridge.reset_test()


def vul(monkeypatch, **extra):
    values = {"URL": "https://shop.example.invalid", "KEY": GEHEIM, "SECRET": "cs_fictief", "HOST": "shop.example.invalid"}
    values.update(extra)
    for k, v in values.items():
        monkeypatch.setenv("NUVEMIXA_WOO_" + k, v)


def test_niet_ingesteld():
    st = bridge.connection_status()
    assert st["state"] == "not_configured" and st["label"] == "Niet ingesteld"


def test_onvolledig_noemt_alleen_namen_en_blijft_niet_ingesteld(monkeypatch):
    monkeypatch.setenv("NUVEMIXA_WOO_KEY", GEHEIM)
    st = bridge.connection_status()
    assert st["state"] == "not_configured"
    assert "NUVEMIXA_WOO_URL" in st["detail"] and GEHEIM not in st["detail"]


def test_geconfigureerd_maar_niet_getest(monkeypatch):
    vul(monkeypatch)
    st = bridge.connection_status()
    assert st["state"] == "configured_untested" and st["label"] == "Geconfigureerd, nog niet getest"


def test_alleen_oude_variabelen_zijn_geen_verbonden_status(monkeypatch):
    for n in ("WOOCOMMERCE_URL", "WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET"):
        monkeypatch.setenv(n, "x")
    assert bridge.connection_status()["state"] == "configured_untested"


def test_verbonden_pas_na_geslaagde_test_en_verloopt(monkeypatch):
    vul(monkeypatch)
    bridge.record_test(True)
    assert bridge.connection_status()["state"] == "connected"
    later = bridge._LAST_TEST["at"] + bridge.TEST_VALID_SECONDS + 5
    assert bridge.connection_status(now=later)["state"] == "configured_untested"


def test_verbindingsfout_toont_reden_zonder_geheimen(monkeypatch):
    vul(monkeypatch)
    bridge.record_test(False, "WooCommerce weigert toegang. Controleer de leesrechten van de API-sleutel.")
    st = bridge.connection_status()
    assert st["state"] == "error" and "leesrechten" in st["detail"] and GEHEIM not in st["detail"]


def test_nooit_verbonden_zonder_test(monkeypatch):
    vul(monkeypatch)
    assert bridge.connection_status()["state"] != "connected"


def test_dashboard_toont_de_status_en_doet_geen_netwerkaanroep(administrator, monkeypatch):
    vul(monkeypatch)

    def verboden(*a, **k):
        raise AssertionError("er mag geen echte API-aanroep worden gedaan")

    monkeypatch.setattr(bridge, "_fetch", verboden)
    page = administrator.get("/dashboard?section=dashboard").get_data(as_text=True)
    assert "Geconfigureerd, nog niet getest" in page and GEHEIM not in page
    page = administrator.get("/dashboard?section=monitoring").get_data(as_text=True)
    assert GEHEIM not in page


def test_monitoring_rij_volgt_de_vier_toestanden(monkeypatch):
    assert dashboard.monitoring_integrations()["WooCommerce"][0] == "unconfigured"
    vul(monkeypatch)
    assert dashboard.monitoring_integrations()["WooCommerce"][0] == "unchecked"
    bridge.record_test(True)
    assert dashboard.monitoring_integrations()["WooCommerce"][0] == "works"
    bridge.record_test(False, "fout")
    assert dashboard.monitoring_integrations()["WooCommerce"][0] == "failed"
