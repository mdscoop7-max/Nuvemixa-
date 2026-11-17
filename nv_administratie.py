"""Administratie-overzicht: rekent met testgegevens en toont echte orders apart.

Er worden geen verzonnen cijfers als echt getoond. Alles uit TEST_* is testdata en
wordt in de weergave altijd als zodanig gelabeld. Echte WooCommerce-orders komen
alleen-lezen binnen via ``real_orders`` en bevatten geen klantgegevens.
"""
from decimal import Decimal, ROUND_HALF_UP

BTW = Decimal("0.21")
PAID_STATUSES = {"processing", "completed"}
STATUS_LABELS = {
    "pending": "In afwachting van betaling", "processing": "Betaald, in behandeling",
    "on-hold": "In de wacht", "completed": "Betaald en afgerond",
    "cancelled": "Geannuleerd", "refunded": "Terugbetaald", "failed": "Betaling mislukt",
}
# Testproducten: bedragen in centen, verkoopprijs inclusief btw.
TEST_PRODUCTS = {
    "TEST-A": {"naam": "Testproduct A", "inkoop": 1250, "verkoop": 2999},
    "TEST-B": {"naam": "Testproduct B", "inkoop": 800, "verkoop": 1999},
    "TEST-C": {"naam": "Testproduct C", "inkoop": 4100, "verkoop": 6995},
}
TEST_ORDERS = [
    {"id": "T-1001", "status": "completed", "regels": [("TEST-A", 2)]},
    {"id": "T-1002", "status": "processing", "regels": [("TEST-B", 1), ("TEST-C", 1)]},
    {"id": "T-1003", "status": "pending", "regels": [("TEST-A", 1)]},
    {"id": "T-1004", "status": "refunded", "regels": [("TEST-C", 1)]},
]
TEST_KOSTEN = {"verzendkosten_per_order": 495, "betaalkosten_procent": Decimal("1.9"), "advertenties": 1500}


def euro(cents):
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(int(cents)), 100)
    return f"{sign}€{whole:,}".replace(",", ".") + f",{rest:02d}"


def _ex_btw(incl):
    return int((Decimal(incl) / (1 + BTW)).quantize(Decimal("1"), ROUND_HALF_UP))


def test_overview():
    """Testdata: omzet, kosten, winst en marge per product (alleen betaalde orders tellen)."""
    products = {sku: dict(p, aantal=0, omzet=0, inkoopkosten=0) for sku, p in TEST_PRODUCTS.items()}
    orders, paid_orders = [], 0
    for order in TEST_ORDERS:
        total = sum(TEST_PRODUCTS[sku]["verkoop"] * qty for sku, qty in order["regels"])
        paid = order["status"] in PAID_STATUSES
        if paid:
            paid_orders += 1
            for sku, qty in order["regels"]:
                products[sku]["aantal"] += qty
                products[sku]["omzet"] += _ex_btw(TEST_PRODUCTS[sku]["verkoop"] * qty)
                products[sku]["inkoopkosten"] += TEST_PRODUCTS[sku]["inkoop"] * qty
        orders.append({"id": order["id"], "status": STATUS_LABELS[order["status"]], "betaald": paid,
                       "totaal": total, "btw": total - _ex_btw(total)})
    rows = []
    for sku, p in products.items():
        winst = p["omzet"] - p["inkoopkosten"]
        rows.append({"sku": sku, **p, "winst": winst,
                     "marge": (Decimal(winst) * 100 / p["omzet"]).quantize(Decimal("0.1")) if p["omzet"] else None})
    omzet = sum(r["omzet"] for r in rows)
    inkoop = sum(r["inkoopkosten"] for r in rows)
    verzend = TEST_KOSTEN["verzendkosten_per_order"] * paid_orders
    paid_total = sum(o["totaal"] for o in orders if o["betaald"])
    betaal = int((Decimal(paid_total) * TEST_KOSTEN["betaalkosten_procent"] / 100).quantize(Decimal("1"), ROUND_HALF_UP))
    kosten = inkoop + verzend + betaal + TEST_KOSTEN["advertenties"]
    netto = omzet - kosten
    return {
        "producten": rows, "orders": orders, "omzet": omzet, "inkoop": inkoop, "verzend": verzend,
        "betaalkosten": betaal, "advertenties": TEST_KOSTEN["advertenties"], "kosten": kosten, "winst": netto,
        "marge": (Decimal(netto) * 100 / omzet).quantize(Decimal("0.1")) if omzet else None,
        "btw_af_te_dragen": sum(o["btw"] for o in orders if o["betaald"]),
    }


def real_orders(order_rows):
    """Echte (alleen-lezen) orders uit WooCommerce samenvatten; zonder klantgegevens."""
    if order_rows is None:
        return None
    per_status = {}
    for row in order_rows:
        per_status[row.get("status")] = per_status.get(row.get("status"), 0) + 1
    return {
        "aantal": len(order_rows),
        "statussen": [{"status": STATUS_LABELS.get(k, str(k)), "aantal": v} for k, v in sorted(per_status.items(), key=lambda i: str(i[0]))],
        "rows": [{"id": r.get("id"), "datum": r.get("date"), "status": STATUS_LABELS.get(r.get("status"), r.get("status")),
                  "totaal": f"{r.get('currency', '')} {r.get('total', '')}".strip()} for r in order_rows],
    }
