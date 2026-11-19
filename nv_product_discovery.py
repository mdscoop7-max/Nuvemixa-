"""Product and editorial research using first-party catalogues and screened RSS."""
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
import json
import re
import time
from time import monotonic

import nv_source_guard
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

import requests

from nv_research_assessment import Fact, assess_offer
from nv_research_identity import approved_catalogue_identity, company_key, offer_key
from nv_research_intent import (
    MEASURE, STOP_WORDS, SUBJECT_CATEGORIES, candidate_queries, english_query, index_query, infer_categories,
    matches, normalize,
    offer_match, power_bank_query, subject_for,
)
from nv_research_safety import gtin, recent_alerts

from nv_research_sources import (
    EDITORIAL_FEEDS, FILTERS, UNKNOWN, cj_reference, editorial_feed, google_search_trends, hama_products, hurtel_products,
    publication_candidates,
    android_publications, publication_kind, rss_publications, supplier, syncee_products, visible_text,
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
    "CN": ("China", "zh", "CN"),
    "HK": ("Hongkong", "zh", "HK"),
    "TW": ("Taiwan", "zh", "TW"),
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

MANUAL_PLATFORMS = ("Google", "TikTok", "Instagram", "Facebook", "YouTube Shorts", "Pinterest Trends")
PLATFORMS = ("Productcatalogi", "Publicaties", "Google Trends", *MANUAL_PLATFORMS)
RESEARCH_CATEGORIES = {"pets": "Huisdieren"}
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
EMPTY_RESULTS = ("Geen bevestigd product en geen bevestigde leverancier gevonden in de geraadpleegde bronnen. "
                 "Dat betekent niet dat het product niet bestaat: NUVEMIXA kan alleen zoeken in de aangesloten catalogi.")
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
    fallback: bool = False
    locale: str = ""
    api: str = "shopify"


CATALOGUES = (
    # Market coverage follows each provider's shipping policy. Item-level shipping
    # and trade availability still depend on the supplier's terms.
    Catalogue("UGREEN", "eu.ugreen.com", "gadgets", EU - {"CY", "LT", "MT"}, "headphones",
              r"power ?bank|charger|oplader|usb|laptop stand|charging",
              "https://www.ugreen.com/pages/wholesale-program"),
    Catalogue("UGREEN", "us.ugreen.com", "gadgets", frozenset({"US"}), "headphones",
              r"power ?bank|charger|usb|laptop stand|charging",
              "https://www.ugreen.com/pages/wholesale-program"),
    Catalogue("Baseus", "eu.baseus.com", "gadgets", (EU - {"CY", "HR", "MT"}) | {"GB"}, "headphones",
              r"power ?bank|charger|usb|laptop stand|charging", "https://eu.baseus.com/pages/wholesale-program"),
    Catalogue("Baseus", "www.baseus.com", "gadgets", frozenset({"US"}), "headphones",
              r"power ?bank|charger|usb|laptop stand|charging", "https://www.baseus.com/pages/wholesale-program"),
    Catalogue("Xtorm", "www.xtorm.eu", "gadgets", EU, "headphones",
              r"power ?bank|charger|usb|charging", "https://www.xtorm.eu/pages/contact"),
    Catalogue("Nedis", "nedis-shop.nl", "gadgets", frozenset({"NL", "BE", "DE"}), "headphones",
              r"power ?bank|charger|usb|headphones|bluetooth speaker", "https://nedis.com/"),
    Catalogue("Nedis", "nedis-shop.nl", "smart-home", frozenset({"NL", "BE", "DE"}), "slimme camera",
              r"smartlife|smart|wifi|zigbee|camera|doorbell|sensor|energy monitoring", "https://nedis.com/"),
    Catalogue("SwitchBot", "eu.switch-bot.com", "smart-home", frozenset("NL BE DE FR ES IT AT".split()),
              "smart home", r"smart|wifi|zigbee|matter|curtain|gordijn|hub|sensor|lighting|rgbicww|door lock"),
    Catalogue("eufy", "eu.eufy.com", "smart-home", frozenset("NL BE DE FR ES IT AT".split()),
              "camera", r"camera|eufycam|doorbell|deurbel|robot vacuum|robovac|homebase",
              "https://www.eufy.com/eu-en/partner-program"),
    Catalogue("eufy", "us.eufy.com", "smart-home", frozenset({"US"}), "camera",
              r"camera|eufycam|doorbell|robot vacuum|robovac|homebase",
              "https://www.eufy.com/business"),
    Catalogue("Cocunat", "www.cocunat.com", "beauty-care", EU | {"GB", "NO", "CH", "TR"},
              "serum", r"serum|cream|skin|shampoo|retinal|mask|face|facial|hair|body|argan oil|oil|beauty"),
    Catalogue("Ferm Living", "fermliving.com", "home-living",
              EU | frozenset("AU CA CH IN JP KR NO NZ SG TR ZA AE".split()), "lamp",
              r"lamp|chair|stoel|sofa|cushion|kussen|vase|vaas|table|tafel|rug|carpet|shelf|lighting",
              "https://fermliving.com/pages/contact"),
    Catalogue("Manduka", "eu.manduka.com", "lifestyle-sport", EU | {"NO", "CH"},
              "yoga mat", r"yoga|mat|bolster|block|towel|handdoek|legging",
              "https://eu.manduka.com/pages/wholesale-application"),
    Catalogue("Pureoil", "pureoil.nl", "beauty-care", frozenset({"NL"}), "huidolie",
              r"oil|skin|olie|serum|haar|hair", fallback=True),
    Catalogue("Aytira", "aytira.nl", "beauty-care", frozenset({"NL"}), "arganolie",
              r"oil|skin|zeep|olie|serum|hair", fallback=True),
    Catalogue("Aurgan", "aurgan.nl", "beauty-care", frozenset({"NL"}), "argan",
              r"oil|skin|zeep|olie|serum|hair", fallback=True, api="woocommerce"),
    Catalogue("Naissance", "naissance.com", "beauty-care", frozenset({"GB"}), "carrier oil",
              r"oil|cream|skin|hair|massage|soap", "https://naissance.com/pages/trade-accounts", fallback=True),
    Catalogue("McGrocer", "mcgrocer.com", "beauty-care", frozenset({"GB"}), "face cream",
              r"cream|skin|hair|body|cosmetics|fragrance|makeup|deodorant|shampoo", fallback=True),
    Catalogue("Veloura Beauty US", "www.velourabeautyus.com", "beauty-care", frozenset({"US"}), "facial care",
              r"facial|skin|face|cream|beauty", fallback=True),
    Catalogue("Kumi", "www.hellokumi.com", "beauty-care", frozenset({"US"}), "face brush",
              r"facial|skin|face|cream|beauty|hair", fallback=True),
    Catalogue("OpenELAB", "openelab.io", "smart-home", frozenset(), "smart home",
              r"wifi|smart|esp32|zigbee|matter|sensor|camera", "https://openelab.io/pages/request-for-quote",
              fallback=True),
    Catalogue("GORNATION", "www.gornation.com", "lifestyle-sport", EU, "resistance bands",
              r"resistance band|fitness|calisthenics|training|gym|workout|weight",
              "https://www.gornation.com/pages/b2b-inquiries", fallback=True),
    Catalogue("ATLETICA", "atletica.de", "lifestyle-sport", EU, "gym equipment",
              r"resistance band|fitness|training|gym|workout|weight|dumbbell|bench",
              fallback=True, locale="/en"),
    Catalogue("AMEICO", "ameico.com", "home-living", frozenset({"US"}), "table lamp",
              r"lamp|table light|chair|furniture|clock|lighting", fallback=True),
    Catalogue("Zafferano America", "zafferanoamerica.com", "home-living", frozenset({"US"}), "table lamp",
              r"lamp|table light|glass|lighting|cordless", fallback=True),
)
TRADE_PROFILES = {
    "UGREEN": ("CN", "Fabrikant / groothandel"),
    "Baseus": ("CN", "Fabrikant"),
    "Xtorm": ("NL", "Merk / zakelijke leverancier"),
    "Nedis": ("NL", "Merk / distributeur"),
    "eufy": ("CN", "Fabrikant"),
    "Ferm Living": ("DK", "Fabrikant / groothandel"),
    "Manduka": ("NL", "Groothandel"),
    "GORNATION": ("DE", "Fabrikant / groothandel"),
    "Naissance": ("GB", "Groothandel"),
    "OpenELAB": ("CN", "Distributeur / zakelijke offertes"),
}
ORIGINS = {code: details[0] for code, details in COUNTRIES.items()}
CATEGORY_HINTS = {
    "gadgets": r"power ?bank|charger|usb|laptop stand|charging|headphones|earbuds|earphones|headset|bluetooth speaker|speaker|tracker|airtag|key finder|cable|armband|phone holder|smartwatch|smart watch|projector|ssd|webcam|drone|keyboard|mouse|tripod|gimbal|ring light|adapter|hub|action camera|dash ?cam",
    "smart-home": r"smart|wifi|zigbee|matter|curtain|hub|sensor|lighting|rgbicww|door lock|camera|doorbell|robot vacuum|robovac|homebase",
    "beauty-care": r"serum|cream|skin|shampoo|retinal|mask|face|facial|hair|body|argan oil|oil|beauty|trimmer|straightener|curling|nail|massager|massage|mirror|flosser|toothbrush|shaver|epilator|jewelry|brush|scalp|soap dispenser|dryer",
    "home-living": r"lamp|chair|sofa|cushion|vase|table|rug|carpet|shelf|lighting|storage|furniture|organizer|organiser|cable management|box|basket|mirror|desk|kitchen|keuken|air ?fryer|blender|cookware|oven|koffiezet\w*",
    "lifestyle-sport": r"yoga|mat|bolster|block|towel|handdoek|legging|fitness|dumbbell|hiking|sport|resistance band|training|bottle|jump rope|skipping rope|kettlebell|massage gun|bag|backpack|luggage|armband|running|foam roller|scale",
    "pets": r"pet|pets|cat|cats|dog|dogs|huisdier|kat|hond",
}
SEEDS = {"gadgets": "headphones", "smart-home": "security camera", "beauty-care": "serum",
         "home-living": "table lamp", "lifestyle-sport": "yoga mat", "pets": "pet accessories"}
UNSAFE = re.compile(
    r"\b(?:porno?\w*|xxx|nsfw|adult\s+(?:content|video|toy)|sex\s+toy|escort|"
    r"casino|gambling|sign[ -]?in|log[ -]?in|inloggen|aanmelden|oauth|"
    r"gift card|cadeaubon|vip membership|shipping protection|advertorial|sponsored post)\b", re.IGNORECASE,
)
def product_matches(term, identity, description=""):
    return offer_match(term, identity, description)[0] == "exact"


def category_matches(category, evidence):
    return not UNSAFE.search(evidence) and bool(
        re.search(r"\b(?:" + CATEGORY_HINTS[category] + r")\b", normalize(evidence))
    )


def relevance_for(term):
    """Bij een specifieke zoekopdracht beslist de productmatch (merk/type/model); de categorielijst
    CATEGORY_HINTS bewaakt alleen leeg of generiek zoeken. Onveilige vermeldingen blijven altijd geweerd."""
    subject_categories = SUBJECT_CATEGORIES.get(subject_for(normalize(term)))
    if subject_categories:
        return lambda category, evidence: category in subject_categories and not UNSAFE.search(evidence)
    if specific_term(term):
        return lambda category, evidence: not UNSAFE.search(evidence)
    return category_matches


def research_links(term, platforms, country, language):
    q = quote(term, safe="")
    urls = {
        "Google": f"https://www.google.com/search?safe=active&gl={country}&hl={language}&q={q}",
        "TikTok": "https://www.tiktok.com/search?q=" + q,
        "TikTok Creative Center": "https://ads.tiktok.com/creative/creativeCenter",
        "Instagram": "https://www.instagram.com/explore/tags/" + quote("".join(normalize(term).split()), safe="") + "/",
        "Facebook": "https://www.facebook.com/search/top?q=" + q,
        "YouTube Shorts": "https://www.youtube.com/results?search_query=" + quote(term + " shorts", safe=""),
        "Pinterest Trends": "https://trends.pinterest.com/",
        "Google Trends": "https://trends.google.com/trends/explore?geo=" + country + "&q=" + q,
    }
    if "TikTok" in platforms:
        platforms = (*platforms, "TikTok Creative Center")
    return [(platform, urls[platform]) for platform in platforms if platform in urls]


def trend_scope(term):
    clean = normalize(term)
    social = r"(?:tiktok|instagram|pinterest|youtube)(?:\s+(?:producten|products|reels|shorts|producttrends|product trends))?"
    if re.fullmatch(r"(?:tiktok|instagram|pinterest|youtube)\s+product\s?trends", clean):
        return "", "social"
    if not re.search(r"\b(?:trending|viral|viraal|populair(?:e)?|popular|trends?)\b", clean):
        return term, None
    topic = re.sub(r"\b(?:trending|viral|viraal|populair(?:e)?|popular|trends?)\b", "", clean).strip()
    broad = {
        "beautyproducten": "beauty-care", "beauty producten": "beauty-care", "beauty products": "beauty-care",
        "keukenproducten": "home-living", "keuken producten": "home-living", "kitchen products": "home-living",
    }
    if topic in broad:
        return "", broad[topic]
    if re.fullmatch(social, topic):
        return "", "social"
    return topic or term, None


CATEGORY_QUERIES = {
    "sportproducten": "lifestyle-sport", "sport producten": "lifestyle-sport", "sports products": "lifestyle-sport",
    "fitnessproducten": "lifestyle-sport", "fitness products": "lifestyle-sport",
    "beautyproducten": "beauty-care", "beauty producten": "beauty-care", "beauty products": "beauty-care",
}


def google_trend_matches(fetch, country, term, categories, broad):
    rows = []
    for row in google_search_trends(fetch, country, read_source):
        title = row["title"]
        if UNSAFE.search(title):
            continue
        if broad and broad != "social":
            if broad == "home-living" and not re.search(
                r"\b(?:kitchen|keuken|air ?fryer|blender|pannen?|cookware|cookers?|oven|koffiezet\w*)\b", normalize(title),
            ):
                continue
            category = broad if broad in categories and category_matches(broad, title) else None
        else:
            if not term or not product_matches(term, title):
                continue
            category = next((slug for slug in categories if slug in infer_categories(title)), None)
            category = category or next((slug for slug in categories if category_matches(slug, title)), None)
        if category and not any(previous["title"].casefold() == title.casefold() for previous in rows):
            rows.append({**row, "category": categories[category], "source": "Google Trends"})
    return rows[:12]


USER_AGENT = "Mozilla/5.0 (compatible; NUVEMIXA-Research/1.0; +https://trendmix.onrender.com)"
MAX_RETRY_WAIT = 3.0


def read_source(fetch, url, params, *, max_bytes=768_000, language=None, deadline=None, limit=7, patient=False):
    """Bound untrusted responses and prevent a provider redirect from changing host.

    Antwoorden worden 10 minuten gedeeld (nv_source_guard). Bij HTTP 429/503 wordt alleen opnieuw
    geprobeerd als de bron een korte Retry-After meegeeft; bij 403/429 wordt de bron gepauzeerd.
    """
    host = urlsplit(url).netloc
    key = (url, tuple(sorted((params or {}).items())), language, max_bytes)
    return nv_source_guard.shared(key, lambda: _download(fetch, url, params, host, max_bytes, language, deadline, limit, patient))


def _download(fetch, url, params, host, max_bytes, language, deadline, limit, patient=False):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
    if language:
        headers["Accept-Language"] = language
    for attempt in (1, 2):
        nv_source_guard.check(host)
        now = monotonic()
        expires = min(now + limit, deadline) if deadline is not None else now + limit
        budget = expires - now
        if budget <= 0:
            raise requests.Timeout("Research deadline reached")
        timeout = (min(3, budget * .4), min(5, budget * .6)) if deadline is not None else (3, min(5, budget))
        if patient:  # achtergrondtaak: traag eerste antwoord van de bron afwachten (de pagina wacht hier niet op)
            timeout = (min(5, budget * .4), min(12, budget * .9))
        try:
            with nv_source_guard.slot(host), fetch(url, params=params, timeout=timeout, allow_redirects=False,
                                                    stream=True, headers=headers) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("Unexpected source status")
                content = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    content.extend(chunk)
                    if monotonic() > expires:
                        raise requests.Timeout("Research source exceeded request deadline")
                    if len(content) > max_bytes:
                        raise ValueError("Source response is too large")
                return bytes(content)
        except requests.HTTPError as error:
            status = getattr(error.response, "status_code", None)
            wait_for = nv_source_guard.retry_after(error)
            if (attempt == 1 and status in (429, 503) and wait_for is not None and wait_for <= MAX_RETRY_WAIT
                    and budget > wait_for + 2):
                time.sleep(wait_for)
                continue
            nv_source_guard.block(host, status, wait_for)
            raise


def catalogue_items(source, term, mode, fetch, attempts, deadline):
    queries = candidate_queries(term) or (source.seed,)
    if power_bank_query(term) and source.host == "nedis-shop.nl":
        queries = ("magnetische powerbank", *queries)
    alternatives, detail_cache = {}, {}
    queried = set()
    for query in queries[:6]:
        if monotonic() >= deadline:
            break
        if query.casefold() in queried:
            continue
        queried.add(query.casefold())
        attempt = {"source": source.name, "query": query, "raw": None}
        try:
            items = catalogue_candidates(source, term, mode, fetch, query, attempt, detail_cache, deadline)
        except SOURCE_ERRORS as error:
            attempt["error"] = source_error(error)
            attempts.append(attempt)
            # Provider-wide access errors are unlikely to improve on retry.
            if isinstance(error, (requests.RequestException, OSError)):
                break
            continue
        attempts.append(attempt)
        exact = [item for item in items if not item.get("match_missing")]
        if exact:
            return exact
        alternatives.update((item["url"], item) for item in items)
    return list(alternatives.values())[:4]


def catalogue_candidates(source, term, mode, fetch, query, attempt, detail_cache, deadline):
    if source.api == "woocommerce":
        rows = json.loads(read_source(fetch, f"https://{source.host}/wp-json/wc/store/v1/products",
                                      {"search": query, "per_page": 10}, deadline=deadline))
        if not isinstance(rows, list):
            raise ValueError("Unexpected WooCommerce catalogue format")
        products = [woocommerce_item(source, row) for row in rows]
    else:
        products = shopify_candidates(source, mode, fetch, query, deadline)
    if not isinstance(products, list):
        raise ValueError("Unexpected catalogue format")
    attempt.update(raw=len(products), rejected={}, similar=0, exact=0)
    results = []
    for product in products[:10]:
        result, reason = catalogue_product(source, term, fetch, product, detail_cache, deadline)
        if result is None:
            attempt["rejected"][reason] = attempt["rejected"].get(reason, 0) + 1
        else:
            attempt["similar" if result.get("match_missing") else "exact"] += 1
            results.append(result)
    attempt["detail_errors"] = sorted({error for _, error in detail_cache.values() if error})
    return results


def shopify_candidates(source, mode, fetch, query, deadline):
    fields = "title,variants.sku,product_type" if mode == "product" else "title,product_type,tag,variants.sku"
    body = read_source(fetch, f"https://{source.host}{source.locale}/search/suggest.json", {
        "q": query, "resources[type]": "product", "resources[limit]": 10,
        "resources[options][fields]": fields,
    }, deadline=deadline)
    return json.loads(body)["resources"]["results"]["products"]


def woocommerce_item(source, row):
    if not isinstance(row, dict) or not isinstance(row.get("permalink"), str):
        return None
    url = urlsplit(row["permalink"])
    if url.scheme != "https" or url.netloc != source.host or url.query or url.fragment:
        return None
    title = row.get("name")
    return {"id": row.get("id"), "title": unescape(title) if isinstance(title, str) else None,
            "handle": row.get("slug"), "type": "", "url": url.path,
            "body": row.get("description"), "gtin": row.get("global_unique_id")}


def shopify_variant(source, fetch, path, product_id, measures, wifi, details, deadline):
    if path not in details and len(details) < 3:
        try:
            data = json.loads(read_source(fetch, f"https://{source.host}{path}.js", {}, deadline=deadline))
            if not isinstance(data, dict) or data.get("id") != product_id or not isinstance(data.get("variants"), list):
                raise ValueError("Unexpected Shopify variant data")
            details[path] = (data["variants"], "")
        except SOURCE_ERRORS as error:
            details[path] = ((), source_error(error))
    variants, _ = details.get(path, ((), ""))
    for variant in variants:
        if not isinstance(variant, dict) or type(variant.get("id")) is not int or variant["id"] <= 0:
            continue
        title = variant.get("title")
        if isinstance(title, str):
            normalized = normalize(title)
            if measures <= set(MEASURE.findall(normalized)) and (
                not wifi or ("wifi" in normalized.split() and "zigbee" not in normalized.split())
            ):
                return variant
    return {}


def specific_term(term):
    """True bij een zoekopdracht met minstens twee betekenisvolle woorden (bijv. merk en producttype)."""
    return len(set(normalize(term or "").split()) - STOP_WORDS) >= 2


def catalogue_product(source, term, fetch, product, details, deadline):
    if not isinstance(product, dict) or type(product.get("id")) is not int or product["id"] <= 0:
        return None, "ongeldige productvermelding"
    title, handle, kind, raw_url = (product.get(key) for key in ("title", "handle", "type", "url"))
    if not all(isinstance(value, str) for value in (title, handle, kind, raw_url)):
        return None, "ongeldige productvermelding"
    if not title.strip() or not re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", handle):
        return None, "ongeldige productvermelding"
    if source.api == "woocommerce":
        path = raw_url
        if not re.fullmatch(r"/product/[a-z0-9_-]+/?", path) or path.strip("/").split("/")[-1] != handle:
            return None, "geen gecontroleerde productlink"
    else:
        path = f"{source.locale}/products/{handle}"
        if raw_url.split("?")[0] != path:
            return None, "geen gecontroleerde productlink"
    identity = f"{title} {kind}"
    evidence = f"{identity} {handle.replace('-', ' ')}"
    if UNSAFE.search(evidence) or UNSAFE.search(normalize(evidence)):
        return None, "onveilige of irrelevante vermelding"
    # Bij een specifieke zoekterm (merk + type/model) bepaalt de productmatch of een product past. De smalle
    # woordenlijst van de bron beperkte eerder het zoeken tot een paar producttypen (bijv. alleen opladers of oliën).
    # Bij een leeg of generiek eenwoordig zoekwoord ("lamp") bewaakt de woordenlijst de categorie.
    if not specific_term(term) and not re.search(r"\b(?:" + source.category_terms + r")\b", normalize(evidence)):
        return None, "categorie buiten selectie"
    description = product.get("body")
    facts = visible_text(description[:35_000]) if isinstance(description, str) else ""
    level, missing = offer_match(term, identity, facts)
    if not level:
        return None, "producttype, merk of model komt niet overeen"
    variant = {}
    normalized_title = normalize(title)
    sizes = {spec for spec in MEASURE.findall(normalize(term)) if spec[1] == "ml"}
    verify_size = sizes and not sizes <= set(MEASURE.findall(normalized_title))
    verify_wifi = "wifi" in normalize(term).split() and {"wifi", "zigbee"} <= set(normalized_title.split())
    if source.api == "shopify" and (verify_size or verify_wifi):
        variant = shopify_variant(source, fetch, path, product["id"], sizes, verify_wifi, details, deadline)
        if variant:
            level, missing = offer_match(term, identity, facts, variant["title"])
        elif level == "exact" and verify_size:
            missing = ("Inhoudsmaat van de productvariant",)
    image = product.get("image")
    if not isinstance(image, str) or not re.fullmatch(
        r"https://cdn\.shopify\.com/s/files/[a-zA-Z0-9_./%-]+\.(?:jpe?g|png|webp)(?:\?v=\d+)?", image,
    ) or ".." in unquote(image):
        image = ""
    variants = product.get("variants")
    records = [v for v in variants if isinstance(v, dict)] if isinstance(variants, list) else []
    codes = {gtin(row.get("barcode")) for row in records}
    barcode = next(iter(codes)) if len(codes) == 1 and len(variants) == len(records) else None
    url = f"https://{source.host}{path}"
    if variant:
        url += f"?variant={variant['id']}"
        title += f" · {variant['title']}"
        barcode = gtin(variant.get("barcode"))
    return {
        "gtin": barcode or gtin(product.get("gtin")), "catalogue_id": (source.host, product["id"]),
        "title": title.strip()[:240], "url": url, "source": source.name,
        "category": source.category, "image": image, "trade_url": source.trade_url,
        "match_missing": missing,
        "match_detail": "Specificaties in catalogus gecontroleerd" if term and not matches(term, identity) else "",
    }, ""


def article_query(term):
    if power_bank_query(term) and "magnetic" in normalize(term).split():
        return "magnetic power bank"
    subject = re.sub(r"\b(?:usbc|\d+\s+(?:mah|w|gb|ml|mm))\b", "", normalize(term))
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
            elif item["source"] == "Xtorm":
                evidence = (("Zakelijke afdeling en vestiging", "https://www.telco-acc.com/en/"),)
            elif item["source"] == "Nedis":
                evidence = (("Nedis B.V. en vestiging", "https://nedis-shop.nl/en/policies/contact-information"),)
            identity = approved_catalogue_identity(item["source"])
            profile = supplier(item["source"], origin, kind, item["trade_url"], evidence=evidence,
                               identity=identity, identity_source=evidence[0][1] if evidence else item["trade_url"],
                               registration=("NL", "11028854") if item["source"] == "Nedis" else None,
                               business=True)
            yield profile, item


def catalogue_leads(products, offers):
    """Webshops met een gevonden product maar zonder zakelijk bewijs: leads, nadrukkelijk onbevestigd.

    Land en voorwaarden blijven onbekend. Ze verschijnen niet bij de filters EU, buiten EU,
    dropshipping of groothandel, omdat daarvoor bewijs nodig is.
    """
    covered = {item["url"] for _, item in offers}
    sources = {source.name: source for source in CATALOGUES}
    for item in products:
        source = sources.get(item.get("source"))
        if not source or item["url"] in covered or item.get("trade_url"):
            continue
        home = f"https://{source.host}"
        profile = supplier(source.name, None, "Webwinkel (zakelijke voorwaarden niet bevestigd)", home,
                           identity=f"lead:{source.host}", identity_source=home)
        yield profile, item


def supplier_role(company):
    """Eén duidelijke rol per bedrijf. Een fabrikant is niet automatisch een dropshippingleverancier."""
    kind = company.get("kind", "").casefold()
    if company.get("name") == "CJdropshipping":
        return "Marktplaats of platform"
    if company.get("dropshipping") is True and company.get("dropshipping_source"):
        return "Dropshippingleverancier"
    if "via syncee" in kind:
        return "Leverancier via marktplaats"
    if kind.startswith("fabrikant") or kind.startswith("merk"):
        return "Fabrikant of merk"
    if "groothandel" in kind:
        return "Groothandel"
    if "webwinkel" in kind:
        return "Webwinkel (niet bevestigd)"
    return "Leverancier"


EU_WAREHOUSES = {
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic", "czechia", "denmark", "estonia",
    "finland", "france", "germany", "greece", "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg",
    "malta", "netherlands", "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden",
}


NL_WAREHOUSES = {"netherlands", "the netherlands", "nederland", "holland", "nl"}
# Alleen bekende landen buiten de EU tellen als "buiten EU"; een onbekende tekst ("Worldwide") blijft onbekend.
NON_EU_WAREHOUSES = {
    "united kingdom", "uk", "great britain", "england", "china", "hong kong", "united states", "usa", "us",
    "australia", "canada", "turkey", "türkiye", "india", "japan", "south korea", "korea", "taiwan", "vietnam",
    "thailand", "singapore", "switzerland", "norway", "new zealand", "mexico", "brazil", "united arab emirates",
    "uae", "ukraine", "israel", "south africa", "malaysia", "indonesia", "philippines", "pakistan", "serbia",
}
COUNTRY_BASES = {"either": "Vestiging of magazijn", "origin": "Alleen vestigingsland", "warehouse": "Alleen magazijnland"}


def warehouse_class(value):
    name = str(value or "").strip().casefold()
    if name in NL_WAREHOUSES:
        return "nl"
    if name in EU_WAREHOUSES:
        return "eu"
    if name in NON_EU_WAREHOUSES:
        return "international"
    return "unknown"


def logistics(company):
    """Magazijn en aandachtspunten uitsluitend uit bevestigde productgegevens; geen kosten of levertijden verzinnen."""
    values = {}
    products = company["products"].values() if isinstance(company["products"], dict) else company["products"]
    for item in products:
        value = str(item.get("warehouse") or "").strip()
        if value and value != UNKNOWN:
            values.setdefault(value, {"nl": "eu"}.get(warehouse_class(value), warehouse_class(value)))
    lead = next((str(item["lead_time"]) for item in products
                 if item.get("lead_time") and item["lead_time"] != UNKNOWN), None)
    classes = {warehouse_class(value) for value in values}
    if not values:
        return {"warehouse_label": None, "warehouse_region": "unknown", "lead_time_note": lead, "warehouse_classes": set(),
                "logistics_notes": ["Magazijnland niet bevestigd: levertijd, invoerrechten en btw zijn onbekend en "
                                    "moeten bij de leverancier worden nagevraagd."]}
    outside = [name for name, region in values.items() if region == "international"]
    inside = [name for name, region in values.items() if region == "eu"]
    notes = []
    if outside:
        notes.append("Magazijn buiten de EU (" + ", ".join(outside) + "): invoerrechten, btw-afhandeling en extra "
                     "levertijd kunnen gelden. Bedragen en termijnen zijn niet bevestigd.")
    if inside:
        notes.append("Magazijn binnen de EU (" + ", ".join(inside) + "): controleer levertijd, retourvoorwaarden "
                     "en btw-afhandeling bij de leverancier. Bedragen en termijnen zijn niet bevestigd.")
    unknown = [name for name, region in values.items() if region == "unknown"]
    if unknown:
        notes.append("Magazijnland niet eenduidig (" + ", ".join(unknown) + "): telt niet als EU of buiten EU.")
    region = "international" if outside else "eu" if inside else "unknown"
    return {"warehouse_label": ", ".join(values), "warehouse_region": region, "warehouse_classes": classes,
            "lead_time_note": lead, "logistics_notes": notes}


def unique_suppliers(offers, supplier_filter, country_basis="either"):
    companies = {}
    shipping_nl = ("Niet beschikbaar", UNKNOWN, "Bevestigd")
    for profile, item in offers:
        key = company_key(profile)
        company = companies.setdefault(key, {**profile, "products": {}, "region": (
            "unknown" if not profile["origin"] else "eu" if profile["origin"] in EU else "international"
        )})
        item_key = offer_key(item)
        previous = company["products"].get(item_key)
        if previous is None or (item.get("shipping", "").startswith("Geverifieerd") and
                                not previous.get("shipping", "").startswith("Geverifieerd")):
            company["products"][item_key] = item
        if profile["shipping"].startswith("Geverifieerd"):
            company["shipping"] = "Bevestigd voor minstens één getoond product"
        company["shipping_nl"] = max(company.get("shipping_nl", profile.get("shipping_nl", UNKNOWN)),
                                     profile.get("shipping_nl", UNKNOWN), key=shipping_nl.index)
        if profile.get("dropshipping") is True and profile.get("dropshipping_source"):
            company["dropshipping"] = True
            company["dropshipping_source"] = profile["dropshipping_source"]
        company["evidence"] = tuple(dict.fromkeys((*company["evidence"], *profile["evidence"])))

    filtered = []
    for company in companies.values():
        company.update(logistics(company))
        if not supplier_in_scope(company, supplier_filter, country_basis):
            continue
        company["origin_name"] = ORIGINS.get(company["origin"], UNKNOWN)
        company["scope_reason"] = scope_reason(company, supplier_filter, country_basis)
        company["role"] = supplier_role(company)
        company["product_count"] = len(company["products"])
        company["products"] = sorted(company["products"].values(),
                                     key=lambda product: not product.get("shipping", "").startswith("Geverifieerd"))
        filtered.append(company)
    return sorted(filtered, key=lambda company: (
        company.get("shipping_nl") != "Bevestigd",
        company.get("dropshipping") is not True,
        company.get("business") is not True,
    ))


def _origin_class(profile):
    origin = profile.get("origin")
    if not origin:
        # Oudere/vereenvoudigde records hebben alleen een regio (eu/international), nooit 'unknown' als EU.
        return {"eu": "eu", "international": "international"}.get(profile.get("region"), "unknown")
    return "nl" if origin == "NL" else "eu" if origin in EU else "international"


def _matches_class(found, scope):
    if scope == "nl":
        return found == "nl"
    if scope == "eu":
        return found in {"nl", "eu"}
    return found == "international"


def supplier_in_scope(profile, scope, country_basis="either"):
    """Landfilter op vestigingsland en/of bevestigd magazijnland. Onbekend telt nooit als NL, EU of buiten EU."""
    if scope in {"nl", "eu", "international"}:
        by_origin = _matches_class(_origin_class(profile), scope)
        by_warehouse = any(_matches_class(found, scope) for found in profile.get("warehouse_classes") or ())
        if country_basis == "origin":
            return by_origin
        if country_basis == "warehouse":
            return by_warehouse
        return by_origin or by_warehouse
    if scope == "dropship":
        return profile.get("dropshipping") is True and bool(profile.get("dropshipping_source"))
    if scope == "trade":
        return profile.get("business") is True
    return True


def scope_reason(company, scope, country_basis="either"):
    """Korte uitleg waarom een leverancier aan het landfilter voldoet (of welk land bekend is)."""
    origin = ORIGINS.get(company.get("origin"), "") if company.get("origin") else ""
    warehouse = company.get("warehouse_label")
    parts = [f"Vestiging: {origin}" if origin else "Vestiging onbekend",
             f"magazijn: {warehouse}" if warehouse else "magazijn onbekend"]
    if scope in {"nl", "eu", "international"}:
        label = {"nl": "Nederland", "eu": "binnen de EU", "international": "buiten de EU"}[scope]
        by_origin = _matches_class(_origin_class(company), scope)
        basis = "vestiging" if by_origin and country_basis != "warehouse" else "magazijn"
        return f"Voldoet via {basis} ({label}) · " + " · ".join(parts)
    return " · ".join(parts)


def catalogue_sources(categories, country, product_mode, *, fallback=False):
    # Choose the source for the target market first. If a provider has no local
    # storefront, its catalogue can still identify products. The offer stays
    # unconfirmed until destination-level evidence is available.
    selected = {}
    for source in CATALOGUES:
        if source.fallback != fallback or source.category not in categories or not (product_mode or source.trade_url):
            continue
        key = (source.name, source.category)
        if key not in selected or (country in source.countries and country not in selected[key].countries):
            selected[key] = source
    return list(selected.values())


def assess_listing(item, company, country, news, alerts, safety_weeks):
    code = item.get("gtin")
    related = [article for article in news if category_matches(item["category"], article["title"] + " " + article["summary"])]
    if code:
        for article in related:
            if code in {gtin(raw) for raw in re.findall(r"\b[0-9]{8,14}\b", article["title"] + " " + article["summary"])}:
                item = {**item, "facts": {**item.get("facts", {}),
                                          "market_signal": Fact(True, article["url"], article["date"])}}
                break
    alert = alerts.get(code)
    return {**item, "assessment": assess_offer(item, company, country, related, alert,
                                               safety_weeks if code else 0)}


SOURCE_ERRORS = (requests.RequestException, ET.ParseError, ValueError, KeyError, TypeError, OSError)


def source_error(error):
    if isinstance(error, nv_source_guard.SourceBlocked):
        return str(error)
    response = getattr(error, "response", None)
    if response is not None:
        code = response.status_code
        return f"HTTP {code}" + (" (bron beperkt of blokkeert verzoeken vanaf deze server)" if code in (403, 429) else "")
    if isinstance(error, requests.Timeout):
        return "time-out"
    if isinstance(error, requests.RequestException):
        return "verbindingsfout"
    return "onverwacht of onbruikbaar bronantwoord"


SYNCEE_BACKGROUND = 28  # seconden eigen budget van de Syncee-taak; de pagina wacht daar niet op
SOURCE_WINDOW = 12  # seconden die een zoekopdracht maximaal op bronnen wacht
_SYNCEE_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="syncee")


def run_syncee(fetch, query, country, selected, term, alternates, budget, supplier_filter, country_basis="either"):
    attempts = []
    # Het magazijnland is pas na het ophalen bekend: alleen bij 'alleen vestigingsland' vooraf op land selecteren.
    by_origin = country_basis == "origin" or supplier_filter not in {"nl", "eu", "international"}
    results = syncee_products(fetch, query, country, selected, SEEDS, read_source, matches, relevance_for(term),
                              term=term, product_matches=product_matches, attempts=attempts,
                              alternates=alternates, deadline=monotonic() + budget,
                              eligible=lambda profile: supplier_in_scope(profile, supplier_filter, "origin"),
                              shortlist=(lambda profile: supplier_in_scope(profile, supplier_filter, "origin"))
                              if by_origin and supplier_filter in {"nl", "eu", "international"} else None)
    return results, attempts


def start_syncee(fetch, query, country, selected, term, alternates, supplier_filter, country_basis="either"):
    key = ("syncee", query, country, tuple(sorted(selected)), tuple(alternates), term, supplier_filter, country_basis)
    return nv_source_guard.job(key, lambda: _SYNCEE_POOL.submit(
        run_syncee, fetch, query, country, selected, term, alternates, SYNCEE_BACKGROUND, supplier_filter,
        country_basis))


def collect(future, errors, source):
    if not future.done():
        errors.append({"source": source, "error": "tijdslimiet voor zoekopdracht bereikt"})
        future.cancel()
        return []
    try:
        return future.result()
    except SOURCE_ERRORS as error:
        errors.append({"source": source, "error": source_error(error)})
        return []


def product_groups(items):
    grouped = {}
    for item in {item["url"]: item for item in items}.values():
        key = offer_key(item)
        if key in grouped:
            grouped[key]["other_sources"].append({"name": item["source"], "url": item["url"]})
        else:
            grouped[key] = {**item, "other_sources": []}
    return list(grouped.values())


def discover(term, country="NL", mode="trends", platforms=None, fetch=None, *,
             category=ALL_PRODUCTS, categories, supplier_filter="all", infer=True, country_basis="either"):
    term = (term or "").strip()[:100]
    if ((category != ALL_PRODUCTS and category not in categories) or mode not in MODES
            or country not in COUNTRIES or supplier_filter not in FILTERS or country_basis not in COUNTRY_BASES):
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
    original_term = term
    term, broad = trend_scope(term) if mode == "trends" else (term, None)
    catalogue_scope = CATEGORY_QUERIES.get(normalize(term)) if mode != "news" else None
    if catalogue_scope in categories and category in (ALL_PRODUCTS, catalogue_scope):
        term = SEEDS[catalogue_scope]
    selected = categories if category == ALL_PRODUCTS else {category: categories[category]}
    inferred = ()
    if category == ALL_PRODUCTS and infer:  # infer=False: 'Overig / Algemeen' zoekt breed in alle categorieën
        explicit = broad or catalogue_scope
        inferred = (explicit,) if explicit in categories else tuple(slug for slug in infer_categories(term) if slug in categories)
    if inferred:
        selected = {slug: categories[slug] for slug in inferred}
    from_catalogues = "Productcatalogi" in platforms and mode != "news" and not broad
    product_mode = mode in PRODUCT_MODES
    trade_mode = from_catalogues and mode != "dropship" and (product_mode or supplier_filter != "dropship")
    dropship_mode = from_catalogues and mode in {"suppliers", "dropship", "trends", "niche", "products", "product"}
    if supplier_filter == "trade":
        dropship_mode = False
    sources = catalogue_sources(selected, country, product_mode) if trade_mode else []
    topic = article_query(term) if term else ("" if broad else SEEDS.get(category, ""))
    errors, attempts, names, pending = [], [], {}, []
    pool = ThreadPoolExecutor(max_workers=32)
    started = monotonic()
    source_deadline = started + SOURCE_WINDOW

    def submit(name, function, *args, **kwargs):
        task = pool.submit(function, *args, **kwargs)
        names[task] = name
        return task

    try:
        product_tasks = [submit(source.name, catalogue_items, source, term, mode, fetch, attempts, started + 7)
                         for source in sources]
        hama_task = (submit("Hama", hama_products, fetch, term, country, read_source, matches, relevance_for(term),
                                 product_matches)
                     if trade_mode and country in {"NL", "DE"} and "gadgets" in selected else None)
        hurtel_task = (submit("Hurtel", hurtel_products, fetch, term, country, selected, SEEDS, read_source,
                                   index_query, product_matches, relevance_for(term))
                       if trade_mode and selected.keys() & {"gadgets", "smart-home"} else None)
        dropship_task = None
        if dropship_mode:
            variants = candidate_queries(term)
            if variants[:1] == (term,) and english_query(term).casefold() != term.casefold():
                variants = (*variants[1:], term)
            dropship_task = start_syncee(fetch, index_query(term) if term else SEEDS[category], country, selected,
                                         term, variants, "all" if product_mode else supplier_filter, country_basis)
        if dropship_task:
            names[dropship_task] = "Syncee"
        readers = [("TechRadar", publication_candidates)]
        if selected.keys() & {"gadgets", "smart-home"}:
            readers.extend((("9to5Mac", rss_publications), ("Android Central", android_publications)))
        news_tasks = [submit(publisher, publications, reader, fetch, topic, term, country, language, selected)
                      for publisher, reader in readers
                      if topic and "Publicaties" in platforms and mode not in SUPPLIER_MODES]
        if broad in EDITORIAL_FEEDS and broad in selected and "Publicaties" in platforms:
            source = EDITORIAL_FEEDS[broad][0]
            news_tasks.append(submit(source, editorial_feed, fetch, broad, read_source))
        trend_task = (submit("Google Trends", google_trend_matches, fetch, country, term, selected, broad)
                      if mode == "trends" and "Google Trends" in platforms and broad != "social" else None)

        if term and trade_mode:
            wait(product_tasks, timeout=2.5)
            exact = sum(entry.get("exact", 0) for entry in tuple(attempts))
            if exact == 0 or (exact < 3 and subject_for(normalize(term))):
                fallback = catalogue_sources(selected, country, product_mode, fallback=True)
                product_tasks.extend(submit(source.name, catalogue_items, source, term, mode, fetch, attempts,
                                            source_deadline - 0.25) for source in fallback)

        all_tasks = product_tasks + news_tasks + [task for task in (hama_task, hurtel_task, dropship_task, trend_task) if task]
        wait(all_tasks, timeout=max(0, source_deadline - monotonic()))
        products = [item for task in product_tasks for item in collect(task, errors, names[task])]
        alternatives = [item for item in products if item.get("match_missing")]
        products = [item for item in products if not item.get("match_missing")]
        offers = list(catalogue_suppliers(products))
        offers.extend(catalogue_leads(products, offers))
        for task in (hama_task, hurtel_task):
            if task:
                listings = collect(task, errors, names[task])
                offers.extend(listings)
                products.extend({**item, "source": profile["name"], "image": ""} for profile, item in listings)

        if dropship_task:
            if dropship_task.done():
                found = collect(dropship_task, errors, "Syncee")
                if found:
                    offers.extend(found[0])
                    attempts.extend(found[1])
            else:
                # Syncee loopt door op de achtergrond; de pagina wacht er niet langer op en ververst zichzelf.
                pending.append("Syncee")
            offers.extend(cj_reference(term, selected, matches))
        articles = [item for task in news_tasks for item in collect(task, errors, names[task])]
        if broad in selected:
            articles = [{**item, "scope": selected[broad] + " · Redactionele selectie",
                         "category": selected[broad]} for item in articles if not UNSAFE.search(item["title"])]
        search_trends = collect(trend_task, errors, "Google Trends") if trend_task else []
        codes = {item["gtin"] for item in products if item.get("gtin")} | {
            item["gtin"] for _, item in offers if item.get("gtin")
        }
        alerts, safety_weeks = {}, 0
        remaining = 17 - (monotonic() - started)
        if codes and country in EU and remaining > 1:
            task = pool.submit(recent_alerts, fetch, read_source, codes)
            wait([task], timeout=remaining)
            outcome = collect(task, errors, "EU Safety Gate")
            if outcome:
                alerts, safety_weeks = outcome
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if product_mode:
        catalogue_urls = {item["url"] for item in products}
        products.extend({**item, "source": profile["name"], "image": item.get("image", "")}
                        for profile, item in offers if item["url"] not in catalogue_urls)
    products = product_groups(products) if product_mode else []
    alternatives = product_groups(alternatives)[:8] if product_mode and not products else []
    news = sorted({item["url"]: item for item in articles}.values(), key=lambda item: item["date"], reverse=True)
    recent = (date.today() - timedelta(days=365)).isoformat()
    trends = [item for item in news if item["date"] >= recent and item["date_label"] == "Publicatie"
              and item["kind"] in {
        "Lanceringen en varianten", "Markt en niche", "Veiligheid en terugroepacties", "Reviews en vergelijkingen",
    }][:8]
    suppliers = unique_suppliers(offers, supplier_filter, country_basis)
    by_url = {item["url"]: profile for profile, item in offers}
    products = [assess_listing(item, by_url.get(item["url"]), country, news, alerts, safety_weeks) for item in products]
    attempts = tuple(attempts)
    reasons = {}
    for entry in (*errors, *attempts):
        reason = entry.get("error") or ", ".join(entry.get("detail_errors") or ())
        if reason:
            reasons.setdefault(entry["source"], reason)
    unavailable = sorted(reasons)
    for company in suppliers:
        company["products"] = [
            assess_listing(item, by_url.get(item["url"], company), country, news, alerts, safety_weeks)
            for item in company["products"]
        ]
    return {
        "term": original_term, "country_name": name, "category_name": categories.get(category, "All products"),
        "links": research_links(" ".join(part for part in (term or original_term, categories.get(category)) if part),
                                platforms, country, language),
        "products": products, "suppliers": suppliers, "news": news, "trends": trends,
        "search_trends": search_trends, "google_trends_checked": bool(trend_task),
        "supplier_products": sum(company["product_count"] for company in suppliers),
        "topic": topic,
        "interpretation": {"queries": candidate_queries(term), "categories": [categories[s] for s in selected],
                           "automatic": bool(inferred)},
        "supplier_suggestions": [query for query in candidate_queries(term) if query.casefold() != term.casefold()][:4],
        "all_sources_failed": bool(sources) and bool(unavailable) and not products and not suppliers
                              and len(unavailable) >= max(1, len(set(names.values())) - 1),
        "preferred_tab": DEFAULT_TABS.get(mode, "products"),
        "pending_sources": pending,
        "fetched_at": __import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M"),
        "next_steps": __import__("nv_supplier_sources").sources_for(selected, country, term),
        "source_unavailable": bool(unavailable), "unavailable_sources": unavailable,
        "unavailable_reasons": reasons,
        "sources_checked": sorted(set(names.values())),
        "search_attempts": attempts, "source_errors": errors, "alternatives": alternatives, "error": None,
    }
