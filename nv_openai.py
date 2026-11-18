"""Centrale, kostenbewaakte OpenAI-koppeling voor het NUVEMIXA-dashboard.

* De sleutel komt uitsluitend uit de Render-omgevingsvariabele OPENAI_API_KEY (alleen backend).
* Eén plek voor modelkeuze, time-outs, foutafhandeling, caching en kostenbewaking.
* AI is altijd optioneel: bij een fout, limiet of ontbrekende sleutel valt de aanroeper terug op normaal zoeken.
* AI levert nooit feiten aan (leveranciers, prijzen, cijfers); aanroepers gebruiken het alleen om bestaande,
  opgehaalde gegevens te interpreteren of te filteren.
"""
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://api.openai.com/v1/"
DEFAULT_MODEL = "gpt-4o-mini"          # goedkoop, ondersteund model voor korte JSON-taken
DEFAULT_SEARCH_MODEL = "gpt-4.1-mini"  # Responses API met web_search (leveranciersbronnen)
# Prijzen per 1 miljoen tokens (USD) voor de kostenschatting; conservatief naar boven afgerond.
PRICES = {"gpt-4o-mini": (0.15, 0.60), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1-nano": (0.10, 0.40)}
FALLBACK_PRICE = (2.50, 10.00)          # onbekend model: reken duur, zodat de limiet eerder ingrijpt
WEB_SEARCH_CALL_USD = 0.025             # per uitgevoerde web_search-aanroep (bovengrens)
DEFAULT_MONTHLY_USD = 3.00              # applicatielimiet; het OpenAI-projectbudget (US$ 5) blijft de achtervang
DEFAULT_DAILY_CALLS = 80
CACHE_SECONDS = 6 * 3600
CACHE_SIZE = 300
COOLDOWN_AFTER_ERROR = 60               # seconden zonder nieuwe aanroep na 429/5xx/time-out
COOLDOWN_AFTER_AUTH = 900

_lock = threading.Lock()
_state = {"month": "", "month_usd": 0.0, "day": "", "day_calls": 0, "blocked_until": 0.0, "last_error": ""}
_cache = {}


class AIUnavailable(Exception):
    """AI niet gebruikt; `code` en `message` zijn veilig om te tonen."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def _float_env(name, default):
    try:
        return max(0.0, float(os.getenv(name, "").strip().replace(",", ".") or default))
    except ValueError:
        return default


def _int_env(name, default):
    try:
        return max(0, int(os.getenv(name, "").strip() or default))
    except ValueError:
        return default


def api_key():
    return os.getenv("OPENAI_API_KEY", "").strip()


def configured():
    """Alleen de sleutel is nodig. NUVEMIXA_AI=off schakelt AI bewust uit."""
    return bool(api_key()) and os.getenv("NUVEMIXA_AI", "").strip().lower() not in {"off", "false", "0", "uit"}


def model():
    return (os.getenv("NUVEMIXA_AI_MODEL", "").strip() or os.getenv("TRENDMIX_AI_MODEL", "").strip()
            or DEFAULT_MODEL)


def search_model():
    return os.getenv("NUVEMIXA_SUPPLIER_SEARCH_MODEL", "").strip() or DEFAULT_SEARCH_MODEL


def limits():
    return (_float_env("NUVEMIXA_AI_MONTHLY_USD", DEFAULT_MONTHLY_USD),
            _int_env("NUVEMIXA_AI_DAILY_CALLS", DEFAULT_DAILY_CALLS))


def _roll(now):
    stamp = datetime.fromtimestamp(now, timezone.utc)
    month, day = stamp.strftime("%Y-%m"), stamp.strftime("%Y-%m-%d")
    if _state["month"] != month:
        _state.update(month=month, month_usd=0.0)
    if _state["day"] != day:
        _state.update(day=day, day_calls=0)


def usage():
    monthly, daily = limits()
    with _lock:
        _roll(time.time())
        return {"month_usd": round(_state["month_usd"], 4), "month_limit_usd": monthly,
                "day_calls": _state["day_calls"], "day_limit": daily,
                "blocked": time.time() < _state["blocked_until"], "last_error": _state["last_error"]}


def status():
    """Korte status voor de interface: active, fallback of off."""
    if not configured():
        return {"state": "off", "label": "AI niet beschikbaar",
                "message": "OPENAI_API_KEY ontbreekt of AI staat uit; normaal zoeken is actief."}
    info = usage()
    if info["blocked"] or info["month_usd"] >= info["month_limit_usd"] or info["day_calls"] >= info["day_limit"]:
        return {"state": "fallback", "label": "AI tijdelijk uit, normaal zoeken",
                "message": info["last_error"] or "De AI-limiet van NUVEMIXA is bereikt; normaal zoeken is actief."}
    return {"state": "active", "label": "AI actief", "message": "AI helpt met zoekwoorden en het filteren van resultaten."}


def reset_for_tests():
    with _lock:
        _state.update(month="", month_usd=0.0, day="", day_calls=0, blocked_until=0.0, last_error="")
        _cache.clear()


def reserve(estimate):
    monthly, daily = limits()
    now = time.time()
    with _lock:
        _roll(now)
        if now < _state["blocked_until"]:
            raise AIUnavailable("cooldown", _state["last_error"] or "AI tijdelijk gepauzeerd na een fout.")
        if _state["day_calls"] >= daily:
            raise AIUnavailable("limit", "Daglimiet voor AI-aanroepen bereikt; normaal zoeken is actief.")
        if _state["month_usd"] + estimate > monthly:
            raise AIUnavailable("budget", "Maandbudget voor AI in NUVEMIXA bereikt; normaal zoeken is actief.")
        _state["day_calls"] += 1
        _state["month_usd"] += estimate  # voorlopig; na het antwoord vervangen door het werkelijke verbruik


def settle(estimate, actual):
    with _lock:
        _state["month_usd"] = max(0.0, _state["month_usd"] - estimate + actual)


def _block(seconds, message):
    with _lock:
        _state["blocked_until"] = time.time() + seconds
        _state["last_error"] = message


def cost(model_name, usage_data, web_calls=0):
    usage_data = usage_data or {}
    prompt = usage_data.get("prompt_tokens", usage_data.get("input_tokens", 0)) or 0
    completion = usage_data.get("completion_tokens", usage_data.get("output_tokens", 0)) or 0
    price_in, price_out = next((p for name, p in PRICES.items() if model_name.startswith(name)), FALLBACK_PRICE)
    return (prompt * price_in + completion * price_out) / 1_000_000 + web_calls * WEB_SEARCH_CALL_USD


def post(path, data, *, timeout, max_bytes=120_000, estimate_usd=0.002):
    """Doet één bewaakte API-aanroep. Gooit AIUnavailable met een toonbare melding bij elke fout."""
    if not configured():
        raise AIUnavailable("not_configured", "AI niet ingesteld (OPENAI_API_KEY ontbreekt); normaal zoeken is actief.")
    reserve(estimate_usd)
    request = urllib.request.Request(API_BASE + path, method="POST", data=json.dumps(data).encode(),
                                     headers={"Authorization": "Bearer " + api_key(),
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read(max_bytes)
    except urllib.error.HTTPError as exc:
        settle(estimate_usd, 0.0)
        if exc.code in (401, 403):
            _block(COOLDOWN_AFTER_AUTH, "De AI-dienst weigert de sleutel. Controleer OPENAI_API_KEY in Render.")
            raise AIUnavailable("auth", "De AI-dienst weigert de sleutel. Controleer OPENAI_API_KEY in Render.") from None
        if exc.code == 429:
            _block(COOLDOWN_AFTER_ERROR, "De AI-dienst meldt een limiet of op tegoed (HTTP 429).")
            raise AIUnavailable("upstream_limit", "De AI-dienst meldt een limiet of op tegoed (HTTP 429).") from None
        if exc.code >= 500:
            _block(COOLDOWN_AFTER_ERROR, f"De AI-dienst gaf een storing (HTTP {exc.code}).")
        raise AIUnavailable("upstream", f"De AI-dienst gaf een fout (HTTP {exc.code}).") from None
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        settle(estimate_usd, 0.0)
        timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
        text = (f"De AI-dienst reageerde niet binnen {timeout} seconden." if timed_out
                else "De AI-dienst is niet bereikbaar.")
        _block(COOLDOWN_AFTER_ERROR, text)
        raise AIUnavailable("timeout" if timed_out else "network", text) from None
    if not raw or not raw.strip():
        settle(estimate_usd, 0.0)
        raise AIUnavailable("empty", "De AI-dienst gaf een leeg antwoord.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        settle(estimate_usd, estimate_usd)
        raise AIUnavailable("invalid_json", "De AI-dienst gaf een onleesbaar antwoord.") from None
    web_calls = sum(1 for item in payload.get("output", []) or [] if isinstance(item, dict)
                    and item.get("type") == "web_search_call")
    settle(estimate_usd, cost(data.get("model", ""), payload.get("usage"), web_calls))
    return payload


def chat_json(task, system, user_payload, *, max_tokens=200, timeout=6):
    """Kort JSON-verzoek met caching. Geeft een dict terug of gooit AIUnavailable."""
    body = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
    key = hashlib.sha256(f"{task}|{model()}|{body}".encode()).hexdigest()
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return json.loads(json.dumps(hit[1]))
    data = {"model": model(), "response_format": {"type": "json_object"}, "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": body[:6000]}]}
    payload = post("chat/completions", data, timeout=timeout, max_bytes=40_000, estimate_usd=0.001)
    try:
        answer = json.loads(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise AIUnavailable("invalid_json", "De AI-dienst gaf een onleesbaar antwoord.") from None
    if not isinstance(answer, dict):
        raise AIUnavailable("invalid_json", "De AI-dienst gaf een onleesbaar antwoord.")
    with _lock:
        _cache[key] = (now, answer)
        if len(_cache) > CACHE_SIZE:
            _cache.pop(min(_cache, key=lambda item: _cache[item][0]))
    return json.loads(json.dumps(answer))
