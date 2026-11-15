"""Evidence-based dropshipping comparison within a product dossier."""
import json
import os
import re
import time
import urllib.request
from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit

from flask import abort, current_app, flash, redirect, request, session, url_for

from nv_dashboard_manager import bp, coupon_today
from nv_permissions import allowed
from nuvemixa_admin_store import connect
from nv_product_dossier import (MARKETS, STORAGE_ERRORS, SUPPLIER_KINDS, amount,
                                candidate_exists, dossier_connection, financials, source)

EU = frozenset("AT BE BG HR CY CZ DE DK EE ES FI FR GR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())
EU_SEARCH_ORDER = ("NL", "BE", "DE", "FR", "ES", "PL")
COUNTRY_CODE = re.compile(r"[A-Z]{2}")
IDENTIFIERS = {"sku": "SKU", "gtin": "GTIN", "model": "Merk en model", "features": "Gecontroleerde kenmerken"}
POINTS = {"delivery": ("Levertijd en magazijn", 30), "margin": ("Kosten en marge", 25),
          "reliability": ("Betrouwbaarheid en bedrijf", 20), "product": ("Voorraad en kwaliteit", 15),
          "returns": ("Retouren en service", 10)}
DIRECTORIES = (
    ("NL", "dropXL B2B", "https://www.dropxl.com/nl/faq.html", "Wonen, tuin en andere categorieën. Vraag het verzendmagazijn en de route per SKU op."),
    ("BE", "Versa Group", "https://www.versagroup.be/media/e7/d3/cd/1777535262/202605-design-catalog.pdf", "Sanitair en inrichting. De catalogus noemt rechtstreekse verzending; vraag het magazijn en de bezorgtijd op."),
    ("DE", "Sirocco", "https://sirocco.de/dropshipping/", "Groothandel voor tuin, gereedschap en andere artikelen. Meldt dropshipping vanuit Kleve; vraag de voorwaarden per bestemming op."),
    ("FR", "JG Distribution", "https://jgdistribution.fr/programme", "Franse B2B-bron voor gadgets en speelgoed; vraag bezorgtijd en retourroute per land op."),
    ("ES", "BigBuy", "https://www.bigbuy.eu/public/doc/Guia_API_BigBuy_EN.pdf", "B2B-catalogus en leveranciers-API. Bevestig magazijn, kosten en levering per SKU."),
    ("PL", "Ikonka", "https://www.ikonka.eu/en/shipping-costs", "Poolse groothandel. Controleer de afspraken over eigen verzendlabels en de voorwaarden per bestemming."),
    ("EE", "Hertwill", "https://hertwill.com/for-brands", "Platform met verschillende merken. Controleer per merk het verzendmagazijn, de bestemming en de voorraad."),
    ("GB", "Avasam", "https://www.avasam.com/dropship-suppliers/", "Platform voor Britse B2B-leveranciers. Verifieer de leverende partij en route."),
    ("INT", "CJdropshipping", "https://www.cjdropshipping.com/help-center", "Sourcing en fulfilment via meerdere magazijnen. Vraag welk magazijn de exacte SKU levert."),
)
TEXT_FIELDS = {"name": "Leverancier", "manufacturer": "Fabrikant of officiële distributeur",
               "company_country": "Bedrijfsland (landcode)", "warehouse_country": "Verzendland magazijn (landcode)",
               "warehouse_location": "Werkelijke magazijnlocatie (stad of adres)",
               "match_value": "SKU, GTIN, merk/model of onderscheidende kenmerken",
               "return_country": "Retourland (landcode)", "return_address": "Retouradres of bevestigde retourinstructie"}
LINKS = {"offer_url": "SKU / offerte, prijzen en voorraad", "warehouse_url": "Verzendlocatie en levertijden",
         "business_url": "Bedrijfsverificatie / officiële distributie", "safety_url": "Productveiligheid",
         "history_url": "Eerdere leveringen", "returns_url": "Retourvoorwaarden en service"}
NUMBERS = {"processing": "Verwerking (werkdagen)", "transport": "Transport (werkdagen)",
           "on_time": "Eerdere leveringen op tijd", "deliveries": "Aantal gemeten leveringen"}
COSTS = {"buy": "Inkoopprijs", "shipping": "Verzendkosten", "duty": "Invoer en overige leverancierskosten"}
CONFIRMATIONS = {"exact_match": "Het betreft hetzelfde product", "dropship": "Verzendt rechtstreeks aan de klant",
                 "safe": "Productveiligheid gecontroleerd voor deze markt", "stock": "Voorraad in dit magazijn bevestigd",
                 "tracking": "Track-and-trace bevestigd", "quality": "Productkwaliteit gecontroleerd",
                 "service": "Klantenservice gecontroleerd"}
TABLE = "supplier_comparisons"


def shipping_band(days):
    if days is None:
        return "Onbekend"
    if days <= 3:
        return "Uitstekend"
    if days <= 5:
        return "Goed"
    if days <= 7:
        return "Alleen bij voldoende voordeel"
    return "Lage prioriteit"


def actual_region(offer, market):
    ship = offer.get("warehouse_country")
    if not (ship and offer.get("warehouse_location") and offer.get("warehouse_url")):
        return 0
    if market in EU:
        return 8 if ship in EU else 0
    if ship == market:
        return 8
    neighbours = ({"US", "CA"}, {"AU", "NZ"}, {"GB", "IE"})
    return 4 if any({market, ship} <= group for group in neighbours) else 0


def assess(offer, market, dossier):
    processing, transport = offer.get("processing"), offer.get("transport")
    days = processing + transport if processing is not None and transport is not None else None
    warehouse_proven = bool(offer.get("warehouse_url") and offer.get("warehouse_country")
                            and offer.get("warehouse_location"))
    region = actual_region(offer, market)
    delivery = (22 if days <= 3 else 17 if days <= 5 else 9 if days <= 7 else 0) if days is not None and warehouse_proven else 0
    supplied = all(offer.get(key, "") != "" for key in COSTS)
    total = sum((Decimal(offer[k]) for k in COSTS), Decimal(0)) if supplied else None
    result = financials(dossier | {key: offer[key] for key in COSTS}) if supplied else None
    contribution = (result["contribution"] / result["net_sales"] * 100) if result else None
    margin = min(25, max(0, round(contribution * 25 / 30))) if contribution is not None else 0
    observed = offer.get("deliveries") or 0
    delivery_history = Decimal(offer.get("on_time") or 0) / observed if observed and offer.get("history_url") else None
    history = round(delivery_history * min(observed, 10) * Decimal("0.6")) if delivery_history is not None else 0
    tracked = bool(offer.get("tracking") and warehouse_proven)
    local_returns = bool(offer.get("returns_url") and offer.get("return_address")
                         and (offer.get("return_country") in EU if market in EU else offer.get("return_country") == market))
    business = bool(offer.get("company_country") and offer.get("business_url"))
    stock = bool(offer.get("stock") and warehouse_proven and offer.get("offer_url"))
    points = {
        "delivery": delivery + region,
        "margin": margin,
        "reliability": 10 * business + 4 * tracked + history,
        "product": 8 * stock + 7 * bool(offer.get("quality") and offer.get("safety_url")),
        "returns": 6 * local_returns + 4 * bool(offer.get("service") and offer.get("returns_url")),
    }
    blockers = []
    gates = (
        ("Verkopersrol", offer.get("kind") in SUPPLIER_KINDS and offer.get("kind") != "retailer"),
        ("Bevestigde SKU of productmatch", offer.get("exact_match") and offer.get("offer_url")),
        ("Rechtstreekse dropshipping", offer.get("dropship") and offer.get("offer_url")),
        ("Productveiligheid", offer.get("safe") and offer.get("safety_url")),
        ("Bedrijfsverificatie", business),
        ("Werkelijke verzendlocatie", warehouse_proven),
        ("Voorraad", stock),
        ("Verwerkingstijd en transport", days is not None),
        ("Inkoop, verzending en overige leverancierskosten", supplied),
    )
    blockers.extend(label for label, confirmed in gates if not confirmed)
    return dict(offer, days=days, band=shipping_band(days), region=region, points=points,
                score=sum(points.values()), ready=not blockers, blockers=blockers, total=total,
                contribution=contribution, financials=result, local_returns=local_returns, tracking=tracked,
                delivery_history=delivery_history)


def rank_offers(records, market, dossier):
    rows = [assess(record, market, dossier) for record in records]
    if market in EU:
        eu_ready = [row for row in rows if row["ready"] and row["region"] == 8]
        for row in rows:
            row["better_than_eu"] = bool(row["ready"] and not row["region"] and eu_ready
                and row["contribution"] is not None and row["local_returns"] and row["tracking"]
                and row["delivery_history"] is not None
                and all(other["contribution"] is not None and other["delivery_history"] is not None
                        and row["days"] <= other["days"] and row["total"] < other["total"]
                        and row["contribution"] > other["contribution"]
                        and row["delivery_history"] >= other["delivery_history"] for other in eu_ready))
    return sorted(rows, key=lambda row: (not row["ready"], -bool(row.get("better_than_eu")), -row["region"],
                                         -row["score"], row["days"] if row["days"] is not None else 999,
                                         row["name"].casefold()))


def directories(market):
    order = EU_SEARCH_ORDER if market in EU else (market,)
    return sorted(DIRECTORIES, key=lambda row: (order.index(row[0]) if row[0] in order else len(order),
                                               row[0] not in EU if market in EU else row[0] not in {market, "INT"}))


def comparison_view(candidate, market, dossier):
    try:
        with dossier_connection(TABLE) as (db, table, mark):
            records = db.execute(f"SELECT payload FROM {table} WHERE candidate_id={mark} AND market={mark}",
                                 (candidate, market)).fetchall()
        offers = rank_offers([json.loads(row[0]) for row in records], market, dossier)
    except STORAGE_ERRORS:
        return {"error": True}
    return {"offers": offers, "qualified": sum(row["ready"] for row in offers), "points": POINTS,
            "sources": LINKS, "directories": directories(market), "identifiers": IDENTIFIERS,
            "text_fields": TEXT_FIELDS, "costs": COSTS, "numbers": NUMBERS, "flags": CONFIRMATIONS,
            "ai": search_configured()}


def parse_comparison(form):
    data = {key: form.get(key, "").strip()[:200] for key in TEXT_FIELDS}
    data["kind"] = form.get("kind", "")
    data["identifier"] = form.get("identifier", "")
    if not data["name"] or data["kind"] not in SUPPLIER_KINDS or data["identifier"] not in IDENTIFIERS:
        raise ValueError("Kies een leverancier, rol en manier om het product te herkennen.")
    for key in ("company_country", "warehouse_country", "return_country"):
        data[key] = data[key].upper()
        if data[key] and not COUNTRY_CODE.fullmatch(data[key]):
            raise ValueError("Gebruik een tweeletterige landcode.")
    data.update({key: source(form.get(key, "")) for key in LINKS})
    data["checked"] = form.get("checked", "")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data["checked"]) or data["checked"] > coupon_today():
        raise ValueError("Vul een geldige controledatum in.")
    date.fromisoformat(data["checked"])
    for key in NUMBERS:
        raw = form.get(key, "")
        if raw and not re.fullmatch(r"[0-9]{1,4}", raw):
            raise ValueError("Gebruik hele, niet-negatieve waarden bij de levertijd en leverhistorie.")
        data[key] = int(raw) if raw else None
    if (data["on_time"] is None) != (data["deliveries"] is None) or (data["on_time"] or 0) > (data["deliveries"] or 0):
        raise ValueError("Controleer de aantallen voor de leverhistorie.")
    data.update({key: amount(form.get(key, "")) for key in COSTS})
    data.update({key: form.get(key) == "1" for key in CONFIRMATIONS})
    if data["exact_match"] and not data["match_value"]:
        raise ValueError("Vul het productkenmerk in waarop de match is gebaseerd.")
    return data


@bp.post("/dashboard/viral/supplier")
def save_supplier_comparison():
    if not allowed("research"):
        abort(403)
    candidate = request.form.get("candidate", type=int)
    market = request.form.get("market")
    if not candidate or market not in MARKETS:
        abort(404)
    try:
        if not candidate_exists(candidate):
            abort(404)
        offer = parse_comparison(request.form)
        with dossier_connection(TABLE) as (db, table, mark):
            action = ("DO UPDATE SET payload=excluded.payload"
                      if request.form.get("replace_existing") == "1" else "DO NOTHING")
            saved = db.execute(f"INSERT INTO {table}(candidate_id, market, supplier_key, payload) "
                               f"VALUES ({mark},{mark},{mark},{mark}) "
                               f"ON CONFLICT(candidate_id,market,supplier_key) {action}",
                               (candidate, market, offer["name"].casefold(), json.dumps(offer, ensure_ascii=False)))
            if saved.rowcount != 1:
                raise ValueError("Dit aanbod bestaat al. Bevestig vervanging om de bestaande gegevens te wijzigen.")
    except ValueError as exc:
        flash(str(exc), "error")
    except STORAGE_ERRORS:
        current_app.logger.error("Leveranciersvergelijking kon niet worden opgeslagen")
        flash("Leveranciersvergelijking tijdelijk niet beschikbaar.", "error")
    else:
        flash("Leveranciersvergelijking opgeslagen.", "success")
    return redirect(url_for("control", section="viral", detail=candidate, offer_market=market), code=303)


def search_configured():
    return bool(os.getenv("NUVEMIXA_SUPPLIER_SEARCH_MODEL", "").strip()
                and os.getenv("OPENAI_API_KEY", "").strip())


def search_supplier_sources(title, identifier, market, *, international=False):
    selected = directories(market)
    domains = [urlsplit(row[2]).hostname.removeprefix("www.") for row in selected]
    # The public B2B shortlist deliberately excludes consumer retailers.
    if market in EU and not international:
        domains = [domain for domain in domains if domain not in {"avasam.com", "cjdropshipping.com"}]
    order = "NL, BE, DE, then FR, ES, PL and other EU warehouses" if market in EU else f"{market} warehouses first, then nearby dispatch countries"
    data = {
        "model": os.environ["NUVEMIXA_SUPPLIER_SEARCH_MODEL"].strip(),
        "store": False,
        "max_tool_calls": 3,
        "max_output_tokens": 450,
        "tools": [{"type": "web_search", "filters": {"allowed_domains": domains}, "search_context_size": "low"}],
        "tool_choice": {"type": "web_search"},
        "instructions": ("Find B2B product or sourcing leads in priority order for the supplied market. "
                         f"Search {order}. Distinguish company address from warehouse. Use at most three distinct "
                         "cited vendor pages. Cite only relevant supplier research leads. "
                         "Never treat a supplier or a product match as verified, never provide price or stock assertions."),
        "input": json.dumps({"public_product_title": title, "public_sku_gtin_or_model": identifier,
                             "destination": market}, ensure_ascii=False),
    }
    query = urllib.request.Request("https://api.openai.com/v1/responses", method="POST",
                                   headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"].strip(),
                                            "Content-Type": "application/json"},
                                   data=json.dumps(data).encode())
    with urllib.request.urlopen(query, timeout=12) as reply:
        response = json.loads(reply.read(120_000))
    result = {}
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for message in item.get("content", []):
            if message.get("type") != "output_text":
                continue
            for ref in message.get("annotations", []):
                if ref.get("type") != "url_citation":
                    continue
                try:
                    url = source(ref.get("url", ""))
                    parsed = urlsplit(url)
                except (ValueError, AttributeError):
                    continue
                host = parsed.hostname or ""
                domain = next((domain for domain in domains if host == domain or host.endswith("." + domain)), None)
                if domain and len(url) <= 240 and not parsed.query and not parsed.fragment:
                    result.setdefault(domain, {"href": url, "name": domain})
    return [result[key] for key in domains if key in result][:3]


@bp.post("/dashboard/viral/supplier-search")
def supplier_search():
    if not allowed("research"):
        abort(403)
    market = request.form.get("market")
    candidate = request.form.get("candidate", type=int)
    if not candidate or market not in MARKETS:
        abort(400)
    destination = url_for("control", section="viral", detail=candidate, offer_market=market)
    identifier = request.form.get("identifier", "").strip()[:120]
    if not search_configured():
        flash("Optionele AI-zoektoegang is niet ingesteld. Gebruik de B2B-bronnen en bewaar gevonden offertes.", "error")
        return redirect(destination, code=303)
    now = time.time()
    if now - session.get("nv_supplier_search_at", 0) < 30:
        flash("Wacht even voordat je opnieuw zoekt.", "error")
        return redirect(destination, code=303)
    try:
        with connect() as db:
            row = db.execute("SELECT title FROM viral_candidates WHERE id=?", (candidate,)).fetchone()
        if row is None:
            abort(404)
        if "@" in (row["title"] + identifier):
            raise ValueError("Gebruik uitsluitend openbare productkenmerken.")
        session["nv_supplier_search_at"] = now
        links = search_supplier_sources(row["title"], identifier, market,
                                        international=request.form.get("international") == "1")
    except (TypeError, AttributeError, *STORAGE_ERRORS):
        current_app.logger.warning("AI-leverancierszoekopdracht tijdelijk niet beschikbaar")
        flash("AI-zoekopdracht niet beschikbaar. Gebruik de B2B-bronnen hieronder.", "error")
    else:
        if links:
            flash(links, "supplier_sources")
        else:
            flash("Geen controleerbare B2B-bron gevonden voor deze zoekopdracht.", "error")
    return redirect(destination, code=303)
