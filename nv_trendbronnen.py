"""Trendbronnen en nichevergelijking.

Eerlijkheidsregel: een bron is alleen "live verbonden" als NUVEMIXA er daadwerkelijk gegevens uit haalt. Voor alle
sociale en zoekplatforms is dat nu NIET zo: zij vragen API-toegang, goedkeuring of een abonnement, en scrapen is niet
toegestaan. Daarom toont deze module per bron de echte status, een officiële route en alleen zoeklinks voor handmatig
onderzoek. Er worden geen trendscores, volumes of verkoopcijfers bedacht.
"""
from urllib.parse import quote, quote_plus, urlencode

from nv_product_discovery import COUNTRIES

STATUS = {
    "live": "Live verbonden", "cache": "Gecachte gegevens", "handmatig": "Handmatig onderzoek",
    "api": "API of abonnement nodig", "niet": "Niet beschikbaar",
}
PERIODS = {"7": "7 dagen", "30": "30 dagen", "90": "90 dagen", "365": "12 maanden"}
GOOGLE_PERIOD = {"7": "now 7-d", "30": "today 1-m", "90": "today 3-m", "365": "today 12-m"}
CATEGORIES = {"smart-home": "Smart Home", "beauty-care": "Beauty & Care", "gadgets": "Gadgets", "home-living": "Home & Living",
              "lifestyle-sport": "Lifestyle & Sport", "shop": "Dierenproducten"}
DEFAULT_TERMS = {"smart-home": "smart plug", "beauty-care": "facial cleanser", "gadgets": "bluetooth speaker",
                 "home-living": "kitchen organizer", "lifestyle-sport": "resistance bands", "shop": "cat water fountain"}
PERIOD_SOURCE = {"google-trends": ("7", "30", "90", "365"), "pinterest": ("30", "90", "365"), "youtube": ("7", "30", "90", "365")}

# (sleutel, naam, status, toegang, officiële route, wat het zou leveren, kosten/voorwaarden)
SOURCES = (
    ("catalogi", "Productcatalogi en publicaties (Productonderzoek)", "live",
     "Eigen zoekopdracht bij aangesloten catalogi; resultaat is live of een cache van max. 10 minuten.",
     "Dashboard → Productonderzoek", "Producten, leveranciers, publicaties. Geen vraag- of verkoopcijfers.", "Geen kosten."),
    ("observaties", "Eigen trendobservaties (Viral Product Finder)", "handmatig",
     "Jij legt per product bron, meetperiode en cijfer vast; opslag in PostgreSQL.",
     "Dashboard → Viral Product Finder", "Alleen wat jij zelf met bron en datum invoert.", "Geen kosten."),
    ("google-trends", "Google Trends", "api",
     "Geen aangesloten API. Een officiële Trends-API bestaat alleen met toegang via Google; niet-officiële scrapers worden niet gebruikt.",
     "https://trends.google.com/trends/", "Relatieve zoekinteresse, regio's, seizoenspatroon (7 dagen t/m 12 maanden).", "Toegang/voorwaarden bij Google; niet aangevraagd."),
    ("google-shopping", "Google Shopping", "niet",
     "Geen openbare API voor markt- of prijsvergelijking van andermans producten; Merchant-API is voor eigen producten.",
     "https://shopping.google.com/", "Handmatig prijzen vergelijken via de zoeklink.", "Niet automatisch ophaalbaar."),
    ("youtube", "YouTube en Shorts", "api",
     "YouTube Data API v3 vereist een eigen API-sleutel (gratis quotum, valt onder Google-voorwaarden). Niet ingesteld.",
     "https://developers.google.com/youtube/v3", "Reviews en zoekresultaten per product.", "Sleutel aanmaken door de eigenaar; nog niet gedaan."),
    ("tiktok", "TikTok", "api",
     "Research-API is beperkt tot goedgekeurde onderzoekers; Creative Center is een openbare website voor handmatig gebruik.",
     "https://ads.tiktok.com/business/creativecenter/", "Populaire hashtags, producten en advertenties (handmatig).", "Aanvraag/goedkeuring vereist; niet gedaan."),
    ("instagram", "Instagram en Reels", "api",
     "Hashtag-gegevens via Meta Graph API vereisen een zakelijk account en appreview. Niet ingesteld.",
     "https://developers.facebook.com/docs/instagram-api/", "Hashtag- en media-interactie.", "Appreview door Meta; niet aangevraagd."),
    ("pinterest", "Pinterest Trends", "handmatig",
     "Openbare Pinterest Trends-website voor handmatig onderzoek; API-toegang vereist goedkeuring.",
     "https://trends.pinterest.com/", "Zoektrends in Beauty, Home, Lifestyle, Fashion.", "Gratis te bekijken; geen koppeling."),
    ("reddit", "Reddit", "api",
     "Commercieel gebruik van de Reddit-API vereist toestemming/afspraken; geen koppeling.",
     "https://support.reddithelp.com/hc/en-us/articles/14945211791892", "Terugkerende productvragen en klachten (handmatig via zoeklink).", "Toestemming nodig; niet gedaan."),
)


def sources():
    return [{"key": k, "name": n, "status": s, "status_label": STATUS[s], "access": a, "official": o, "delivers": d, "cost": c}
            for k, n, s, a, o, d, c in SOURCES]


def manual_links(term, country="NL", period="90"):
    """Alleen deeplinks naar openbare zoekpagina's voor handmatig onderzoek; er wordt niets opgehaald of gescrapet."""
    t = (term or "").strip()[:100]
    if not t:
        return []
    geo = country if country in COUNTRIES else "NL"
    per = period if period in PERIODS else "90"
    return [
        {"source": "Google Trends", "period": per in PERIOD_SOURCE["google-trends"],
         "url": "https://trends.google.com/trends/explore?" + urlencode({"q": t, "geo": geo, "date": GOOGLE_PERIOD[per]})},
        {"source": "Google Shopping", "period": False, "url": "https://www.google.com/search?" + urlencode({"tbm": "shop", "q": t, "gl": geo})},
        {"source": "YouTube", "period": False, "url": "https://www.youtube.com/results?search_query=" + quote_plus(t + " review")},
        {"source": "TikTok", "period": False, "url": "https://www.tiktok.com/search?q=" + quote_plus(t)},
        {"source": "Instagram", "period": False, "url": "https://www.instagram.com/explore/tags/" + quote("".join(t.split()).lower()) + "/"},
        {"source": "Pinterest", "period": False, "url": "https://www.pinterest.com/search/pins/?q=" + quote_plus(t)},
        {"source": "Reddit", "period": False, "url": "https://www.reddit.com/search/?q=" + quote_plus(t)},
    ]


def next_steps(term, category, country):
    """Doorklik: trend → productonderzoek → leveranciers/partners → kandidaat. Alleen links naar bestaande menu's."""
    t = (term or "").strip()[:80]
    return {
        "products": "/dashboard?" + urlencode({"section": "onderzoek", "research_run": 1, "research_category": category,
                                               "research_mode": "products", "research_term": t, "research_country": country,
                                               "research_supplier_filter": "all", "research_platform": "Productcatalogi"}),
        "suppliers": "/dashboard?" + urlencode({"section": "onderzoek", "research_run": 1, "research_category": category,
                                                "research_mode": "dropship", "research_term": t, "research_country": country,
                                                "research_supplier_filter": "all", "research_platform": "Productcatalogi"}),
        "partners": "/dashboard?" + urlencode({"section": "partners", "q": t}),
        "candidates": "/dashboard?section=concepten",
        "viral": "/dashboard?section=viral",
    }


def view(args):
    cat_a = args.get("a") if args.get("a") in CATEGORIES else "smart-home"
    cat_b = args.get("b") if args.get("b") in CATEGORIES else "beauty-care"
    country = args.get("land") if args.get("land") in COUNTRIES else "NL"
    period = args.get("periode") if args.get("periode") in PERIODS else "90"
    niches = []
    for cat in (cat_a, cat_b):
        term = (args.get("t_" + cat_a if cat == cat_a else "t_" + cat_b) or DEFAULT_TERMS[cat]).strip()[:80]
        niches.append({"category": cat, "label": CATEGORIES[cat], "term": term, "links": manual_links(term, country, period),
                       "next": next_steps(term, cat, country)})
    return {"sources": sources(), "niches": niches, "form": {"a": cat_a, "b": cat_b, "land": country, "periode": period},
            "categories": CATEGORIES, "countries": COUNTRIES, "periods": PERIODS, "status": STATUS,
            "live_count": sum(1 for s in SOURCES if s[2] in ("live", "cache")),
            "missing_count": sum(1 for s in SOURCES if s[2] in ("api", "niet"))}
