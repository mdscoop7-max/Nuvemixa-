"""Prices and dated offers for dashboard-managed products."""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from zoneinfo import ZoneInfo

COSTS = ("cost_price", "shipping_cost", "packaging_cost", "payment_cost", "advertising_cost", "other_cost")
CENT = Decimal(".01")


def today():
    return datetime.now(ZoneInfo("Europe/Amsterdam")).date()


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def number(value, maximum=Decimal("9999999.99")):
    try:
        value = Decimal(str(value or 0).replace(",", "."))
        if not value.is_finite() or not 0 <= value <= maximum or value != money(value):
            raise ValueError
        return value
    except (ValueError, InvalidOperation):
        raise ValueError("Controleer de bedragen en percentages (maximaal twee decimalen).") from None


def price_fields(form, previous=None):
    costs = {key: number(form.get(key)) for key in COSTS}
    total = sum(costs.values())
    margin = number(form.get("margin"), Decimal("99.99"))
    vat = number(form.get("vat"))
    if vat not in (0, 9, 21):
        raise ValueError("Kies een geldig btw-tarief.")
    manual = form.get("price_mode") == "manual"
    net = money(total / (1 - margin / 100))
    previous = previous or {}
    # Opening an existing product or editing an offer must never change its regular price.
    recalculate = not previous or form.get("recalculate_price") == "1"
    gross = number(form.get("price")) if manual else (
        number(net + money(net * vat / 100)) if recalculate else number(previous.get("price")))
    return {**{k: str(v) for k, v in costs.items()}, "price": float(gross), "margin": str(margin),
            "vat": str(vat), "price_mode": "manual" if manual else "auto"}


def offer_fields(form, gross):
    enabled = form.get("offer_enabled") == "1"
    start, end = (form.get(key, "") for key in ("offer_start", "offer_end"))
    sale = number(form.get("sale_price"))
    try:
        for value in (start, end):
            if value:
                date.fromisoformat(value)
    except ValueError:
        raise ValueError("Controleer de actieperiode.") from None
    if enabled and (not start or not end or end < start):
        raise ValueError("Kies een start- en einddatum; de einddatum moet op of na de startdatum liggen.")
    if enabled and not 0 < sale < number(gross):
        raise ValueError(f"De actieprijs moet hoger zijn dan € 0 en lager dan de normale verkoopprijs (€ {number(gross):.2f}).")
    return dict(offer_enabled=enabled, offer_start=start, offer_end=end, sale_price=str(sale),
                offer_shop=form.get("offer_shop") == "1", offer_list=form.get("offer_list") == "1", offer_week=form.get("offer_week") == "1")


def record_prices(product, previous):
    """Record real publication intervals, including scheduled prices and periods of invisibility."""
    keys = ("hidden", "price", "offer_enabled", "offer_shop", "offer_start", "offer_end", "sale_price")
    history = list(previous.get("price_history", []))
    state = {k: product.get(k) for k in keys}
    if not history or any(history[-1].get(k) != state[k] for k in keys):
        history.append(dict(state, day=today().isoformat()))
    product["price_history"] = history


def active(row, day):
    return bool(row.get("offer_enabled") and row.get("offer_shop")
                and row.get("offer_start") and row.get("offer_end")
                and row["offer_start"] <= day <= row["offer_end"])


def public_price(product):
    day = today().isoformat()
    if not active(product, day):
        return dict(product, old_price=None, badge=None) if "offer_enabled" in product else product
    result = dict(product, price=float(product["sale_price"]), old_price=None, badge=None)
    start = date.fromisoformat(product["offer_start"])
    first = (start - timedelta(days=30)).isoformat()
    history = product.get("price_history", [])
    candidates = []
    for index, row in enumerate(history):
        left = max(row["day"], first)
        right = min(history[index + 1]["day"] if index + 1 < len(history) else day,
                    (start - timedelta(days=1)).isoformat())
        if right < left or row.get("hidden"):
            continue
        candidates.append(float(row["price"]))
        if row.get("offer_enabled") and row.get("offer_shop") and row["offer_start"] <= right and row["offer_end"] >= left:
            candidates.append(float(row["sale_price"]))
    if history and history[0]["day"] <= first and candidates and min(candidates) > result["price"]:
        result.update(old_price=min(candidates), badge="Aanbieding")
    return result
