"""Public research adapters. Each result retains the source that supports it."""
from concurrent.futures import ThreadPoolExecutor, wait
from functools import partial
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import json
import re
from time import monotonic
from urllib.parse import quote, urlencode, urlsplit
import xml.etree.ElementTree as ET

import requests

from nv_research_assessment import Fact
from nv_research_safety import gtin

UNKNOWN = "Niet bevestigd"
FILTERS = {
    "all": "Alle leveranciers",
    "eu": "Binnen EU",
    "international": "Buiten EU",
    "dropship": "Alleen dropshipping",
    "trade": "Groothandel / fabrikant",
}
SYNCEE_HELP = "https://help.syncee.com/en/articles/8925120-shipping-information"
# Explicit company/brand location evidence, separate from the ship-from
# warehouse in the marketplace product record.
SYNCEE_SUPPLIER_ORIGINS = {
    "221318": ("CN", "https://www.gflai.com/"),
    "234156": ("AU", "https://oliveoilskincare.com.au/policies/privacy-policy"),
    "253317": ("AU", "https://syncee.com/supplier/253317/nne-living"),
    "312377": ("HU", "https://www.hoppline.eu/shop_contact.php?tab=shipping"),
    "546145": ("GB", "https://cashymart.com/nb/pages/terms-of-services"),
    "727418": ("AU", "https://www.lifebay.com.au/pages/contact"),
    "802498": ("US", "https://www.tips-usa.com/pdf_profile.cfm?RecordID=754BC7B3144883AED4D6869405BE32BC"),
    "1459958": ("IN", "https://fasderma.com/pages/contact-us"),
    "1569216": ("NL", "https://pe-cosmetics.com/nl"),
    "105656": ("IT", "https://www.maiden-art.com/policies/legal-notice"),
    "279866": ("RO", "https://www.orderchamp.com/store/tomescu-st-cristian-pfa/listings/1842806604644353"),
}
SYNCEE_INTEGRATION = "https://help.syncee.com/en/articles/8885881-how-to-install-syncee-to-your-wordpress-store-woocommerce-integration"
CJ_TERMS = "https://oss.cjdropshipping.com/pdf/CJ%20Dropshipping%20Agreement%202025.6.12.pdf"
CJ_PRODUCT = (
    "https://cjdropshipping.com/product/"
    "mini-fast-charging-magnetic-wireless-power-bank-5000-mah-portable-p-1462611587847294976.html"
)
TECHRADAR = "https://www.techradar.com"
ANDROID_CENTRAL = "https://www.androidcentral.com"
HURTEL = "https://hurtel.com"
HURTEL_BUSINESS = HURTEL + "/en/about/hurtel-wholesale-become-our-b2b-partner-192"
HURTEL_FAQ = HURTEL + "/pl/help/faq-najczesciej-zadawane-pytania-w-hurtowni-hurtel-210"
ARTICLE_PATH = re.compile(r"/(?:[a-z0-9-]+/){1,4}[a-z0-9-]+/?")
INTENTS = (
    ("Veiligheid en terugroepacties", r"recall|recalled|fire risk|safety alert|terugroepactie"),
    ("Reviews en vergelijkingen", r"review|comparison|compared|vs|test|tested|best|beste"),
    ("Lanceringen en varianten", r"launch(?:es|ed)?|new|release(?:s|d)?|announc(?:e|es|ed)|unveil(?:s|ed)?|nieuw"),
    ("Markt en niche", r"trend(?:s)?|market|niche|marktontwikkeling"),
)


def visible_text(html):
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", html)).split())


def google_search_trends(fetch, country, read):
    """Read the public Trending Now feed. Its traffic figures are approximate searches."""
    url = "https://trends.google.com/trending/rss"
    document = ET.fromstring(read(fetch, url, {"geo": country}, max_bytes=512_000))
    if document.tag != "rss" or document.find("channel") is None:
        raise ValueError("Onverwachte Google Trends-feed")
    now = datetime.now(timezone.utc)
    namespace = "{https://trends.google.com/trending/rss}"
    for item in document.findall("./channel/item")[:100]:
        title = (item.findtext("title") or "").strip()[:160]
        volume = (item.findtext(namespace + "approx_traffic") or "").strip()
        try:
            observed = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (ValueError, TypeError, OverflowError):
            continue
        if not title or observed.tzinfo is None or not now - timedelta(days=7) <= observed <= now + timedelta(minutes=5):
            continue
        yield {
            "title": title, "date": observed.date().isoformat(),
            "indicator": volume if re.fullmatch(r"[\d,. ]{1,14}\+?", volume) else "",
            "url": "https://trends.google.com/trending?" + urlencode({"geo": country, "q": title}),
        }


EDITORIAL_FEEDS = {
    "beauty-care": ("Allure", "https://www.allure.com/feed/rss", {"shopping"}),
    "home-living": ("The Kitchn", "https://www.thekitchn.com/main.rss", {"tools", "kitchen tools"}),
}


def editorial_feed(fetch, category, read):
    source, feed, included = EDITORIAL_FEEDS[category]
    document = ET.fromstring(read(fetch, feed, {}, max_bytes=512_000))
    if document.tag != "rss" or document.find("channel") is None:
        raise ValueError("Onverwachte publicatiefeed")
    articles = []
    for row in document.findall("./channel/item")[:40]:
        tags = {(x.text or "").strip().casefold() for x in row.findall("category")}
        if not included & tags or any("sponsor" in tag or "advertorial" in tag for tag in tags):
            continue
        title = (row.findtext("title") or "").strip()[:240]
        address = urlsplit((row.findtext("link") or "").strip())
        if (address.scheme != "https" or address.netloc != urlsplit(feed).netloc
                or not re.fullmatch(r"/(?:[a-z0-9-]+/){0,3}[a-z0-9-]+/?", address.path) or not title):
            continue
        try:
            published = parsedate_to_datetime(row.findtext("pubDate") or "").date()
        except (ValueError, TypeError, OverflowError):
            continue
        if not date.today() - timedelta(days=90) <= published <= date.today():
            continue
        articles.append({
            "title": title, "summary": "", "source": source, "kind": "Reviews en vergelijkingen",
            "date": published.isoformat(), "date_label": "Publicatie", "url": address._replace(query="", fragment="").geturl(),
        })
    return articles[:10]


def supplier(name, origin, kind, website, *, dropshipping=None, shipping=UNKNOWN, checked=None,
             integration=UNKNOWN, orders=UNKNOWN, returns=UNKNOWN, evidence=(), identity=None,
             identity_source=None, registration=None, business=None, dropshipping_source=None, minimum=UNKNOWN):
    return {
        "name": name, "origin": origin, "kind": kind, "website": website,
        "identity": identity, "identity_source": identity_source, "registration": registration,
        "business": business, "dropshipping_source": dropshipping_source,
        "dropshipping": dropshipping, "shipping": shipping, "checked": checked or date.today().isoformat(),
        "warehouse": UNKNOWN, "purchase_price": UNKNOWN, "stock": UNKNOWN, "lead_time": UNKNOWN,
        "shipping_cost": UNKNOWN, "minimum": minimum, "integration": integration,
        "orders": orders, "returns": returns, "evidence": evidence,
    }


def hama_products(fetch, term, country, read, matches, relevant, product_matches):
    locale = {"NL": "nl/nl", "DE": "de/de"}[country]
    business = {
        "NL": "https://business.nl.hama.com/nieuw-sluit-u-nu-aan/klant-worden",
        "DE": "https://business.de.hama.com/neu-jetzt-registrieren/als-neukunde-registrieren",
    }[country]
    name = "Hama B.V." if country == "NL" else "Hama"
    profile = supplier(name, country, "Distributeur", business, business=True,
                       identity=f"hama:{country}", identity_source=business,
                       evidence=(("Vestiging en verkoopkantoren", "https://company.hama.com/about-us/worldwide"),))
    root = "https://www.hama.com"
    search = term or "bluetooth speaker"
    # The catalogue uses powerbank as one word and local writing for capacity.
    query = re.sub(r"(?i)\bpower\s+bank\b", "powerbank", search)
    query = re.sub(r"(?<=\d)[. ](?=\d{3})|(?<=\d)\s+(?=mah)", "", query, flags=re.I)
    try:
        body = read(fetch, f"{root}/{locale}/catalogsearch/result/", {"q": query}, max_bytes=2_500_000).decode("utf-8")
    except (requests.RequestException, ValueError, OSError):
        body = ""
    paths = rf'{re.escape(root)}/{locale}/[a-z0-9-]+-[0-9]{{8}}'
    candidates = re.findall(
        rf'<a\s+class="product-item-info"\s+href="({paths})"[^>]*>(.*?)</a>',
        body, re.S,
    )
    listings = []
    for url, card in candidates[:20]:
        name_match = re.search(r'<strong class="product name product-item-name">(.{1,350}?)</strong>', card, re.S)
        if name_match and relevant("gadgets", visible_text(name_match[1])) and product_matches(term, visible_text(name_match[1])):
            listings.append({"title": visible_text(name_match[1]), "url": url, "category": "gadgets"})

    # Direct product record covers a model that the public search index omits in some locales.
    model = "Hama Qi2 magnetische draadloze powerbank 10000mAh 15W"
    # USB-C is a detail-page specification, so allow that model to be examined
    # and let the actual product details decide whether it qualifies.
    if term and product_matches(term, model, "USB-C"):
        product_path = {
            "NL": "qi2-draadloos-power-pack-10000mah-magnetisch-inductief-opladen-15w-ant-00201752",
            "DE": "qi2-kabelloses-power-pack-10000mah-magnetisch-induktiv-laden-15w-anth-00201752",
        }[country]
        url = f"{root}/{locale}/{product_path}"
        try:
            detail = read(fetch, url, {}, max_bytes=1_000_000).decode("utf-8")
        except (requests.RequestException, ValueError, OSError):
            detail = ""
        title = re.search(r"<h1\b[^>]*>(.{1,600}?)</h1>", detail, re.S)
        details = detail.partition('class="product info detailed"')[2][:80_000]
        if title and matches("magnetic power bank 10000mah", visible_text(title[1])) and product_matches(
            term, visible_text(title[1]), visible_text(details),
        ):
            listings.insert(0, {"title": visible_text(title[1]), "url": url, "category": "gadgets",
                                "match_detail": "Specificaties in catalogus gecontroleerd"})
    return [(profile, row) for row in listings]


def hurtel_products(fetch, term, country, categories, seeds, read, index_query, product_matches, relevant):
    eligible = [category for category in categories if category in {"gadgets", "smart-home"}]
    query = index_query(term) if term else seeds[eligible[0]]
    body = read(fetch, HURTEL + "/en/search", {"text": query}, max_bytes=2_000_000).decode("utf-8")
    profile = supplier("Hurtel", "PL", "Groothandel / distributeur", HURTEL_BUSINESS,
                       dropshipping=False, dropshipping_source=HURTEL_FAQ, business=True,
                       identity="hurtel:pl", identity_source=HURTEL_BUSINESS,
                       integration="CSV/XML-catalogus na zakelijke aanmelding",
                       evidence=(("Zakelijke voorwaarden en dropshippingstatus", HURTEL_FAQ),))
    rows = {}
    listing = re.compile(
        r'<a class="search_top__name" href="([^"]+)"><span class="search_top__name_text">([^<]{1,300})'
    )
    hits = list(listing.finditer(body))
    for index, hit in enumerate(hits[:45]):
        url = unescape(hit[1]).split("?", 1)[0]
        if not re.fullmatch(r"https://hurtel\.com/en/products/[a-z0-9-]+-[0-9]+", url):
            continue
        title = visible_text(hit[2])
        category = next((cid for cid in eligible if relevant(cid, title)
                         and product_matches(term or seeds[cid], title)), None)
        if category and url not in rows:
            end = min(hit.end() + 1800, hits[index + 1].start()) if index + 1 < len(hits) else hit.end() + 1800
            code = re.search(r'EAN:\s*</span>\s*<span class="searchList__param_value">([0-9]+)</span>',
                             body[hit.end():end])
            rows[url] = {"title": title, "url": url, "category": category,
                         "gtin": gtin(code[1]) if code else None}
    return [(profile, item) for item in list(rows.values())[:10]]


def syncee_product_details(fetch, url, country, read, *, include_description=False):
    try:
        html = read(fetch, url, {}, max_bytes=4_000_000).decode("utf-8")
        state = re.search(r'<script id="ng-state" type="application/json">(.*?)</script>', html, re.S)
        if not state:
            return {}
        product_id = urlsplit(url).path.split("/")[2]
        endpoint = "https://entry.syncee.com/syncee-product-service/api/v1/products/" + product_id
        product = next((entry["b"] for entry in json.loads(state[1]).values()
                        if isinstance(entry, dict) and entry.get("u") == endpoint), {})
        if not isinstance(product, dict) or product.get("ID") != product_id:
            return {}
    except (requests.RequestException, ValueError, OSError, KeyError, AttributeError):
        return {}

    rows = [row for row in product.get("SHIPPING", []) or [] if isinstance(row, dict)
            and isinstance(row.get("locations"), list)]
    destinations = {location for row in rows for location in row["locations"] if isinstance(location, str)}
    settings = product.get("SETTINGS")
    warehouse = settings.get("warehouseLocation") if isinstance(settings, dict) else None
    warehouse = warehouse[:80] if isinstance(warehouse, str) and warehouse.strip() else UNKNOWN
    result = {"warehouse": warehouse}
    if include_description:
        # The platform's explicit listing label is product evidence. Generic
        # marketing elsewhere on the site is not a confirmation for this SKU.
        title = re.search(r"<title>\s*Dropship\s+([^<]+)</title>", html, re.I)
        product_title = product.get("TITLE")
        listing_title = visible_text(title[1]).removesuffix(" - Syncee") if title else ""
        if listing_title and isinstance(product_title, str):
            public_name = re.sub(r"[^\w]+", " ", listing_title.casefold()).strip()
            record_name = re.sub(r"[^\w]+", " ", visible_text(product_title).casefold()).strip()
        else:
            public_name, record_name = "", ""
        if public_name and (record_name == public_name or record_name.startswith(public_name + " ")):
            result["dropshipping"] = True
            result["dropshipping_source"] = url
            result["facts"] = {"dropshipping": Fact(True, url, date.today().isoformat())}
        result["shipping_nl"] = delivery_status(destinations, "NL")
        result["catalogue_id"] = ("syncee", product_id)
    description = product.get("DESCRIPTION")
    if include_description and isinstance(description, str):
        result["_description"] = visible_text(description[:35_000])
    if country in destinations:
        row = next(row for row in rows if country in (row.get("locations") or []))
        days = (row.get("minShippingDays"), row.get("maxShippingDays"))
        time = (f"{days[0]}–{days[1]} dagen (geschat door aanbieder)"
                if all(type(value) is int for value in days) and 0 < days[0] <= days[1] <= 365 else UNKNOWN)
        if include_description and result.get("dropshipping") is True:
            observed = date.today().isoformat()
            result["facts"]["direct_delivery"] = Fact(True, url, observed)
        # Use a quote only when the route itself identifies its currency.
        currency, cost = row.get("currency"), row.get("shippingCost")
        if (include_description and isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency)
                and type(cost) in (int, float) and 0 <= cost <= 1_000_000):
            result["shipping_cost"] = f"{currency} {cost:.2f}"
        return {**result, "shipping": "Geverifieerd in deze productvermelding", "lead_time": time}
    # A list of destination countries excludes the selected country. An empty
    # list or unrecognized region must stay unconfirmed.
    if delivery_status(destinations, country) == "Niet beschikbaar":
        return {"shipping": "Niet beschikbaar voor dit doelland"}
    return result


def delivery_status(destinations, country):
    if country in destinations:
        return "Bevestigd"
    if destinations and all(re.fullmatch(r"[A-Z]{2}(?:-[A-Z0-9]{1,3})?", code)
                            and code not in {"EU", "WW"} for code in destinations):
        return "Niet beschikbaar"
    return UNKNOWN


def syncee_products(fetch, query, country, categories, seeds, read, matches, relevant, *, term, product_matches,
                    attempts=None, alternates=(), deadline=None, eligible=None, shortlist=None):
    queries = {}
    for variant in (query, *alternates):
        queries.setdefault(variant.casefold(), variant)
    offers = {}
    for variant in list(queries.values())[:3]:
        if deadline is not None and monotonic() >= deadline:
            break
        attempt = {"source": "Syncee", "query": variant, "raw": None}
        result = syncee_search(fetch, variant, country, categories, seeds, read, matches, relevant,
                               term, product_matches, attempt, deadline=deadline, shortlist=shortlist)
        if attempts is not None:
            attempts.append(attempt)
        for profile, item in result:
            offers.setdefault(item["url"], (profile, item))
        if any(eligible is None or eligible(profile) for profile, _ in result):
            break
    return list(offers.values())


def syncee_search(fetch, query, country, categories, seeds, read, matches, relevant,
                  term, product_matches, attempt, deadline=None, shortlist=None):
    candidates = {}
    if deadline is not None:
        # De bron mag nooit langer duren dan de zoekopdracht zelf: lees binnen dezelfde tijdslimiet.
        read = partial(read, deadline=deadline, limit=15, patient=True)

    # Syncee canonicalizes spaces to %20 and drops unrecognized shipping parameters.
    # The public listing does not establish shipping for an individual product.
    query_params = urlencode({"search": query, "searchType": "PRODUCTS"}, quote_via=quote)
    body = read(fetch, "https://syncee.com/collections/1/products?" + query_params,
                {}, max_bytes=4_000_000).decode("utf-8")
    cards = re.findall(r"<app-product-card\b[^>]*>(.*?)</app-product-card>", body, re.S)
    attempt["raw"] = len(cards)
    for card in cards[:60]:
        product = re.search(r'href="(/product/[0-9_]+/[a-z0-9-]+)"[^>]*>\s*<div[^>]+class="h5 title cursor-pointer"[^>]*>([^<]{1,300})</div>', card)
        seller = re.search(r'href="(/supplier/[0-9]+/[a-z0-9-]+)"[^>]*>([^<]{1,140})</a>', card)
        if not product or not seller:
            continue
        title = visible_text(product[2])
        title_match = bool(term and product_matches(term, title))
        category = next((cid for cid in categories if relevant(cid, title)
                         and (title_match or matches(query or seeds[cid], title))), None)
        if not category:
            continue
        seller_url = "https://syncee.com" + seller[1]
        # Only assign a country when supported by the supplier's public profile.
        seller_id = seller[1].split("/")[2]
        origin, location_source = SYNCEE_SUPPLIER_ORIGINS.get(seller_id, (None, None))
        evidence = (("Dropshipping en verzending", SYNCEE_HELP), ("WooCommerce", SYNCEE_INTEGRATION))
        if location_source:
            evidence += (("Vestigingsland", location_source),)
        profile = supplier(visible_text(seller[2]), origin, "Leverancier via Syncee", seller_url,
                           identity=f"syncee:{seller_id}", identity_source=seller_url,
                           orders="Platformfunctie; activering per leverancier controleren",
                           integration="WooCommerce-koppeling via Syncee; aansluiting en voorwaarden controleren",
                           evidence=evidence)
        if shortlist is not None and not shortlist(profile):
            continue
        entries = candidates.setdefault(seller_url, {})
        entries[product[1]] = (profile, {"title": title, "url": "https://syncee.com" + product[1], "category": category})

    # Limit public item lookups. A listing without a confirmed route remains
    # visible as a lead, unless the route is expressly unavailable.
    results = []
    ranked = [sorted(seller.values(), key=lambda offer: not product_matches(term, offer[1]["title"]))
              for seller in candidates.values()]
    ranked.sort(key=lambda seller: not product_matches(term, seller[0][1]["title"]))
    selected = [offer for seller in ranked[:6] for offer in seller[:2]]
    attempt["rejected"] = {
        "productlink, categorie of zoekvariant past niet": min(len(cards), 60) - sum(map(len, candidates.values())),
        "controlelimiet per leverancier of bron": max(0, len(cards) - 60) + sum(map(len, candidates.values())) - len(selected),
    }
    if not selected:
        attempt["exact"] = 0
        return results
    # Maximaal 4 gelijktijdige detailverzoeken (sluit aan op de limiet per bron); wat niet op tijd
    # binnen is, blijft "onbevestigd" in plaats van de zoekopdracht te vertragen.
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        futures = [pool.submit(syncee_product_details, fetch, offer[1]["url"], country, read,
                               include_description=True) for offer in selected]
        wait(futures, timeout=None if deadline is None else max(0.5, deadline - monotonic()))
        details = [future.result() if future.done() and not future.exception() else {} for future in futures]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    for (profile, product), data in zip(selected, details):
        description = data.pop("_description", "")
        if (data.get("shipping") != "Niet beschikbaar voor dit doelland"
                and product_matches(term, product["title"], description)):
            if not product_matches(term, product["title"]):
                data["match_detail"] = "Specificaties in catalogus gecontroleerd"
            company_terms = {key: data[key] for key in ("dropshipping", "dropshipping_source", "shipping", "shipping_nl")
                             if key in data}
            results.append(({**profile, **company_terms}, {**product, **data}))
    attempt["exact"] = len(results)
    attempt["rejected"]["productspecificaties of levering onbevestigd"] = len(selected) - len(results)
    return results


def cj_reference(query, categories, matches):
    # Public CJ listing shows the 10,000 mAh variant. Its public origin may require
    # a browser challenge for current shipping or inventory, so retain the date.
    title = "Magnetic Wireless Power Bank — varianten 5000 mAh en 10000 mAh"
    if "gadgets" not in categories or not query or not matches(query, title):
        return []
    profile = supplier("CJdropshipping", "CN", "Dropshippingpartner", "https://cjdropshipping.com/",
                       dropshipping=True, dropshipping_source=CJ_PRODUCT, checked="2026-11-16",
                       identity="cj:cn", identity_source=CJ_TERMS, business=True,
                       orders="Product- en orderverwerking via CJ API beschikbaar",
                       integration="Publieke CJ-documentatie; account en koppeling vereist",
                       evidence=(("Dropshippingvoorwaarden", CJ_TERMS),
                                 ("Product- en orderverwerking", "https://developers.cjdropshipping.com/en/api/start/standardOperationProcessing.html")))
    return [(profile, {"title": title, "url": CJ_PRODUCT, "category": "gadgets",
                       "facts": {"dropshipping": Fact(True, CJ_PRODUCT, profile["checked"])}})]


def publication_kind(text):
    for label, pattern in INTENTS:
        if re.search(r"\b(?:" + pattern + r")\b", text, re.I):
            return label
    return "Productnieuws"


def publication_candidates(fetch, query, country, language, read):
    return publisher_search(fetch, query, country, language, read, TECHRADAR, "TechRadar")


def android_publications(fetch, query, country, language, read):
    return publisher_search(fetch, query, country, language, read, ANDROID_CENTRAL, "Android Central")


def publisher_search(fetch, query, country, language, read, site, publisher):
    page = read(fetch, site + "/search", {"searchTerm": query},
                max_bytes=3_500_000, language=f"{language}-{country}").decode("utf-8")
    for url, title, article in re.findall(
        rf'<a href="({re.escape(site)}/[^"]+)" class="article-link" aria-label="([^"]+)"[^>]*>\s*<article\b[^>]*>(.*?)</article>',
        page, re.S,
    )[:30]:
        parsed = urlsplit(unescape(url))
        if parsed.query or not ARTICLE_PATH.fullmatch(parsed.path) or parsed.path.startswith(("/search/", "/author/", "/deals/")):
            continue
        time = re.search(r'(Published|last updated)\s+<time datetime="([0-9]{4}-[0-9]{2}-[0-9]{2})T', article, re.I)
        summary = re.search(r'<p class="synopsis">(.{1,700}?)</p>', article, re.S)
        if time:
            yield {"title": visible_text(title), "url": site + parsed.path, "source": publisher,
                   "date": time[2], "date_label": "Publicatie" if time[1].lower() == "published" else "Bijgewerkt",
                   "summary": visible_text(summary[1]) if summary else ""}


def rss_publications(fetch, query, country, language, read):
    # A publisher's own search RSS exposes direct article links and timestamps.
    host = "9to5mac.com"
    body = read(fetch, "https://" + host + "/", {"s": query, "feed": "rss2"},
                max_bytes=2_000_000, language=f"{language}-{country}")
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", body, re.I):
        raise ValueError("Unexpected RSS declaration")
    for item in ET.fromstring(body).findall("./channel/item")[:25]:
        url = item.findtext("link", "")
        if not re.fullmatch(r"https://9to5mac\.com/[0-9]{4}/[0-9]{2}/[0-9]{2}/[a-z0-9-]+/", url):
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", "")).date().isoformat()
        except (ValueError, TypeError):
            continue
        yield {"title": item.findtext("title", "").strip(), "url": url, "source": "9to5Mac",
               "date": published, "date_label": "Publicatie",
               "summary": visible_text(item.findtext("description", ""))}
