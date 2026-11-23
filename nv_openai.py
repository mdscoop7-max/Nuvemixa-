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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

API_BASE = "https://api.openai.com/v1/"
DEFAULT_MODEL = "gpt-4o-mini"          # goedkoop, ondersteund model voor korte JSON-taken
DEFAULT_SEARCH_MODEL = "gpt-4.1-mini"  # Responses API met web_search (leveranciersbronnen)
# Prijzen per 1 miljoen tokens (USD) voor de kostenschatting; conservatief naar boven afgerond.
PRICES = {"gpt-4o-mini": (0.15, 0.60), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1-nano": (0.10, 0.40)}
FALLBACK_PRICE = (2.50, 10.00)          # onbekend model: reken duur, zodat de limiet eerder ingrijpt
WEB_SEARCH_CALL_USD = 0.025             # per uitgevoerde web_search-aanroep (bovengrens)
DEFAULT_MONTHLY_USD = 3.00              # interne schatting, geen garantie; het OpenAI-projectbudget (US$ 5) is de echte grens
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


UNPERSISTED_DAILY_CALLS = 20            # strengere daglimiet zolang de teller niet blijvend kan worden opgeslagen
SQLITE_TABLE = ("CREATE TABLE IF NOT EXISTS ai_usage (period TEXT PRIMARY KEY, "
                "usd REAL NOT NULL DEFAULT 0, calls INTEGER NOT NULL DEFAULT 0)")
UPSERT = ("INSERT INTO ai_usage(period, usd, calls) VALUES (?, ?, ?) ON CONFLICT(period) DO UPDATE "
          "SET usd = ai_usage.usd + excluded.usd, calls = ai_usage.calls + excluded.calls")


def _periods(now):
    stamp = datetime.fromtimestamp(now, timezone.utc)
    return stamp.strftime("%Y-%m"), stamp.strftime("%Y-%m-%d")


def _roll(now):
    month, day = _periods(now)
    if _state["month"] != month:
        _state.update(month=month, month_usd=0.0)
    if _state["day"] != day:
        _state.update(day=day, day_calls=0)


def store_connect():
    """Dashboardopslag (PostgreSQL of SQLite). Vervangbaar in tests."""
    import nuvemixa_admin_store
    return nuvemixa_admin_store.connect()


def _persist(now, usd=0.0, calls=0):
    """Telt op in de blijvende opslag en geeft (maand_usd, dag_aanroepen) terug, of None als dat niet lukt.

    Alleen INSERT/UPDATE op de eigen tabel ai_usage; er wordt nooit iets verwijderd."""
    month, day = _periods(now)
    try:
        with store_connect() as db:
            db.execute(SQLITE_TABLE)
            if usd or calls:
                db.execute(UPSERT, (month, float(usd), int(calls)))
                db.execute(UPSERT, (day, 0.0, int(calls)))
            m = db.execute("SELECT usd FROM ai_usage WHERE period = ?", (month,)).fetchone()
            d = db.execute("SELECT calls FROM ai_usage WHERE period = ?", (day,)).fetchone()
            return (float(m[0]) if m else 0.0), (int(d[0]) if d else 0)
    except Exception:  # opslag niet beschikbaar, bevroren of tabel nog niet gemigreerd
        return None


# De blijvende teller mag een request NOOIT laten wachten op de database: elke verbinding Render (Oregon) ->
# Neon (Frankfurt) kost seconden. Lezen gebeurt via een geheugenbuffer die op de achtergrond wordt ververst;
# schrijven gebeurt op de achtergrond in één volgorde-bewarende thread.
SNAPSHOT_TTL = 120          # seconden dat een gelezen stand geldig blijft
RESERVE_WAIT = 1.5          # max. wachttijd op de eerste stand na een herstart (alleen bij een AI-aanroep)
_snap = {"at": 0.0, "periods": None, "value": None, "pending": None}
_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nv-ai-usage")


def _remember(now, value):
    if value is not None:
        with _lock:
            _snap.update(at=time.time(), periods=_periods(now), value=value)
    return value


def _write(now, usd, calls):
    return _remember(now, _persist(now, usd, calls))


def _stored(now, wait=0.0):
    """Laatst bekende blijvende stand (maand_usd, dag_aanroepen) of None. Blokkeert hooguit `wait` seconden."""
    with _lock:
        snap = _snap["value"] if _snap["periods"] == _periods(now) else None
        fresh = snap is not None and time.time() - _snap["at"] < SNAPSHOT_TTL
        pending = _snap["pending"]
        if not fresh and (pending is None or pending.done()):
            pending = _snap["pending"] = _writer.submit(_write, now, 0.0, 0)
    if fresh or wait <= 0:
        return snap
    try:
        return pending.result(timeout=wait) or snap
    except Exception:  # time-out of opslagfout: niet wachten, strengere limiet geldt
        return snap


def _add_to_snapshot(now, usd, calls):
    with _lock:
        if _snap["value"] is not None and _snap["periods"] == _periods(now):
            month_usd, day_calls = _snap["value"]
            _snap["value"] = (month_usd + usd, day_calls + calls)
    _writer.submit(_write, now, usd, calls)


def flush(timeout=5):
    """Wacht tot alle achtergrondschrijfacties klaar zijn (tests en afsluiten)."""
    try:
        _writer.submit(lambda: None).result(timeout=timeout)
    except Exception:
        pass


def usage(wait=0.0):
    monthly, daily = limits()
    now = time.time()
    stored = _stored(now, wait)
    with _lock:
        _roll(now)
        month_usd, day_calls = stored if stored else (_state["month_usd"], _state["day_calls"])
        return {"month_usd": round(max(month_usd, _state["month_usd"]), 4), "month_limit_usd": monthly,
                "day_calls": max(day_calls, _state["day_calls"]),
                "day_limit": daily if stored else min(daily, UNPERSISTED_DAILY_CALLS),
                "persistent": stored is not None,
                "blocked": now < _state["blocked_until"], "last_error": _state["last_error"]}


def status():
    """Korte status voor de interface: active, fallback of off. Wacht nooit op de database."""
    if not configured():
        return {"state": "off", "label": "AI niet beschikbaar",
                "message": "OPENAI_API_KEY ontbreekt of AI staat uit; normaal zoeken is actief."}
    info = usage()
    if info["blocked"] or info["month_usd"] >= info["month_limit_usd"] or info["day_calls"] >= info["day_limit"]:
        return {"state": "fallback", "label": "AI tijdelijk uit, normaal zoeken",
                "message": info["last_error"] or "De interne AI-limiet van NUVEMIXA is bereikt; normaal zoeken is actief."}
    note = ("Interne schatting deze maand: US$ {:.2f} van US$ {:.2f}; het OpenAI-projectbudget blijft de echte grens."
            .format(info["month_usd"], info["month_limit_usd"]))
    if not info["persistent"]:
        note += " Blijvende teller wordt geladen of is niet bereikbaar: strengere daglimiet actief."
    return {"state": "active", "label": "AI actief",
            "message": "AI helpt met zoekwoorden en het filteren van resultaten. " + note}


def reset_for_tests():
    flush()
    with _lock:
        _state.update(month="", month_usd=0.0, day="", day_calls=0, blocked_until=0.0, last_error="")
        _snap.update(at=0.0, periods=None, value=None, pending=None)
        _cache.clear()


def reserve(estimate):
    monthly, daily = limits()
    now = time.time()
    stored = _stored(now, RESERVE_WAIT)
    with _lock:
        _roll(now)
        if now < _state["blocked_until"]:
            raise AIUnavailable("cooldown", _state["last_error"] or "AI tijdelijk gepauzeerd na een fout.")
        month_usd = max(stored[0] if stored else 0.0, _state["month_usd"])
        day_calls = max(stored[1] if stored else 0, _state["day_calls"])
        if day_calls >= (daily if stored else min(daily, UNPERSISTED_DAILY_CALLS)):
            raise AIUnavailable("limit", "Daglimiet voor AI-aanroepen bereikt; normaal zoeken is actief.")
        if month_usd + estimate > monthly:
            raise AIUnavailable("budget", "Intern maandbudget voor AI in NUVEMIXA bereikt; normaal zoeken is actief.")
        try:
            import nv_store
            reservation = nv_store.reserve_ai(estimate, monthly, daily)
        except Exception:
            raise AIUnavailable('budget_store', 'Centrale AI-budgetcontrole niet beschikbaar of limiet bereikt; normaal zoeken is actief.') from None
        _state["day_calls"] += 1
        _state["month_usd"] += estimate  # voorlopig; na het antwoord vervangen door het werkelijke verbruik
    _add_to_snapshot(now, estimate, 1)
    return reservation


def settle(estimate, actual, reservation=None):
    if reservation:
        import nv_store
        nv_store.settle_ai(reservation,actual)
    with _lock:
        _state["month_usd"] = max(0.0, _state["month_usd"] - estimate + actual)
    if actual != estimate:
        _add_to_snapshot(time.time(), actual - estimate, 0)


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
    reservation = reserve(estimate_usd)
    request = urllib.request.Request(API_BASE + path, method="POST", data=json.dumps(data).encode(),
                                     headers={"Authorization": "Bearer " + api_key(),
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read(max_bytes)
    except urllib.error.HTTPError as exc:
        settle(estimate_usd, estimate_usd if exc.code >= 500 else 0.0, reservation)
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
        settle(estimate_usd, estimate_usd, reservation)
        timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
        text = (f"De AI-dienst reageerde niet binnen {timeout} seconden." if timed_out
                else "De AI-dienst is niet bereikbaar.")
        _block(COOLDOWN_AFTER_ERROR, text)
        raise AIUnavailable("timeout" if timed_out else "network", text) from None
    if not raw or not raw.strip():
        settle(estimate_usd, estimate_usd, reservation)
        raise AIUnavailable("empty", "De AI-dienst gaf een leeg antwoord.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        settle(estimate_usd, estimate_usd, reservation)
        raise AIUnavailable("invalid_json", "De AI-dienst gaf een onleesbaar antwoord.") from None
    web_calls = sum(1 for item in payload.get("output", []) or [] if isinstance(item, dict)
                    and item.get("type") == "web_search_call")
    settle(estimate_usd, cost(data.get("model", ""), payload.get("usage"), web_calls), reservation)
    return payload


def chat_json(task, system, user_payload, *, max_tokens=200, timeout=5):
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
