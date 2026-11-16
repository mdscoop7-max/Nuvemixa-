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


def automatic_margin(purchase_price, vat_rate="21"):
    """Illustrative Dutch sales-price scenario from one VAT-exclusive purchase price.

    Defaults are assumptions, not verified supplier quotes or tax advice.
    """
    purchase = _amount(purchase_price, "inkoopprijs")
    if purchase == 0:
        raise ValueError("Vul een inkoopprijs groter dan € 0 in.")
    vat = _amount(vat_rate, "btw")
    if vat > 100:
        raise ValueError("Btw-percentage buiten bereik.")
    shipping = Decimal("4.95")
    advertising = Decimal("3.00")
    returns = Decimal("1.00")
    transaction_fixed = Decimal("0.35")
    transaction_pct = Decimal("0.025")
    target_margin = Decimal("0.25")
    factor = Decimal("1") + vat / 100
    denominator = (Decimal("1") - target_margin) / factor - transaction_pct
    selling = ((purchase + shipping + advertising + returns + transaction_fixed) / denominator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = transaction_fixed + selling * transaction_pct
    revenue = selling / factor
    total_cost = purchase + shipping + advertising + returns + fee
    profit = revenue - total_cost
    q = lambda v: str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "purchase": q(purchase), "selling": q(selling), "vat": q(selling-revenue),
        "revenue_ex_vat": q(revenue), "shipping": q(shipping),
        "advertising": q(advertising), "returns": q(returns),
        "platform": q(fee), "total_cost": q(total_cost),
        "profit": q(profit), "margin_pct": q(profit / revenue * 100),
        "vat_rate": q(vat),
        "assumptions": "Indicatief Nederlands scenario: inkoop exclusief btw; 21% btw, € 4,95 verzending, € 3,00 reclame, € 1,00 retourreserve en € 0,35 + 2,5% transactiekosten. Verkoopadvies gebaseerd op circa 25% marge op omzet excl. btw. Geen geverifieerde marktprijs, leverancierskosten of belastingadvies."
    }
