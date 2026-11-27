"""Zoekgeschiedenis per gebruiker en per zoekbalk, permanent opgeslagen (Neon via nv_research_store).

Geen AI en geen externe aanroepen: alleen lezen/schrijven van de eigen rij. Maximaal 20 termen per zoekbalk,
nieuwste eerst, zonder dubbele termen (hoofdletterongevoelig).
"""
import hashlib
import re

from flask import abort, jsonify, request, session

import nv_research_store as store
from nv_dashboard_manager import bp
from nv_permissions import allowed

MAX_ITEMS = 20
FIELD = re.compile(r"^[a-z0-9_:.-]{3,80}$")


def user_key():
    """Eigenaar of medewerker; nooit e-mailadres of naam in de sleutel."""
    staff = session.get("nv_staff_id")
    who = f"staff:{staff}" if type(staff) is int else ("owner" if session.get("nv_admin") else "")
    if not who:
        abort(403)
    return hashlib.sha256(who.encode()).hexdigest()[:16]


def key_for(field):
    if not FIELD.fullmatch(field or ""):
        abort(400)
    return f"history:v1:{user_key()}:{field}"


def items_for(key):
    row = store.load(key)
    items = (row or {}).get("payload", {}).get("items", [])
    return [item for item in items if isinstance(item, str)][:MAX_ITEMS]


def reply(items):
    response = jsonify({"ok": True, "items": items})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/dashboard/zoekgeschiedenis")
def history_list():
    if not allowed("research"):
        abort(403)
    return reply(items_for(key_for(request.args.get("veld", ""))))


@bp.post("/dashboard/zoekgeschiedenis")
def history_change():
    if not allowed("research"):
        abort(403)
    key = key_for(request.form.get("veld", ""))
    action = request.form.get("actie", "")
    term = " ".join((request.form.get("term") or "").split())[:100]
    items = items_for(key)
    if action == "toevoegen" and len(term) >= 2:
        items = [term, *[item for item in items if item.casefold() != term.casefold()]][:MAX_ITEMS]
    elif action == "verwijderen":
        items = [item for item in items if item.casefold() != term.casefold()]
    elif action == "wissen":
        items = []
    else:
        abort(400)
    store.save(key, "done", {"items": items})
    return reply(items)
