"""Dashboardroute en sjablooncontext voor het open webonderzoek (nv_web_discovery).

Eén zoekcomponent voor Productonderzoek & niches, Leveranciers, Dropshipping, Groothandels/fabrikanten, Partners en
Internationaal marktonderzoek. De pagina laadt direct; de AI-zoekopdracht loopt apart (JSON), zodat een trage bron
nooit de hele dashboardpagina laat vastlopen (gunicorn-time-out van 30 s).
"""
import os
import threading
import time
from datetime import datetime, timezone

from flask import abort, current_app, jsonify, request, session

import nv_openai
import nv_web_discovery as engine
from nv_dashboard_manager import bp
from nv_permissions import allowed

DAILY_VARIABLE = "NUVEMIXA_WEB_RESEARCH_DAILY_LIMIT"
DEFAULT_DAILY = 25          # extra rem per dag; het centrale AI-maandbudget (nv_openai) blijft de echte grens
COOLDOWN_SECONDS = 8
SECTION_KIND = {"onderzoek": "products", "leveranciers": "suppliers", "partners": "partners",
                "internationaal": "suppliers"}
SECTION_TITLE = {
    "onderzoek": "Live webonderzoek: producten en niches bij leveranciers",
    "leveranciers": "Leveranciers, dropshipping en groothandels zoeken (live web + controle)",
    "partners": "Partners live zoeken op het web",
    "internationaal": "Internationaal: leveranciers per land zoeken",
}
_lock = threading.Lock()
_busy = threading.Semaphore(2)
_usage = {"day": "", "count": 0}


def daily_limit():
    try:
        return max(0, int(os.getenv(DAILY_VARIABLE, "").strip() or DEFAULT_DAILY))
    except ValueError:
        return DEFAULT_DAILY


def usage():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _lock:
        if _usage["day"] != day:
            _usage.update(day=day, count=0)
        return {"used": _usage["count"], "limit": daily_limit()}


def reserve():
    state = usage()
    saved = session.get("nv_web_research_usage")
    saved = saved if isinstance(saved, dict) and saved.get("d") == _usage["day"] else {"d": _usage["day"], "c": 0}
    if state["used"] >= state["limit"] or saved.get("c", 0) >= state["limit"]:
        return False
    with _lock:
        _usage["count"] += 1
    session["nv_web_research_usage"] = {"d": _usage["day"], "c": int(saved.get("c", 0)) + 1}
    return True


def reply(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/dashboard/onderzoek/webzoeken")
def web_research():
    if not allowed("research"):
        abort(403)
    form = request.form
    term = form.get("term", "")
    kind = form.get("kind", "suppliers")
    exclude = [d.strip().lower() for d in (form.get("exclude") or "").split(",") if d.strip()][:40]
    if not nv_openai.configured():
        return reply({"ok": False, "code": "not_configured", "message": "AI niet beschikbaar: OPENAI_API_KEY ontbreekt "
                      "op Render. Er is niets verzonden."})
    now = time.time()
    if now - session.get("nv_web_research_at", 0) < COOLDOWN_SECONDS:
        return reply({"ok": False, "code": "cooldown", "message": "Wacht een paar seconden voordat je opnieuw zoekt."}, 429)
    if not _busy.acquire(blocking=False):
        return reply({"ok": False, "code": "busy", "message": "Er lopen al twee zoekopdrachten. Wacht tot die klaar zijn."}, 429)
    try:
        try:
            # Eerst valideren en cache bekijken (kost niets); pas bij een echte AI-aanroep telt de daglimiet.
            args = (term, kind, form.get("category", ""), form.get("country", "").upper(), form.get("scope", "all"),
                    exclude)
            payload = engine.cached(engine.prepare(*args)[-1])
            if payload is None:
                if not reserve():
                    return reply({"ok": False, "code": "limit", "message": "Daglimiet voor live webonderzoek bereikt. "
                                  "Er is niets verzonden.", "usage": usage()}, 429)
                session["nv_web_research_at"] = now
                payload = engine.search(*args)
        except engine.SearchError as exc:
            return reply({"ok": False, "code": exc.code, "message": exc.message}, 400)
        except nv_openai.AIUnavailable as exc:
            current_app.logger.warning("Webonderzoek: AI niet beschikbaar (%s)", exc.code)
            return reply({"ok": False, "code": exc.code, "message": "AI niet beschikbaar: " + exc.message})
        current_app.logger.info("Webonderzoek %s: %s kandidaten, %s uniek, %s gecontroleerd, %s ms%s",
                                payload["kind"], payload["meta"]["candidates"], payload["unique_companies"],
                                payload["verified_count"], payload["meta"]["elapsed_ms"],
                                " (cache)" if payload.get("cached") else "")
        return reply({"ok": True, **payload, "usage": usage()})
    finally:
        _busy.release()


def view_context(section):
    if section not in SECTION_KIND:
        return None
    return {"configured": nv_openai.configured(), "section": section, "title": SECTION_TITLE[section],
            "kind": SECTION_KIND[section], "kinds": [(k, v[0]) for k, v in engine.KINDS.items()],
            "categories": list(engine.CATEGORIES.items()), "countries": sorted(engine.COUNTRY_NAMES.items(),
                                                                                key=lambda item: item[1]),
            "scopes": list(engine.SCOPES.items()), "usage": usage(), "country_required": section == "internationaal"}
