"""Transparent scenario calculations for AI Productonderzoek.

All amounts are user-provided EUR inputs, not supplier quotes or verified VAT advice.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

FIELDS = ("selling_price", "purchase_cost", "shipping_cost", "advertising_cost", "platform_fee", "returns_reserve", "other_cost")
MAX_AMOUNT = Decimal("1000000")


def _amount(raw, name):
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Vul een geldig bedrag in bij " + name) from None
    if not value.is_finite() or value < 0 or value > MAX_AMOUNT or value.as_tuple().exponent < -2:
        raise ValueError("Bedrag buiten toegestaan bereik bij " + name)
    return value


def calculate_margin(data):
    """Returns deterministic scenario totals. VAT is an explicit user input.

    The selling price includes VAT. Costs are assumed VAT-exclusive; input tax,
    customs and cross-border tax rules are NOT calculated.
    """
    amounts = {name: _amount(data.get(name, ""), name) for name in FIELDS}
    vat = _amount(data.get("vat_rate", ""), "vat_rate")
    if vat > 100:
        raise ValueError("Btw-percentage moet tussen 0 en 100 liggen")
    selling = amounts["selling_price"]
    revenue_ex_vat = selling / (Decimal("1") + vat / Decimal("100"))
    costs = sum((amounts[key] for key in FIELDS if key != "selling_price"), Decimal("0"))
    profit = revenue_ex_vat - costs
    margin = (profit / revenue_ex_vat * 100) if revenue_ex_vat else Decimal("0")
    q = lambda n: str(n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "revenue_ex_vat": q(revenue_ex_vat),
        "total_cost": q(costs),
        "profit": q(profit),
        "margin_pct": q(margin),
        "vat_amount": q(selling - revenue_ex_vat),
        "assumptions": "Scenario, geen geverifieerde marktdata. Verkoopprijs inclusief btw; kosten exclusief btw. Geen berekening van voorbelasting, invoerrechten of landspecifieke btw-regels.",
    }
