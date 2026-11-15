"""Market offers and supporting evidence for existing Viral Product Finder candidates."""
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit

import psycopg
from flask import abort, current_app, flash, redirect, request, url_for

import nv_dashboard_postgres
from nuvemixa_admin_store import connect
from nv_dashboard_manager import bp, coupon_today
from nv_merchant_audit import product_issues
from nv_permissions import allowed

MARKETS = {
    "NL": ("Nederland", "EUR", "NUVEMIXA.nl"), "BE": ("België", "EUR", "NUVEMIXA.nl"),
    "DE": ("Duitsland", "EUR", "NUVEMIXA.nl"), "FR": ("Frankrijk", "EUR", "NUVEMIXA.nl"),
    "ES": ("Spanje", "EUR", "NUVEMIXA.nl"), "GB": ("Verenigd Koninkrijk", "GBP", "NUVEMIXA.com"),
    "US": ("Verenigde Staten", "USD", "NUVEMIXA.com"), "CA": ("Canada", "CAD", "NUVEMIXA.com"),
    "AU": ("Australië", "AUD", "NUVEMIXA.com"),
}
FIELDS = {
    "gross": "Verkoopprijs inclusief belasting", "tax": "Af te dragen belasting per order",
    "buy": "Inkoop in verkoopvaluta", "shipping": "Verzending", "duty": "Invoer en overige belastingen",
    "payment": "Betaal- en platformkosten", "returns": "Verwachte retourkosten",
    "warranty": "Verwachte garantie- en defectkosten", "fx": "Valutabuffer",
    "other": "Overige variabele kosten", "ads": "Advertentiekosten per order",
    "fixed": "Toegerekende vaste kosten per order", "stress": "Extra kosten in tegenvallend scenario",
}
STAGES = ("Signaal", "Vraag bevestigd", "Leverancier bevestigd", "Proefbestelling geslaagd", "Klaar voor Merchant")
PROOFS = {
    "demand": "Vraagbron", "offer": "Schriftelijke offerte", "trial": "Bewijs proefbestelling",
    "exchange": "Wisselkoersbron",
}
SUPPLIER_KINDS = {"manufacturer": "Fabrikant", "distributor": "Distributeur", "dropshipper": "Dropshipper", "retailer": "Prijsreferentie (retailer)"}
STORAGE_ERRORS = (sqlite3.Error, psycopg.Error, OSError, ValueError, RuntimeError)


def amount(value):
    value = value.strip().replace(",", ".")
    if not value:
        return ""
    if not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,6})?", value):
        raise ValueError("Gebruik een geldig, positief bedrag of nul.")
    return str(Decimal(value))


def source(value):
    value = value.strip()
    if value:
        url = urlsplit(value)
        if (len(value) > 450 or url.scheme != "https" or not url.hostname
                or url.username or url.password or any(ch.isspace() for ch in value) or chr(92) in value):
            raise ValueError("Gebruik een openbare HTTPS-bron.")
    return value


def financials(record):
    required = ("gross", "tax", "buy", "shipping", "duty", "payment", "returns", "warranty", "fx", "other", "ads")
    if any(record.get(key, "") == "" for key in required):
        return None
    numbers = {key: Decimal(record[key]) for key in required}
    gross, net = numbers["gross"], numbers["gross"] - numbers["tax"]
    if net <= 0:
        return None
    costs = sum(numbers[key] for key in ("buy", "shipping", "duty", "payment", "returns", "warranty", "fx", "other"))
    breakeven = net - costs
    contribution = breakeven - numbers["ads"]
    return {
        "net_sales": net, "contribution": contribution,
        "breakeven_cpa": breakeven if breakeven > 0 else None,
        "roas": gross / breakeven if breakeven > 0 else None,
        "net_margin": (100 * (contribution - Decimal(record["fixed"])) / net) if record.get("fixed") else None,
        "stress": contribution - Decimal(record["stress"]) if record.get("stress") else None,
    }


@contextmanager
def dossiers():
    if nv_dashboard_postgres.configured():
        with nv_dashboard_postgres.connect() as db:
            yield db, "nuvemixa_dashboard.product_dossier_offers", "%s"
    else:
        with connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS product_dossier_offers (
               candidate_id integer NOT NULL, market text NOT NULL, payload text NOT NULL,
               PRIMARY KEY(candidate_id, market))""")
            yield db, "product_dossier_offers", "?"


def dossier_stage(record, listed_product, currency):
    if not (record.get("demand_url") and record.get("demand_confirmed")):
        return 0
    if not (record.get("offer_url") and record.get("supplier_name")
            and record.get("supplier_kind") in SUPPLIER_KINDS and record["supplier_kind"] != "retailer"
            and record.get("dropship") and record.get("stock") in ("in_stock", "out_of_stock")
            and record.get("buy") and record.get("shipping") and record.get("delivery") and record.get("returns_terms")):
        return 1
    if not (record.get("trial_url") and record.get("trial_passed") and record.get("quality")):
        return 2
    if (not listed_product or not record.get("merchant_confirmed") or record["stock"] != "in_stock"
            or listed_product.get("stock_status") != record["stock"]
            or listed_product.get("currency", "EUR") != currency
            or Decimal(str(listed_product["price"])) != Decimal(record.get("gross") or "-1")
            or not financials(record)
            or product_issues(listed_product, current_app.static_folder)):
        return 3
    return 4


def dossier_view(candidate):
    market = request.args.get("offer_market", candidate["country"])
    market = market if market in MARKETS else "NL"
    listed_products = current_app.extensions["nuvemixa_catalog_api"][1]()
    products = {str(item["id"]): item for item in listed_products}
    try:
        with dossiers() as (db, table, mark):
            rows = db.execute(f"SELECT market, payload FROM {table} WHERE candidate_id={mark} ORDER BY market",
                              (candidate["id"],)).fetchall()
        offers = {row[0]: json.loads(row[1]) for row in rows}
    except STORAGE_ERRORS:
        return {"error": True, "market": market}
    current = offers.get(market, {})
    try:
        with connect() as db:
            suppliers = db.execute("SELECT id,name,status FROM suppliers ORDER BY name LIMIT 250").fetchall()
    except STORAGE_ERRORS:
        suppliers = []
    stage = dossier_stage(current, products.get(current.get("catalog_id")), MARKETS[market][1])
    return {"market": market, "markets": MARKETS, "market_info": MARKETS[market], "fields": FIELDS,
            "record": current, "offers": offers, "financials": financials(current), "stage": stage,
            "stages": STAGES, "sources": PROOFS, "types": SUPPLIER_KINDS, "products": products, "suppliers": suppliers}


@bp.post("/dashboard/viral/dossier")
def save_dossier():
    if not allowed("research"):
        abort(403)
    form = request.form
    candidate, market = form.get("candidate", type=int), form.get("market")
    if not candidate or market not in MARKETS:
        abort(400)
    try:
        supplier_id = form.get("supplier_id", type=int)
        with connect() as db:
            if not db.execute("SELECT 1 FROM viral_candidates WHERE id=?", (candidate,)).fetchone():
                abort(404)
            supplier = db.execute("SELECT id,name,status FROM suppliers WHERE id=?", (supplier_id,)).fetchone() if supplier_id else None
        if supplier_id and (not supplier or supplier["status"] == "afgekeurd"):
            raise ValueError("Kies een beschikbare leverancier.")
        record = {key: amount(form.get(key, "")) for key in FIELDS}
        for name in ("manufacturer", "supplier_name", "delivery", "returns_terms", "risks", "sku", "quality"):
            record[name] = form.get(name, "").strip()[:500]
        for key in PROOFS:
            url = source(form.get(key + "_url", ""))
            checked = form.get(key + "_date", "")
            if url and (not checked or date.fromisoformat(checked).isoformat() > coupon_today()):
                raise ValueError("Vul bij elke bron een geldige controledatum in.")
            record[key + "_url"], record[key + "_date"] = url, checked if url else ""
        for name, valid in (("stock", ("", "in_stock", "out_of_stock")), ("supplier_kind", ("", *SUPPLIER_KINDS))):
            record[name] = form.get(name, "")
            if record[name] not in valid:
                raise ValueError("Controleer de geselecteerde waarden.")
        record["supplier_id"] = supplier_id
        if supplier:
            record["supplier_name"] = supplier["name"]
        for flag in ("dropship", "merchant_confirmed", "demand_confirmed", "trial_passed"):
            record[flag] = form.get(flag) == "1"
        record["catalog_id"] = form.get("catalog_id", "")
        if record["catalog_id"] and not any(str(item["id"]) == record["catalog_id"]
                                            for item in current_app.extensions["nuvemixa_catalog_api"][1]()):
            raise ValueError("Kies een bestaand catalogusproduct.")
        original = amount(form.get("offer_amount", ""))
        rate = amount(form.get("exchange_rate", ""))
        currency = form.get("offer_currency", "").strip().upper()
        record.update(offer_amount=original, offer_currency=currency, exchange_rate=rate)
        if original:
            if not re.fullmatch(r"[A-Z]{3}", currency):
                raise ValueError("Gebruik een drieletterige valutacode bij de offerte.")
            if currency != MARKETS[market][1] and (not rate or Decimal(rate) <= 0 or not record["exchange_url"]):
                raise ValueError("Vul wisselkoers, bron en datum in bij een offerte in een andere valuta.")
            record["buy"] = str((Decimal(original) * (Decimal(rate) if currency != MARKETS[market][1] else 1))
                                .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        with dossiers() as (db, table, mark):
            db.execute(f"INSERT INTO {table} (candidate_id,market,payload) VALUES ({mark},{mark},{mark})"
                       " ON CONFLICT(candidate_id,market) DO UPDATE SET payload=excluded.payload",
                       (candidate, market, json.dumps(record, ensure_ascii=False)))
    except ValueError as exc:
        flash(str(exc), "error")
    except STORAGE_ERRORS:
        current_app.logger.error("Productdossier tijdelijk niet beschikbaar")
        flash("Productdossier kon niet worden opgeslagen.", "error")
    else:
        flash("Productdossier opgeslagen.", "success")
    return redirect(url_for("control", section="viral", detail=candidate, offer_market=market), code=303)
