"""Product and editorial research using first-party catalogues and screened RSS."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

import requests

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

PLATFORMS = ("Productcatalogi", "Bing", "Google", "TikTok", "Instagram", "Facebook")
MODES = {
    "trends": "Trends en nichekansen",
    "niche": "Direct nicheproducten zoeken",
    "product": "Specifiek product zoeken",
    "suppliers": "Leveranciers zoeken",
}
ALL_PRODUCTS = "shop"
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
# Only editorial paths. Forum posts, internal search, redirects and login paths
# never qualify as article links.
PUBLISHERS = {
    "tweakers.net": r"/(?:nieuws|reviews)/[0-9]+/[a-z0-9-]+\.html",
    "www.bright.nl": r"/(?:nieuws|reviews)/[0-9]+/[a-z0-9-]+\.html",
    "www.rtings.com": r"/[a-z0-9-]+/reviews/(?:[a-z0-9-]+/)*[a-z0-9-]+/?",
    "www.theverge.com": r"/(?:tech|reviews|news)/[0-9]+/[a-z0-9-]+/?",
}
UNSAFE = re.compile(
    r"\b(?:porno?\w*|xxx|nsfw|adult\s+(?:content|video|toy)|sex\s+toy|escort|"
    r"casino|gambling|sign[ -]?in|log[ -]?in|inloggen|aanmelden|oauth|"
    r"gift card|cadeaubon|vip membership|shipping protection)\b", re.IGNORECASE,
)
ALIASES = {
    "magnetische": "magnetic", "magnetisch": "magnetic", "draadloze": "wireless",
    "draadloos": "wireless", "oplader": "charger", "slimme": "smart", "slim": "smart",
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
    value = re.sub(r"\bpower[ -]?banks?\b", "power bank", value)
    value = re.sub(r"(?<=\d)(?=mah\b)", " ", value)
    words = re.findall(r"[^\W_]+", value)
    return " ".join(ALIASES.get(word, word) for word in words)


def matches(search, evidence):
    required = set(normalize(search).split()) - STOP_WORDS
    return bool(required) and required.issubset(normalize(evidence).split())


def editorial_match(search, evidence, categories):
    return matches(search, evidence) and any(
        re.search(r"\b(?:" + source.category_terms + r")\b", normalize(evidence))
        for source in CATALOGUES if source.category in categories
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


def read_source(fetch, url, params):
    """Bound untrusted responses and prevent a provider redirect from changing host."""
    with fetch(url, params=params, timeout=(3, 4), allow_redirects=False, stream=True,
               headers={"User-Agent": "NUVEMIXA-Research/1.0"}) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected source status")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            content.extend(chunk)
            if len(content) > 768_000:
                raise ValueError("Source response is too large")
        return bytes(content)


def catalogue_items(source, term, mode, fetch):
    query = normalize(term) if term else source.seed
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
                or (term and not matches(term, evidence))):
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


def editorial_items(term, country, language, categories, mode, fetch):
    hosts = tuple(PUBLISHERS)[:2] if country in {"NL", "BE"} else tuple(PUBLISHERS)[2:] if country in {"US", "CA"} else ()
    if not term or not hosts:
        return []
    sites = " OR ".join(f"site:{host}" for host in hosts)
    intent = "trend" if mode == "trends" else "review"
    query = f'{normalize(term)} {intent} ({sites})'
    body = read_source(fetch, "https://www.bing.com/search", {
        "q": query, "format": "rss", "adlt": "strict", "cc": country, "mkt": f"{language}-{country}",
    })
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", body, re.IGNORECASE):
        raise ValueError("Unexpected RSS declaration")
    items = []
    for item in ET.fromstring(body).findall("./channel/item")[:20]:
        title = (item.findtext("title") or "").strip()[:240]
        url = (item.findtext("link") or "").strip()
        try:
            parts = urlsplit(url)
            host = parts.hostname
        except ValueError:
            continue
        if (parts.scheme != "https" or host not in hosts or parts.netloc != host
                or not re.fullmatch(PUBLISHERS[host], parts.path) or parts.query
                or UNSAFE.search(f"{title} {unquote(parts.path)}")
                or not editorial_match(term, title, categories)):
            continue
        items.append({"title": title, "source": host, "url": f"https://{host}{parts.path}"})
    return items


def collect(future, errors):
    try:
        return future.result()
    except (requests.RequestException, ET.ParseError, ValueError, KeyError, TypeError, OSError):
        errors.append(True)
        return []


def discover(term, country="NL", mode="trends", platforms=None, fetch=None, *,
             category=ALL_PRODUCTS, categories):
    term = (term or "").strip()[:100]
    if ((category != ALL_PRODUCTS and category not in categories)
            or mode not in MODES or country not in COUNTRIES):
        return {"error": "Kies een geldige webshopcategorie, zoektype en doelland."}
    if term and (not (set(normalize(term).split()) - STOP_WORDS) or UNSAFE.search(term)):
        return {"error": EMPTY_RESULTS}
    if not term and (mode == "product" or category == ALL_PRODUCTS):
        return {"error": "Vul een product of niche in, of kies een specifieke webshopcategorie."}
    platforms = tuple(dict.fromkeys(p for p in (PLATFORMS if platforms is None else platforms) if p in PLATFORMS))
    if not platforms:
        return {"error": "Selecteer minimaal één onderzoeksplatform."}
    fetch = fetch or requests.get
    name, language, _ = COUNTRIES[country]
    selected = categories if category == ALL_PRODUCTS else {category: categories[category]}
    sources = [
        source for source in CATALOGUES
        if "Productcatalogi" in platforms and source.category in selected and country in source.countries
        and (mode != "suppliers" or source.trade_url)
    ]
    errors = []
    with ThreadPoolExecutor(max_workers=7) as pool:
        product_tasks = [pool.submit(catalogue_items, source, term, mode, fetch) for source in sources]
        news_task = (pool.submit(editorial_items, term, country, language, selected, mode, fetch)
                     if "Bing" in platforms and mode != "suppliers" else None)
        products = [item for task in product_tasks for item in collect(task, errors)]
        news = collect(news_task, errors) if news_task else []
    products = list({item["url"]: item for item in products}.values())
    news = list({item["url"]: item for item in news}.values())
    suppliers = [item for item in products if item["trade_url"]]
    return {
        "term": term, "country_name": name, "category_name": categories.get(category, "All products"),
        "links": research_links(" ".join(part for part in (term, categories.get(category)) if part),
                                platforms, country, language),
        "products": products if mode != "suppliers" else [],
        "suppliers": suppliers,
        "news": news,
        "trends": [item for item in news if re.search(r"\btrends?\b", item["title"], re.IGNORECASE)]
        if mode == "trends" else [],
        "source_unavailable": bool(errors),
        "error": None,
    }
