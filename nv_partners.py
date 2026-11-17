"""Partnerzoekmachine: drie gescheiden samenwerkingsmodellen, elk feit met status en bron.

Model A  directe dropshipping   : bedrijf of platform zegt zelf dat het namens webshops verzendt.
Model B  potentiële partner     : interessant assortiment, maar verzending/inkoop/samenwerking moet nog worden gevraagd.
Model C  affiliatepartner       : commissie via een programma. NUVEMIXA is dan NIET de verkoper; affiliateproducten
                                  komen nooit automatisch in WooCommerce.

Elke eigenschap heeft een status: feit (gelezen op de officiële pagina van het bedrijf), aanwijzing (alleen uit een
derde bron, zoekresultaat of de bestaande code) of onbekend. Niets hieruit is een bestaande overeenkomst; er worden geen
aanvragen of berichten verstuurd. De data is onderzocht op 17-11-2026 en kan veranderen.
"""
from urllib.parse import quote

from flask import abort, flash, redirect, request, url_for

from nv_dashboard_manager import bp
from nv_permissions import allowed

CHECKED = "17-11-2026"
CATEGORIES = {"gadgets": "Gadgets", "beauty-care": "Beauty & Care", "lifestyle-sport": "Lifestyle & Sport",
              "home-living": "Home & Living", "smart-home": "Smart Home"}
EU = frozenset("NL BE DE FR ES IT PL AT PT IE SE DK FI CZ SK HU RO BG GR HR SI LT LV EE LU MT CY".split())
MODELS = {"A": "A · Directe dropshipping", "B": "B · Potentiële dropship-/resellerpartner", "C": "C · Affiliatepartner"}
STATUS = {"aantoonbaar": "Biedt aantoonbaar dropshipping aan", "mogelijk": "Mogelijke partner",
          "affiliate": "Alleen affiliate", "ongeschikt": "Ongeschikt voor NUVEMIXA nu"}
TYPES = {"platform": "Dropshippingplatform", "groothandel": "Groothandel", "merk": "Merk met B2B-programma",
         "webshop": "Webshop", "netwerk": "Affiliatenetwerk", "gids": "Informatiebron"}
FACT, HINT, UNKNOWN = "feit", "aanwijzing", "onbekend"
STATUS_LABEL = {FACT: "Gecontroleerd feit", HINT: "Aanwijzing", UNKNOWN: "Onbekend"}
CRITERIA = (  # (sleutel, label, gewicht)
    ("relevantie", "Relevantie voor categorieën", 3), ("ondersteuning", "Dropship-/resellerondersteuning", 3),
    ("levering", "Levering NL/Europa", 3), ("kwaliteit", "Productkwaliteit", 2), ("prijzen", "Inkoopprijs en marge", 2),
    ("verzending", "Verzendkosten en levertijd", 2), ("voorwaarden", "Retour en zakelijke voorwaarden", 2),
    ("integratie", "API, productfeed of plugin", 2), ("kosten", "Maandelijkse kosten", 2),
    ("affiliate", "Affiliateprogramma", 1), ("aanvraag", "Zakelijke aanvraag vereist", 1),
)
POINTS = {FACT: 1.0, HINT: 0.5, UNKNOWN: 0.0}


def f(text, status=UNKNOWN, url=""):
    return {"text": text, "status": status, "url": url}


def U(text="Niet onderzocht."):
    return f(text)


def entry(name, url, country, ptype, models, status, cats, products, ships, cost, integration, facts, note="", favorable=()):
    """`favorable`: criteria die het bedrijf volgens de gelezen tekst daadwerkelijk positief invult."""
    return {"name": name, "url": url, "country": country, "type": ptype, "models": tuple(models), "status": status,
            "categories": tuple(cats), "products": tuple(products), "ships": ships, "cost": cost,
            "integration": tuple(integration), "facts": facts, "note": note, "favorable": frozenset(favorable)}


PARTNERS = (
    entry("Beautinow", "https://beautinow.com/nl/parfum-dropshipping-europa/", "NL", "groothandel", "A", "aantoonbaar",
          ("beauty-care",), ("parfum", "geuren", "designerparfum", "testers"), {"EU", "GB"}, "onbekend", ("feed",),
          {"relevantie": f("Meer dan 2.000 parfums van 200+ designer- en nichemerken (eigen opgave).", HINT),
           "ondersteuning": f("De pagina biedt dropshipping aan; geen private label.", FACT),
           "levering": f("Verzending vanuit Nederland naar EU en VK; wereldwijd alleen als toekomstplan.", FACT),
           "kwaliteit": f("Merkproducten; echtheid en merkrechten zelf navragen.", HINT),
           "prijzen": U("Geen inkoopprijzen vermeld."),
           "verzending": f("Gratis verzending volgens de pagina (voorwaarden op aparte pagina, niet gelezen); besteld voor 15:00 = zelfde dag verzonden.", FACT),
           "voorwaarden": U("Retour- en zakelijke voorwaarden niet gelezen."),
           "integratie": f("Productfeed beschikbaar; geen API vermeld.", FACT),
           "kosten": U("Geen dropshippingkosten vermeld."),
           "affiliate": U(), "aanvraag": f("Aanvragen via e-mail of contactformulier, met doellanden en verwacht volume.", FACT)},
          "Parfum: let op echtheid, merkrechten en verkoopbeperkingen van merken.",
          ("relevantie", "ondersteuning", "levering", "verzending", "integratie", "aanvraag")),
    entry("Droppery", "https://droppery.io/this-startup-connects-suppliers-and-webshops-with-dropshipping-as-a-service",
          "NL", "platform", "AB", "mogelijk", ("home-living", "beauty-care", "lifestyle-sport"),
          ("meubels", "cosmetica", "horloges", "europese merken"), {"EU"}, "onbekend", ("plugin",),
          {"relevantie": f("Voorbeelden op de pagina: meubels, cosmetica en horloges; geen volledige categorielijst.", FACT),
           "ondersteuning": f("Dropshipping-as-a-service: leveranciers keuren zelf goed welke webshops hun producten verkopen.", FACT),
           "levering": f("Richt zich op Europese webshops; leverlanden per leverancier onbekend.", HINT),
           "kwaliteit": f("Alleen 'kwaliteitsgerichte' Europese retailers; geen kwaliteitsgegevens over producten.", HINT),
           "prijzen": U(), "verzending": U(),
           "voorwaarden": U(),
           "integratie": f("Beschikbaar via Lightspeed- en Sendcloud-appstore. WooCommerce-koppeling niet vermeld.", FACT),
           "kosten": f("Leveranciers betalen een vaste maandprijs; kosten voor webshops niet vermeld (derde bron noemt eigen-site-abonnementen).", HINT),
           "affiliate": U(), "aanvraag": f("Goedkeuring door elke leverancier nodig.", FACT)},
          "Geschikt om kleinere Europese merken te ontdekken; toegang is per merk en niet gegarandeerd.",
          ("ondersteuning", "aanvraag")),
    entry("GOGETTERS", "https://europeanpurpose.com/nl/categorie/europese-dropshipping-platforms-tools", "NL", "platform", "A",
          "mogelijk", tuple(CATEGORIES), ("breed assortiment Europese leveranciers",), {"EU"}, "onbekend", ("plugin",),
          {"relevantie": f("Importeert voorraad van Europese leveranciers; 600.000+ producten volgens het bedrijf (derde bron).", HINT),
           "ondersteuning": f("Dropshipping-app; ondersteuning voor WooCommerce niet gecontroleerd (derde bron noemt Shopify).", HINT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": f("App-integratie; WooCommerce niet bevestigd.", HINT), "kosten": U("Kosten niet gelezen."),
           "affiliate": U(), "aanvraag": U()}, "Alleen via een derde bron gevonden: eigen pagina nog lezen.", ("ondersteuning",)),
    entry("Hertwill", "https://hertwill.com/dropshipping-suppliers-europe", "EE", "platform", "A", "aantoonbaar",
          ("beauty-care", "home-living", "lifestyle-sport"), ("beautyaccessoires", "kleding", "tassen", "kinderproducten"),
          {"EU"}, "gratis+betaald", ("api", "plugin"),
          {"relevantie": f("200+ EU- en VS-merken, 7.000+ producten: Beauty & Personal Care, Home & Garden, Apparel, Footwear, Bags.", FACT, "https://hertwill.com/dropshipping-suppliers-europe"),
           "ondersteuning": f("Dropshippingplatform; EU-leveranciers verzenden vanuit EU-magazijnen.", FACT),
           "levering": f("EU-magazijnen voor EU-leveranciers; per merk controleren.", FACT),
           "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": f("WooCommerce-plugin en dropshipping-API.", FACT),
           "kosten": f("Gratis plan zonder creditcard (5 producten, 10 orders/maand volgens derde bron); betaald €19,99–€49,99 per maand (derde bron).", HINT),
           "affiliate": U(), "aanvraag": f("Account aanmaken.", FACT)}, "", ("relevantie", "ondersteuning", "levering", "integratie", "kosten")),
    entry("SelfNamed", "https://dodropshipping.com/best-dropshipping-suppliers-in-europe-free-and-paid/", "LV", "platform", "A",
          "mogelijk", ("beauty-care",), ("huidverzorging", "haarverzorging", "lichaamsverzorging", "make-up", "private label"),
          {"EU", "US"}, "gratis+betaald", ("plugin",),
          {"relevantie": f("Private-label beautyproducten.", HINT), "ondersteuning": f("Productie in Letland, verzending vanuit EU of VS.", HINT),
           "levering": f("Verzending vanuit EU of VS.", HINT), "kwaliteit": U(), "prijzen": U(), "verzending": U(),
           "voorwaarden": U("Private label: eigen merkrechten en productaansprakelijkheid uitzoeken."),
           "integratie": f("Shopify, WooCommerce, Squarespace, Wix.", HINT),
           "kosten": f("Gratis starten; Pro €29 per maand (derde bron).", HINT), "affiliate": U(), "aanvraag": U()},
          "Alleen via een derde bron; eigen pagina nog lezen.", ("relevantie", "ondersteuning", "levering", "integratie", "kosten")),
    entry("Everspring", "https://dodropshipping.com/best-dropshipping-suppliers-in-europe-free-and-paid/", "EU", "platform", "A",
          "mogelijk", ("home-living",), ("kamerplanten", "bloemen", "planten"), {"EU"}, "betaald", ("api", "plugin"),
          {"relevantie": f("Planten en bloemen van Europese kwekers (14.000+ producten volgens derde bron).", HINT),
           "ondersteuning": f("White-label verzending naar 20+ Europese landen.", HINT), "levering": f("20+ Europese landen.", HINT),
           "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": f("Shopify, WooCommerce en API.", HINT), "kosten": f("€149 per maand, optioneel €350 opzet (derde bron).", HINT),
           "affiliate": U(), "aanvraag": U()}, "Levende producten: houdbaarheid en retouren zijn een apart risico.",
          ("relevantie", "ondersteuning", "levering", "integratie")),
    entry("Droplo", "https://europeanpurpose.com/nl/categorie/europese-dropshipping-platforms-tools", "PL", "platform", "A", "mogelijk",
          tuple(CATEGORIES), ("groothandel en dropshipping, breed",), {"EU"}, "onbekend", ("plugin",),
          {"relevantie": U("Categorieën niet gelezen."), "ondersteuning": f("B2B-platform voor groothandel en dropshipping (derde bron).", HINT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": f("Koppelt met Allegro, Shopify en WooCommerce (derde bron).", HINT), "kosten": U(),
           "affiliate": U(), "aanvraag": U()}, "Alleen via een derde bron.", ("ondersteuning", "integratie")),
    entry("Orderchamp", "https://www.emerce.nl/nieuws/inkoopplatform-orderchamp-voegt-dropshipping-toe-aanbod", "EU", "platform", "AB",
          "mogelijk", ("home-living", "lifestyle-sport", "beauty-care"), ("merken en kleinere ontwerpers",), {"EU"}, "onbekend", (),
          {"relevantie": U("Categorieën niet gelezen."), "ondersteuning": f("Groothandelsmarktplaats; titel van een nieuwsbericht meldt dat dropshipping is toegevoegd.", HINT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(), "integratie": U(),
           "kosten": U(), "affiliate": U(), "aanvraag": U()}, "Interessant voor kleinere merken; werking per merk uitzoeken.", ("ondersteuning",)),
    entry("BigBuy", "https://www.bigbuy.eu/en/dropshipping-ecommerce.html", "ES", "platform", "A", "aantoonbaar",
          tuple(CATEGORIES), ("huis", "keuken", "meubels", "speelgoed", "gadgets"), {"EU"}, "gratis+betaald", ("api", "plugin"),
          {"relevantie": f("200.000+ producten, 5.000+ merken (eigen opgave).", FACT, "https://www.bigbuy.eu/en/dropshipping-ecommerce.html"),
           "ondersteuning": f("Officiële dropshipping met voorraad in Europa.", FACT), "levering": f("Europese voorraad.", FACT),
           "kwaliteit": U(), "prijzen": U("Prijzen zichtbaar na een (gratis) account."), "verzending": U(), "voorwaarden": U(),
           "integratie": f("Officiële REST-API (Bearer-sleutel) en WooCommerce-plugin via derde partij.", FACT, "https://www.bigbuy.eu/academy/en/?p=620"),
           "kosten": f("B2B Pack gratis; Ecommerce €89 per maand + €89 opzet (derde bron).", HINT),
           "affiliate": U(), "aanvraag": f("Account en contract voor API-sleutel.", FACT)},
          "Grote naam: niet de enige route, wel een reële vergelijking.", ("relevantie", "ondersteuning", "levering", "integratie")),
    entry("dropXL (vidaXL)", "https://www.dropxl.com/nl/faq.html", "NL", "platform", "A", "aantoonbaar", ("home-living",),
          ("meubels", "tuin", "wonen"), {"EU"}, "betaald", ("api", "plugin"),
          {"relevantie": f("Woon-, tuin- en meubelassortiment (derde bron).", HINT), "ondersteuning": f("Dropshipping vanuit Europa (derde bron).", HINT),
           "levering": f("Vanuit Europa.", HINT), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": f("Account geeft API-token; WooCommerce-plugin van Woosa.", HINT), "kosten": f("Maandelijkse platformkosten, bedrag niet gevonden.", HINT),
           "affiliate": U(), "aanvraag": f("Registratie via het portaal.", HINT)}, "", ("relevantie", "ondersteuning", "levering", "integratie")),
    entry("Syncee", "https://syncee.com/pricing", "HU", "platform", "A", "aantoonbaar", tuple(CATEGORIES), ("breed marktplaatsassortiment",), {"EU", "US"},
          "gratis+betaald", ("plugin",),
          {"relevantie": f("Marktplaats met leveranciers wereldwijd.", HINT), "ondersteuning": f("Importeren naar WooCommerce vraagt een betaald plan.", FACT, "https://syncee.com/pricing"),
           "levering": U("Per leverancier."), "kwaliteit": U(), "prijzen": f("Groothandelsprijzen zichtbaar in het gratis plan.", FACT),
           "verzending": U(), "voorwaarden": U(), "integratie": f("Productimport en ordersync via app.", FACT),
           "kosten": f("Vanaf $39,99 per maand (Basic); gratis plan om te kijken.", FACT, "https://syncee.com/pricing"),
           "affiliate": U(), "aanvraag": U()}, "", ("ondersteuning", "prijzen", "integratie", "kosten")),
    entry("CJdropshipping", "https://developers.cjdropshipping.com/en/api/api2/api/product.html", "CN", "platform", "A", "aantoonbaar",
          tuple(CATEGORIES), ("breed",), {"EU", "US"}, "onbekend", ("api",),
          {"relevantie": f("Categorieboom en trefwoordzoeken via API.", FACT), "ondersteuning": f("Dropshipping met voorraad per magazijn.", FACT),
           "levering": f("Zoeken per land en magazijn via de API.", FACT), "kwaliteit": U("Per product controleren; lange levertijd bij verzending uit China."),
           "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": f("Officiële API (key, token 180 dagen).", FACT, "https://developers.cjdropshipping.com/en/api/api2/api/auth.html"),
           "kosten": U("Kosten van API-toegang niet in de documentatie."), "affiliate": U(), "aanvraag": f("Account voor API-key.", FACT)}, "",
          ("relevantie", "ondersteuning", "levering", "integratie")),
    entry("Aqara", "https://aqara.cn/eu/partner/resellers-retailers", "CN", "merk", "B", "mogelijk", ("smart-home", "gadgets"),
          ("slimme sensoren", "hubs", "schakelaars", "camera's"), None, "onbekend", (),
          {"relevantie": f("Smart-homeproducten.", FACT), "ondersteuning": f("Reseller- en retailerprogramma met aanvraagformulier; dropshipping niet vermeld.", FACT),
           "levering": U("Beperkt tot het contractueel afgesproken gebied."), "kwaliteit": U(), "prijzen": U("Verplicht lokale adviesprijs (MSRP) te volgen."),
           "verzending": U(), "voorwaarden": f("Vereist professionele website met Aqara-pagina, fysiek bedrijfsadres, nazorg en technische ondersteuning; vertrouwelijke voorwaarden.", FACT),
           "integratie": U(), "kosten": U(), "affiliate": U(), "aanvraag": f("Aanvraag via formulier; reactie binnen 5 werkdagen.", FACT)},
          "Prijsregels (MSRP) beperken de marge; fysiek bedrijfsadres vereist.", ("relevantie", "ondersteuning", "voorwaarden", "aanvraag")),
    entry("Homey", "https://homey.app/en-fi/wiki/retail", "SE", "merk", "B", "mogelijk", ("smart-home",), ("smart-homehubs", "Homey Pro"), None,
          "onbekend", (),
          {"relevantie": f("Smart-homehubs (Homey Pro, Pro mini, Bridge).", FACT), "ondersteuning": f("Retailpagina met contactformulier; geen criteria, geen vermelding van dropshipping.", FACT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U("Geen voorwaarden vermeld."),
           "integratie": U(), "kosten": U(), "affiliate": U(), "aanvraag": f("Contactformulier.", FACT)}, "", ("relevantie", "ondersteuning", "aanvraag")),
    entry("Nuki", "https://nuki.io/en-ad/business-solutions/become-a-reseller", "AT", "merk", "B", "ongeschikt", ("smart-home",),
          ("slimme sloten",), None, "gratis", (),
          {"relevantie": f("Slimme sloten.", FACT), "ondersteuning": f("Resellerprogramma voor installateurs, elektriciens of slotenmakers; webshops en dropshipping niet vermeld.", FACT),
           "levering": U(), "kwaliteit": U(), "prijzen": f("Exclusieve resellerprijzen en bonusprogramma.", FACT), "verzending": U(),
           "voorwaarden": f("Vereist installatie-expertise, EU-bedrijf en btw-nummer.", FACT), "integratie": U(),
           "kosten": f("Registratie gratis en vrijblijvend.", FACT), "affiliate": U(), "aanvraag": f("Registratieformulier.", FACT)},
          "Ongeschikt tenzij NUVEMIXA installatie-expertise aantoont: het programma richt zich op installateurs.", ("relevantie", "prijzen", "kosten", "aanvraag")),
    entry("GL.iNet", "https://www.gl-inet.com/nl/pages/become-a-reseller", "CN", "merk", "B", "mogelijk", ("gadgets", "smart-home"),
          ("reisrouters", "netwerkapparatuur"), None, "onbekend", (),
          {"relevantie": U("Alleen de bestaande 'become a reseller'-pagina gezien in een zoekresultaat."), "ondersteuning": f("Resellerpagina bestaat (niet gelezen).", HINT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(), "integratie": U(), "kosten": U(),
           "affiliate": U(), "aanvraag": U()}, "Pagina nog lezen voordat dit meer dan een lead is.", ("ondersteuning",)),
    entry("Hama", "https://www.hama.com", "DE", "merk", "B", "mogelijk", ("gadgets",), ("accessoires", "audio", "smartphone-accessoires"), {"NL", "DE"},
          "onbekend", ("feed",),
          {"relevantie": f("Elektronica-accessoires; NUVEMIXA zoekt in de publieke catalogus (NL/DE).", HINT),
           "ondersteuning": f("Zakelijke aanmelding via het Hama business-portaal (bestaande code, niet opnieuw gelezen).", HINT),
           "levering": f("Alleen NL en DE in de code.", HINT), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(),
           "integratie": U(), "kosten": U(), "affiliate": U(), "aanvraag": f("Zakelijke aanmelding.", HINT)}, "", ("relevantie", "ondersteuning", "levering")),
    entry("Ikonka", "https://www.shoper.pl/katalog-hurtowni/hurtownia/ikonka", "PL", "groothandel", "A", "mogelijk",
          ("gadgets", "home-living", "beauty-care"), ("gadgets", "speelgoed", "huis en tuin"), {"EU"}, "betaald", (),
          {"relevantie": f("Gadgets, speelgoed, cosmeticaaccessoires, huis en tuin.", HINT), "ondersteuning": f("Poolse dropshippinggroothandel.", HINT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U("Per klant afgesproken."),
           "integratie": f("Alleen via groothandelsintegratie (Shoper/Apilo); geen openbare API gevonden.", HINT),
           "kosten": f("Het Shoper-platform is betaald.", HINT), "affiliate": U(), "aanvraag": f("Aanvraag via groothandelsintegratie.", HINT)}, "",
          ("relevantie", "ondersteuning")),
    entry("Versa Group", "https://www.versagroup.be/", "BE", "groothandel", "B", "mogelijk", ("home-living",), ("sanitair", "inrichting"), None,
          "onbekend", (), {k: U() for k, _, _ in CRITERIA}, "Alleen de omschrijving uit de bestaande code; pagina niet gelezen.", ()),
    entry("Sirocco", "https://sirocco.de/dropshipping/", "DE", "groothandel", "B", "mogelijk", ("home-living",), ("tuin", "gereedschap"), None,
          "onbekend", (), {k: U() for k, _, _ in CRITERIA}, "Alleen de omschrijving uit de bestaande code; pagina niet bereikbaar.", ()),
    entry("JG Distribution", "https://jgdistribution.fr/programme", "FR", "groothandel", "B", "mogelijk", ("gadgets",), ("gadgets", "speelgoed"), None,
          "onbekend", (), {k: U() for k, _, _ in CRITERIA}, "Alleen de omschrijving uit de bestaande code; pagina niet bereikbaar.", ()),
    entry("Avasam", "https://www.avasam.com/dropship-suppliers/", "GB", "platform", "B", "mogelijk", tuple(CATEGORIES), ("Britse B2B-leveranciers",), {"GB"},
          "onbekend", (), {k: U() for k, _, _ in CRITERIA}, "Alleen de omschrijving uit de bestaande code; pagina niet bereikbaar.", ()),
    entry("Awin (Nederland)", "https://affi.io/m/awin-netherlands", "GB", "netwerk", "C", "affiliate", tuple(CATEGORIES),
          ("per adverteerder",), None, "onbekend", ("feed",),
          {"relevantie": f("Affiliatenetwerk met Nederlandse adverteerders; per programma verschillend.", HINT),
           "ondersteuning": f("Alleen commissie; geen dropshipping. NUVEMIXA is niet de verkoper.", FACT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U("Publishervoorwaarden niet gelezen."),
           "integratie": f("Productfeeds per adverteerder worden vaak aangeboden; niet gecontroleerd.", HINT), "kosten": U(),
           "affiliate": f("Netwerk met affiliateprogramma's.", HINT), "aanvraag": f("Per programma aanmelden en goedkeuring afwachten.", HINT)},
          "Pagina zelf was niet leesbaar; alleen een zoekresultaat.", ("affiliate",)),
    entry("Daisycon", "https://daisycon.com/nl-be/publishers", "NL", "netwerk", "C", "affiliate", tuple(CATEGORIES), ("per adverteerder",), None,
          "onbekend", ("feed",),
          {"relevantie": f("Affiliatenetwerk met publisherpagina en publishervoorwaarden.", HINT),
           "ondersteuning": f("Alleen commissie; geen dropshipping. NUVEMIXA is niet de verkoper.", FACT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": f("Algemene publishervoorwaarden bestaan (niet gelezen).", HINT),
           "integratie": U(), "kosten": U(), "affiliate": f("Netwerk met affiliateprogramma's.", HINT), "aanvraag": f("Per campagne aanmelden.", HINT)},
          "", ("affiliate",)),
    entry("TradeTracker", "https://www.sourceforge.net/software/product/TradeTracker", "NL", "netwerk", "C", "affiliate", tuple(CATEGORIES),
          ("per adverteerder",), None, "onbekend", (),
          {"relevantie": U("Alleen een zoekresultaat gezien."), "ondersteuning": f("Alleen commissie; geen dropshipping.", FACT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(), "integratie": U(), "kosten": U(),
           "affiliate": f("Affiliatenetwerk (zoekresultaat).", HINT), "aanvraag": U()}, "Alleen via een zoekresultaat.", ("affiliate",)),
    entry("123Wonen", "https://www.affilitizer.com/programs/www.123wonen.nl", "NL", "webshop", "C", "affiliate", ("home-living",),
          ("meubels", "wonen"), {"NL"}, "onbekend", (),
          {"relevantie": f("Woonwebshop met affiliateprogramma volgens een lijst van derden.", HINT),
           "ondersteuning": f("Alleen affiliate: geen bewijs dat zij dropshipping aanbieden.", FACT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(), "integratie": U(), "kosten": U(),
           "affiliate": f("Staat als affiliateprogramma in de lijst van derden.", HINT), "aanvraag": U()},
          "Affiliateproducten worden NIET aan de WooCommerce-catalogus toegevoegd.", ("affiliate",)),
    entry("BrandsGateway", "https://dodropshipping.com/best-dropshipping-suppliers-in-europe-free-and-paid/", "EU", "platform", "A", "ongeschikt",
          (), ("designermode",), {"EU"}, "betaald", ("api", "plugin"),
          {"relevantie": f("Designermode: buiten de vijf NUVEMIXA-categorieën.", HINT), "ondersteuning": f("Dropshipping van mode.", HINT),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(), "integratie": f("WooCommerce, REST-API/CSV.", HINT),
           "kosten": f("Vanaf €180 per maand (derde bron).", HINT), "affiliate": U(), "aanvraag": U()},
          "Mode valt buiten de huidige categorieën en kost vanaf €180 per maand.", ()),
    entry("SaleHoo", "https://dodropshipping.com/best-dropshipping-suppliers-in-europe-free-and-paid/", "NZ", "gids", "B", "ongeschikt", (),
          ("leveranciersgids",), None, "betaald", (),
          {"relevantie": f("Gids met 8.000+ leveranciers; levert zelf geen producten.", HINT), "ondersteuning": U("Geen leverancier maar een abonnementsdienst."),
           "levering": U(), "kwaliteit": U(), "prijzen": U(), "verzending": U(), "voorwaarden": U(), "integratie": U(),
           "kosten": f("Betaald abonnement (derde bron).", HINT), "affiliate": U(), "aanvraag": U()},
          "Geen partner: een betaalde gids. Valt buiten de eis van geen nieuwe abonnementen.", ()),
)


def brand_programs():
    """Merken uit de bestaande catalogusbronnen met een zakelijke aanmeldlink in de code (B, alleen aanwijzing)."""
    from nv_product_discovery import CATALOGUES, TRADE_PROFILES
    known = {p["name"].lower() for p in PARTNERS}
    out, seen = [], set()
    for c in CATALOGUES:
        if c.name.lower() in known or c.name in seen or not c.trade_url:
            continue
        seen.add(c.name)
        origin, role = TRADE_PROFILES.get(c.name, ("", "Merk"))
        facts = {k: U() for k, _, _ in CRITERIA}
        facts["ondersteuning"] = f("De bestaande code bevat een zakelijke aanmeldlink; inhoud niet gelezen.", HINT, c.trade_url)
        facts["relevantie"] = f(f"NUVEMIXA zoekt in de webshop-catalogus ({CATEGORIES.get(c.category, c.category)}).", HINT)
        out.append(entry(c.name, c.trade_url, origin or "?", "merk", "B", "mogelijk", (c.category,), (), None, "onbekend", (), facts,
                         "Rol volgens bestaande code: " + role + ". Niet live bevestigd.", ("relevantie", "ondersteuning")))
    return out


def all_partners():
    return list(PARTNERS) + brand_programs()


def score(p):
    """Geschiktheid 0-100 uit alleen wat bekend is; zekerheid = deel van de criteria dat feit is."""
    total = sum(w for _, _, w in CRITERIA)
    got = sum(w * POINTS[p["facts"][k]["status"]] for k, _, w in CRITERIA if k in p["favorable"])
    certainty = sum(1 for k, _, _ in CRITERIA if p["facts"][k]["status"] == FACT)
    hints = sum(1 for k, _, _ in CRITERIA if p["facts"][k]["status"] == HINT)
    if certainty >= 6:
        label = "Grotendeels gecontroleerd"
    elif certainty + hints >= 5:
        label = "Deels aanwijzingen"
    else:
        label = "Vooral onbekend"
    return {"fit": round(100 * got / total), "facts": certainty, "hints": hints, "unknown": len(CRITERIA) - certainty - hints, "label": label}


def covers(p, country):
    if not country or p["ships"] is None:
        return True
    return country in p["ships"] or ("EU" in p["ships"] and country in EU)


def search(args):
    q = (args.get("q") or "").strip().lower()[:80]
    want = {k: (args.get(k) or "").strip() for k in ("cat", "land", "type", "model", "kosten", "integratie", "status")}
    rows = []
    for p in all_partners():
        if want["cat"] and want["cat"] not in p["categories"]:
            continue
        if want["land"] and not covers(p, want["land"]):
            continue
        if want["type"] and p["type"] != want["type"]:
            continue
        if want["model"] and want["model"] not in p["models"]:
            continue
        if want["status"] and p["status"] != want["status"]:
            continue
        if want["kosten"]:
            cost = p["cost"]
            if want["kosten"] == "gratis" and "gratis" not in cost:
                continue
            if want["kosten"] == "betaald" and "betaald" not in cost:
                continue
            if want["kosten"] == "onbekend" and cost != "onbekend":
                continue
        if want["integratie"]:
            if want["integratie"] == "geen-bekend":
                if p["integration"]:
                    continue
            elif want["integratie"] not in p["integration"]:
                continue
        if q:
            hay = " ".join((p["name"], p["note"], " ".join(p["products"]), " ".join(CATEGORIES.get(c, c) for c in p["categories"]))).lower()
            if not all(word in hay for word in q.split()):
                continue
        rows.append({**p, "score": score(p), "model_labels": [MODELS[m] for m in p["models"]], "type_label": TYPES[p["type"]],
                     "status_label": STATUS[p["status"]], "cat_labels": [CATEGORIES.get(c, c) for c in p["categories"]]})
    order = {"aantoonbaar": 0, "mogelijk": 1, "affiliate": 2, "ongeschikt": 3}
    rows.sort(key=lambda r: (order[r["status"]], -r["score"]["fit"], r["name"].lower()))
    return rows


def discovery_links(term, category, country):
    """Zoeklinks om kleinere webshops en merken te vinden. Alleen links: er wordt niets automatisch opgehaald of verstuurd."""
    subject = " ".join(x for x in (term, CATEGORIES.get(category, "")) if x).strip() or "webshop"
    tld = {"NL": "nl", "BE": "be", "DE": "de", "FR": "fr", "ES": "es", "IT": "it", "PL": "pl"}.get(country, "")
    site = f" site:.{tld}" if tld else ""
    words = {"NL": '"wederverkoper" OR "dealer worden" OR "voor webshops" OR "dropshipping"',
             "DE": '"Wiederverkäufer" OR "Händler werden" OR "Dropshipping"',
             "FR": '"revendeur" OR "devenir distributeur" OR "dropshipping"'}.get(country, '"reseller" OR "become a retailer" OR "dropshipping"')
    queries = (("Merken en winkels met reseller-/dealerpagina", f"{subject} {words}{site}"),
               ("Programma's voor webshops (B2B/dropship)", f'{subject} "wholesale" OR "groothandel" OR "B2B" "webshops"{site}'),
               ("Affiliateprogramma's", f'{subject} "affiliateprogramma" OR "partnerprogramma" OR "affiliate program"{site}'),
               ("Kleine fabrikanten", f'{subject} "fabrikant" OR "manufacturer" "zakelijk" OR "B2B"{site}'))
    return [{"label": label, "url": "https://www.google.com/search?q=" + quote(query.strip(), safe="")} for label, query in queries]


def candidate_note(model, status, name):
    return f"[Kandidaat · model {model} · {STATUS.get(status, status)}] Nog geen overeenkomst en geen contact gelegd. Bron: partnerzoeker {CHECKED}."


def candidates():
    """Kandidatenlijst = bestaande leverancierslijst met status 'onderzoek' en een kandidaat-notitie."""
    from nuvemixa_admin_store import list_suppliers
    try:
        return [r for r in list_suppliers() if str(r["notes"]).startswith("[Kandidaat")]
    except Exception:  # opslag tijdelijk niet beschikbaar: pagina blijft werken
        return None


def view(args):
    rows = search(args)
    return {"rows": rows, "total": len(all_partners()), "form": {k: (args.get(k) or "") for k in
            ("q", "cat", "land", "type", "model", "kosten", "integratie", "status")},
            "discovery": discovery_links((args.get("q") or "").strip()[:80], args.get("cat", ""), args.get("land", "")),
            "candidates": candidates(), "criteria": CRITERIA, "checked": CHECKED, "models": MODELS, "types": TYPES,
            "categories": CATEGORIES, "statuses": STATUS}


@bp.post("/dashboard/partners/kandidaat")
def save_candidate():
    """Bewaart een bedrijf op de kandidatenlijst. Stuurt niets naar het bedrijf en publiceert niets."""
    if not allowed("research"):
        abort(403)
    from nuvemixa_admin_store import add_supplier
    name = (request.form.get("name") or "").strip()
    match = next((p for p in all_partners() if p["name"] == name), None)
    try:
        if match:
            add_supplier(match["name"], "", match["url"], candidate_note("/".join(match["models"]), match["status"], name))
        else:  # eigen vondst, bijvoorbeeld een kleinere webshop
            model = request.form.get("model", "B")
            add_supplier(name, "", (request.form.get("url") or "").strip(),
                         ("[Kandidaat · model %s · eigen vondst, ongecontroleerd] " % (model if model in "ABC" else "B"))
                         + (request.form.get("notes") or "").strip()[:900])
        flash("Bedrijf bewaard op de kandidatenlijst. Er is niets verstuurd.", "success")
    except ValueError as error:
        flash(str(error), "error")
    except Exception:
        flash("Opslaan is nu niet gelukt; probeer het later opnieuw.", "error")
    return redirect(url_for("control", section="partners"), code=303)
