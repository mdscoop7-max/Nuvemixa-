"""Tijdelijke bevriezing van dashboardschrijfacties tijdens een opslagmigratie.

Standaard UIT (NUVEMIXA_DASHBOARD_FREEZE). Is de schakelaar aan, dan:
- krijgen alle routes die in de dashboarddatabase schrijven een 503 (per route, niet per HTTP-methode);
- worden de twee externe AI-routes geblokkeerd om onnodige API-kosten te voorkomen;
- slaan bezoekerstellers en klantactiviteit stil over (inloggen blijft werken);
- openen SQLite-verbindingen alleen-lezen en worden er geen mappen aangemaakt.
Inloggen met 2FA, uitloggen, winkelwagen en contactformulier schrijven niet in de dashboarddatabase en blijven werken.
"""
import os
import sqlite3
from pathlib import Path

from flask import Response, request

SWITCH = "NUVEMIXA_DASHBOARD_FREEZE"
_TRUE = {"1", "true", "yes", "on"}

# Routes (Flask-endpointnamen) die in de dashboarddatabase schrijven.
WRITE_ENDPOINTS = frozenset({
    "admin_add_research_note",
    "admin_add_supplier",
    "admin_create_customer",
    "customer_register",
    "nv_manage.catalog",
    "nv_manage.save_candidate",   # schrijft alleen via de bestaande leverancierslijst; verstuurt niets
    "nv_manage.sources_test",     # alleen-lezen bronnentest, schrijft niets in de database
    "nv_manage.coupons",
    "nv_manage.password",
    "nv_manage.save_dossier",
    "nv_manage.save_market",
    "nv_manage.save_supplier_comparison",
    "nv_manage.save_viral",
    "nv_manage.seo_scan",
    "nv_manage.team",
})
# Externe (betaalde) AI-aanroepen: tijdens de migratie geblokkeerd.
AI_ENDPOINTS = frozenset({
    "nv_manage.research_suggestion",
    "nv_manage.supplier_ai_search",
    "nv_manage.supplier_search",
})
# Routes die zelf stil overslaan (publieke bezoekmeting, met CORS-antwoord).
IN_PLACE_ENDPOINTS = frozenset({"webshop_visits.webshop_visit"})
# Niet-GET-routes die niet in de dashboarddatabase schrijven.
ALLOWED_ENDPOINTS = frozenset({
    "admin_2fa",
    "admin_2fa_setup",
    "admin_login",
    "admin_logout",
    "admin_supplier_feed_preview",
    "afrekenen",
    "contact",
    "customer_login",
    "customer_logout",
    "nuvemixa_woo.commerce_refresh",      # alleen-lezen WooCommerce, schrijft niets in de database
    "nuvemixa_woo.commerce_test",         # idem: één alleen-lezen aanroep
    "nv_manage.publicatie_goedkeuren",   # schrijft alleen in de sessie, niet in de database
    "nv_manage.publicatie_publiceren",   # verzendt nooit zonder schrijfkoppeling
    "trendmix_assistant",
    "winkelwagen",
    "wishlist",
})
# Alleen deze actie van deze route schrijft (maakt de klantdatabase aan).
MONITORING_ENDPOINT = "admin_monitoring_check"
MONITORING_WRITE_ACTION = "initialize_customers"

MESSAGE = ("Het dashboard staat tijdelijk in onderhoud omdat de opslag wordt verplaatst. "
           "Er is niets opgeslagen. Probeer het over enkele minuten opnieuw.")


def frozen():
    return os.getenv(SWITCH, "").strip().lower() in _TRUE


def sqlite_connect(path, timeout):
    """Normale SQLite-verbinding; alleen-lezen zolang de bevriezing aan staat."""
    if not frozen():
        return sqlite3.connect(str(path), timeout=timeout)
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=timeout)


def blocked(endpoint, method, action=""):
    if endpoint in WRITE_ENDPOINTS or endpoint in AI_ENDPOINTS:
        return True
    return endpoint == MONITORING_ENDPOINT and method == "POST" and action == MONITORING_WRITE_ACTION


def guard():
    if not frozen() or request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    if blocked(request.endpoint, request.method, request.form.get("action", "")):
        response = Response(MESSAGE, status=503, mimetype="text/plain")
        response.headers["Retry-After"] = "120"
        response.headers["Cache-Control"] = "no-store"
        return response
    return None


def init_app(app):
    app.before_request(guard)
