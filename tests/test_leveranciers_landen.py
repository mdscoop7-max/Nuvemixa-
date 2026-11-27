"""Landenfilters (Nederland, EU, buiten EU, wereldwijd), leveranciersrijen zonder verzonnen contactgegevens."""
import pathlib

import nv_product_rows
from nv_market_search import filter_suppliers
from nv_product_discovery import supplier_in_scope
from nv_research_sources import FILTERS

ROOT = pathlib.Path(__file__).resolve().parents[1]
NL = {"origin": "NL", "region": "eu", "name": "NL BV"}
DE = {"origin": "DE", "region": "eu", "name": "DE GmbH"}
CN = {"origin": "CN", "region": "international", "name": "CN Ltd"}
UNK = {"origin": "", "region": "unknown", "name": "Onbekend"}


def test_supplier_scopes():
    assert list(FILTERS)[:2] == ["all", "nl"]
    pick = lambda scope: [c["name"] for c in (NL, DE, CN, UNK) if supplier_in_scope(c, scope)]
    assert pick("nl") == ["NL BV"]
    assert pick("eu") == ["NL BV", "DE GmbH"]          # onbekende vestiging nooit als EU
    assert pick("international") == ["CN Ltd"]
    assert pick("all") == ["NL BV", "DE GmbH", "CN Ltd", "Onbekend"]


def test_market_region_filter():
    form = {"region": "nl", "supplier_type": "all", "ships_nl": False, "country": "NL"}
    assert [c["name"] for c in filter_suppliers([NL, DE, CN, UNK], form)] == ["NL BV"]
    form["region"] = "international"
    assert [c["name"] for c in filter_suppliers([NL, DE, CN, UNK], form)] == ["CN Ltd"]


def test_supplier_rows_only_show_real_contact_data():
    rows = nv_product_rows.suppliers([
        {"name": "Xtorm", "website": "https://www.xtorm.eu", "origin_name": "Nederland", "dropshipping": None,
         "evidence": (("Contact", "https://www.xtorm.eu/pages/contact"),), "products": [1, 2]},
        {"name": "X", "website": "https://x.example", "email": "geen-email", "phone": "bel ons", "dropshipping": True,
         "dropshipping_source": "https://x.example/ds", "products": []},
        {"name": "Y", "email": "sales@y.example", "phone": "+31 20 123 4567", "products": []},
    ])
    assert rows[0]["email"] is None and rows[0]["phone"] is None and rows[0]["contact_url"].endswith("/contact")
    assert rows[0]["dropship"] == "Niet bevestigd" and rows[0]["origin"] == "Nederland"
    assert rows[1]["email"] is None and rows[1]["phone"] is None and rows[1]["dropship"] == "Bevestigd"
    assert rows[2]["email"] == "sales@y.example" and rows[2]["phone"] == "+31 20 123 4567" and rows[2]["origin"] == "Onbekend"


def test_live_margin_and_search_history_scripts():
    margin = (ROOT / "static/nv-margin-live.js").read_text(encoding="utf-8")
    assert "NIET als € 0" in margin and "missing.push" in margin
    history = (ROOT / "static/nv-search-history.js").read_text(encoding="utf-8")
    # Sinds 27-11-2026: permanente geschiedenis per gebruiker op de server, lijst onder de zoekbalk.
    assert "/dashboard/zoekgeschiedenis" in history and "input.value = ''" in history and "Alles wissen" in history
    page = (ROOT / "templates/dashboard.html").read_text(encoding="utf-8")
    assert "margin_form('onderzoek', 'nv-margin-live'" in page and "nv-search-history.js" in page
    assert "margin_form('calculator', 'nv-calc-live'" in page and "nv-margin-core.js" in page


def test_catalog_changes_are_cached_and_invalidated_on_save(monkeypatch):
    import nv_catalog_manager as cm
    reads = []
    monkeypatch.setattr(cm, "_read_catalog_changes", lambda: reads.append(1) or ([], [("c", "s", {"name": "x"})]))
    cm.invalidate_changes()
    first, second = cm.catalog_changes(), cm.catalog_changes()
    assert first == second and len(reads) == 1
    class DB:
        def execute(self, *a):
            pass
    cm.save(DB(), "product", "c", "s", {"name": "y"})
    cm.catalog_changes()
    assert len(reads) == 2
    cm.invalidate_changes()


def test_search_history_keeps_ten_and_covers_partner_search():
    history = (ROOT / "static/nv-search-history.js").read_text(encoding="utf-8")
    import nv_search_history
    assert nv_search_history.MAX_ITEMS == 20 and "params.get(input.name)" in history
    partners = (ROOT / "templates/_dashboard_partners.html").read_text(encoding="utf-8")
    assert 'input type="search" name="q" data-history="partners:q"' in partners
