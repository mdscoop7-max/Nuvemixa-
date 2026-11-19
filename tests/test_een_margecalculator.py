"""Eén gedeelde rekenmodule voor 'Winstmarge per product' en 'Prijs & marge calculator' (browser = server)."""
import json
import pathlib
import re
import shutil
import subprocess

import pytest
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401

from nv_product_margin import UNIFIED_COSTS, unified_margin

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = [
    {"purchase_cost": "12.50", "target_margin": "35"},
    {"purchase_cost": "12.50", "target_margin": "25"},
    {"purchase_cost": "4.99", "target_margin": "15", "vat_rate": "9"},
    {"purchase_cost": "39.95", "target_margin": "40"},
    {"purchase_cost": "0.99", "target_margin": "20", "std_shipping": "2.50", "std_fee_pct": "1.9"},
    {"purchase_cost": "12.50", "target_margin": "35", "selling_price": "39.95", "shipping_cost": "4.95",
     "advertising_cost": "3", "returns_reserve": "1", "transaction_fee": "0.29", "transaction_pct": "1.5",
     "platform_fee": "0", "other_cost": "0"},
    {"purchase_cost": "12.50", "target_margin": "30", "shipping_cost": "0", "selling_price": "24.99"},
    {"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": "standard"},
    {"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": "free"},
    {"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": "own", "shipping_cost": "6.50"},
    {"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": "unknown"},
    {"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": "standard", "customer_shipping": "4.95",
     "selling_price": "34.95"},
    {"purchase_cost": "8", "target_margin": "25", "shipping_choice": "own", "shipping_cost": "3.10",
     "customer_shipping": "2.50", "std_fee_pct": "1.9"},
]


def js_inputs(case):
    def val(name, pct=False):
        raw = case.get(name, "")
        if raw == "":
            return None
        n = float(raw.replace(",", "."))
        return n if pct else round(n * 100)
    actual, standard = {}, {}
    for key, actual_name, standard_name, _ in UNIFIED_COSTS:
        actual[key] = val(actual_name, key == "fee_pct")
        s = val(standard_name, key == "fee_pct")
        if s is not None:
            standard[key] = s
    vat = val("vat_rate", True)
    return {"purchase": val("purchase_cost"), "vat": 21 if vat is None else vat, "target": float(case["target_margin"]),
            "own": val("selling_price"), "actual": actual, "standard": standard,
            "shippingChoice": case.get("shipping_choice", "own"), "customerShipping": val("customer_shipping") or 0}


@pytest.fixture(scope="module")
def browser_results():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js niet beschikbaar")
    code = ("const m=require(%r);const cases=JSON.parse(process.argv[1]);"
            "console.log(JSON.stringify(cases.map(c=>m.compute(c))))") % str(ROOT / "static/nv-margin-core.js")
    out = subprocess.run([node, "-e", code, json.dumps([js_inputs(c) for c in CASES])],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("index", range(len(CASES)))
def test_browser_and_server_calculate_identically(browser_results, index):
    server, browser = unified_margin(CASES[index]), browser_results[index]
    for key in ("selling", "customer", "total", "revenue", "vat", "fee", "costs", "gross", "profit"):
        assert server["advice"][key] == browser["advice"][key], key
    assert abs(server["advice"]["margin"] - browser["advice"]["margin"]) < 1e-9
    assert server["kind"] == browser["kind"] and server["assumed"] == browser["assumed"]
    if server["own"]:
        assert {k: server["own"][k] for k in ("profit", "fee", "revenue", "reaches", "short")} == \
               {k: browser["own"][k] for k in ("profit", "fee", "revenue", "reaches", "short")}


def test_reference_price_and_every_margin_choice():
    assert unified_margin({"purchase_cost": "12.50", "target_margin": "35"})["advice"]["selling"] == 4256
    for target in (15, 20, 25, 30, 35, 40):
        r = unified_margin({"purchase_cost": "12.50", "target_margin": str(target)})
        assert abs(r["advice"]["margin"] - target) < 0.2


def test_missing_costs_are_assumptions_and_explicit_zero_is_real():
    preliminary = unified_margin({"purchase_cost": "12.50", "target_margin": "35"})
    assert preliminary["kind"] == "A" and len(preliminary["assumed"]) == 7
    zero = unified_margin({"purchase_cost": "12.50", "target_margin": "35", "platform_fee": "0"})
    assert zero["sources"]["platform"] == "nul" and "Platformkosten" not in zero["assumed"]
    real = unified_margin({"purchase_cost": "12.50", "target_margin": "35", **{a: "0" for _, a, _, _ in UNIFIED_COSTS}})
    assert real["kind"] == "B" and real["assumed"] == []
    assert real["advice"]["selling"] < preliminary["advice"]["selling"]   # werkelijke kosten veranderen de prijs


@pytest.mark.parametrize("bad", [{"purchase_cost": ""}, {"purchase_cost": "-1"}, {"purchase_cost": "1.234"},
                                 {"purchase_cost": "10", "vat_rate": "150"}, {"purchase_cost": "10", "target_margin": "abc"},
                                 {"purchase_cost": "10", "shipping_cost": "-2"},
                                 {"purchase_cost": "10", "target_margin": "40", "transaction_pct": "90"}])
def test_invalid_input_is_rejected(bad):
    with pytest.raises(ValueError):
        unified_margin(bad)


def _table(html, marker):
    block = html.split(f'id="{marker}"', 1)[1].split("</table>", 1)[0]
    return [re.sub(r"\s+", " ", c).strip() for c in re.findall(r"<td>(.*?)</td>", block, re.S)]


def test_both_pages_show_the_same_result(administrator):
    query = "margin_run=1&margin_method=unified&purchase_cost=12.50&target_margin=35"
    onderzoek = administrator.get(f"/dashboard?section=onderzoek&{query}").get_data(as_text=True)
    calculator = administrator.get(f"/dashboard?section=calculator&{query}").get_data(as_text=True)
    assert _table(onderzoek, "nv-margin-live") == _table(calculator, "nv-calc-live")
    assert "€ 42,56" in _table(calculator, "nv-calc-live")
    for html in (onderzoek, calculator):
        assert 'name="std_fee_fixed"' in html and 'value="0.35"' in html and 'name="target_margin" value="40"' in html
        assert "A · Voorlopige adviesprijs" in html


@pytest.mark.parametrize("choice,extra,price,source", [
    ("standard", {}, 4256, "aanname"), ("free", {}, 3290, "nul"),
    ("own", {"shipping_cost": "6.50"}, 4559, "ingevuld"), ("unknown", {}, 4256, "onbekend"),
])
def test_shipping_choice_changes_advice_and_label(choice, extra, price, source):
    r = unified_margin({"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": choice, **extra})
    assert r["advice"]["selling"] == price and r["sources"]["shipping"] == source
    assert abs(r["advice"]["margin"] - 35) < 0.05
    if choice == "unknown":
        assert any("nog onbekend" in label for label in r["assumed"])


def test_customer_shipping_is_revenue_not_free_for_seller():
    r = unified_margin({"purchase_cost": "12.50", "target_margin": "35", "shipping_choice": "standard",
                        "customer_shipping": "4.95"})
    # Klant betaalt € 4,95 verzending: productprijs daalt, totaal blijft gelijk; verkoper betaalt nog steeds verzending.
    assert r["advice"]["selling"] == 3761 and r["advice"]["total"] == 4256 and r["used"]["shipping"] == 495
    with pytest.raises(ValueError):
        unified_margin({"purchase_cost": "1", "target_margin": "15", "shipping_choice": "free", "customer_shipping": "500"})


def test_new_layout_on_both_pages(administrator):
    for section in ("onderzoek", "calculator"):
        html = administrator.get(f"/dashboard?section={section}").get_data(as_text=True)
        assert 'name="shipping_choice"' in html and "Geen verzendkosten voor mij (€ 0)" in html
        assert "Kosten en berekening bekijken" in html and "Uitgebreide rekentabel" in html
        assert 'name="customer_shipping"' in html
