"""Leveranciersdekking per categorie en doelland, met per bron hoe zoeken kan en wat het vraagt.

Alles in dit register komt uit onderzoek op 17-11-2026 in de officiële bronpagina's (zie `evidence`) of uit de
bestaande code. Bronnen waarvan de pagina niet gelezen kon worden, staan als `onderzocht=False`: daarvan is alleen
de omschrijving uit de code bekend. Er worden geen toegang, prijzen of catalogusgegevens verzonnen.

De handmatige bronnentest (POST) doet pas een aanroep na een klik van de eigenaar; pagina's openen doet nooit iets.
"""
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import abort, flash, redirect, request, url_for

from nv_dashboard_manager import admin, bp
from nv_permissions import allowed

CATEGORIES = ("gadgets", "beauty-care", "lifestyle-sport", "home-living", "smart-home")
EU = frozenset("NL BE DE FR ES IT PL AT PT IE SE DK FI CZ SK HU RO BG GR HR SI LT LV EE LU MT CY".split())
RESEARCHED = "17-11-2026"

# access: api | account | handmatig | openbaar
ACCESS_LABELS = {
    "api": "Officiële API (account of contract nodig)",
    "account": "Account nodig",
    "openbaar": "Openbare catalogus",
    "handmatig": "Alleen handmatige link",
}
TYPE_LABELS = {
    "merkwebshop": "Merkwebshop", "groothandel": "Groothandel", "dropship": "Dropshippingplatform",
    "marktplaats": "Marktplaats", "distributeur": "Distributeur",
}

# Bronnen die NUVEMIXA (nog) niet doorzoekt: alleen een link om zelf te onderzoeken.
LINK_SOURCES = (
    {"name": "BigBuy", "type": "dropship", "scope": "EU", "categories": ("all",), "access": "api", "onderzocht": True,
     "url": "https://www.bigbuy.eu/en/dropshipping-ecommerce.html",
     "facts": "Meer dan 200.000 producten, ruim 5.000 merken, voorraad in Europa (volgens BigBuy zelf).",
     "requirement": "Officiële REST-API (Bearer-sleutel). Sleutel via het BigBuy-paneel of contactformulier; vraagt een actief "
                    "Ecommerce-contract of hoger pack. Een gratis account toont prijzen.",
     "cost": "Prijs van het pack staat niet op de onderzochte pagina's.",
     "evidence": (("Dropshipping", "https://www.bigbuy.eu/en/dropshipping-ecommerce.html"),
                  ("API-toegang", "https://www.bigbuy.eu/academy/en/?p=620"),
                  ("API-gids", "https://www.bigbuy.eu/public/doc/Guia_API_BigBuy_EN.pdf"))},
    {"name": "CJdropshipping", "type": "dropship", "scope": "INT", "categories": ("all",), "access": "api",
     "onderzocht": True, "url": "https://developers.cjdropshipping.com/en/api/api2/api/product.html",
     "facts": "Categorieboom en zoeken op trefwoord en land via de API; voorraad per magazijn. Welke producten per categorie "
              "beschikbaar zijn, is niet gecontroleerd.",
     "requirement": "Officiële API: API-key uit een CJ-account, daarmee een toegangstoken (180 dagen). Endpoints o.a. "
                    "getCategory, listV2 (trefwoord, countryCode) en voorraad.",
     "cost": "Kosten van API-toegang staan niet in de documentatie.",
     "evidence": (("Authenticatie", "https://developers.cjdropshipping.com/en/api/api2/api/auth.html"),
                  ("Product-API", "https://developers.cjdropshipping.com/en/api/api2/api/product.html"))},
    {"name": "dropXL (vidaXL)", "type": "dropship", "scope": "EU", "categories": ("home-living",), "access": "account",
     "onderzocht": True, "url": "https://www.dropxl.com/nl/faq.html",
     "facts": "De code omschrijft wonen, tuin en andere categorieën; de categoriedekking is niet gecontroleerd.",
     "requirement": "Registratie via het dropXL-portaal; account geeft de volledige catalogus en een API-token.",
     "cost": "Maandelijkse platformkosten, direct door dropXL gefactureerd (bedrag niet gevonden).",
     "evidence": (("Hoe een dropXL-account werkt", "https://help.woosa.com/en/articles/75685-how-does-my-vidaxl-dropxl-dropshipping-account-work"),)},
    {"name": "Hertwill", "type": "dropship", "scope": "EU", "categories": ("beauty-care", "home-living", "lifestyle-sport"),
     "access": "account", "onderzocht": True, "url": "https://hertwill.com/dropshipping-suppliers-europe",
     "facts": "Meer dan 200 EU- en VS-merken en 7.000+ producten (Beauty & Personal Care, Home & Garden, Apparel, Footwear, Bags). "
              "Gevestigd in Tallinn; EU-leveranciers verzenden vanuit EU-magazijnen.",
     "requirement": "Account (gratis plan zonder creditcard), WooCommerce-plugin en een dropshipping-API voor eigen koppelingen.",
     "cost": "Betaalde plannen voor meer producten en orders; prijzen staan niet op de onderzochte pagina.",
     "evidence": (("Dropshipping suppliers Europe", "https://hertwill.com/dropshipping-suppliers-europe"),)},
    {"name": "Ikonka", "type": "groothandel", "scope": "EU", "categories": ("gadgets", "home-living", "beauty-care"),
     "access": "account", "onderzocht": True, "url": "https://www.shoper.pl/katalog-hurtowni/hurtownia/ikonka",
     "facts": "Poolse dropshippinggroothandel: gadgets, speelgoed, cosmetica-accessoires, huis en tuin.",
     "requirement": "Alleen via een groothandelsintegratie (Shoper met Apilo); voorwaarden worden per klant afgesproken. "
                    "Geen openbare API gevonden.",
     "cost": "Het Shoper-platform is betaald (14 dagen proef).",
     "evidence": (("Ikonka via Shoper", "https://www.shoper.pl/katalog-hurtowni/hurtownia/ikonka"),)},
    {"name": "Versa Group", "type": "groothandel", "scope": "EU", "categories": ("home-living",), "access": "handmatig",
     "onderzocht": False, "url": "https://www.versagroup.be/",
     "facts": "Alleen de omschrijving uit de code (sanitair en inrichting, PDF-catalogus); niet onderzocht.",
     "requirement": "Handmatig contact en catalogus opvragen.", "cost": "Onbekend.", "evidence": ()},
    {"name": "Sirocco", "type": "groothandel", "scope": "EU", "categories": ("home-living",), "access": "handmatig",
     "onderzocht": False, "url": "https://sirocco.de/dropshipping/",
     "facts": "Alleen de omschrijving uit de code (tuin en gereedschap); de pagina was niet bereikbaar.",
     "requirement": "Handmatig voorwaarden opvragen.", "cost": "Onbekend.", "evidence": ()},
    {"name": "JG Distribution", "type": "groothandel", "scope": "EU", "categories": ("gadgets",), "access": "handmatig",
     "onderzocht": False, "url": "https://jgdistribution.fr/programme",
     "facts": "Alleen de omschrijving uit de code (gadgets en speelgoed); de pagina was niet bereikbaar.",
     "requirement": "Handmatig programma-voorwaarden opvragen.", "cost": "Onbekend.", "evidence": ()},
    {"name": "Avasam", "type": "dropship", "scope": "GB", "categories": ("all",), "access": "handmatig",
     "onderzocht": False, "url": "https://www.avasam.com/dropship-suppliers/",
     "facts": "Alleen de omschrijving uit de code (platform voor Britse B2B-leveranciers); de pagina was niet bereikbaar.",
     "requirement": "Handmatig account en voorwaarden controleren.", "cost": "Onbekend.", "evidence": ()},
)

# Bronnen die NUVEMIXA al doorzoekt buiten de merkwebshops.
CONNECTED_EXTRA = (
    {"name": "Syncee", "type": "marktplaats", "scope": "INT", "categories": ("all",), "access": "account",
     "onderzocht": True, "url": "https://syncee.com/pricing",
     "facts": "NUVEMIXA leest de openbare productlijst; levering per product is daarmee niet bevestigd.",
     "requirement": "Gratis plan: producten bekijken en groothandelsprijzen zien. Importeren naar WooCommerce vraagt een betaald plan.",
     "cost": "Vanaf $39,99 per maand (Basic, 100 producten); 3 dagen proef. Geen publieke zoek-API gevonden.",
     "evidence": (("Prijzen", "https://syncee.com/pricing"),)},
    {"name": "Hama", "type": "distributeur", "scope": "EU", "categories": ("gadgets",), "access": "openbaar",
     "onderzocht": False, "url": "https://www.hama.com", "countries": ("NL", "DE"),
     "facts": "Doorzoekt de openbare webwinkelcatalogus (alleen NL en DE).",
     "requirement": "Zakelijke aanmelding via het Hama business-portaal voor inkoopvoorwaarden.", "cost": "Onbekend.", "evidence": ()},
    {"name": "Hurtel", "type": "groothandel", "scope": "EU", "categories": ("gadgets", "smart-home"), "access": "openbaar",
     "onderzocht": False, "url": "https://hurtel.com",
     "facts": "Doorzoekt de openbare zoekpagina. De code legt vast dat Hurtel geen dropshipping doet.",
     "requirement": "Zakelijke aanmelding; catalogus als CSV of XML na aanmelding.", "cost": "Onbekend.", "evidence": ()},
)


def _brand_catalogues():
    from nv_product_discovery import CATALOGUES, TRADE_PROFILES
    seen = {}
    for c in CATALOGUES:
        entry = seen.setdefault(c.name, {
            "name": c.name, "type": "merkwebshop", "categories": set(), "countries": set(), "access": "openbaar",
            "onderzocht": False, "url": "https://" + c.host, "trade_url": c.trade_url,
            "role": TRADE_PROFILES.get(c.name, ("", ""))[1] or "Webwinkel (zakelijke voorwaarden niet bevestigd)",
            "fallback": c.fallback})
        entry["categories"].add(c.category)
        entry["countries"] |= set(c.countries)
    for entry in seen.values():
        entry["categories"] = tuple(sorted(entry["categories"]))
        entry["countries"] = tuple(sorted(entry["countries"]))
        entry["facts"] = "Doorzoekt de openbare zoekfunctie van de webshop; niet live bevestigd vanuit onze testomgeving."
        entry["requirement"] = ("Zakelijk aanmelden via " + entry["trade_url"]) if entry["trade_url"] else "Geen zakelijk programma gevonden in de code."
        entry["cost"] = "Onbekend."
        entry["evidence"] = ()
        entry["scope"] = "EU" if set(entry["countries"]) & EU else "INT"
    return list(seen.values())


def connected_sources():
    return _brand_catalogues() + [dict(x) for x in CONNECTED_EXTRA]


def _scope_ok(scope, country):
    return scope == "INT" or (scope == "EU" and country in EU) or scope == country


def _covers(entry, categories):
    cats = entry.get("categories", ())
    return "all" in cats or bool(set(cats) & set(categories))


def search_link(entry, term):
    host = entry["url"].split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
    query = f"site:{host} {term}".strip()
    return "https://www.google.com/search?q=" + quote(query, safe="")


def sources_for(categories, country, term="", limit=6):
    """Link-bronnen om verder te onderzoeken, afhankelijk van categorie en doelland (beste eerst)."""
    rows = []
    for entry in LINK_SOURCES:
        if not _covers(entry, categories):
            continue
        exact = entry["scope"] == country or (entry["scope"] == "EU" and country in EU)
        if not (exact or entry["scope"] == "INT"):
            continue
        specific = 0 if "all" not in entry["categories"] else 1
        rank = (0 if entry["onderzocht"] else 1, specific, 0 if exact else 1)
        rows.append((rank, entry))
    rows.sort(key=lambda r: r[0])
    out = []
    for _, entry in rows[:limit]:
        out.append({**entry, "type_label": TYPE_LABELS[entry["type"]], "access_label": ACCESS_LABELS[entry["access"]],
                    "search_link": search_link(entry, term)})
    return out


def coverage(country):
    """Per categorie: wat NUVEMIXA nu doorzoekt (voor dit land) en welke link-bronnen er zijn."""
    connected = connected_sources()
    result = {}
    for slug in CATEGORIES:
        now = []
        for entry in connected:
            if not _covers(entry, (slug,)):
                continue
            if entry.get("countries") and country not in entry["countries"] and country not in EU:
                continue
            if entry.get("countries") and country not in entry["countries"]:
                continue
            now.append({"name": entry["name"], "type_label": TYPE_LABELS[entry["type"]],
                        "fallback": bool(entry.get("fallback"))})
        links = [{"name": e["name"], "access_label": e["access_label"], "onderzocht": e["onderzocht"]}
                 for e in sources_for((slug,), country, limit=20)]
        result[slug] = {"connected": now, "links": links}
    return result


# --- Handmatige bronnentest (alleen na een klik; alleen lezen) ---------------------------------------------

_TEST = {"at": None, "rows": []}
_TEST_BUDGET = 14.0


def test_state():
    return {"at": _TEST["at"], "rows": list(_TEST["rows"])}


def reset_test():
    _TEST.update(at=None, rows=[])


def run_source_test(fetch=None):
    """Eén alleen-lezen zoekopdracht per catalogus met de eigen standaardterm van de bron. Schrijft niets weg."""
    import requests
    import nv_product_discovery as npd
    fetch = fetch or requests.get
    deadline = time.monotonic() + _TEST_BUDGET
    sources, seen = [], set()
    for c in npd.CATALOGUES:
        if c.host not in seen:
            seen.add(c.host)
            sources.append(c)

    def probe(source):
        attempt = {"source": source.name, "query": source.seed, "raw": None}
        started = time.monotonic()
        try:
            npd.catalogue_candidates(source, source.seed, "products", fetch, source.seed, attempt, {}, deadline)
            n = attempt.get("raw") or 0
            return {"name": source.name, "host": source.host, "status": "ok" if n else "leeg", "count": n,
                    "detail": "" if n else "Bereikbaar, maar geen producten voor de testterm.",
                    "ms": round((time.monotonic() - started) * 1000)}
        except npd.SOURCE_ERRORS as error:
            return {"name": source.name, "host": source.host, "status": "fout", "count": 0,
                    "detail": npd.source_error(error), "ms": round((time.monotonic() - started) * 1000)}

    pool = ThreadPoolExecutor(max_workers=8)
    try:
        tasks = {pool.submit(probe, s): s for s in sources}
        wait(tasks, timeout=_TEST_BUDGET)
        rows = []
        for task, source in tasks.items():
            rows.append(task.result() if task.done() else
                        {"name": source.name, "host": source.host, "status": "fout", "count": 0,
                         "detail": "Geen antwoord binnen de tijdslimiet.", "ms": None})
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    rows.sort(key=lambda r: (r["status"] != "ok", r["name"]))
    _TEST.update(at=datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M"), rows=rows)
    return rows


@bp.post("/dashboard/onderzoek/bronnen-testen")
def sources_test():
    if not admin():  # doet uitgaande aanroepen: alleen de eigenaar
        abort(403)
    run_source_test()
    flash("Bronnentest uitgevoerd (alleen lezen). Resultaat staat onder 'Bronnen en dekking'.", "success")
    return redirect(url_for("control", section="onderzoek"), code=303)
