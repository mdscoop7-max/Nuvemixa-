"""Optional evidence prioritisation for the private research dashboard."""
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request

import nv_openai

from flask import abort, current_app, flash, redirect, request, session, url_for

from nuvemixa_admin_store import connect
from nv_dashboard_manager import bp
from nv_permissions import allowed

ACTIONS = {
    "demand": "Zoek een tweede onafhankelijke bron voor vraag in dezelfde markt.",
    "competition": "Vergelijk de prijs inclusief levering bij aanbieders in dit land.",
    "supplier": "Vraag per SKU een schriftelijke dropshippingofferte op.",
    "sample": "Controleer kwaliteit, verpakking en levertijd met een proefbestelling.",
    "costs": "Vul de ontbrekende kosten en het tegenvallende scenario in.",
}


def research_enabled():
    # Centrale configuratie: alleen OPENAI_API_KEY is nodig (NUVEMIXA_AI=off schakelt uit).
    return nv_openai.configured()


def choose_action(country, observations):
    data = {
        "model": nv_openai.model(),
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Choose one next dropshipping research step based on the supplied "
             "market and observed metadata. Return JSON only: {\"action\": <one allowed action ID>, "
             "\"evidence\": <array of row IDs>}. Prefer corroborating demand when evidence is sparse. "
             "No free text, new measurements, supplier claims, or source URLs."},
            {"role": "user", "content": json.dumps({"country": country, "observations": observations,
                                                    "allowed_actions": ACTIONS}, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": 160,
    }
    result = nv_openai.post("chat/completions", data, timeout=7, max_bytes=20_000, estimate_usd=0.001)
    decision = json.loads(result["choices"][0]["message"]["content"])
    action = decision["action"]
    evidence = decision["evidence"]
    if (action not in ACTIONS or not isinstance(evidence, list) or len(evidence) > 12
            or any(type(index) is not int or not 1 <= index <= len(observations) for index in evidence)):
        raise ValueError("Ongeldige aanbeveling")
    return action, list(dict.fromkeys(evidence))


@bp.post("/dashboard/viral/assistant")
def research_suggestion():
    if not allowed("research"):
        abort(403)
    candidate = request.form.get("candidate", type=int)
    if not candidate:
        abort(400)
    destination = url_for("control", section="viral", detail=candidate)
    if not research_enabled():
        flash("De AI-onderzoeksassistent is nog niet geconfigureerd.", "error")
        return redirect(destination, code=303)
    now = time.time()
    last_run = session.get("nv_research_ai_at", 0)
    if 0 <= now - last_run < 20:
        flash("Wacht even voor een nieuwe analyse.", "error")
        return redirect(destination, code=303)
    try:
        with connect() as db:
            row = db.execute("SELECT country FROM viral_candidates WHERE id=?", (candidate,)).fetchone()
            if row is None:
                abort(404)
            rows = db.execute("""SELECT platform, observed, "window", metric, value, estimate
                FROM viral_observations WHERE candidate=?
                ORDER BY observed DESC, platform, metric, "window", source LIMIT 12""", (candidate,)).fetchall()
        if not rows:
            flash("Voeg een controleerbare waarneming toe voordat je AI inschakelt.", "error")
            return redirect(destination, code=303)
        observations = [dict(item, row_id=index) for index, item in enumerate(rows, 1)]
        session["nv_research_ai_at"] = now
        action, matches = choose_action(row["country"], observations)
    except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError, sqlite3.Error,
            nv_openai.AIUnavailable):
        current_app.logger.warning("Onderzoeksassistent niet beschikbaar")
        flash("AI-analyse is tijdelijk niet beschikbaar.", "error")
    else:
        related = ", ".join(f"{observations[i-1]['platform']} {observations[i-1]['observed']} "
                            f"({observations[i-1]['window']} dagen)" for i in matches)
        flash(ACTIONS[action] + (f" Gebaseerd op opgeslagen waarnemingen: {related}." if related else ""), "success")
    return redirect(destination, code=303)
