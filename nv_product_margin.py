"""Transparent scenario calculations for AI Productonderzoek.

All amounts are user-provided EUR inputs, not supplier quotes or verified VAT advice.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

REQUIRED = ("selling_price", "purchase_cost")
COST_FIELDS = {
    "shipping_cost": "Verzending",
    "advertising_cost": "Advertenties",
    "transaction_fee": "Transactiekosten",
    "platform_fee": "Platformkosten",
    "returns_reserve": "Retourreserve",
    "other_cost": "Invoer en afhandeling",
}
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
    amounts = {name: _amount(data.get(name, ""), name) for name in REQUIRED}
    entered = {key: _amount(data[key], label) for key, label in COST_FIELDS.items()
               if str(data.get(key, "")).strip()}
    vat = _amount(data.get("vat_rate", ""), "vat_rate")
    if vat > 100:
        raise ValueError("Btw-percentage moet tussen 0 en 100 liggen")
    selling = amounts["selling_price"]
    revenue_ex_vat = selling / (Decimal("1") + vat / Decimal("100"))
    gross_profit = revenue_ex_vat - amounts["purchase_cost"]
    costs = amounts["purchase_cost"] + sum(entered.values(), Decimal("0"))
    profit = revenue_ex_vat - costs
    margin = (profit / revenue_ex_vat * 100) if revenue_ex_vat else Decimal("0")
    q = lambda n: str(n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "revenue_ex_vat": q(revenue_ex_vat),
        "total_cost": q(costs),
        "profit": q(profit),
        "margin_pct": q(margin),
        "vat_amount": q(selling - revenue_ex_vat),
        "gross_profit": q(gross_profit),
        "gross_margin_pct": q(gross_profit / revenue_ex_vat * 100) if revenue_ex_vat else None,
        "purchase": q(amounts["purchase_cost"]),
        "entered_costs": [(COST_FIELDS[key], q(amount)) for key, amount in entered.items()],
        "missing_costs": [label for key, label in COST_FIELDS.items() if key not in entered],
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


# ---------------------------------------------------------------------------
# Gedeelde rekenmodule voor 'Winstmarge per product' en 'Prijs & marge calculator'.
# Exacte tegenhanger van static/nv-margin-core.js (zelfde floatberekening en afronding, getest op pariteit).
# ---------------------------------------------------------------------------
import math

UNIFIED_COSTS = (
    ("shipping", "shipping_cost", "std_shipping", "Verzend- en fulfilmentkosten"),
    ("advertising", "advertising_cost", "std_advertising", "Advertentiekosten"),
    ("returns", "returns_reserve", "std_returns", "Retourkosten"),
    ("fee_fixed", "transaction_fee", "std_fee_fixed", "Betaalprovider vast"),
    ("fee_pct", "transaction_pct", "std_fee_pct", "Betaalprovider %"),
    ("platform", "platform_fee", "std_platform", "Platformkosten"),
    ("other", "other_cost", "std_other", "Invoer- en overige kosten"),
)
UNIFIED_DEFAULTS = {"shipping": 495, "advertising": 300, "returns": 100, "fee_fixed": 35, "fee_pct": 2.5,
                    "platform": 0, "other": 0}
MARGIN_TARGETS = (15, 20, 25, 30, 35, 40)


def _round_half_up(value):
    return math.copysign(math.floor(abs(value) + 1e-9 + 0.5), value) if value else 0


def _field(data, name, *, percent=False, limit=None):
    raw = str(data.get(name, "") or "").strip()
    if not raw:
        return None
    value = _amount(raw, name)
    if limit is not None and value > limit:
        raise ValueError("Waarde buiten bereik bij " + name)
    return float(value) if percent else int(_round_half_up(float(value) * 100))


def _figures(selling, purchase, used, factor):
    fee = used["fee_fixed"] + selling * used["fee_pct"] / 100
    revenue = selling / factor
    costs = purchase + used["shipping"] + used["advertising"] + used["returns"] + used["platform"] + used["other"] + fee
    profit = revenue - costs
    return {"selling": int(_round_half_up(selling)), "revenue": int(_round_half_up(revenue)),
            "vat": int(_round_half_up(selling - revenue)), "fee": int(_round_half_up(fee)),
            "costs": int(_round_half_up(costs)), "gross": int(_round_half_up(revenue - purchase)),
            "profit": int(_round_half_up(profit)),
            "gross_pct": 100 * (revenue - purchase) / revenue if revenue else 0,
            "margin": 100 * profit / revenue if revenue else 0}


def unified_margin(data):
    """Zelfde regels als NVMargin.compute. Lege werkelijke kosten = onbekend → zichtbare standaardaanname."""
    purchase = _field(data, "purchase_cost")
    if not purchase:
        raise ValueError("Vul een inkoopprijs groter dan € 0 in.")
    vat = _field(data, "vat_rate", percent=True, limit=100)
    vat = 21.0 if vat is None else vat
    try:
        target = float(str(data.get("target_margin", "25") or "25").replace(",", "."))
    except ValueError:
        raise ValueError("Kies een geldige winstmarge.") from None
    if not 0 <= target < 100:
        raise ValueError("Kies een geldige winstmarge.")
    used, sources, assumed = {}, {}, []
    for key, actual_name, standard_name, label in UNIFIED_COSTS:
        pct = key == "fee_pct"
        actual = _field(data, actual_name, percent=pct, limit=99.99 if pct else None)
        standard = _field(data, standard_name, percent=pct, limit=99.99 if pct else None)
        standard = UNIFIED_DEFAULTS[key] if standard is None else standard
        if actual is None:
            used[key], sources[key] = standard, "aanname"
            assumed.append(label)
        else:
            used[key], sources[key] = actual, ("nul" if actual == 0 else "ingevuld")
    factor = 1 + vat / 100
    denominator = (1 - target / 100) / factor - used["fee_pct"] / 100
    if denominator <= 0:
        raise ValueError("Deze marge is met deze betaalkosten en btw niet haalbaar.")
    fixed = (purchase + used["shipping"] + used["advertising"] + used["returns"] + used["platform"]
             + used["other"] + used["fee_fixed"])
    advice = _figures(_round_half_up(fixed / denominator), purchase, used, factor)
    result = {"kind": "A" if assumed else "B", "assumed": assumed, "used": used, "sources": sources,
              "purchase": purchase, "vat": vat, "target": target, "advice": advice, "own": None}
    own = _field(data, "selling_price")
    if own:
        figures = _figures(own, purchase, used, factor)
        figures["reaches"] = own >= advice["selling"]
        figures["short"] = max(0, advice["selling"] - own)
        result["own"] = figures
    return result
