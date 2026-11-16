"""Product and editorial research using first-party catalogues and screened RSS."""
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
import json
import re
from time import monotonic
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

import requests

from nv_research_assessment import Fact, assess_offer
from nv_research_identity import approved_catalogue_identity, company_key, offer_key
from nv_research_intent import (
    MEASURE, STOP_WORDS, candidate_queries, index_query, infer_categories,
    matches, normalize,
    offer_match, power_bank_query, subject_for,
)
from nv_research_safety import gtin, recent_alerts

from nv_research_sources import (
    FILTERS, UNKNOWN, cj_reference, hama_products, hurtel_products, publication_candidates,
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
EMPTY_RESULTS = "De geraadpleegde productbronnen leverden geen bevestigde match op voor deze selectie."
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
    Catalogue("Xtorm", "www.xtorm.eu", "gadgets", EU, "power bank",
              r"power ?bank|charger|usb|charging", "https://www.xtorm.eu/pages/contact"),
    Catalogue("Nedis", "nedis-shop.nl", "gadgets", frozenset({"NL", "BE", "DE"}), "powerbank",
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
ORIGINS = {**{code: details[0] for code, details in COUNTRIES.items()}, "CN": "China"}
CATEGORY_HINTS = {
    "gadgets": r"power ?bank|charger|usb|laptop stand|charging|headphones|earbuds|bluetooth speaker",
    "smart-home": r"smart|wifi|zigbee|matter|curtain|hub|sensor|lighting|rgbicww|door lock|camera|doorbell|robot vacuum|robovac|homebase",
    "beauty-care": r"serum|cream|skin|shampoo|retinal|mask|face|facial|hair|body|argan oil|oil|beauty",
    "home-living": r"lamp|chair|sofa|cushion|vase|table|rug|carpet|shelf|lighting|storage|furniture",
    "lifestyle-sport": r"yoga|mat|bolster|block|towel|handdoek|legging|fitness|dumbbell|hiking|sport|resistance band|training",
}
SEEDS = {"gadgets": "power bank", "smart-home": "security camera", "beauty-care": "serum",
         "home-living": "table lamp", "lifestyle-sport": "yoga mat"}
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


def research_links(term, platforms, country, language):
    q = quote(term, safe="")
    urls = {
        "Google": f"https://www.google.com/search?safe=active&gl={country}&hl={language}&q={q}",
        "TikTok": "https://www.tiktok.com/search?q=" + q,
        "Instagram": "https://www.instagram.com/explore/tags/" + quote("".join(normalize(term).split()), safe="") + "/",
        "Facebook": "https://www.facebook.com/search/top?q=" + q,
    }
    return [(platform, urls[platform]) for platform in platforms if platform in urls]


def read_source(fetch, url, params, *, max_bytes=768_000, language=None, deadline=None):
    """Bound untrusted responses and prevent a provider redirect from changing host."""
    headers = {"User-Agent": "NUVEMIXA-Research/1.0"}
    if language:
        headers["Accept-Language"] = language
    now = monotonic()
    expires = min(now + 7, deadline) if deadline is not None else now + 7
    budget = expires - now
    if budget <= 0:
        raise requests.Timeout("Research deadline reached")
    timeout = (min(3, budget * .4), min(5, budget * .6)) if deadline is not None else (3, 5)
    with fetch(url, params=params, timeout=timeout, allow_redirects=False, stream=True,
               headers=headers) as response:
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
    if not re.search(r"\b(?:" + source.category_terms + r")\b", normalize(evidence)):
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


def unique_suppliers(offers, supplier_filter):
    companies = {}
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
        netherlands = profile.get("shipping_nl", UNKNOWN)
        current = company.get("shipping_nl", netherlands)
        if netherlands == "Bevestigd" or current == "Niet beschikbaar":
            current = netherlands
        company["shipping_nl"] = current
        if profile.get("dropshipping") is True and profile.get("dropshipping_source"):
            company["dropshipping"] = True
            company["dropshipping_source"] = profile["dropshipping_source"]
        company["evidence"] = tuple(dict.fromkeys((*company["evidence"], *profile["evidence"])))

    filtered = []
    for company in companies.values():
        if supplier_filter == "eu" and company["region"] != "eu":
            continue
        if supplier_filter == "international" and company["region"] != "international":
            continue
        if supplier_filter == "dropship" and company["dropshipping"] is not True:
            continue
        if supplier_filter == "trade" and company["business"] is not True:
            continue
        company["origin_name"] = ORIGINS.get(company["origin"], UNKNOWN)
        company["role"] = supplier_role(company)
        company["product_count"] = len(company["products"])
        company["products"] = sorted(company["products"].values(),
                                     key=lambda product: not product.get("shipping", "").startswith("Geverifieerd"))
        filtered.append(company)
    return filtered


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
    response = getattr(error, "response", None)
    if response is not None:
        return f"HTTP {response.status_code}"
    if isinstance(error, requests.Timeout):
        return "time-out"
    if isinstance(error, requests.RequestException):
        return "verbindingsfout"
    return "onverwacht of onbruikbaar bronantwoord"


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
    inferred = tuple(slug for slug in infer_categories(term) if slug in categories) if category == ALL_PRODUCTS else ()
    if inferred:
        selected = {slug: categories[slug] for slug in inferred}
    from_catalogues = "Productcatalogi" in platforms and mode != "news"
    product_mode = mode in PRODUCT_MODES
    trade_mode = from_catalogues and mode != "dropship" and (product_mode or supplier_filter != "dropship")
    dropship_mode = from_catalogues and mode in {"suppliers", "dropship", "trends", "niche", "products", "product"}
    if supplier_filter == "trade":
        dropship_mode = False
    sources = catalogue_sources(selected, country, product_mode) if trade_mode else []
    topic = article_query(term) if term else SEEDS.get(category, "")
    errors, attempts, names = [], [], {}
    pool = ThreadPoolExecutor(max_workers=16)
    started = monotonic()
    source_deadline = started + 12

    def submit(name, function, *args, **kwargs):
        task = pool.submit(function, *args, **kwargs)
        names[task] = name
        return task

    try:
        product_tasks = [submit(source.name, catalogue_items, source, term, mode, fetch, attempts, started + 7)
                         for source in sources]
        hama_task = (submit("Hama", hama_products, fetch, term, country, read_source, matches, category_matches,
                                 product_matches)
                     if trade_mode and country in {"NL", "DE"} and "gadgets" in selected else None)
        hurtel_task = (submit("Hurtel", hurtel_products, fetch, term, country, selected, SEEDS, read_source,
                                   index_query, product_matches, category_matches)
                       if trade_mode and selected.keys() & {"gadgets", "smart-home"} else None)
        dropship_task = (submit("Syncee", syncee_products, fetch, index_query(term) if term else SEEDS[category],
                                     country, selected, SEEDS, read_source, matches, category_matches,
                                     term=term, product_matches=product_matches,
                                     attempts=attempts, alternates=candidate_queries(term), deadline=source_deadline)
                         if dropship_mode else None)
        readers = [("TechRadar", publication_candidates)]
        if selected.keys() & {"gadgets", "smart-home"}:
            readers.extend((("9to5Mac", rss_publications), ("Android Central", android_publications)))
        news_tasks = [submit(publisher, publications, reader, fetch, topic, term, country, language, selected)
                      for publisher, reader in readers
                      if topic and "Publicaties" in platforms and mode not in SUPPLIER_MODES]

        if term and product_tasks:
            wait(product_tasks, timeout=2.5)
            exact = sum(entry.get("exact", 0) for entry in tuple(attempts))
            if exact == 0 or (exact < 3 and subject_for(normalize(term))):
                fallback = catalogue_sources(selected, country, product_mode, fallback=True)
                product_tasks.extend(submit(source.name, catalogue_items, source, term, mode, fetch, attempts,
                                            source_deadline - 0.25) for source in fallback)

        all_tasks = product_tasks + news_tasks + [task for task in (hama_task, hurtel_task, dropship_task) if task]
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
            offers.extend(collect(dropship_task, errors, names[dropship_task]))
            offers.extend(cj_reference(term, selected, matches))
        articles = [item for task in news_tasks for item in collect(task, errors, names[task])]
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
    suppliers = unique_suppliers(offers, supplier_filter)
    by_url = {item["url"]: profile for profile, item in offers}
    products = [assess_listing(item, by_url.get(item["url"]), country, news, alerts, safety_weeks) for item in products]
    attempts = tuple(attempts)
    unavailable = sorted({entry["source"] for entry in (*errors, *attempts)
                          if entry.get("error") or entry.get("detail_errors")})
    for company in suppliers:
        company["products"] = [
            assess_listing(item, by_url.get(item["url"], company), country, news, alerts, safety_weeks)
            for item in company["products"]
        ]
    return {
        "term": term, "country_name": name, "category_name": categories.get(category, "All products"),
        "links": research_links(" ".join(part for part in (term, categories.get(category)) if part),
                                platforms, country, language),
        "products": products, "suppliers": suppliers, "news": news, "trends": trends,
        "supplier_products": sum(company["product_count"] for company in suppliers),
        "topic": topic,
        "interpretation": {"queries": candidate_queries(term), "categories": [categories[s] for s in selected],
                           "automatic": bool(inferred)},
        "all_sources_failed": bool(sources) and bool(unavailable) and not products and not suppliers
                              and len(unavailable) >= max(1, len(set(names.values())) - 1),
        "preferred_tab": DEFAULT_TABS.get(mode, "products"),
        "source_unavailable": bool(unavailable), "unavailable_sources": unavailable,
        "sources_checked": sorted(set(names.values())),
        "search_attempts": attempts, "source_errors": errors, "alternatives": alternatives, "error": None,
    }
