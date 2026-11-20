"""Livegang-checklist: alleen namen, nooit waarden; status volgt de omgevingsvariabelen."""
import nv_livegang
from test_system_check import administrator  # noqa: F401

ALL = {"NUVEMIXA_BEDRIJFSNAAM": "x", "NUVEMIXA_ADRES": "x", "NUVEMIXA_KVK": "x", "NUVEMIXA_BTW": "x", "NUVEMIXA_EMAIL": "x"}


def test_company_step_follows_environment(monkeypatch):
    for name in ALL:
        monkeypatch.delenv(name, raising=False)
    assert next(s for s in nv_livegang.checklist() if s["key"] == "bedrijf")["ok"] is False
    for name, value in ALL.items():
        monkeypatch.setenv(name, value)
    assert next(s for s in nv_livegang.checklist() if s["key"] == "bedrijf")["ok"] is True


def test_orders_step_needs_final_switches(monkeypatch):
    for name in ("WOOCOMMERCE_URL", "WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET"):
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("NUVEMIXA_VERIFIED_SHIPPING_COUNTRIES_JSON", '{"nederland": "NL"}')
    monkeypatch.delenv("TRENDMIX_LIVE_ORDERS", raising=False)
    monkeypatch.delenv("NUVEMIXA_SHIPPING_READY", raising=False)
    assert next(s for s in nv_livegang.checklist() if s["key"] == "bestellen")["ok"] is False
    monkeypatch.setenv("NUVEMIXA_SHIPPING_READY", "true")
    monkeypatch.setenv("TRENDMIX_LIVE_ORDERS", "true")
    assert next(s for s in nv_livegang.checklist() if s["key"] == "bestellen")["ok"] is True


def test_page_shows_names_but_never_values(administrator, monkeypatch):
    monkeypatch.setenv("NUVEMIXA_WOO_SECRET", "cs_supergeheim123")
    html = administrator.get("/dashboard?section=woocommerce").get_data(as_text=True)
    assert "Livegang-checklist" in html and "NUVEMIXA_WOO_SECRET" in html and "cs_supergeheim123" not in html
