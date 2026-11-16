"""Live, source-linked product discovery signals for the existing NUVEMIXA dashboard.

A news mention is NOT a verified trend, sales volume, profit estimate or supplier.
No social-network scraping and no invented numbers.
"""
from datetime import datetime, timezone
from urllib.parse import urlencode
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
PLATFORMS = ("Google", "TikTok", "Instagram", "Facebook")
EU_COUNTRIES = {"NL", "BE", "DE", "FR", "ES", "IT", "PL", "AT", "PT", "IE", "SE", "DK", "FI", "CZ", "SK", "HU", "RO", "BG", "GR", "HR", "SI", "LT", "LV", "EE", "LU", "MT", "CY"}
# Discovery destinations, not verified supplier matches or inventory.
SUPPLIER_DIRECTORIES = (
    ("BigBuy", "https://www.bigbuy.eu/"),
    ("Syncee", "https://syncee.com/"),
    ("Spocket", "https://www.spocket.co/"),
)


def research_links(term, platforms):
    from urllib.parse import quote
    q = quote(term, safe="")
    urls = {
        "Google": "https://www.google.com/search?q=" + q,
        "TikTok": "https://www.tiktok.com/search?q=" + q,
        "Instagram": "https://www.instagram.com/explore/tags/" + quote(term.replace(" ", ""), safe="") + "/",
        "Facebook": "https://www.facebook.com/search/top?q=" + q,
    }
    return [(platform, urls[platform]) for platform in platforms if platform in urls]



def _public_rss_search(query, fetch, limit=6):
    """Read public Bing RSS search results. No scraping or inferred metrics."""
    from urllib.parse import urlparse
    url = "https://www.bing.com/search?" + urlencode({"q": query, "format": "rss"})
    try:
        response = fetch(url, timeout=5, headers={"User-Agent": "Mozilla/5.0 NUVEMIXA-Research"})
        response.raise_for_status()
        if len(response.content) > 500_000:
            return []
        root = ET.fromstring(response.content)
        output = []
        for item in root.findall("./channel/item")[:limit]:
            title = (item.findtext("title") or "").strip()[:240]
            link = (item.findtext("link") or "").strip()
            host = urlparse(link).hostname or ""
            if title and link.startswith("https://") and host and not host.endswith(".local"):
                output.append({"title": title, "url": link, "source": host})
        return output
    except (requests.RequestException, ET.ParseError, ValueError, OSError):
        return []


def discover(term, country="NL", mode="trends", platforms=None, fetch=None):
    """Fetch real Google News RSS items; never claim they are platform metrics.

    Fetcher injection supports deterministic tests without outbound requests.
    """
    term = (term or "").strip()[:100]
    if not term:
        return {"error": "Vul een product, niche of zoekterm in.", "items": []}
    country = country if country in COUNTRIES else "NL"
    platforms = [p for p in (PLATFORMS if platforms is None else platforms) if p in PLATFORMS]
    if not platforms:
        return {"error": "Selecteer minimaal één platform.", "items": []}
    name, language, region = COUNTRIES[country]
    search_phrase = term + (" product trend" if mode == "trends" else "")
    params = urlencode({"q": search_phrase, "hl": language + "-" + region, "gl": region, "ceid": region + ":" + language})
    feed_url = "https://news.google.com/rss/search?" + params
    result = {
        "term": term, "country": country, "country_name": name, "mode": mode,
        "platforms": platforms, "links": research_links(term, platforms),
        "items": [], "web_items": [], "supplier_items": [], "error": None, "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "supplier_directories": SUPPLIER_DIRECTORIES if country in EU_COUNTRIES else (),
    }
    try:
        response = (fetch or requests.get)(feed_url, timeout=7, headers={"User-Agent": "NUVEMIXA-Research/1.0"})
        response.raise_for_status()
        if len(response.content) > 500_000:
            raise ValueError("Feed te groot")
        root = ET.fromstring(response.content)
        for item in root.findall("./channel/item")[:10]:
            title = (item.findtext("title") or "").strip()[:240]
            url = (item.findtext("link") or "").strip()
            if not title or not url.startswith("https://"):
                continue
            result["items"].append({
                "title": title, "url": url,
                "published": (item.findtext("pubDate") or "").strip()[:80],
                "source": (item.findtext("source") or "Google Nieuws").strip()[:100],
            })
    except (requests.RequestException, ET.ParseError, ValueError, OSError):
        result["error"] = "Live nieuwsbronnen zijn tijdelijk niet bereikbaar. Probeer later opnieuw."
    fetcher = fetch or requests.get
    # Separate public web searches; a failed source never fabricates results.
    result["web_items"] = _public_rss_search(term + " " + name + " product review", fetcher)
    result["supplier_items"] = _public_rss_search(
        term + " supplier wholesale dropshipping EU warehouse", fetcher
    )
    return result
