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

from flask import abort, current_app, jsonify, request, session

from nv_dashboard_manager import bp
from nv_permissions import allowed
from nv_product_dossier import MARKETS
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


def reserve_search():
    """Telt een zoekopdracht mee vóór de externe aanroep (ook bij een fout: bewust voorzichtig)."""
    state = usage_snapshot()
    if state["month_used"] >= state["month_limit"]:
        return "Het maandelijkse zoeklimiet is bereikt. Er is geen zoekopdracht verstuurd."
    if state["day_used"] >= state["day_limit"]:
        return "Het dagelijkse zoeklimiet is bereikt. Er is geen zoekopdracht verstuurd."
    with _lock:
        _usage["month_count"] += 1
        _usage["day_count"] += 1
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


def call_openai(values, rows):
    domains = [urlsplit(row[2]).hostname.removeprefix("www.") for row in rows]
    destination = values["country"] or ("EU" if values["eu_only"] else "any")
    wish = " Prefer suppliers that mention WooCommerce or Sell The Trend integrations." if values["prefer_woo"] else ""
    data = {
        "model": os.environ["NUVEMIXA_SUPPLIER_SEARCH_MODEL"].strip(), "store": False,
        "max_tool_calls": 3, "max_output_tokens": 450,
        "tools": [{"type": "web_search", "filters": {"allowed_domains": domains}, "search_context_size": "low"}],
        "tool_choice": {"type": "web_search"},
        "instructions": ("Find dropshipping supplier pages for the requested product. Use at most three distinct cited "
                         "supplier pages from the allowed domains. Never invent company names, websites, contacts, "
                         "prices, stock or delivery times. Treat nothing as verified." + wish),
        "input": json.dumps({"product": values["query"], "category": values["category"],
                             "keyword": values["keyword"], "destination": destination}, ensure_ascii=False),
    }
    req = urllib.request.Request("https://api.openai.com/v1/responses", method="POST",
                                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"].strip(),
                                          "Content-Type": "application/json"},
                                 data=json.dumps(data).encode())
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as reply:
        raw = reply.read(120_000)
    if not raw.strip():
        raise ValueError("leeg")
    try:
        return json.loads(raw), domains
    except json.JSONDecodeError as exc:
        raise ValueError("json") from exc


def extract_cited(response, domains):
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
                    url = source(ref.get("url", ""))
                    parsed = urlsplit(url)
                except (ValueError, AttributeError):
                    continue
                host = parsed.hostname or ""
                domain = next((d for d in domains if host == d or host.endswith("." + d)), None)
                if domain and len(url) <= 240 and not parsed.query and not parsed.fragment:
                    found.setdefault(domain, {"href": url, "title": clean(ref.get("title"), 120)})
    return received, found


def answer(payload, status=200):
    reply = jsonify(payload)
    reply.status_code = status
    reply.headers["Cache-Control"] = "no-store"
    return reply


def failure(code, message, status, **extra):
    return answer({"ok": False, "code": code, "message": message, "results": [], **extra}, status)


def run_search(values, rows):
    started = time.perf_counter()
    try:
        response, domains = call_openai(values, rows)
    except urllib.error.HTTPError as exc:
        code = exc.code
        if code in (401, 403):
            return failure("auth", "De AI-dienst weigert de sleutel. Controleer OPENAI_API_KEY in Render.", 503)
        if code == 429:
            return failure("upstream_limit", "De AI-dienst meldt een limiet of tegoed dat op is. Er is niets getoond.", 503)
        return failure("upstream", f"De AI-dienst gaf een fout (HTTP {code}). Probeer het later opnieuw.", 503)
    except TimeoutError:
        return failure("timeout", f"De AI-dienst reageerde niet binnen {TIMEOUT_SECONDS} seconden.", 503)
    except urllib.error.URLError as exc:
        reason = "timeout" if isinstance(getattr(exc, "reason", None), TimeoutError) else "network"
        text = (f"De AI-dienst reageerde niet binnen {TIMEOUT_SECONDS} seconden." if reason == "timeout"
                else "De AI-dienst is niet bereikbaar. Controleer de verbinding en probeer het later opnieuw.")
        return failure(reason, text, 503)
    except ValueError as exc:
        text = "De AI-dienst gaf een leeg antwoord." if str(exc) == "leeg" else "De AI-dienst gaf een onleesbaar antwoord."
        return failure("empty" if str(exc) == "leeg" else "invalid_json", text, 503)
    except OSError:
        return failure("network", "De AI-dienst is niet bereikbaar.", 503)
    received, found = extract_cited(response, domains)
    by_domain = {urlsplit(row[2]).hostname.removeprefix("www."): row for row in rows}
    results = [card_for(by_domain[domain], found[domain]) for domain in domains if domain in found][:3]
    meta = {"elapsed_ms": round((time.perf_counter() - started) * 1000), "citations_received": received,
            "sources_accepted": len(results), "cached": False, "persistent": False}
    if not results:
        return {"ok": True, "message": "Geen controleerbare bron gevonden voor deze zoekopdracht.", "results": [], "meta": meta}
    return {"ok": True, "message": "", "results": results, "meta": meta}


@bp.post("/dashboard/leveranciers/ai-zoeken")
def supplier_ai_search():
    if not allowed("research"):
        abort(403)
    values, error = parse_search(request.form)
    if error:
        return failure("invalid", error, 400)
    if not search_configured():
        return failure("not_configured", "AI-configuratie ontbreekt: stel OPENAI_API_KEY en "
                       "NUVEMIXA_SUPPLIER_SEARCH_MODEL in op Render. Er is niets verzonden.", 503)
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
