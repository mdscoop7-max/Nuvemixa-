"""Read-only WooCommerce console for the existing NUVEMIXA Flask application.

Register with app.register_blueprint(nuvemixa_woo_blueprint). Never put API
secrets in templates, frontend JavaScript or an unencrypted repository.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from collections import Counter
from urllib.parse import urlsplit

import requests
from flask import Blueprint, current_app, make_response, redirect, render_template, url_for

nuvemixa_woo_blueprint = Blueprint("nuvemixa_woo", __name__, template_folder="templates", static_folder="static", static_url_path="/admin/commerce-assets")

class CommerceConnectionError(Exception):
    """Controlled error without leaking credentials or customer information."""


def _admin_required():
    # Uses the existing NUVEMIXA admin policy, not a new independent login.
    checker = current_app.extensions.get("nuvemixa_admin_checker")
    # Reuse the existing admin policy: session, expiration and any extra checks.
    # Fail closed if the application has not explicitly provided that policy.
    return bool(callable(checker) and checker())


def _config():
    base = os.environ.get("NUVEMIXA_WOO_URL", "").strip().rstrip("/")
    key = os.environ.get("NUVEMIXA_WOO_KEY", "").strip()
    secret = os.environ.get("NUVEMIXA_WOO_SECRET", "").strip()
    if not (base and key and secret):
        return None
    try:
        url = urlsplit(base)
        port = url.port
    except ValueError as exc:
        raise CommerceConnectionError("WooCommerce-adres is ongeldig.") from exc
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or port not in (None, 443)):
        raise CommerceConnectionError("WooCommerce-configuratie is ongeldig: gebruik een HTTPS-adres zonder extra parameters.")
    # Allow a WordPress subdirectory, but prevent path traversal.
    if any(p in (".", "..") for p in url.path.split("/")) or "%" in url.path:
        raise CommerceConnectionError("WooCommerce-pad is niet toegestaan.")
    # The environment value is administrator-controlled. Require an explicit
    # hostname lock to prevent accidental calls to an unrelated target.
    lock = os.environ.get("NUVEMIXA_WOO_HOST", "").strip().lower()
    if not lock or url.hostname.lower() != lock:
        raise CommerceConnectionError("WooCommerce-hostnaam is niet expliciet bevestigd.")
    return base, key, secret, url.hostname


def read_configuration_present():
    return all(os.environ.get("NUVEMIXA_WOO_" + key, "").strip() for key in ("URL", "KEY", "SECRET", "HOST"))


# --- Verbindingsstatus (vier toestanden) -------------------------------------------------
# Alleen in het geheugen: een herstart zet de status terug naar "nog niet getest".
# Er worden nooit sleutels, geheimen of volledige adressen in een melding opgenomen.
import time as _time

_REQUIRED = ("URL", "KEY", "SECRET", "HOST")
TEST_VALID_SECONDS = 3600
_LAST_TEST = {"ok": None, "at": 0.0, "reason": "", "success_at": 0.0}
_SNAPSHOT = {"at": 0.0, "products": [], "orders": [], "stats": {}}


def missing_configuration():
    """Alleen de NAMEN van ontbrekende variabelen, nooit waarden."""
    return ["NUVEMIXA_WOO_" + k for k in _REQUIRED if not os.environ.get("NUVEMIXA_WOO_" + k, "").strip()]


def record_test(ok, reason=""):
    now = _time.time()
    _LAST_TEST.update(ok=bool(ok), at=now, reason=str(reason)[:160] if not ok else "")
    if ok:
        _LAST_TEST["success_at"] = now


def reset_test():
    _LAST_TEST.update(ok=None, at=0.0, reason="", success_at=0.0)
    _SNAPSHOT.update(at=0.0, products=[], orders=[], stats={})


def connection_status(now=None):
    """Geeft precies een van: not_configured, configured_untested, connected, error."""
    now = _time.time() if now is None else now
    missing = missing_configuration()
    if not missing:
        fresh = _LAST_TEST["ok"] is not None and now - _LAST_TEST["at"] <= TEST_VALID_SECONDS
        if fresh and _LAST_TEST["ok"]:
            return {"state": "connected", "label": "Verbonden en gecontroleerd", "tone": "ok",
                    "detail": "Laatste alleen-lezen test geslaagd. De test is maximaal een uur geldig.", "missing": []}
        if fresh:
            return {"state": "error", "label": "Verbindingsfout", "tone": "bad",
                    "detail": _LAST_TEST["reason"] or "De alleen-lezen test is mislukt.", "missing": []}
        return {"state": "configured_untested", "label": "Geconfigureerd, nog niet getest", "tone": "warn",
                "detail": "Alle vier variabelen zijn aanwezig. Er is nog geen verbindingstest gedaan: klik op 'Verbinding testen'.", "missing": []}
    legacy = all(os.environ.get(k, "").strip() for k in ("WOOCOMMERCE_URL", "WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET"))
    if legacy and len(missing) == len(_REQUIRED):
        return {"state": "configured_untested", "label": "Geconfigureerd, nog niet getest", "tone": "warn",
                "detail": "Alleen de oudere WOOCOMMERCE_*-variabelen zijn aanwezig. Voor de alleen-lezen test van het dashboard zijn de vier NUVEMIXA_WOO_*-variabelen nodig.",
                "missing": missing}
    partial = len(missing) < len(_REQUIRED)
    return {"state": "not_configured", "label": "Niet ingesteld", "tone": "off",
            "detail": ("Onvolledig. Ontbreekt: " + ", ".join(missing) + ".") if partial
                      else "Er is nog geen WooCommerce-koppeling ingesteld.", "missing": missing}


def read_recent_orders():
    config = _config()
    if config is None:
        return None
    base, key, secret, host = config
    return _fetch(base, (key, secret), "orders?per_page=20&orderby=date&order=desc", host)


def _check_public_dns(host):
    """Reject loopback/local/private/link-local/reserved targets (SSRF defense)."""
    try:
        addresses = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise CommerceConnectionError("WooCommerce-adres is niet bereikbaar via DNS.") from exc
    if not addresses:
        raise CommerceConnectionError("WooCommerce-host heeft geen DNS-adres.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise CommerceConnectionError("WooCommerce moet op een publiek HTTPS-adres staan.")


def _fetch(base, auth, path, host):
    _check_public_dns(host)
    endpoint = base + "/wp-json/wc/v3/" + path
    try:
        # No redirects: do not forward Basic-auth credentials to a redirect.
        with requests.get(endpoint, auth=auth, headers={"Accept": "application/json", "User-Agent": "NUVEMIXA-Commerce-ReadOnly/1.0"},
                          timeout=(3, 8), allow_redirects=False, stream=True) as resp:
            if resp.status_code in (401, 403):
                raise CommerceConnectionError("WooCommerce weigert toegang. Controleer de leesrechten van de API-sleutel.")
            if resp.status_code != 200:
                raise CommerceConnectionError("WooCommerce reageerde niet succesvol (HTTP %d)." % resp.status_code)
            if "application/json" not in resp.headers.get("Content-Type", "").lower():
                raise CommerceConnectionError("WooCommerce gaf geen JSON-antwoord terug.")
            raw = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                raw.extend(chunk)
                if len(raw) > 500_000:
                    raise CommerceConnectionError("WooCommerce-antwoord is te groot.")
            import json
            data = json.loads(raw)
            if not isinstance(data, list):
                raise CommerceConnectionError("WooCommerce gaf een onverwacht antwoord.")
            return data
    except requests.RequestException as exc:
        current_app.logger.warning("WooCommerce connectieprobleem (%s)", exc.__class__.__name__)
        raise CommerceConnectionError("Verbinding met WooCommerce mislukt.") from exc
    except (ValueError, UnicodeError) as exc:
        raise CommerceConnectionError("WooCommerce-antwoord bevat ongeldige gegevens.") from exc


def _safe_preview(rows, resource):
    if resource == "products":
        return [{"id": str(p.get("id", ""))[:20], "name": str(p.get("name") or "Onbekend")[:120],
                 "sku": str(p.get("sku") or "—")[:64], "stock": str(p.get("stock_status") or "onbekend")[:30],
                 "price": str(p.get("price") or "—")[:30]}
                for p in rows if isinstance(p, dict)]
    # No customer addresses, names, emails, IPs or order line items rendered.
    return [{"id": str(p.get("id", ""))[:20], "status": str(p.get("status") or "onbekend")[:32],
             "date": str(p.get("date_created") or "")[:19], "total": str(p.get("total") or "—")[:24]}
            for p in rows if isinstance(p, dict)]


def _when(ts):
    """Leesbaar tijdstip in Nederlandse tijd, of None."""
    if not ts:
        return None
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(ts, ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M")


def _back(**extra):
    from flask import request
    if request.form.get("embedded") == "1":
        extra["embedded"] = "1"
    return redirect(url_for("nuvemixa_woo.commerce_console", **extra), code=303)


def _readonly_config():
    """Geeft (base, key, secret, host) of None. Foutmeldingen bevatten nooit sleutels."""
    return _config()


@nuvemixa_woo_blueprint.get("/admin/commerce")
def commerce_console():
    """Toont alleen de laatst bekende status. Doet GEEN WooCommerce-aanroep."""
    if not _admin_required():
        return redirect(url_for("admin_login"), code=302)
    connection = connection_status()
    state = {"connected": "connected", "error": "error"}.get(connection["state"], "unconfigured")
    context = {"state": state, "error": connection["detail"] if state == "error" else None,
               "products": list(_SNAPSHOT["products"]), "orders": list(_SNAPSHOT["orders"]),
               "stats": dict(_SNAPSHOT["stats"]), "woo_admin": None, "connection": connection,
               "last_success": _when(_LAST_TEST["success_at"]), "snapshot_at": _when(_SNAPSHOT["at"]),
               "can_test": not connection["missing"] and connection["state"] != "not_configured"}
    resp = make_response(render_template("nv_commerce.html", **context))
    resp.headers["Cache-Control"] = "no-store, private, max-age=0"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    # No JavaScript and no remote assets; template loads one own CSS file.
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'"
    return resp


@nuvemixa_woo_blueprint.post("/admin/commerce/test")
def commerce_test():
    """Eén alleen-lezen aanroep (1 product) na een bewuste klik van de eigenaar."""
    if not _admin_required():
        return redirect(url_for("admin_login"), code=302)
    try:
        config = _readonly_config()
        if config is None:
            record_test(False, "WooCommerce is niet (volledig) ingesteld.")
        else:
            base, key, secret, host = config
            _fetch(base, (key, secret), "products?per_page=1", host)
            record_test(True)
    except CommerceConnectionError as exc:
        record_test(False, exc)
    return _back()


@nuvemixa_woo_blueprint.post("/admin/commerce/refresh")
def commerce_refresh():
    """Leest maximaal 20 recente producten en 20 bestellingen (alleen-lezen) na een bewuste klik."""
    if not _admin_required():
        return redirect(url_for("admin_login"), code=302)
    try:
        config = _readonly_config()
        if config is None:
            record_test(False, "WooCommerce is niet (volledig) ingesteld.")
            return _back()
        base, key, secret, host = config
        products = _fetch(base, (key, secret), "products?per_page=20&orderby=date&order=desc", host)
        orders = _fetch(base, (key, secret), "orders?per_page=20&orderby=date&order=desc", host)
        preview_p, preview_o = _safe_preview(products, "products"), _safe_preview(orders, "orders")
        _SNAPSHOT.update(at=_time.time(), products=preview_p, orders=preview_o,
                         stats={"visible_products": len(products), "visible_orders": len(orders),
                                "statuses": dict(Counter(o["status"] for o in preview_o))})
        record_test(True)
    except CommerceConnectionError as exc:
        record_test(False, exc)
    return _back()
