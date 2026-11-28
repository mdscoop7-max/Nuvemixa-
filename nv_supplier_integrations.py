"""Leverancierskoppelingen: CJdropshipping, EPROLO en SaleHoo (beheer, status en de API-functies die echt bestaan).

Gegevens: alleen wat op 28-11-2026 op de officiële pagina's stond (bron per gegeven); de rest is 'Nog niet bevestigd'.
Koppelingen staan standaard UIT. Een API-sleutel staat alleen in een omgevingsvariabele op Render, nooit in de database
of in de pagina. Activeren kan pas na een geslaagde verbindingstest. Er worden geen bestellingen geplaatst, geen
betalingen gedaan, geen retouren aangemeld en geen accounts aangemaakt: die API-functies zijn gedocumenteerd en
'voorbereid', maar bewust niet aan een knop gekoppeld.

CJdropshipping (API 2.0, https://developers.cjdropshipping.com): token via getAccessToken met de API-sleutel uit het
CJ-account; daarna header CJ-Access-Token. Maximaal 1 aanroep per seconde (QPS 1) volgens de documentatie.
EPROLO: API-documentatie alleen op aanvraag via de accountbeheerder: niets te bouwen zonder die documentatie.
SaleHoo: betaalde leveranciersgids, geen leverancier en geen openbare API: nooit als dropshippingleverancier behandeld.
"""
import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from flask import abort, flash, jsonify, redirect, request, url_for

import nv_research_store as store
from nv_dashboard_manager import admin, bp
from nv_permissions import allowed

CHECKED = "28-11-2026"
NB = "Nog niet bevestigd"
CJ_BASE = "https://developers.cjdropshipping.com/api2.0/v1/"
CJ_DOCS = "https://developers.cjdropshipping.com/en/api/api2/api/"
TIMEOUT = 15


def F(value, url=""):
    """Een gegeven met bron. Zonder bron is het niet bevestigd."""
    return {"value": value, "url": url, "confirmed": bool(url)}


def U(note=""):
    return {"value": NB + (f" ({note})" if note else ""), "url": "", "confirmed": False}


CAPABILITIES = {
    "search": "Producten zoeken", "import": "Producten importeren", "images": "Productafbeeldingen importeren",
    "price": "Inkoopprijzen ophalen", "stock": "Voorraad synchroniseren", "shipping_cost": "Verzendkosten ophalen",
    "lead_time": "Levertijden ophalen", "order": "Bestellingen doorsturen", "order_status": "Bestelstatus synchroniseren",
    "tracking": "Track & Trace ophalen", "return_create": "Retouraanmeldingen doorsturen",
    "return_status": "Retourstatus volgen",
}
# gebouwd = werkt in het dashboard zodra de sleutel staat en de koppeling actief is; voorbereid = endpoint in de officiële
# documentatie, bewust niet aan een knop gekoppeld (plaatst/verandert iets bij de leverancier of vraagt echte orders).
STATE = {"gebouwd": "Gebouwd (werkt na koppeling)", "voorbereid": "Voorbereid, nog niet actief",
         "niet": "Niet ondersteund", "onbekend": "Onbekend: documentatie niet openbaar", "handmatig": "Alleen handmatig"}

SUPPLIERS = {
    "cj": {
        "name": "CJdropshipping", "logo": "cj", "kind": "dropshipping", "env": "NUVEMIXA_CJ_API_KEY",
        "website": "https://cjdropshipping.com/", "terms": "https://cjdropshipping.com/dispute-policy.html",
        "docs": CJ_DOCS + "auth.html",
        "setup": "Maak (met jouw toestemming) een CJ-account, maak in het CJ-account een API-sleutel aan en zet die op "
                 "Render als omgevingsvariabele NUVEMIXA_CJ_API_KEY. Daarna: Verbinding testen en Activeren.",
        "facts": {
            "subscription": U("kosten van API-toegang staan niet in de API-documentatie"),
            "kvk": U(),
            "dropshipping": F("Ja: producten, bestellingen en verzending via CJ (API-onderdelen Product, Shopping, "
                              "Logistic)", CJ_DOCS + "shopping.html"),
            "categories": F("Brede catalogus; categorieboom via de API (getCategory)", CJ_DOCS + "product.html"),
            "country": U("in eerder onderzoek: China"),
            "eu_warehouses": F("Magazijnlijst en voorraad per land via de API (globalWarehouseList, voorraad per SKU); "
                               "welke EU-landen precies: " + NB.lower(), CJ_DOCS + "product.html"),
            "ship_nl_be": F("Verzendopties en -kosten per land via de API (freightCalculate met endCountryCode NL/BE)",
                            CJ_DOCS + "logistic.html"),
            "delivery": F("Levertijd per verzendmethode via de API (logisticAging); geen vaste termijn gepubliceerd",
                          CJ_DOCS + "logistic.html"),
            "returns": F("Geschillen (o.a. retour/terugbetaling) via de API-onderdelen Dispute; het beleid zelf "
                         "('Refund, Resend and Returns') is achter een menselijke verificatie en niet gelezen",
                         CJ_DOCS + "dispute.html"),
            "return_address": U(),
            "private_label": F("CJ-verpakkingen en gepersonaliseerde producten via de API (cjPackaging, individualization)",
                               CJ_DOCS + "product.html"),
            "api": F("Ja, openbare API 2.0 met sleutel en toegangstoken; maximaal 1 aanroep per seconde",
                     CJ_DOCS + "auth.html"),
        },
        "capabilities": {
            "search": ("gebouwd", "product/listV2 (trefwoord, voorraadland)"),
            "import": ("gebouwd", "product/query; overnemen alleen als conceptproduct, nooit direct in de webshop"),
            "images": ("gebouwd", "bigImage en productImageSet uit product/query (afbeelding van de leverancier)"),
            "price": ("gebouwd", "sellPrice in USD, omgerekend met de ECB-koers in de calculator"),
            "stock": ("gebouwd", "product/stock/queryBySku: voorraad per magazijnland, op verzoek"),
            "shipping_cost": ("gebouwd", "logistic/freightCalculate naar NL (USD)"),
            "lead_time": ("gebouwd", "logisticAging uit freightCalculate"),
            "order": ("voorbereid", "shopping/order/createOrderV2: plaatst een echte bestelling; niet gekoppeld"),
            "order_status": ("voorbereid", "shopping/order/getOrderDetail: pas zinvol met doorgestuurde bestellingen"),
            "tracking": ("gebouwd", "logistic/trackInfo met een trackingnummer"),
            "return_create": ("voorbereid", "disputes/create: meldt een geschil bij CJ; niet gekoppeld"),
            "return_status": ("voorbereid", "disputes/getDisputeList en getDisputeDetail"),
        },
    },
    "eprolo": {
        "name": "EPROLO", "logo": "eprolo", "kind": "dropshipping", "env": "",
        "website": "https://eprolo.com/", "terms": "https://eprolo.com/project/terms-and-conditions/",
        "docs": "https://eprolo.com/eprolo-api/",
        "setup": "EPROLO geeft API-documentatie alleen na aanvraag: account aanmaken (alleen e-mailadres, met jouw "
                 "toestemming) en via de accountbeheerder in het EPROLO-dashboard de API aanvragen. Zonder die "
                 "documentatie bouwt NUVEMIXA geen koppeling.",
        "facts": {
            "subscription": F("Gratis: geen maandabonnement voor het platform en de integraties; eigen merklabel "
                              "vanaf $19,90 per jaar plus kosten per bestelling", "https://eprolo.com/"),
            "kvk": F("Volgens EPROLO is alleen een e-mailadres nodig om te registreren (geen KvK genoemd); het "
                     "registratieformulier zelf is niet ingevuld", "https://eprolo.com/eprolo-api/"),
            "dropshipping": F("Ja: producten importeren, bestellingen synchroniseren, EPROLO verpakt en verzendt",
                              "https://eprolo.com/"),
            "categories": F("Breed (107 niches); sterk in mode; ook print-on-demand", "https://eprolo.com/"),
            "country": F("Hongkong (Hong Kong Eprolo Technology Limited, bedrijfsnummer 75529645)",
                         "https://eprolo.com/project/terms-and-conditions/"),
            "eu_warehouses": F("Ja, als 3PL-opslag voor eigen ingekochte voorraad (met opslagkosten): VK, DE, CZ, FR, "
                               "IT, ES, FI, SE, IE, NL, PL, BE, NO; lokaal 2-5 dagen. De openbare catalogus heeft alleen "
                               "een 'US Warehouse'-collectie: welke catalogusproducten zonder eigen voorraad uit een EU-"
                               "magazijn komen is niet openbaar (per product controleren na registratie)",
                               "https://eprolo.com/warehousing-and-fulfillment/"),
            "ship_nl_be": F("Wereldwijd via o.a. Netherlands Post en Singapore Post; terugbetaling als levering naar "
                            "Europa langer dan 30 dagen duurt", "https://eprolo.com/shipping-methods"),
            "delivery": F("Meestal 5-15 dagen; naar Europa uit China 6-10 dagen, uit een EU-magazijn 2-5 dagen; "
                          "verzendkosten per product op de productpagina", "https://eprolo.com/warehousing-and-fulfillment/"),
            "returns": F("Kleding: 7 dagen retour zonder opgaaf van reden; overige producten: " + NB.lower(),
                         "https://eprolo.com/about-us"),
            "return_address": F("Niet gepubliceerd; het bedrijfsadres is volgens EPROLO uitdrukkelijk géén retouradres",
                                "https://eprolo.com/project/terms-and-conditions/"),
            "private_label": F("Ja: eigen labels, hangtags en verpakking zonder minimumafname (mode)",
                               "https://eprolo.com/about-us"),
            "api": F("Bestaat, maar documentatie alleen op aanvraag via de accountbeheerder",
                     "https://eprolo.com/eprolo-api/"),
        },
        "capabilities": {key: ("onbekend", "API-documentatie niet openbaar") for key in CAPABILITIES},
    },
    "salehoo": {
        "name": "SaleHoo", "logo": "salehoo", "kind": "directory", "env": "",
        "website": "https://www.salehoo.com/", "terms": "https://www.salehoo.com/pricing",
        "docs": "https://www.salehoo.com/pricing",
        "setup": "SaleHoo is een betaalde leveranciersgids (abonnement). NUVEMIXA sluit geen abonnement af. Gevonden "
                 "leveranciers kun je zelf als kandidaat toevoegen en daarna los controleren.",
        "facts": {
            "subscription": F("Betaald: Starter $9 per maand, Pro $49 per maand (jaarbetaling), Enterprise op "
                              "aanvraag; 60 dagen geld-terug", "https://www.salehoo.com/pricing"),
            "kvk": U(),
            "dropshipping": F("Nee, zelf geen leverancier: gids met 8.000+ leveranciers; dropshipping via die "
                              "leveranciers", "https://www.salehoo.com/pricing"),
            "categories": F("Veel niches; leveranciers filterbaar op land en verzendbestemming",
                            "https://www.salehoo.com/pricing"),
            "country": F("Nieuw-Zeeland (Christchurch)", "https://www.salehoo.com/pricing"),
            "eu_warehouses": F("Niet van toepassing (gids); leveranciers o.a. in Europa", "https://www.salehoo.com/pricing"),
            "ship_nl_be": F("Per leverancier; filter 'Ships Worldwide' of per land", "https://www.salehoo.com/pricing"),
            "delivery": U("per leverancier"), "returns": U("per leverancier"), "return_address": U("per leverancier"),
            "private_label": U("per leverancier"),
            "api": F("Geen openbare API genoemd; export via CSV, directe import alleen voor Shopify",
                     "https://www.salehoo.com/pricing"),
        },
        "capabilities": {**{key: ("niet", "Gids, geen leverancier") for key in CAPABILITIES},
                         "search": ("handmatig", "Leveranciers zoeken in de SaleHoo-gids (met abonnement)"),
                         "import": ("handmatig", "CSV-export; NUVEMIXA importeert niets automatisch")},
    },
}
FACT_LABELS = {
    "subscription": "Gratis of betaald abonnement", "kvk": "KvK verplicht", "dropshipping": "Dropshipping",
    "categories": "Productcategorieën", "country": "Vestigingsland", "eu_warehouses": "Europese magazijnen",
    "ship_nl_be": "Verzending naar Nederland en België", "delivery": "Levertijden en verzendkosten",
    "returns": "Retourvoorwaarden", "return_address": "Retouradres", "private_label": "Eigen merklabel en verpakking",
    "api": "API-beschikbaarheid",
}
STATUSES = ("Niet gekoppeld", "API-sleutel vereist", "Account vereist", "Verbonden", "Verbindingsfout", "Uitgeschakeld")


class IntegrationError(Exception):
    """Foutmelding die veilig aan de eigenaar getoond mag worden (zonder sleutel of token)."""


# ------------------------------------------------------------------ status (permanent in research_cache) -----------
def _key(slug):
    return f"integration:v1:{slug}"


def state(slug):
    """Altijd uit de database (niet uit het procesgeheugen): bij meerdere serverprocessen moet activeren of
    deactiveren overal direct gelden. Geen opslag bereikbaar = behandeld als uitgeschakeld."""
    import json
    payload = {}
    try:
        with store.connect() as db:
            store._sqlite(db)
            row = db.execute("SELECT payload FROM research_cache WHERE cache_key = ?", (_key(slug),)).fetchone()
        payload = json.loads(row[0]) if row is not None else {}
    except Exception:  # noqa: BLE001
        payload = {}
    return {"enabled": bool(payload.get("enabled")), "test": payload.get("test") or {}}


def _save(slug, data):
    store.save(_key(slug), "done", data, wait=True)


def has_key(slug):
    env = SUPPLIERS[slug]["env"]
    return bool(env and os.getenv(env, "").strip())


def status(slug):
    s = SUPPLIERS[slug]
    if not s["env"]:
        return "Account vereist"
    if not has_key(slug):
        return "API-sleutel vereist"
    st = state(slug)
    if not st["test"]:
        return "Niet gekoppeld"
    if not st["test"].get("ok"):
        return "Verbindingsfout"
    return "Verbonden" if st["enabled"] else "Uitgeschakeld"


def active(slug):
    return status(slug) == "Verbonden"


# ------------------------------------------------------------------ CJdropshipping API ------------------------------
class CJ:
    _lock = threading.Lock()
    _token = {"value": "", "expires": 0.0}
    _last = [0.0]

    @classmethod
    def _wait(cls):
        with cls._lock:
            pause = 1.05 - (time.monotonic() - cls._last[0])   # QPS 1 volgens de documentatie
            if pause > 0:
                time.sleep(pause)
            cls._last[0] = time.monotonic()

    @classmethod
    def _call(cls, method, path, *, params=None, json=None, token=True, session=None):
        cls._wait()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["CJ-Access-Token"] = cls.token(session=session)
        try:
            reply = (session or requests).request(method, CJ_BASE + path, params=params, json=json, headers=headers,
                                                  timeout=TIMEOUT)
            data = reply.json()
        except (requests.RequestException, ValueError) as exc:
            raise IntegrationError(f"CJ niet bereikbaar ({type(exc).__name__}).") from None
        if not isinstance(data, dict) or not data.get("result"):
            message = str((data or {}).get("message") or f"HTTP {reply.status_code}")[:160]
            raise IntegrationError(f"CJ weigerde het verzoek: {message}")
        return data.get("data")

    @classmethod
    def token(cls, session=None, force=False):
        if not force and cls._token["value"] and time.time() < cls._token["expires"]:
            return cls._token["value"]
        key = os.getenv(SUPPLIERS["cj"]["env"], "").strip()
        if not key:
            raise IntegrationError("Geen API-sleutel: zet NUVEMIXA_CJ_API_KEY op Render.")
        data = cls._call("POST", "authentication/getAccessToken", json={"apiKey": key}, token=False, session=session)
        value = (data or {}).get("accessToken") or ""
        if not value:
            raise IntegrationError("CJ gaf geen toegangstoken terug.")
        expiry = (data or {}).get("accessTokenExpiryDate") or ""
        try:
            expires = datetime.fromisoformat(expiry).timestamp() - 3600
        except ValueError:
            expires = time.time() + 12 * 3600
        cls._token.update(value=value, expires=expires)   # alleen in het geheugen van dit proces
        return value

    @classmethod
    def search(cls, keyword, country="", size=20, session=None):
        params = {"keyWord": keyword[:100], "page": 1, "size": max(1, min(int(size), 50))}
        if country:
            params["countryCode"] = country
        data = cls._call("GET", "product/listV2", params=params, session=session) or {}
        rows = []
        for block in data.get("content") or []:
            for p in block.get("productList") or []:
                rows.append({
                    "pid": p.get("id") or "", "sku": p.get("sku") or "", "name": p.get("nameEn") or "",
                    "image": p.get("bigImage") if str(p.get("bigImage") or "").startswith("https://") else "",
                    "price_usd": _num(p.get("nowPrice") or p.get("sellPrice")),
                    "category": " / ".join(x for x in (p.get("oneCategoryName"), p.get("twoCategoryName"),
                                                       p.get("threeCategoryName")) if x),
                    "inventory": p.get("warehouseInventoryNum"), "verified_inventory": p.get("totalVerifiedInventory"),
                    "ce": p.get("hasCECertification") == 1, "delivery_cycle": p.get("deliveryCycle") or "",
                    "free_shipping": p.get("addMarkStatus") == 1,
                })
        return rows

    @classmethod
    def stock(cls, sku, session=None):
        data = cls._call("GET", "product/stock/queryBySku", params={"sku": sku[:60]}, session=session) or []
        return [{"country": d.get("countryCode") or "", "area": d.get("areaEn") or "",
                 "total": d.get("totalInventoryNum"), "cj": d.get("cjInventoryNum"),
                 "factory": d.get("factoryInventoryNum")} for d in data if isinstance(d, dict)]

    @classmethod
    def shipping(cls, pid, end="NL", session=None):
        detail = cls._call("GET", "product/query", params={"pid": pid[:80]}, session=session) or {}
        variants = detail.get("variants") or []
        if not variants:
            raise IntegrationError("CJ gaf geen varianten voor dit product.")
        vid = variants[0].get("vid")
        options = cls._call("POST", "logistic/freightCalculate", json={
            "startCountryCode": "CN", "endCountryCode": end, "products": [{"quantity": 1, "vid": vid}]},
            session=session) or []
        return {"variant": variants[0].get("variantNameEn") or variants[0].get("variantSku") or "",
                "options": [{"name": o.get("logisticName") or "", "days": o.get("logisticAging") or "",
                             "price_usd": _num(o.get("logisticPrice"))} for o in options if isinstance(o, dict)]}

    @classmethod
    def tracking(cls, number, session=None):
        data = cls._call("GET", "logistic/trackInfo", params={"trackNumber": number[:60]}, session=session) or []
        return [{k: d.get(k) for k in ("trackingNumber", "logisticName", "trackingFrom", "trackingTo", "deliveryDay",
                                       "deliveryTime", "trackingStatus", "lastMileCarrier", "lastTrackNumber")}
                for d in data if isinstance(d, dict)]


def _num(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ marge ------------------------------------------
from nv_product_margin import MARGIN_PRESETS  # noqa: E402  (één bron voor de categorie-marges)


def margin_link(name, price_usd, category="", shipping_usd=None):
    """'Bereken marge' met de inkoopprijs in USD; de calculator rekent om met de ECB-koers en toont koers en datum."""
    args = {"section": "calculator", "margin_product": name[:120], "margin_amount": f"{price_usd:.2f}",
            "margin_currency": "USD"}
    if category in MARGIN_PRESETS:
        args["margin_category"] = category
    return "/dashboard?" + urlencode(args) + "#tm-calc"


# ------------------------------------------------------------------ routes ---------------------------------------
def _back(message, kind="success"):
    flash(message, kind)
    return redirect(url_for("control", section="leveranciers", _anchor="nv-koppelingen"), code=303)


@bp.post("/dashboard/leveranciers/koppeling/<slug>/<action>")
def integration_action(slug, action):
    """Verbinding testen, activeren of deactiveren. Alleen de eigenaar; plaatst nooit iets bij de leverancier."""
    if not admin():
        abort(403)
    if slug not in SUPPLIERS or action not in ("test", "activeren", "deactiveren"):
        abort(404)
    name = SUPPLIERS[slug]["name"]
    current = state(slug)
    if action == "deactiveren":
        _save(slug, {**current, "enabled": False})
        return _back(f"{name} is uitgeschakeld. Er wordt niets meer opgehaald.")
    if not SUPPLIERS[slug]["env"]:
        return _back(f"{name}: {status(slug)}. Er is geen API-koppeling om te testen of te activeren.", "error")
    if not has_key(slug):
        return _back(f"{name}: API-sleutel vereist ({SUPPLIERS[slug]['env']} op Render).", "error")
    if action == "test":
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        try:
            CJ.token(force=True)
            test = {"ok": True, "at": now, "message": "Toegangstoken ontvangen van CJ."}
        except IntegrationError as exc:
            test = {"ok": False, "at": now, "message": str(exc)}
        _save(slug, {"enabled": current["enabled"] and test["ok"], "test": test})
        return _back(f"{name}: {test['message']}", "success" if test["ok"] else "error")
    if not current["test"].get("ok"):
        return _back(f"{name} kan pas geactiveerd worden na een geslaagde verbindingstest.", "error")
    _save(slug, {**current, "enabled": True})
    return _back(f"{name} is geactiveerd. Producten verschijnen alleen als concept; niets gaat automatisch online.")


def _json(payload, code=200):
    response = jsonify(payload)
    response.status_code = code
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/dashboard/leveranciers/cj/<what>")
def cj_query(what):
    """Alleen-lezen opvragingen bij CJ (zoeken, voorraad, verzending, tracking). Vereist een actieve koppeling."""
    if not allowed("research"):
        abort(403)
    if what not in ("zoeken", "voorraad", "verzending", "tracking"):
        abort(404)
    if not active("cj"):
        return _json({"ok": False, "message": f"CJdropshipping: {status('cj')}. Er is niets opgevraagd."}, 409)
    value = " ".join((request.form.get("q") or "").split())[:100]
    if len(value) < 2:
        return _json({"ok": False, "message": "Vul een zoekterm, SKU, product-ID of trackingnummer in."}, 400)
    try:
        if what == "zoeken":
            rows = CJ.search(value, country=(request.form.get("country") or "").upper()[:2])
            category = request.form.get("category", "")
            for r in rows:
                r["margin_url"] = margin_link(r["name"], r["price_usd"], category) if r["price_usd"] else ""
            return _json({"ok": True, "products": rows, "checked": datetime.now(timezone.utc).isoformat()})
        if what == "voorraad":
            return _json({"ok": True, "stock": CJ.stock(value)})
        if what == "verzending":
            return _json({"ok": True, **CJ.shipping(value, (request.form.get("country") or "NL").upper()[:2])})
        return _json({"ok": True, "tracking": CJ.tracking(value)})
    except IntegrationError as exc:
        return _json({"ok": False, "message": str(exc)}, 502)


def view():
    rows = []
    for slug, s in SUPPLIERS.items():
        from nv_platform_logos import LOGOS
        st = state(slug)
        rows.append({"slug": slug, **{k: s[k] for k in ("name", "kind", "env", "website", "terms", "docs", "setup")},
                     "logo": LOGOS.get(s["logo"], ""), "status": status(slug), "test": st["test"],
                     "facts": [(FACT_LABELS[k], s["facts"][k]) for k in FACT_LABELS],
                     "capabilities": [(CAPABILITIES[k], STATE[s["capabilities"][k][0]], s["capabilities"][k][0],
                                       s["capabilities"][k][1]) for k in CAPABILITIES]})
    return {"suppliers": rows, "checked": CHECKED, "can_manage": bool(admin()), "statuses": STATUSES,
            "presets": MARGIN_PRESETS}
