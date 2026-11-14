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


@nuvemixa_woo_blueprint.get("/admin/commerce")
def commerce_console():
    if not _admin_required():
        return redirect(url_for("admin_login"), code=302)
    context = {"state": "unconfigured", "error": None, "products": [], "orders": [], "stats": {}, "woo_admin": None}
    try:
        config = _config()
        if config:
            base, key, secret, host = config
            context["woo_admin"] = base + "/wp-admin/"
            products = _fetch(base, (key, secret), "products?per_page=20&orderby=date&order=desc", host)
            orders = _fetch(base, (key, secret), "orders?per_page=20&orderby=date&order=desc", host)
            context["products"] = _safe_preview(products, "products")
            context["orders"] = _safe_preview(orders, "orders")
            context["stats"] = {"visible_products": len(products), "visible_orders": len(orders),
                                "statuses": dict(Counter(p["status"] for p in context["orders"]))}
            context["state"] = "connected"
    except CommerceConnectionError as exc:
        context["state"] = "error"
        context["error"] = str(exc)
    resp = make_response(render_template("nv_commerce.html", **context))
    resp.headers["Cache-Control"] = "no-store, private, max-age=0"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    # No JavaScript and no remote assets; template loads one own CSS file.
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'self'; form-action 'none'"
    return resp
