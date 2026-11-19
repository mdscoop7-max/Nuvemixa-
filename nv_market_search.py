"""Zoekpagina's voor Viral Product Finder en Internationaal marktonderzoek.

Beide pagina's gebruiken dezelfde bronnen als AI Productonderzoek (nv_product_discovery.discover).
Er worden geen scores, vraagcijfers of prijzen bedacht: wat de bronnen niet leveren, wordt als
onbekend getoond.
"""
from collections import Counter
from datetime import date, timedelta

from nv_ai_search import ai_discover as discover  # AI-ondersteund, valt terug op normaal zoeken
from nv_product_discovery import ALL_PRODUCTS, COUNTRIES, MANUAL_PLATFORMS, RESEARCH_CATEGORIES

REGIONS = {"all": "Wereldwijd", "nl": "Nederland", "eu": "Binnen EU", "international": "Buiten EU"}
SUPPLIER_TYPES = {
    "all": "Alle soorten", "dropship": "Dropshipping", "wholesale": "Groothandel", "manufacturer": "Fabrikant of merk",
}
PERIODS = {"slim": "Slim", "7": "7 dagen", "14": "14 dagen", "30": "30 dagen", "90": "90 dagen", "365": "12 maanden", "0": "Alle periodes"}
VIRAL_SOURCES = {"all": "Producten en publicaties", "products": "Alleen productbronnen", "news": "Alleen publicaties"}
PRICE_NOTE = ("Marktprijzen en verkoopcijfers leveren de huidige bronnen niet. Ze worden daarom niet getoond "
              "of geschat. Controleer prijzen handmatig via de bronlinks.")
TREND_NOTE = ("Er is geen betrouwbare trendscore of marktvraag beschikbaar. De signalen hieronder zijn "
              "openbare publicaties en productvermeldingen, geen verkoopcijfers.")


def choice(args, key, options, default):
    value = args.get(key, default)
    return value if value in options else default


def dropship_label(company):
    if company.get("dropshipping") is True:
        return "Bevestigd"
    if company.get("dropshipping") is False:
        return "Niet beschikbaar"
    return "Niet bevestigd"


def ships_to_netherlands(company, country):
    if company.get("shipping_nl") == "Bevestigd":
        return True
    return country == "NL" and str(company.get("shipping", "")).startswith("Bevestigd")


def parse(kind, args, categories):
    """Lees en valideer de zoekopdracht. Ongeldige waarden vallen terug op de standaard.

    De parameters beginnen met 'm' zodat ze niet botsen met de bestaande filters van het handmatige onderzoek.
    """
    category = args.get("mcat", ALL_PRODUCTS)
    return {
        "q": args.get("mq", "").strip()[:100],
        "country": choice(args, "mland", COUNTRIES, "NL"),
        "category": category if category == ALL_PRODUCTS or category in categories else ALL_PRODUCTS,
        "region": choice(args, "mregio", REGIONS, "all"),
        "supplier_type": choice(args, "mtype", SUPPLIER_TYPES, "all"),
        "ships_nl": args.get("mnl") == "1",
        "dropship_only": args.get("mdrop") == "1",
        "period": choice(args, "mperiode", PERIODS, "slim"),
        "source": choice(args, "mbron", VIRAL_SOURCES, "all"),
        "google_trends": args.get("mgoogle") == "1",
        "run": args.get("mrun") == "1",
    }


def filter_suppliers(suppliers, form):
    kept = []
    for company in suppliers:
        if form["region"] == "nl":
            if company.get("origin") != "NL":
                continue
        elif form["region"] != "all" and company["region"] != form["region"]:
            continue
        role = company.get("role", "")
        if form["supplier_type"] == "dropship" and company.get("dropshipping") is not True:
            continue
        if form["supplier_type"] == "wholesale" and role != "Groothandel":
            continue
        if form["supplier_type"] == "manufacturer" and role != "Fabrikant of merk":
            continue
        if form["ships_nl"] and not ships_to_netherlands(company, form["country"]):
            continue
        kept.append(company)
    return kept


def attach_supplier_refs(products, suppliers):
    by_url = {}
    for company in suppliers:
        for item in company["products"]:
            by_url.setdefault(item["url"], []).append(company)
    result = []
    for item in products:
        companies = by_url.get(item["url"], [])
        refs = [{"name": c["name"], "role": c.get("role", ""), "region": c["region"], "website": c["website"],
                 "dropshipping": dropship_label(c), "dropshipping_source": c.get("dropshipping_source"),
                 "confirmed_business": c.get("business") is True} for c in companies]
        result.append({**item, "supplier_refs": refs,
                       "signal_count": len(item.get("assessment", {}).get("market_context", []))})
    return result


def within_period(articles, period, kind="viral"):
    if period == "slim":
        days = __import__("nv_research_period").SMART.get(kind, 30)
        period = "0" if days is None else str(days)
    if period == "0":
        return articles
    start = (date.today() - timedelta(days=int(period))).isoformat()
    return [article for article in articles if article["date"] >= start]


def opportunities_and_risks(view, form):
    """Waarnemingen uit de gevonden gegevens. Geen schattingen of voorspellingen."""
    suppliers, products = view["suppliers"], view["products"]
    good, risks = [], []
    eu = [c for c in suppliers if c["region"] == "eu"]
    outside = [c for c in suppliers if c["region"] == "international"]
    confirmed_dropship = [c for c in suppliers if c.get("dropshipping") is True]
    if products:
        good.append(f"{len(products)} productvermelding{'en' if len(products) != 1 else ''} met bevestigde match in de bronnen.")
    if eu:
        good.append(f"{len(eu)} leverancier{'s' if len(eu) != 1 else ''} binnen de EU gevonden (vestiging volgens bron).")
    if confirmed_dropship:
        good.append("Dropshipping bevestigd bij " + ", ".join(c["name"] for c in confirmed_dropship[:4]) + ".")
    if view["publications"]:
        good.append(f"{len(view['publications'])} publicatie{'s' if len(view['publications']) != 1 else ''} over dit onderwerp gevonden.")
    if form["run"] and not suppliers:
        risks.append("Geen leverancier gevonden. Zoek met een kortere of Engelse productnaam of onderzoek handmatig.")
    if suppliers and not eu:
        risks.append("Geen leverancier met bevestigde vestiging binnen de EU gevonden.")
    if outside:
        risks.append("Leveranciers buiten de EU: controleer vertrekmagazijn, invoerrechten, btw, levertijd en conformiteitsdocumentatie.")
    if suppliers and not confirmed_dropship:
        risks.append("Bij geen enkele gevonden leverancier is dropshipping bevestigd.")
    if suppliers and not any(ships_to_netherlands(c, form["country"]) for c in suppliers):
        risks.append("Verzending naar Nederland is bij geen enkele leverancier bevestigd.")
    if any(item.get("assessment", {}).get("alert") for item in products):
        risks.append("Een of meer producten hebben een Safety Gate-melding. Controleer de productdetails.")
    risks.append("Marktvraag, verkoopcijfers en prijzen zijn niet beschikbaar uit de huidige bronnen.")
    return good, risks


def search_view(kind, categories, args, *, fetch=None):
    """kind is 'viral' of 'internationaal'. Geeft altijd een dict terug die de template kan tonen."""
    categories = {**categories, **RESEARCH_CATEGORIES}
    form = parse(kind, args, categories)
    view = {"kind": kind, "form": form, "categories": categories, "countries": COUNTRIES, "regions": REGIONS,
            "supplier_types": SUPPLIER_TYPES, "periods": PERIODS, "sources": VIRAL_SOURCES,
            "price_note": PRICE_NOTE, "trend_note": TREND_NOTE, "ran": False, "error": None,
            "products": [], "suppliers": [], "publications": [], "trends": [], "competitors": [],
            "opportunities": [], "risks": [], "pending_sources": [], "links": [], "unavailable": [], "sources_checked": [],
            "empty_message": "", "result": None, "ai": None, "rows": [],
            "supplier_rows_fn": __import__("nv_product_rows").suppliers}
    if not form["run"]:
        return view
    if not form["q"]:
        view["error"] = "Vul een product, niche of zoekterm in."
        return view
    platforms = ["Productcatalogi", "Publicaties", *MANUAL_PLATFORMS]
    if kind == "viral" and form["source"] == "products":
        platforms = ["Productcatalogi", *MANUAL_PLATFORMS]
    elif kind == "viral" and form["source"] == "news":
        platforms = ["Publicaties", *MANUAL_PLATFORMS]
    if kind == "viral" and form["google_trends"]:
        platforms.append("Google Trends")
    supplier_filter = {"dropship": "dropship", "wholesale": "trade", "manufacturer": "trade"}.get(form["supplier_type"], "all")
    result = discover(form["q"], country=form["country"], mode="trends" if kind == "viral" else "products",
                      platforms=platforms, fetch=fetch, category=form["category"],
                      categories=categories, supplier_filter=supplier_filter)
    view["ran"] = True
    if result.get("error"):
        view["error"] = result["error"]
        return view
    suppliers = filter_suppliers(result["suppliers"], form)
    products = attach_supplier_refs(result["products"], suppliers)
    if form["dropship_only"] or kind == "viral" and form["supplier_type"] == "dropship":
        products = [p for p in products if any(r["dropshipping"] == "Bevestigd" for r in p["supplier_refs"])]
    if form["region"] != "all" or form["ships_nl"]:
        products = [p for p in products if p["supplier_refs"]]
    publications = within_period(result["news"], form["period"], kind)
    trends = within_period(result["trends"], form["period"], kind)
    counts = Counter(item["source"] for item in products)
    view.update(
        result=result, products=products, suppliers=suppliers, publications=publications, trends=trends,
        competitors=[{"source": name, "count": number,
                      "links": [p for p in products if p["source"] == name][:3]} for name, number in counts.most_common()],
        links=result.get("links", []), unavailable=result.get("unavailable_sources", []), unavailable_reasons=result.get("unavailable_reasons", {}), pending_sources=result.get("pending_sources", []),
        sources_checked=result.get("sources_checked", []), empty_message="Geen bevestigde producten gevonden voor deze selectie.",
        alternatives=result.get("alternatives", []), country_name=result["country_name"],
        interpretation=result.get("interpretation"), all_failed=result.get("all_sources_failed", False),
        ai=result.get("ai"),
        rows=__import__("nv_product_rows").build(products, suppliers, categories),
        period_label=(PERIODS[form["period"]] + (" → {} dagen".format(__import__("nv_research_period").SMART.get(kind, 30))
                      if form["period"] == "slim" else "") + " · alleen publicaties met datum; productbronnen en leveranciers niet gefilterd"),
    )
    view["opportunities"], view["risks"] = opportunities_and_risks(view, form)
    return view
