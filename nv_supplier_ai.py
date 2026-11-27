"""AI-zoekbalk voor dropshipleveranciers in het onderdeel Leveranciers.

Gebruikt de bestaande OpenAI Responses API (webzoeken, beperkt tot de gecontroleerde bronnen) en neemt
uitsluitend bronnen over die het antwoord werkelijk citeert. Resultaten worden niet opgeslagen: ze bestaan
alleen in het antwoord op deze zoekopdracht. Alles wat niet aantoonbaar is, krijgt 'Niet bevestigd'.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import abort, current_app, jsonify, request, session, url_for

from nv_dashboard_manager import bp
from nv_permissions import allowed
from nv_product_dossier import MARKETS
import nv_openai
from nv_supplier_finder import DIRECTORIES, EU, search_configured, source

CATEGORIES = ("Gadgets", "Smart Home", "Beauty & Care", "Home & Living", "Lifestyle & Sport")
COUNTRIES = tuple(sorted(EU | {"GB"}))
UNCONFIRMED = "Niet bevestigd"
TIMEOUT_SECONDS = 15
COOLDOWN_SECONDS = 10
CACHE_SECONDS = 3600
MONTHLY_VARIABLE = "NUVEMIXA_SUPPLIER_AI_MONTHLY_LIMIT"
DAILY_VARIABLE = "NUVEMIXA_SUPPLIER_AI_DAILY_LIMIT"
DEFAULT_MONTHLY, DEFAULT_DAILY = 60, 10
# Alleen wat de gecontroleerde bronvermelding zelf zegt; de rest blijft 'Niet bevestigd'.
KNOWN = {
    "versagroup.be": {"categories": "Sanitair en inrichting", "dropshipping": "Catalogus noemt rechtstreekse verzending"},
    "sirocco.de": {"categories": "Tuin, gereedschap en andere artikelen", "dropshipping": "Bron meldt dropshipping vanuit Kleve"},
    "bigbuy.eu": {"dropshipping": "Bron meldt dropshipping met eigen voorraad (bigbuy.eu/en/dropshipping.html)"},
    "dropxl.com": {"categories": "Wonen, tuin en andere categorieën"},
    "jgdistribution.fr": {"categories": "Gadgets en speelgoed"},
}
FREEZE_VARIABLE = "NUVEMIXA_DASHBOARD_FREEZE"  # zelfde schakelaar als de bevriezing van de dashboardopslag
FREEZE_MESSAGE = ("Het dashboard staat tijdelijk in onderhoud omdat de opslag wordt verplaatst. "
                  "Er is niets verzonden en er zijn geen kosten gemaakt.")
_lock = threading.Lock()
_usage = {"month": "", "month_count": 0, "day": "", "day_count": 0}
_cache = {}
_busy = threading.Lock()


def _int_variable(name, default):
    try:
        return max(0, int(os.getenv(name, "").strip() or default))
    except ValueError:
        return default


def limits():
    return _int_variable(MONTHLY_VARIABLE, DEFAULT_MONTHLY), _int_variable(DAILY_VARIABLE, DEFAULT_DAILY)


def usage_snapshot(now=None):
    now = now or datetime.now(timezone.utc)
    month, day = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
    with _lock:
        if _usage["month"] != month:
            _usage.update(month=month, month_count=0)
        if _usage["day"] != day:
            _usage.update(day=day, day_count=0)
        monthly, daily = limits()
        return {"month_used": _usage["month_count"], "month_limit": monthly,
                "day_used": _usage["day_count"], "day_limit": daily}


def frozen():
    return os.getenv(FREEZE_VARIABLE, "").strip().lower() in {"1", "true", "yes", "on"}


def session_usage(now=None):
    """Teller per ingelogde browser (ondertekende cookie): overleeft een herstart van de server."""
    now = now or datetime.now(timezone.utc)
    month, day = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
    saved = session.get("nv_supplier_ai_usage")
    saved = saved if isinstance(saved, dict) else {}
    month_count = saved.get("mc", 0) if saved.get("m") == month and isinstance(saved.get("mc"), int) else 0
    day_count = saved.get("dc", 0) if saved.get("d") == day and isinstance(saved.get("dc"), int) else 0
    return month, day, max(0, month_count), max(0, day_count)


def reserve_search():
    """Telt een zoekopdracht mee vóór de externe aanroep (ook bij een fout: bewust voorzichtig).

    Twee tellers gelden tegelijk: de servergeheugenteller (alle gebruikers, reset bij herstart) en een
    ondertekende teller in de sessiecookie van deze beheerder (blijft bestaan zolang de browsersessie duurt).
    """
    state = usage_snapshot()
    month, day, session_month, session_day = session_usage()
    if state["month_used"] >= state["month_limit"] or session_month >= state["month_limit"]:
        return "Het maandelijkse zoeklimiet is bereikt. Er is geen zoekopdracht verstuurd."
    if state["day_used"] >= state["day_limit"] or session_day >= state["day_limit"]:
        return "Het dagelijkse zoeklimiet is bereikt. Er is geen zoekopdracht verstuurd."
    with _lock:
        _usage["month_count"] += 1
        _usage["day_count"] += 1
    session["nv_supplier_ai_usage"] = {"m": month, "mc": session_month + 1, "d": day, "dc": session_day + 1}
    return None


def clean(value, size):
    return re.sub(r"\s+", " ", (value or "")).strip()[:size]


def parse_search(form):
    """Valideert de zoekopdracht. Geeft (waarden, foutmelding)."""
    values = {"query": clean(form.get("query"), 120), "category": clean(form.get("category"), 40),
              "country": clean(form.get("country"), 2).upper(), "keyword": clean(form.get("keyword"), 60),
              "eu_only": form.get("eu_only") == "1", "prefer_woo": form.get("prefer_woo") == "1"}
    if len(values["query"]) < 2:
        return values, "Vul een productnaam in van minimaal 2 tekens."
    if "@" in values["query"] + values["keyword"]:
        return values, "Gebruik uitsluitend openbare productgegevens, geen e-mailadressen."
    if values["category"] and values["category"] not in CATEGORIES:
        return values, "Kies een geldige productcategorie."
    if values["country"] and values["country"] not in COUNTRIES:
        return values, "Kies een geldig land uit de lijst."
    return values, None


def select_sources(values):
    """Gecontroleerde bronnen voor deze zoekopdracht, het gekozen land eerst."""
    rows = list(DIRECTORIES)
    if values["eu_only"]:
        rows = [row for row in rows if row[0] in EU]
    if values["country"]:
        rows = [row for row in rows if row[0] == values["country"]]
    elif not values["eu_only"]:
        rows.sort(key=lambda row: (row[0] not in EU, row[0]))
    return rows


def card_for(row, page):
    country, name, website, _note = row
    host = urlsplit(website).hostname.removeprefix("www.")
    facts = KNOWN.get(host, {})
    root = f"{urlsplit(website).scheme}://{urlsplit(website).hostname}/"
    return {
        "name": name, "country": country if country != "INT" else "Internationaal",
        "website": root, "categories": facts.get("categories", UNCONFIRMED),
        "dropshipping": facts.get("dropshipping", UNCONFIRMED), "woocommerce": UNCONFIRMED,
        "sell_the_trend": UNCONFIRMED, "delivery": UNCONFIRMED, "contact": UNCONFIRMED,
        "source": {"label": page.get("title") or host, "href": page["href"], "origin": "AI-zoekopdracht (geciteerde bronpagina)",
                   "directory": website},
    }


# Verzoekvarianten: bij een HTTP 400 (verzoek geweigerd, niets verwerkt en niets in rekening gebracht) proberen
# we één keer een eenvoudiger verzoek. Alleen bronnen op de goedgekeurde domeinen tellen, ook zonder domeinfilter.
REQUEST_VARIANTS = ("volledig", "zonder domeinfilter, met site:-zoekvragen", "eenvoudig zonder domeinfilter")
# Sommige modellen (o.a. gpt-4.1-mini) ondersteunen 'filters' in web_search niet (HTTP 400, param=tools). Na zo'n
# weigering slaan we binnen dit proces de filtervariant over, zodat er geen geweigerd verzoek meer voorafgaat.
_filters_refused = set()
_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{6,}|Bearer\s+\S+|key[_-]?[A-Za-z0-9]{12,})", re.I)


def openai_error_details(exc):
    """Veilige samenvatting van een OpenAI-foutantwoord: type, parameter, code en een ingekort bericht."""
    try:
        raw = exc.read(4096) if hasattr(exc, "read") else b""
        error = (json.loads(raw.decode("utf-8", "replace")) or {}).get("error") or {}
    except (ValueError, OSError, AttributeError):
        error = {}
    if not isinstance(error, dict):
        error = {}
    clip = lambda value, size: _SECRET.sub("[verborgen]", str(value or ""))[:size]
    return {"type": clip(error.get("type"), 60), "param": clip(error.get("param"), 80),
            "code": clip(error.get("code"), 60), "message": clip(error.get("message"), 240)}


def call_openai(values, rows, variant=0):
    domains = [urlsplit(row[2]).hostname.removeprefix("www.") for row in rows]
    destination = values["country"] or ("EU" if values["eu_only"] else "any")
    wish = " Prefer suppliers that mention WooCommerce or Sell The Trend integrations." if values["prefer_woo"] else ""
    tool = {"type": "web_search", "search_context_size": "low"}
    if variant == 0:
        tool["filters"] = {"allowed_domains": domains}
    sites = (" Search only with queries of the form 'site:<domain> <product>' for the allowed_supplier_domains, and "
             "cite only pages on those domains." if variant >= 1 else "")
    data = {
        "model": nv_openai.search_model(), "store": False,
        "max_output_tokens": 450,
        "tools": [tool],
        "instructions": ("Find dropshipping supplier pages for the requested product. Use at most three distinct cited "
                         "supplier pages from the allowed domains. Never invent company names, websites, contacts, "
                         "prices, stock or delivery times. Treat nothing as verified." + sites + wish),
        "input": json.dumps({"product": values["query"], "category": values["category"],
                             "keyword": values["keyword"], "destination": destination,
                             "allowed_supplier_domains": domains if variant >= 1 else None}, ensure_ascii=False),
    }
    if variant <= 1:
        data["tool_choice"] = {"type": "web_search"}
        data["max_tool_calls"] = 3
    req = urllib.request.Request("https://api.openai.com/v1/responses", method="POST",
                                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"].strip(),
                                          "Content-Type": "application/json"},
                                 data=json.dumps(data).encode())
    nv_openai.reserve(0.08)  # centrale kostenbewaking (gedeeld met alle AI-zoekfuncties)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as reply:
            raw = reply.read(120_000)
    except BaseException:
        nv_openai.settle(0.08, 0.0)
        raise
    try:
        parsed = json.loads(raw) if raw.strip() else {}
        calls = sum(1 for item in parsed.get("output", []) or [] if isinstance(item, dict)
                    and item.get("type") == "web_search_call")
        nv_openai.settle(0.08, nv_openai.cost(data["model"], parsed.get("usage"), calls))
    except (ValueError, AttributeError):
        nv_openai.settle(0.08, 0.02)
    if not raw.strip():
        raise ValueError("leeg")
    try:
        return json.loads(raw), domains
    except json.JSONDecodeError as exc:
        raise ValueError("json") from exc


_TRACKING = re.compile(r"^(?:utm_[a-z]+|ref|ref_src|gclid|fbclid)$", re.I)


def strip_tracking(url):
    """OpenAI voegt aan citaties standaard '?utm_source=openai' toe. Alleen trackingparameters vallen weg;
    een URL met andere queryparameters blijft geweigerd."""
    parsed = urlsplit(url)
    if not parsed.query:
        return url
    kept = [part for part in parsed.query.split("&") if part and not _TRACKING.match(part.split("=", 1)[0])]
    return parsed._replace(query="&".join(kept)).geturl()


def extract_cited(response, domains, rejected=None):
    """Alleen werkelijk geciteerde pagina's op toegestane domeinen; één kaart per domein."""
    received, found = 0, {}
    for item in response.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for message in item.get("content", []) or []:
            if message.get("type") != "output_text":
                continue
            for ref in message.get("annotations", []) or []:
                if ref.get("type") != "url_citation":
                    continue
                received += 1
                try:
                    url = strip_tracking(source(ref.get("url", "")))
                    parsed = urlsplit(url)
                except (ValueError, AttributeError):
                    continue
                host = parsed.hostname or ""
                domain = next((d for d in domains if host == d or host.endswith("." + d)), None)
                if domain and len(url) <= 240 and not parsed.query and not parsed.fragment:
                    found.setdefault(domain, {"href": url, "title": clean(ref.get("title"), 120)})
                elif rejected is not None and host:
                    rejected.append(host[:80] if not domain else host[:60] + " (url-vorm)")
    return received, found


def answer(payload, status=200):
    reply = jsonify(payload)
    reply.status_code = status
    reply.headers["Cache-Control"] = "no-store"
    return reply


def failure(code, message, status, **extra):
    return answer({"ok": False, "code": code, "message": message, "results": [], **extra}, status)


def unavailable(code, message, values, **extra):
    """AI niet beschikbaar: geen 503, wel een duidelijke melding en een link naar normaal zoeken."""
    fallback = url_for("control", section="onderzoek", research_run="1", research_mode="suppliers",
                       research_term=values.get("query", ""), research_platform="Productcatalogi",
                       research_supplier_filter="eu" if values.get("eu_only") else "all",
                       research_country_basis="either", _anchor="nv-product-results")
    return answer({"ok": False, "state": "unavailable", "code": code, "message": message, "results": [],
                   "fallback_url": fallback, **extra}, 200)


def run_search(values, rows):
    started = time.perf_counter()
    details = None
    response = domains = None
    # gpt-4.1-mini (standaard) weigert web_search.filters met HTTP 400; die variant alleen bij een ander model.
    first = 1 if nv_openai.search_model() in _filters_refused or nv_openai.search_model().startswith("gpt-4.1") else 0
    for variant in range(first, len(REQUEST_VARIANTS)):
        try:
            response, domains = call_openai(values, rows, variant)
            values = {**values, "_variant": REQUEST_VARIANTS[variant]}
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise_http = exc
                break
            details = openai_error_details(exc)
            if variant == 0 and details["param"] == "tools" and "filters" in details["message"]:
                _filters_refused.add(nv_openai.search_model())
            current_app.logger.warning(
                "OpenAI weigerde leverancierszoekverzoek (%s): HTTP 400 type=%s param=%s code=%s bericht=%s",
                REQUEST_VARIANTS[variant], details["type"], details["param"], details["code"], details["message"])
            raise_http = None
        except BaseException as exc:  # noqa: BLE001 - doorgeven aan de foutafhandeling hieronder
            raise_http = exc
            break
    else:
        return unavailable("upstream", "AI niet beschikbaar: OpenAI weigert het verzoek (HTTP 400"
                           + (f", parameter {details['param']}" if details and details["param"] else "")
                           + "). Normaal zoeken werkt wel.", values,
                           detail={k: details[k] for k in ("type", "param", "code")} if details else {})
    if response is None and raise_http is not None:
        return search_failure(raise_http, values)
    return finish_search(response, domains, rows, started, values)


def search_failure(exc, values):
    try:
        raise exc
    except urllib.error.HTTPError as exc:
        code = exc.code
        details = openai_error_details(exc)
        current_app.logger.warning("OpenAI-fout bij leverancierszoeken: HTTP %s type=%s param=%s code=%s",
                                   code, details["type"], details["param"], details["code"])
        if code in (401, 403):
            return unavailable("auth", "AI niet beschikbaar: de AI-dienst weigert de sleutel. Controleer OPENAI_API_KEY "
                               "in Render. Normaal zoeken werkt wel.", values)
        if code == 429:
            return unavailable("upstream_limit", "AI niet beschikbaar: de AI-dienst meldt een limiet of tegoed dat op is. "
                               "Normaal zoeken werkt wel.", values)
        return unavailable("upstream", f"AI niet beschikbaar: de AI-dienst gaf een fout (HTTP {code}). "
                           "Normaal zoeken werkt wel.", values)
    except TimeoutError:
        return unavailable("timeout", f"AI niet beschikbaar: geen antwoord binnen {TIMEOUT_SECONDS} seconden. "
                           "Normaal zoeken werkt wel.", values)
    except urllib.error.URLError as exc:
        reason = "timeout" if isinstance(getattr(exc, "reason", None), TimeoutError) else "network"
        text = (f"AI niet beschikbaar: geen antwoord binnen {TIMEOUT_SECONDS} seconden." if reason == "timeout"
                else "AI niet beschikbaar: de AI-dienst is niet bereikbaar.")
        return unavailable(reason, text + " Normaal zoeken werkt wel.", values)
    except ValueError as exc:
        text = "De AI-dienst gaf een leeg antwoord." if str(exc) == "leeg" else "De AI-dienst gaf een onleesbaar antwoord."
        return unavailable("empty" if str(exc) == "leeg" else "invalid_json", "AI niet beschikbaar: " + text[0].lower()
                           + text[1:] + " Normaal zoeken werkt wel.", values)
    except OSError:
        return unavailable("network", "AI niet beschikbaar: de AI-dienst is niet bereikbaar. Normaal zoeken werkt wel.", values)
    except nv_openai.AIUnavailable as exc:
        return failure("limit", exc.message, 429)


def finish_search(response, domains, rows, started, values):
    rejected = []
    received, found = extract_cited(response, domains, rejected)
    if rejected:
        # Alleen hostnamen: geen volledige URL's, sleutels of zoektermen in de log.
        current_app.logger.info("AI-leverancierszoeken: %s citatie(s) buiten goedgekeurde domeinen: %s",
                                len(rejected), ", ".join(sorted(set(rejected))[:8]))
    by_domain = {urlsplit(row[2]).hostname.removeprefix("www."): row for row in rows}
    results = [card_for(by_domain[domain], found[domain]) for domain in domains if domain in found][:3]
    meta = {"elapsed_ms": round((time.perf_counter() - started) * 1000), "citations_received": received,
            "variant": values.get("_variant"), "rejected_hosts": sorted(set(rejected))[:8],
            "sources_accepted": len(results), "cached": False, "persistent": False}
    if not results:
        return {"ok": True, "message": "Geen controleerbare bron gevonden voor deze zoekopdracht.", "results": [], "meta": meta}
    return {"ok": True, "message": "", "results": results, "meta": meta}


@bp.post("/dashboard/leveranciers/ai-zoeken")
def supplier_ai_search():
    if not allowed("research"):
        abort(403)
    if frozen():
        return failure("frozen", FREEZE_MESSAGE, 503)
    values, error = parse_search(request.form)
    if error:
        return failure("invalid", error, 400)
    if not search_configured():
        return unavailable("not_configured", "AI niet beschikbaar: AI-configuratie ontbreekt (OPENAI_API_KEY op Render). "
                           "Er is niets verzonden. Normaal zoeken werkt wel.", values)
    rows = select_sources(values)
    if not rows:
        return failure("no_sources", "Er is geen gecontroleerde bron voor deze combinatie van land en filters. "
                       "Er is niets verzonden en er zijn geen kosten gemaakt.", 200)
    key = json.dumps(values, sort_keys=True)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        payload = json.loads(json.dumps(hit[1]))
        payload["meta"].update(cached=True, usage=usage_snapshot())
        return answer(payload)
    if now - session.get("nv_supplier_ai_at", 0) < COOLDOWN_SECONDS:
        return failure("cooldown", "Wacht een paar seconden voordat je opnieuw zoekt.", 429)
    if not _busy.acquire(blocking=False):
        return failure("busy", "Er loopt al een AI-zoekopdracht. Wacht tot die klaar is.", 429)
    try:
        refused = reserve_search()
        if refused:
            return failure("limit", refused, 429, usage=usage_snapshot())
        session["nv_supplier_ai_at"] = now
        current_app.logger.info("AI-leverancierszoekopdracht gestart")
        payload = run_search(values, rows)
        if isinstance(payload, dict):
            payload["meta"]["usage"] = usage_snapshot()
            _cache[key] = (now, payload)
            if len(_cache) > 50:
                _cache.pop(min(_cache, key=lambda item: _cache[item][0]))
            return answer(payload)
        return payload
    finally:
        _busy.release()


def view_context():
    snapshot = usage_snapshot()
    return {"configured": search_configured(), "categories": CATEGORIES,
            "countries": [(code, MARKETS[code][0] if code in MARKETS else code) for code in COUNTRIES], "usage": snapshot,
            "sources": [(row[0], row[1], row[2]) for row in DIRECTORIES]}
