"""Landfilters: vestigingsland en magazijnland gescheiden; onbekend telt nooit als NL, EU of buiten EU."""
import pytest

import nv_market_search
from nv_product_discovery import logistics, scope_reason, supplier_in_scope, warehouse_class


def company(name, origin, *warehouses):
    data = {"name": name, "origin": origin, "products": [{"warehouse": w} for w in warehouses]}
    data.update(logistics(data))
    return data


KYRO = company("KYRO Beauty", None, "Netherlands")          # magazijn NL, vestiging onbekend
TERRE = company("Terre Verdi", None, "United Kingdom")       # magazijn VK
ZEROCM = company("Onbekende verkoper", None, "China")       # magazijn China
HAMA = company("Hama B.V.", "NL")                           # bevestigde Nederlandse vestiging, magazijn onbekend
MAIDEN = company("Maiden-Art", "IT", "Italy")
WORLD = company("Wereldwijd BV", None, "Worldwide")          # onduidelijk magazijn
ALL = [KYRO, TERRE, ZEROCM, HAMA, MAIDEN, WORLD]


def names(scope, basis):
    return [c["name"] for c in ALL if supplier_in_scope(c, scope, basis)]


@pytest.mark.parametrize("scope,basis,expected", [
    ("nl", "either", ["KYRO Beauty", "Hama B.V."]),
    ("nl", "origin", ["Hama B.V."]),
    ("nl", "warehouse", ["KYRO Beauty"]),
    ("eu", "either", ["KYRO Beauty", "Hama B.V.", "Maiden-Art"]),
    ("eu", "origin", ["Hama B.V.", "Maiden-Art"]),
    ("international", "either", ["Terre Verdi", "Onbekende verkoper"]),
    ("international", "origin", []),
    ("international", "warehouse", ["Terre Verdi", "Onbekende verkoper"]),
])
def test_country_filter_by_basis(scope, basis, expected):
    assert names(scope, basis) == expected


def test_unknown_warehouse_text_is_never_eu_or_outside():
    assert warehouse_class("Worldwide") == "unknown"
    assert WORLD["warehouse_region"] == "unknown"
    for scope in ("nl", "eu", "international"):
        assert "Wereldwijd BV" not in names(scope, "either")


def test_kyro_is_not_labelled_as_dutch_company():
    reason = scope_reason(KYRO, "nl", "either")
    assert reason.startswith("Voldoet via magazijn (Nederland)") and "Vestiging onbekend" in reason
    assert scope_reason(HAMA, "nl", "either").startswith("Voldoet via vestiging (Nederland)")


def test_market_search_uses_same_rules_and_basis_switch():
    form = nv_market_search.parse("internationaal", {"mregio": "nl", "mbasis": "warehouse"}, {})
    kept = nv_market_search.filter_suppliers([dict(c) for c in ALL], form)
    assert [c["name"] for c in kept] == ["KYRO Beauty"]
    assert kept[0]["scope_reason"].startswith("Voldoet via magazijn")
    assert nv_market_search.parse("internationaal", {}, {})["basis"] == "either"
