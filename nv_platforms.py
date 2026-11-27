"""Centraal register van onderzoeksplatforms (één bron voor alle onderzoeksmenu's).

Per platform: naam, groep, korte omschrijving, functie, kosten, account, of NUVEMIXA het zelf automatisch raadpleegt,
API, regionale beperking, logo-domein en links per webshopcategorie en periode. Een externe snelkoppeling is nooit
'doorzocht': alleen wat NUVEMIXA zelf ophaalt (RSS, Google Trends Trending now, aangesloten catalogi, Syncee) heet
'Automatisch geraadpleegd'.

Linksjablonen (opgelost in nv-platforms.js, zonder AI en zonder kosten):
  {q}  zoekterm of categoriewoord (URL-gecodeerd)   {qt} idem als hashtag zonder spaties   {qd} idem met streepjes
  {geo} landcode (NL)   {days} 7/14/30   {since} datum JJJJ-MM-DD   {tbs} Google qdr:w/qdr:m   {gt} Google Trends-periode
  {yt} YouTube-uploadfilter   {rt} Reddit week/month   {ttp} TikTok Creative Center 7/30
Periode: 'exact' (7/14/30 precies), 'approx' (7 = week, 14 en 30 = maand), 'max7' (alleen laatste 7 dagen), 'none'.
Logo: het eigen icoon van het platform (favicon/apple-touch-icon op het eigen domein, hotlinked, geen kopie), anders
een neutrale letter-tegel. Er worden geen merkafbeeldingen opgeslagen of bewerkt.
"""
from urllib.parse import quote

GROUPS = {
    "social": "Sociale media",
    "trends": "Trends en advertenties",
    "markets": "Internationale marktplaatsen",
    "suppliers": "Leveranciers en dropshipping",
    "tools": "Gespecialiseerde onderzoeksplatforms",
    "sources": "Productcatalogi en publicaties",
}
CATEGORIES = {"gadgets": "Gadgets", "smart-home": "Smart Home", "beauty-care": "Beauty & Care",
              "home-living": "Home & Living", "lifestyle-sport": "Lifestyle & Sport"}
WORDS = {
    "en": {"gadgets": "gadgets", "smart-home": "smart home", "beauty-care": "beauty products",
           "home-living": "home decor", "lifestyle-sport": "fitness"},
    "nl": {"gadgets": "gadgets", "smart-home": "smart home", "beauty-care": "verzorging", "home-living": "wonen",
           "lifestyle-sport": "sport"},
    "de": {"gadgets": "Gadgets", "smart-home": "Smart Home", "beauty-care": "Beauty", "home-living": "Wohnen",
           "lifestyle-sport": "Fitness"},
    "fr": {"gadgets": "gadgets", "smart-home": "maison connectée", "beauty-care": "beauté",
           "home-living": "décoration maison", "lifestyle-sport": "fitness"},
}
COST = {"free": "Gratis", "limited": "Beperkt gratis", "paid": "Betaald"}
ACCOUNT = {"no": "Geen account nodig", "some": "Account voor sommige functies", "yes": "Account nodig"}
PERIOD = {"exact": "Periode wordt exact toegepast", "approx": "Periode bij benadering (week of maand)",
          "max7": "Toont alleen de laatste 7 dagen", "none": "Periode niet via link in te stellen"}


def P(key, name, group, domain, desc, function, cost, account, home, *, all=None, cat=None, paths=None, lang="en",
      period="none", auto="", api="", region="", logo=""):
    return {"key": key, "name": name, "group": group, "domain": domain, "desc": desc, "function": function,
            "cost": cost, "account": account, "home": home, "all": all or home, "cat": cat, "paths": paths or {},
            "lang": lang, "period": period, "auto": auto, "api": api, "region": region, "logo": logo}


AMAZON = {"gadgets": "electronics", "smart-home": "electronics", "beauty-care": "beauty", "home-living": "kitchen",
          "lifestyle-sport": "sports"}
PLATFORMS = [
    # ---------------------------------------------------------------- sociale media
    P("tiktok", "TikTok", "social", "tiktok.com", "Korte video's; virale producten zie je hier vaak het eerst.",
      "Video's en hashtags zoeken", "free", "some", "https://www.tiktok.com/explore",
      cat="https://www.tiktok.com/search?q={q}", api="Research API alleen voor onderzoeksinstellingen (niet aangesloten)"),
    P("instagram", "Instagram", "social", "instagram.com", "Foto's en Reels met hashtags per niche.",
      "Hashtags en Reels bekijken", "free", "yes", "https://www.instagram.com/explore/",
      cat="https://www.instagram.com/explore/tags/{qt}/", api="Graph API alleen voor eigen bedrijfsaccount (niet aangesloten)"),
    P("facebook", "Facebook", "social", "facebook.com", "Groepen, pagina's en Marketplace.",
      "Berichten, groepen en pagina's zoeken", "free", "yes", "https://www.facebook.com/",
      cat="https://www.facebook.com/search/top?q={q}"),
    P("youtube", "YouTube / Shorts", "social", "youtube.com", "Reviews, unboxings en Shorts.",
      "Video's zoeken, gefilterd op uploaddatum", "free", "no", "https://www.youtube.com/",
      all="https://www.youtube.com/results?search_query=trending+products+shorts&sp={yt}",
      cat="https://www.youtube.com/results?search_query={q}+shorts&sp={yt}", period="approx",
      api="YouTube Data API (gratis sleutel nodig, niet aangesloten)"),
    P("pinterest", "Pinterest", "social", "pinterest.com", "Inspiratie en zoekgedrag rond wonen, beauty en cadeaus.",
      "Pins en ideeën zoeken", "free", "some", "https://www.pinterest.com/ideas/",
      cat="https://www.pinterest.com/search/pins/?q={q}"),
    P("reddit", "Reddit", "social", "reddit.com", "Eerlijke gebruikerservaringen en productaanbevelingen.",
      "Topberichten per week of maand", "free", "no", "https://www.reddit.com/",
      all="https://www.reddit.com/r/shutupandtakemymoney/top/?t={rt}",
      cat="https://www.reddit.com/search/?q={q}&sort=top&t={rt}", period="approx",
      api="Reddit API (aanvraag nodig, niet aangesloten)"),
    P("threads", "Threads", "social", "threads.com", "Tekstberichten van Instagram-gebruikers.",
      "Berichten zoeken", "free", "yes", "https://www.threads.com/", cat="https://www.threads.com/search?q={q}"),
    P("snapchat", "Snapchat", "social", "snapchat.com", "Spotlight: populaire korte video's.",
      "Spotlight bekijken", "free", "some", "https://www.snapchat.com/spotlight"),
    P("x", "X", "social", "x.com", "Realtime berichten en nieuws.", "Berichten zoeken vanaf een datum", "free",
      "yes", "https://x.com/explore", cat="https://x.com/search?q={q}%20since%3A{since}&f=top", period="exact",
      api="X API is betaald (niet aangesloten)"),
    # ---------------------------------------------------------------- trends en advertenties
    P("google", "Google", "trends", "google.com", "Algemene zoekmachine, gefilterd op recente resultaten.",
      "Recente webresultaten", "free", "no", "https://www.google.com/",
      all="https://www.google.com/search?q=trending+products&tbs={tbs}&gl={geo}",
      cat="https://www.google.com/search?q={q}&tbs={tbs}&gl={geo}", period="approx"),
    P("google-trends", "Google Trends", "trends", "trends.google.com", "Zoekinteresse in de tijd en wat nu trending is.",
      "Trending now en zoekinteresse", "free", "no", "https://trends.google.com/",
      all="https://trends.google.com/trending?geo={geo}&hours=168",
      cat="https://trends.google.com/trends/explore?date={gt}&geo={geo}&q={q}", period="approx",
      auto="Trending now (RSS) voor NL, BE en DE wordt automatisch gelezen in Onderzoeksplatforms & trends"),
    P("google-shopping", "Google Shopping", "trends", "shopping.google.com", "Prijzen en aanbieders van een product.",
      "Aanbiedingen en prijzen vergelijken", "free", "no", "https://shopping.google.com/",
      cat="https://www.google.com/search?tbm=shop&gl={geo}&q={q}"),
    P("google-news", "Google News", "trends", "news.google.com", "Nieuws over lanceringen en producten.",
      "Nieuws van de gekozen periode", "free", "no", "https://news.google.com/?hl=nl&gl=NL&ceid=NL:nl",
      all="https://news.google.com/search?q=product%20launch%20when%3A{days}d&hl=nl&gl=NL&ceid=NL%3Anl",
      cat="https://news.google.com/search?q={q}%20when%3A{days}d&hl=nl&gl=NL&ceid=NL%3Anl", period="exact"),
    P("tiktok-cc", "TikTok Creative Center", "trends", "ads.tiktok.com", "Populaire hashtags, nummers en advertenties.",
      "Trending hashtags per periode", "free", "some",
      "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
      all="https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en?period={ttp}",
      period="approx", region="Niet elk land beschikbaar; sommige gegevens alleen na inloggen"),
    P("tiktok-shop", "TikTok Shop", "trends", "shop.tiktok.com", "Winkel binnen TikTok met bestsellers.",
      "Producten en verkopers bekijken", "free", "some", "https://shop.tiktok.com/",
      region="Niet beschikbaar in Nederland (wel o.a. VK, VS, DE, FR, ES, IT)"),
    P("pinterest-trends", "Pinterest Trends", "trends", "trends.pinterest.com", "Stijgende zoektermen op Pinterest.",
      "Zoektrends per land", "free", "yes", "https://trends.pinterest.com/", region="Bedrijfsaccount vereist"),
    P("meta-ads", "Meta Ad Library", "trends", "facebook.com", "Lopende advertenties op Facebook en Instagram.",
      "Advertenties van concurrenten bekijken", "free", "no",
      "https://www.facebook.com/ads/library/",
      all="https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={geo}&media_type=all",
      cat="https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={geo}&q={q}"
          "&search_type=keyword_unordered&media_type=all", api="Ad Library API (identiteitscontrole nodig)"),
    P("google-ads-tc", "Google Ads Transparency Center", "trends", "adstransparency.google.com",
      "Advertenties per adverteerder of domein.", "Advertenties van concurrenten bekijken", "free", "no",
      "https://adstransparency.google.com/", all="https://adstransparency.google.com/?region={geo}"),
    P("exploding-topics", "Exploding Topics", "trends", "explodingtopics.com", "Snel groeiende onderwerpen en merken.",
      "Opkomende onderwerpen", "limited", "some", "https://explodingtopics.com/"),
    P("trend-hunter", "Trend Hunter", "trends", "trendhunter.com", "Innovaties en nieuwe productideeën.",
      "Trendartikelen zoeken", "limited", "some", "https://www.trendhunter.com/"),   # zoeklinks geven 410 (27-11)
    P("product-hunt", "Product Hunt", "trends", "producthunt.com", "Nieuwe producten en apps, dagelijks gerangschikt.",
      "Lanceringen bekijken", "free", "some", "https://www.producthunt.com/",
      cat="https://www.producthunt.com/search?q={q}"),
    P("kickstarter", "Kickstarter", "trends", "kickstarter.com", "Crowdfunding: nieuwe producten vóór de markt.",
      "Nieuwe en populaire projecten", "free", "no", "https://www.kickstarter.com/",
      all="https://www.kickstarter.com/discover/advanced?sort=newest",
      cat="https://www.kickstarter.com/discover/advanced?term={q}&sort=popularity"),
    P("indiegogo", "Indiegogo", "trends", "indiegogo.com", "Crowdfunding met veel gadgets en uitvindingen.",
      "Trending campagnes", "free", "no", "https://www.indiegogo.com/",
      all="https://www.indiegogo.com/explore/all?project_type=campaign&sort=trending",
      cat="https://www.indiegogo.com/explore/all?project_type=campaign&sort=trending&q={q}"),
    # ---------------------------------------------------------------- marktplaatsen
    P("amazon", "Amazon", "markets", "amazon.nl", "Grootste webwinkel; zoeken op product of categorie.",
      "Producten en reviews", "free", "no", "https://www.amazon.nl/", cat="https://www.amazon.nl/s?k={q}"),
    P("amazon-bestsellers", "Amazon Best Sellers", "markets", "amazon.nl", "Best verkochte producten per categorie.",
      "Bestsellerlijst (elk uur bijgewerkt)", "free", "no", "https://www.amazon.nl/gp/bestsellers/",
      paths={k: f"https://www.amazon.nl/gp/bestsellers/{v}/" for k, v in AMAZON.items()}, logo="amazon"),
    P("amazon-movers", "Amazon Movers & Shakers", "markets", "amazon.nl",
      "Grootste stijgers in verkooprang van de afgelopen 24 uur.", "Snelste stijgers", "free", "no",
      "https://www.amazon.nl/gp/movers-and-shakers/",
      paths={k: f"https://www.amazon.nl/gp/movers-and-shakers/{v}/" for k, v in AMAZON.items()}, logo="amazon"),
    P("amazon-new", "Amazon New Releases", "markets", "amazon.nl", "Populairste nieuwe producten.",
      "Nieuwe bestsellers", "free", "no", "https://www.amazon.nl/gp/new-releases/",
      paths={k: f"https://www.amazon.nl/gp/new-releases/{v}/" for k, v in AMAZON.items()}, logo="amazon"),
    P("bol", "bol.com", "markets", "bol.com", "Grootste webwinkel van Nederland en België.", "Producten en prijzen",
      "free", "no", "https://www.bol.com/nl/nl/", cat="https://www.bol.com/nl/nl/s/?searchtext={q}", lang="nl",
      region="Nederland en België", api="Partnerprogramma-API voor verkopers/affiliates (niet aangesloten)"),
    P("aliexpress", "AliExpress", "markets", "aliexpress.com", "Chinese webwinkel, veel dropshipping-producten.",
      "Producten en inkoopprijzen", "free", "no", "https://www.aliexpress.com/",
      cat="https://www.aliexpress.com/w/wholesale-{qd}.html"),
    P("alibaba", "Alibaba", "markets", "alibaba.com", "Groothandel en fabrikanten (B2B).", "Fabrikanten en MOQ",
      "free", "some", "https://www.alibaba.com/", cat="https://www.alibaba.com/trade/search?SearchText={q}"),
    P("ebay", "eBay", "markets", "ebay.com", "Internationale marktplaats, nieuw en tweedehands.",
      "Aanbod en verkochte artikelen", "free", "no", "https://www.ebay.com/",
      cat="https://www.ebay.com/sch/i.html?_nkw={q}"),
    P("etsy", "Etsy", "markets", "etsy.com", "Handgemaakt, personaliseerbaar en vintage.", "Niches en ontwerpen",
      "free", "no", "https://www.etsy.com/", cat="https://www.etsy.com/search?q={q}"),
    P("temu", "Temu", "markets", "temu.com", "Goedkope producten rechtstreeks uit China.", "Prijsniveau en aanbod",
      "free", "no", "https://www.temu.com/nl", cat="https://www.temu.com/search_result.html?search_key={q}"),
    P("shein", "SHEIN", "markets", "shein.com", "Mode, accessoires en woonartikelen.", "Aanbod en prijzen", "free",
      "no", "https://nl.shein.com/", cat="https://nl.shein.com/pdsearch/{q}/"),
    P("walmart", "Walmart", "markets", "walmart.com", "Grootste Amerikaanse retailer.", "Aanbod in de VS", "free",
      "no", "https://www.walmart.com/", cat="https://www.walmart.com/search?q={q}", region="Alleen VS"),
    P("kaufland", "Kaufland", "markets", "kaufland.de", "Duitse marktplaats, ook voor externe verkopers.",
      "Aanbod in Duitsland", "free", "no", "https://www.kaufland.de/",
      cat="https://www.kaufland.de/s/?search_value={q}", lang="de", region="Duitsland en enkele EU-landen"),
    P("cdiscount", "Cdiscount", "markets", "cdiscount.com", "Grote Franse webwinkel.", "Aanbod in Frankrijk",
      "free", "no", "https://www.cdiscount.com/", cat="https://www.cdiscount.com/search/10/{q}.html", lang="fr",
      region="Frankrijk"),
    P("1688", "1688", "markets", "1688.com", "Chinese binnenlandse groothandel van Alibaba.",
      "Fabrieksprijzen in China", "free", "some", "https://www.1688.com/",
      cat="https://s.1688.com/selloffer/offer_search.htm?keywords={q}", region="Chinees; inkoop meestal via agent"),
    P("rakuten", "Rakuten", "markets", "rakuten.co.jp", "Grootste Japanse marktplaats.", "Aanbod in Japan", "free",
      "no", "https://www.rakuten.co.jp/", cat="https://search.rakuten.co.jp/search/mall/{q}/", region="Japan"),
    P("shopee", "Shopee", "markets", "shopee.sg", "Grootste marktplaats van Zuidoost-Azië.", "Aanbod in Azië",
      "free", "no", "https://shopee.sg/", cat="https://shopee.sg/search?keyword={q}",
      region="Zuidoost-Azië en Taiwan"),
    P("lazada", "Lazada", "markets", "lazada.sg", "Marktplaats van Alibaba in Zuidoost-Azië.", "Aanbod in Azië",
      "free", "no", "https://www.lazada.sg/", cat="https://www.lazada.sg/catalog/?q={q}", region="Zuidoost-Azië"),
    # ---------------------------------------------------------------- leveranciers en dropshipping
    P("syncee", "Syncee", "suppliers", "syncee.com", "Dropshipping-marktplaats met (EU-)leveranciers.",
      "Leveranciers en productfeeds", "limited", "yes", "https://syncee.com/",
      auto="Producten worden automatisch doorzocht in Productonderzoek"),
    P("bigbuy", "BigBuy", "suppliers", "bigbuy.eu", "Europese groothandel en dropshipper (Spanje).",
      "Groothandel met EU-magazijn", "paid", "yes", "https://www.bigbuy.eu/en/", api="API bij abonnement"),
    P("cj", "CJdropshipping", "suppliers", "cjdropshipping.com", "Dropshipping met magazijnen in China, EU en VS.",
      "Producten en verzendopties", "free", "yes", "https://cjdropshipping.com/",
      api="API voor geregistreerde gebruikers"),   # zoeklink vraagt menselijke verificatie: alleen homepage
    P("hertwill", "Hertwill", "suppliers", "hertwill.com", "Europese dropshipping-leverancier.",
      "EU-dropshipping", "limited", "yes", "https://www.hertwill.com/"),
    P("spocket", "Spocket", "suppliers", "spocket.co", "Dropshipping met EU- en VS-leveranciers.",
      "Leveranciers per land", "limited", "yes", "https://www.spocket.co/"),
    P("zendrop", "Zendrop", "suppliers", "zendrop.com", "Dropshipping met eigen fulfilment.", "Producten en fulfilment",
      "limited", "yes", "https://www.zendrop.com/"),
    P("faire", "Faire", "suppliers", "faire.com", "Groothandel van onafhankelijke merken voor winkels.",
      "Merken en groothandelsprijzen", "free", "yes", "https://www.faire.com/",
      cat="https://www.faire.com/search?q={q}"),
    P("ankorstore", "Ankorstore", "suppliers", "ankorstore.com", "Europese groothandel van merken voor winkels.",
      "Merken en groothandelsprijzen", "free", "yes", "https://www.ankorstore.com/"),
    P("orderchamp", "Orderchamp", "suppliers", "orderchamp.com", "Groothandelsplatform (onderdeel van Ankorstore).",
      "Merken voor winkels", "free", "yes", "https://www.orderchamp.com/"),
    P("global-sources", "Global Sources", "suppliers", "globalsources.com", "Fabrikanten uit Azië (B2B).",
      "Fabrikanten zoeken", "free", "some", "https://www.globalsources.com/",
      cat="https://www.globalsources.com/searchList/products?keyWord={q}"),
    P("made-in-china", "Made-in-China", "suppliers", "made-in-china.com", "Chinese fabrikanten en exporteurs.",
      "Fabrikanten zoeken", "free", "some", "https://www.made-in-china.com/",
      cat="https://www.made-in-china.com/multi-search/{qd}/F1/1.html"),
    P("europages", "Europages", "suppliers", "europages.com", "Europese bedrijvengids met fabrikanten.",
      "Europese fabrikanten zoeken", "free", "no", "https://www.europages.com/"),
    P("kompass", "Kompass", "suppliers", "kompass.com", "Internationale bedrijvengids.", "Bedrijven per branche",
      "limited", "some", "https://www.kompass.com/"),
    P("dhgate", "DHgate", "suppliers", "dhgate.com", "Chinese groothandel in kleine aantallen.",
      "Kleine groothandelsorders", "free", "no", "https://www.dhgate.com/",
      cat="https://www.dhgate.com/wholesale/search.do?searchkey={q}"),
    # ---------------------------------------------------------------- gespecialiseerde tools
    P("sell-the-trend", "Sell The Trend", "tools", "sellthetrend.com", "Productonderzoek voor dropshipping.",
      "Productonderzoek", "paid", "yes", "https://www.sellthetrend.com/"),
    P("minea", "Minea", "tools", "minea.com", "Advertentiespionage voor TikTok, Facebook en Pinterest.",
      "Advertentie- en productonderzoek", "limited", "yes", "https://www.minea.com/"),
    P("dropship-io", "Dropship.io", "tools", "dropship.io", "Shopify-winkels en productverkopen schatten.",
      "Dropshippingonderzoek", "limited", "yes", "https://www.dropship.io/"),
    P("niche-scraper", "Niche Scraper", "tools", "nichescraper.com", "Productideeën uit winkels en advertenties.",
      "Productontdekking", "limited", "yes", "https://nichescraper.com/"),
    P("ecomhunt", "Ecomhunt", "tools", "ecomhunt.com", "Dagelijks geselecteerde producten.", "Productideeën",
      "limited", "yes", "https://ecomhunt.com/"),
    P("pipiads", "Pipiads", "tools", "pipiads.com", "TikTok-advertenties doorzoeken.", "TikTok-advertentieonderzoek",
      "limited", "yes", "https://www.pipiads.com/"),
    P("kalodata", "Kalodata", "tools", "kalodata.com", "Analyse van TikTok Shop.", "TikTok Shop-onderzoek",
      "limited", "yes", "https://www.kalodata.com/"),
    P("fastmoss", "FastMoss", "tools", "fastmoss.com", "TikTok Shop-producten en creators.", "TikTok-productonderzoek",
      "limited", "yes", "https://www.fastmoss.com/"),
    P("jungle-scout", "Jungle Scout", "tools", "junglescout.com", "Amazon-productonderzoek.", "Amazon-onderzoek",
      "paid", "yes", "https://www.junglescout.com/"),
    P("helium10", "Helium 10", "tools", "helium10.com", "Amazon-tools voor zoekwoorden en producten.",
      "Amazon-productonderzoek", "limited", "yes", "https://www.helium10.com/"),
    P("semrush", "Semrush", "tools", "semrush.com", "Zoekwoorden- en concurrentieonderzoek.", "Markt- en zoekwoordenonderzoek",
      "limited", "yes", "https://www.semrush.com/"),
    P("similarweb", "Similarweb", "tools", "similarweb.com", "Bezoekersschattingen van websites.",
      "Concurrentieonderzoek", "limited", "some", "https://www.similarweb.com/",
      all="https://www.similarweb.com/top-websites/e-commerce-and-shopping/"),
]


def _sources():
    """Productcatalogi en publicaties die NUVEMIXA zelf raadpleegt (uit de bestaande code, niet overgetypt)."""
    import nv_trends
    from nv_product_discovery import CATALOGUES
    rows, seen = [], set()
    for cat, feeds in nv_trends.FEEDS.items():
        for name, url, region in feeds:
            host = url.split("/")[2]
            if host in seen:          # The Verge levert twee feeds: één kaart
                continue
            seen.add(host)
            rows.append(P("feed-" + host, name.split(" – ")[0], "sources", host.removeprefix("www."),
                          f"Redactie ({region}); gedateerde artikelen over {CATEGORIES[cat]}.", "Publicaties (RSS)",
                          "free", "no", "https://" + host + "/",
                          auto="RSS-feed wordt automatisch gelezen in Onderzoeksplatforms & trends"))
    for c in CATALOGUES:
        if c.name in seen:
            continue
        seen.add(c.name)
        rows.append(P("cat-" + c.host, c.name, "sources", c.host.removeprefix("www."),
                      f"Aangesloten productcatalogus ({CATEGORIES.get(c.category, c.category)}).",
                      "Productcatalogus", "free", "no", f"https://{c.host}/",
                      auto="Catalogus wordt automatisch doorzocht in Productonderzoek"))
    return rows


def all_platforms():
    return PLATFORMS + _sources()


def _fill(template, q):
    return (template.replace("{q}", quote(q, safe="")).replace("{qt}", quote("".join(q.split()).lower(), safe=""))
            .replace("{qd}", quote("-".join(q.split()), safe="-")))


def links(p):
    """Per categorie een sjabloon waarin alleen nog periode/land staan (+ 'term' met {q} voor een eigen zoekterm)."""
    words = WORDS.get(p["lang"], WORDS["en"])
    out = {"all": p["all"]}
    for cat in CATEGORIES:
        if cat in p["paths"]:
            out[cat] = p["paths"][cat]
        elif p["cat"]:
            out[cat] = _fill(p["cat"], words[cat])
        else:
            out[cat] = p["all"]
    out["term"] = p["cat"] or ""
    return out


def card(p):
    from nv_platform_logos import LOGOS
    row = {k: p[k] for k in ("key", "name", "group", "domain", "desc", "function", "period", "auto", "api", "region")}
    row.update(logo_url=LOGOS.get(p["logo"] or p["key"], ""), initial=p["name"][:1].upper(),
               cost=COST[p["cost"]], cost_key=p["cost"], account=ACCOUNT[p["account"]], account_key=p["account"],
               period_label=PERIOD[p["period"]], links=links(p), category_link=bool(p["cat"] or p["paths"]),
               home=p["home"])
    return row


def resolve(url, period_days=14, geo="NL", today=None):
    """Zelfde vervanging als nv-platforms.js (voor tests en de linkcontrole)."""
    from datetime import date, timedelta
    today = today or date.today()
    week = period_days <= 7
    values = {"{geo}": geo, "{days}": str(period_days), "{since}": (today - timedelta(days=period_days)).isoformat(),
              "{tbs}": "qdr:w" if week else "qdr:m", "{gt}": "now%207-d" if week else "today%201-m",
              "{yt}": "EgIIAw%253D%253D" if week else "EgIIBA%253D%253D", "{rt}": "week" if week else "month",
              "{ttp}": "7" if week else "30"}
    for token, value in values.items():
        url = url.replace(token, value)
    return url


def view(id, title, lead, groups=None, *, cat_source="", period_source="", term_source="", country_source="",
         compact=False, open_all=False, open_first=True, panel=True):
    """Context voor _platform_cards.html. groups: welke groepen (standaard alle). *_source: CSS-selector van een
    bestaand veld op de pagina (categorie, periode, zoekterm, land). Zonder categorie-/periodeveld krijgt het blok een
    eigen compacte bediening. Geen AI, geen netwerkverkeer: alleen links."""
    groups = groups or list(GROUPS)
    rows = []
    for p in all_platforms():
        if p["group"] in groups:
            row = card(p)
            row["href"] = resolve(row["links"]["all"], 14)
            rows.append(row)
    return {"id": id, "title": title, "lead": lead,
            "groups": [(g, GROUPS[g], [r for r in rows if r["group"] == g]) for g in groups],
            "count": len(rows), "auto": sum(1 for r in rows if r["auto"]), "cat_source": cat_source,
            "period_source": period_source, "term_source": term_source, "country_source": country_source,
            "compact": compact, "open_all": open_all, "open_first": open_first, "panel": panel,
            "categories": CATEGORIES}
