"""Product and editorial research using first-party catalogues and screened RSS."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
import json
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

import requests

from nv_research_sources import (
    FILTERS, UNKNOWN, cj_reference, hama_products, publication_candidates,
    publication_kind, rss_publications, supplier, syncee_products,
)

COUNTRIES = {
    "NL": ("Nederland", "nl", "NL"),
    "BE": ("België", "nl", "BE"),
    "DE": ("Duitsland", "de", "DE"),
    "FR": ("Frankrijk", "fr", "FR"),
    "ES": ("Spanje", "es", "ES"),
    "IT": ("Italië", "it", "IT"),
    "PL": ("Polen", "pl", "PL"),
    "AT": ("Oostenrijk", "de", "AT"),
    "PT": ("Portugal", "pt", "PT"),
    "IE": ("Ierland", "en", "IE"),
    "SE": ("Zweden", "sv", "SE"),
    "DK": ("Denemarken", "da", "DK"),
    "FI": ("Finland", "fi", "FI"),
    "NO": ("Noorwegen", "no", "NO"),
    "CH": ("Zwitserland", "de", "CH"),
    "CZ": ("Tsjechië", "cs", "CZ"),
    "SK": ("Slowakije", "sk", "SK"),
    "HU": ("Hongarije", "hu", "HU"),
    "RO": ("Roemenië", "ro", "RO"),
    "BG": ("Bulgarije", "bg", "BG"),
    "GR": ("Griekenland", "el", "GR"),
    "HR": ("Kroatië", "hr", "HR"),
    "SI": ("Slovenië", "sl", "SI"),
    "LT": ("Litouwen", "lt", "LT"),
    "LV": ("Letland", "lv", "LV"),
    "EE": ("Estland", "et", "EE"),
    "LU": ("Luxemburg", "fr", "LU"),
    "MT": ("Malta", "en", "MT"),
    "CY": ("Cyprus", "en", "CY"),
    "GB": ("Verenigd Koninkrijk", "en", "GB"),
    "US": ("Verenigde Staten", "en", "US"),
    "CA": ("Canada", "en", "CA"),
    "AU": ("Australië", "en", "AU"),
    "NZ": ("Nieuw-Zeeland", "en", "NZ"),
    "JP": ("Japan", "ja", "JP"),
    "KR": ("Zuid-Korea", "ko", "KR"),
    "SG": ("Singapore", "en", "SG"),
    "IN": ("India", "en", "IN"),
    "BR": ("Brazilië", "pt", "BR"),
    "MX": ("Mexico", "es", "MX"),
    "ZA": ("Zuid-Afrika", "en", "ZA"),
    "AE": ("Verenigde Arabische Emiraten", "en", "AE"),
    "TR": ("Turkije", "tr", "TR"),
}

PLATFORMS = ("Productcatalogi", "Publicaties", "Google", "TikTok", "Instagram", "Facebook")
MODES = {
    "products": "Producten zoeken",
    "trends": "Trends en nichekansen",
    "niche": "Direct nicheproducten zoeken",
    "product": "Specifiek product zoeken",
    "suppliers": "Leveranciers zoeken",
    "dropship": "Dropshippingpartners zoeken",
    "wholesale": "Groothandels en fabrikanten zoeken",
    "news": "Nieuws en productreviews zoeken",
}
ALL_PRODUCTS = "shop"
SUPPLIER_MODES = {"suppliers", "dropship", "wholesale"}
PRODUCT_MODES = {"products", "trends", "niche", "product"}
DEFAULT_TABS = {**dict.fromkeys(SUPPLIER_MODES, "suppliers"), "trends": "trends", "news": "news"}
EMPTY_RESULTS = "Geen betrouwbare, relevante productresultaten gevonden."
EU = frozenset("NL BE DE FR ES IT PL AT PT IE SE DK FI CZ SK HU RO BG GR HR SI LT LV EE LU MT CY".split())


@dataclass(frozen=True)
class Catalogue:
    name: str
    host: str
    category: str
    countries: frozenset
    seed: str
    # Terms from product names/types or URLs that establish the webshop category.
    category_terms: str
    trade_url: str = ""


CATALOGUES = (
    # Market coverage follows each provider's shipping policy. Item-level shipping
    # and trade availability still depend on the supplier's terms.
    Catalogue("UGREEN", "eu.ugreen.com", "gadgets", EU - {"CY", "LT", "MT"}, "power bank",
              r"power ?bank|charger|oplader|usb|laptop stand|charging",
              "https://www.ugreen.com/pages/wholesale-program"),
    Catalogue("UGREEN", "us.ugreen.com", "gadgets", frozenset({"US"}), "power bank",
              r"power ?bank|charger|usb|laptop stand|charging",
              "https://www.ugreen.com/pages/wholesale-program"),
    Catalogue("Baseus", "eu.baseus.com", "gadgets", (EU - {"CY", "HR", "MT"}) | {"GB"}, "power bank",
              r"power ?bank|charger|usb|laptop stand|charging", "https://eu.baseus.com/pages/wholesale-program"),
    Catalogue("Baseus", "www.baseus.com", "gadgets", frozenset({"US"}), "power bank",
              r"power ?bank|charger|usb|laptop stand|charging", "https://www.baseus.com/pages/wholesale-program"),
    Catalogue("SwitchBot", "eu.switch-bot.com", "smart-home", frozenset("NL BE DE FR ES IT AT".split()),
              "smart home", r"smart|wifi|zigbee|matter|curtain|gordijn|hub|sensor|lighting|rgbicww|door lock"),
    Catalogue("eufy", "eu.eufy.com", "smart-home", frozenset("NL BE DE FR ES IT AT".split()),
              "camera", r"camera|eufycam|doorbell|deurbel|robot vacuum|robovac|homebase",
              "https://www.eufy.com/eu-en/partner-program"),
    Catalogue("eufy", "us.eufy.com", "smart-home", frozenset({"US"}), "camera",
              r"camera|eufycam|doorbell|robot vacuum|robovac|homebase",
              "https://www.eufy.com/business"),
    Catalogue("Cocunat", "www.cocunat.com", "beauty-care", EU | {"GB", "NO", "CH", "TR"},
              "serum", r"serum|cream|crème|skincare|shampoo|retinal|mask|face|hair|body|skin"),
    Catalogue("Ferm Living", "fermliving.com", "home-living",
              EU | frozenset("AU CA CH IN JP KR NO NZ SG TR ZA AE".split()), "lamp",
              r"lamp|chair|stoel|sofa|cushion|kussen|vase|vaas|table|tafel|rug|carpet|shelf|lighting",
              "https://fermliving.com/pages/contact"),
    Catalogue("Manduka", "eu.manduka.com", "lifestyle-sport", EU | {"NO", "CH"},
              "yoga mat", r"yoga|mat|bolster|block|towel|handdoek|legging",
              "https://eu.manduka.com/pages/wholesale-application"),
)
TRADE_PROFILES = {
    "UGREEN": ("CN", "Fabrikant / groothandel"),
    "Baseus": ("CN", "Fabrikant"),
    "eufy": ("CN", "Fabrikant"),
    "Ferm Living": ("DK", "Fabrikant / groothandel"),
    "Manduka": ("NL", "Groothandel"),
}
ORIGINS = {**{code: details[0] for code, details in COUNTRIES.items()}, "CN": "China"}
CATEGORY_HINTS = {
    "gadgets": r"power ?bank|charger|usb|laptop stand|charging|headphones|earbuds|bluetooth speaker",
    "smart-home": r"smart|wifi|zigbee|matter|curtain|hub|sensor|lighting|rgbicww|door lock|camera|doorbell|robot vacuum|robovac|homebase",
    "beauty-care": r"serum|cream|crème|skincare|shampoo|retinal|mask|face|hair|body|skin",
    "home-living": r"lamp|chair|sofa|cushion|vase|table|rug|carpet|shelf|lighting|storage|furniture",
    "lifestyle-sport": r"yoga|mat|bolster|block|towel|handdoek|legging|fitness|dumbbell|hiking|sport",
}
SEEDS = {"gadgets": "power bank", "smart-home": "security camera", "beauty-care": "serum",
         "home-living": "table lamp", "lifestyle-sport": "yoga mat"}
UNSAFE = re.compile(
    r"\b(?:porno?\w*|xxx|nsfw|adult\s+(?:content|video|toy)|sex\s+toy|escort|"
    r"casino|gambling|sign[ -]?in|log[ -]?in|inloggen|aanmelden|oauth|"
    r"gift card|cadeaubon|vip membership|shipping protection|advertorial|sponsored post)\b", re.IGNORECASE,
)
ALIASES = {
    "magnetische": "magnetic", "magnetischen": "magnetic", "magnetisch": "magnetic", "draadloze": "wireless",
    "draadloos": "wireless", "kabelloses": "wireless", "oplader": "charger", "slimme": "smart", "slim": "smart",
    "gordijn": "curtain", "gordijnen": "curtain", "deurbel": "doorbell",
    "beveiligingscamera": "security camera", "vloerlamp": "floor lamp",
    "tafellamp": "table lamp", "stoel": "chair", "kussen": "cushion", "tafel": "table",
    "vaas": "vase", "yogamat": "yoga mat", "yogamatten": "yoga mat",
    "rgbicww": "rgbicww smart", "eufycam": "eufycam camera",
}
STOP_WORDS = {"a", "de", "een", "en", "for", "het", "in", "met", "the", "van", "voor", "with"}


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"(?<=\d)[., ](?=\d{3}\b)", "", value)
    value = re.sub(r"\bpower[ -]?(?:banks?|packs?)\b", "power bank", value)
    value = re.sub(r"(?<=\d)(?=mah\b)", " ", value)
    words = re.findall(r"[^\W_]+", value)
    return " ".join(ALIASES.get(word, word) for word in words)


def matches(search, evidence):
    required = set(normalize(search).split()) - STOP_WORDS
    return bool(required) and required.issubset(normalize(evidence).split())


def category_matches(category, evidence):
    return not UNSAFE.search(evidence) and bool(
        re.search(r"\b(?:" + CATEGORY_HINTS[category] + r")\b", normalize(evidence))
    )


def research_links(term, platforms, country, language):
    q = quote(term, safe="")
    urls = {
        "Google": f"https://www.google.com/search?safe=active&gl={country}&hl={language}&q={q}",
        "TikTok": "https://www.tiktok.com/search?q=" + q,
        "Instagram": "https://www.instagram.com/explore/tags/" + quote("".join(normalize(term).split()), safe="") + "/",
        "Facebook": "https://www.facebook.com/search/top?q=" + q,
    }
    return [(platform, urls[platform]) for platform in platforms if platform in urls]


def read_source(fetch, url, params, *, max_bytes=768_000, language=None):
    """Bound untrusted responses and prevent a provider redirect from changing host."""
    headers = {"User-Agent": "NUVEMIXA-Research/1.0"}
    if language:
        headers["Accept-Language"] = language
    with fetch(url, params=params, timeout=(3, 5), allow_redirects=False, stream=True,
               headers=headers) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected source status")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            content.extend(chunk)
            if len(content) > max_bytes:
                raise ValueError("Source response is too large")
        return bytes(content)


def catalogue_items(source, term, mode, fetch):
    query = english_query(term) if term else source.seed
    fields = "title,variants.sku,product_type" if mode == "product" else "title,product_type,tag,variants.sku"
    body = read_source(fetch, f"https://{source.host}/search/suggest.json", {
        "q": query, "resources[type]": "product", "resources[limit]": 10,
        "resources[options][fields]": fields,
    })
    products = json.loads(body)["resources"]["results"]["products"]
    if not isinstance(products, list):
        raise ValueError("Unexpected catalogue format")
    results = []
    for product in products[:10]:
        if not isinstance(product, dict) or type(product.get("id")) is not int or product["id"] <= 0:
            continue
        title, handle, kind = (product.get(key) for key in ("title", "handle", "type"))
        if not all(isinstance(value, str) for value in (title, handle, kind)):
            continue
        if not title.strip() or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", handle):
            continue
        path = f"/products/{handle}"
        raw_url = product.get("url")
        if not isinstance(raw_url, str) or raw_url.split("?")[0] != path:
            continue
        evidence = f"{title} {kind} {handle.replace('-', ' ')}"
        if (UNSAFE.search(evidence) or not re.search(r"\b(?:" + source.category_terms + r")\b", normalize(evidence))
                or (term and not matches(term, evidence)) or UNSAFE.search(normalize(evidence))):
            continue
        image = product.get("image")
        if not isinstance(image, str) or not re.fullmatch(
            r"https://cdn\.shopify\.com/s/files/[a-zA-Z0-9_./%-]+\.(?:jpe?g|png|webp)(?:\?v=\d+)?", image,
        ) or ".." in unquote(image):
            image = ""
        results.append({
            "title": title.strip()[:240], "url": f"https://{source.host}{path}", "source": source.name,
            "category": source.category, "image": image, "trade_url": source.trade_url,
        })
    return results


def english_query(term):
    # Provider indexes may treat capacities attached to the unit as one token.
    return re.sub(r"(?<=\d) (?=mah\b)", "", normalize(term))


def article_query(term):
    subject = re.sub(r"\b\d+\s+(?:mah|w|gb|ml|mm)\b", "", normalize(term))
    subject = " ".join(subject.split())
    return subject if len(set(subject.split()) - STOP_WORDS) >= 2 else normalize(term)


def publications(reader, fetch, topic, term, country, language, categories):
    articles = []
    for item in reader(fetch, topic, country, language, read_source):
        evidence = item["title"] + " " + item["summary"]
        if not item["title"] or UNSAFE.search(evidence + " " + item["url"]) or not matches(topic, evidence):
            continue
        # Demand subject evidence in the headline as well as the full topic in
        # the editorial excerpt, so incidental references cannot qualify.
        title_words = set(normalize(item["title"]).split())
        topic_words = set(normalize(topic).split()) - STOP_WORDS
        if len(title_words & topic_words) < min(2, len(topic_words)):
            continue
        if not any(category_matches(cid, evidence) for cid in categories):
            continue
        try:
            published = date.fromisoformat(item["date"])
        except ValueError:
            continue
        if published > date.today():
            continue
        item["kind"] = publication_kind(evidence)
        item["scope"] = "Zelfde product of zoekterm" if term and matches(term, evidence) else "Verwante niche"
        articles.append(item)
    return articles[:10]


def catalogue_suppliers(products):
    for item in products:
        if item["trade_url"]:
            origin, kind = TRADE_PROFILES[item["source"]]
            # A country-specific catalogue establishes market coverage for
            # research. It does not establish wholesale shipping for this SKU.
            evidence = ()
            if item["source"] == "Baseus":
                evidence = (("Wederverkoop via apart distributeursprogramma", item["trade_url"]),)
            profile = supplier(item["source"], origin, kind, item["trade_url"], evidence=evidence)
            yield profile, item


def unique_suppliers(offers, supplier_filter):
    companies = {}
    for profile, item in offers:
        name_key = re.sub(r"[^a-z0-9]+", "", profile["name"].casefold())
        if not name_key:
            continue
        # Multiple regional storefronts and multiple SKUs are a single company.
        company = companies.setdefault(name_key, {**profile, "products": {}, "region": (
            "unknown" if not profile["origin"] else "eu" if profile["origin"] in EU else "international"
        )})
        company["products"][item["url"]] = item
        if profile["shipping"].startswith("Geverifieerd"):
            company["shipping"] = "Geverifieerd voor minstens één getoond product"
    filtered = []
    for company in companies.values():
        if supplier_filter == "eu" and company["region"] != "eu":
            continue
        if supplier_filter == "international" and company["region"] != "international":
            continue
        if supplier_filter == "dropship" and company["dropshipping"] is not True:
            continue
        if supplier_filter == "trade" and company["dropshipping"] is True:
            continue
        company["origin_name"] = ORIGINS.get(company["origin"], UNKNOWN)
        company["product_count"] = len(company["products"])
        company["products"] = sorted(company["products"].values(),
                                     key=lambda product: not product.get("shipping", "").startswith("Geverifieerd"))
        filtered.append(company)
    return filtered


def collect(future, errors):
    try:
        return future.result()
    except (requests.RequestException, ET.ParseError, ValueError, KeyError, TypeError, OSError):
        errors.append(True)
        return []


def discover(term, country="NL", mode="trends", platforms=None, fetch=None, *,
             category=ALL_PRODUCTS, categories, supplier_filter="all"):
    term = (term or "").strip()[:100]
    if ((category != ALL_PRODUCTS and category not in categories) or mode not in MODES
            or country not in COUNTRIES or supplier_filter not in FILTERS):
        return {"error": "Kies een geldige webshopcategorie, zoektype, doelland en leverancierfilter."}
    if term and (not (set(normalize(term).split()) - STOP_WORDS) or UNSAFE.search(term)):
        return {"error": EMPTY_RESULTS}
    if not term and (mode == "product" or category == ALL_PRODUCTS):
        return {"error": "Vul een product of niche in, of kies een specifieke webshopcategorie."}
    platforms = tuple(dict.fromkeys(
        "Publicaties" if p == "Bing" else p
        for p in (PLATFORMS if platforms is None else platforms) if p in (*PLATFORMS, "Bing")
    ))
    if not platforms:
        return {"error": "Selecteer minimaal één onderzoeksplatform."}
    fetch = fetch or requests.get
    name, language, _ = COUNTRIES[country]
    selected = categories if category == ALL_PRODUCTS else {category: categories[category]}
    from_catalogues = "Productcatalogi" in platforms and mode != "news"
    product_mode = mode in PRODUCT_MODES
    trade_mode = from_catalogues and mode != "dropship" and (product_mode or supplier_filter != "dropship")
    dropship_mode = from_catalogues and mode in {"suppliers", "dropship", "trends", "niche", "products", "product"}
    if supplier_filter == "trade":
        dropship_mode = False
    sources = [
        source for source in CATALOGUES
        if trade_mode and source.category in selected and country in source.countries
        and (product_mode or source.trade_url)
    ]
    topic = article_query(term) if term else SEEDS.get(category, "")
    errors = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        product_tasks = [pool.submit(catalogue_items, source, term, mode, fetch) for source in sources]
        hama_task = (pool.submit(hama_products, fetch, term, country, read_source, matches, category_matches)
                     if trade_mode and country in {"NL", "DE"} and "gadgets" in selected else None)
        dropship_task = (pool.submit(syncee_products, fetch, english_query(term) if term else SEEDS[category],
                                     country, selected, SEEDS, read_source, matches, category_matches)
                         if dropship_mode else None)
        readers = [publication_candidates]
        if selected.keys() & {"gadgets", "smart-home"}:
            readers.append(rss_publications)
        news_tasks = [pool.submit(publications, reader, fetch, topic, term, country, language, selected)
                      for reader in readers if topic and "Publicaties" in platforms and mode not in SUPPLIER_MODES]

        products = [item for task in product_tasks for item in collect(task, errors)]
        offers = list(catalogue_suppliers(products))
        hama = collect(hama_task, errors) if hama_task else []
        offers.extend(hama)
        products.extend({**item, "source": profile["name"], "image": ""} for profile, item in hama)
        if dropship_task:
            offers.extend(collect(dropship_task, errors))
            offers.extend(cj_reference(term, selected, matches))
        articles = [item for task in news_tasks for item in collect(task, errors)]

    products = list({item["url"]: item for item in products}.values()) if product_mode else []
    news = sorted({item["url"]: item for item in articles}.values(), key=lambda item: item["date"], reverse=True)
    recent = (date.today() - timedelta(days=365)).isoformat()
    trends = [item for item in news if item["date"] >= recent and item["kind"] in {
        "Lanceringen en varianten", "Markt en niche", "Veiligheid en terugroepacties",
    }][:8]
    suppliers = unique_suppliers(offers, supplier_filter)
    return {
        "term": term, "country_name": name, "category_name": categories.get(category, "All products"),
        "links": research_links(" ".join(part for part in (term, categories.get(category)) if part),
                                platforms, country, language),
        "products": products, "suppliers": suppliers, "news": news, "trends": trends,
        "supplier_products": sum(company["product_count"] for company in suppliers),
        "topic": topic,
        "preferred_tab": DEFAULT_TABS.get(mode, "products"),
        "source_unavailable": bool(errors), "error": None,
    }
