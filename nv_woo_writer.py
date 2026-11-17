"""Voorbereide, standaard uitgeschakelde WooCommerce-schrijfkoppeling: maakt uitsluitend een CONCEPT (draft) aan.

Veiligheid:
- Aparte sleutelvariabelen voor schrijven (NUVEMIXA_WOO_WRITE_KEY / _SECRET); de leessleutel wordt hier nooit gebruikt.
  Nooit sleutels in code of GitHub: alleen de NAMEN staan hier, de waarden staan in Render.
- Alleen https, hostnaamslot (NUVEMIXA_WOO_HOST), geen inloggegevens in de URL, geen redirects, vaste time-outs.
- Het enige pad is POST /wp-json/wc/v3/products met status "draft"; elk ander status wordt geweigerd.
- Eerst een alleen-lezen controle op dezelfde SKU: bestaat die al, dan wordt niets aangemaakt.
- Wordt alleen aangeroepen via nv_publicatie.publish(): na controles, geldige goedkeuring (1 uur, gebonden aan de
  gegevens) en NUVEMIXA_WOO_WRITE=on. Er is geen automatische publicatie en geen verwijder- of wijzigfunctie.
Getest uitsluitend met mocks (tests/test_woo_writer.py); nooit tegen de echte webshop.
"""
import os
from urllib.parse import quote, urlsplit

import requests

WRITE_VARIABLES = ("NUVEMIXA_WOO_URL", "NUVEMIXA_WOO_HOST", "NUVEMIXA_WOO_WRITE_KEY", "NUVEMIXA_WOO_WRITE_SECRET")
TIMEOUT = (5, 15)


class WriteError(Exception):
    """Veilige foutmelding (zonder sleutels of adressen)."""


def missing_configuration():
    """Alleen de NAMEN van ontbrekende variabelen."""
    return [name for name in WRITE_VARIABLES if not os.environ.get(name, "").strip()]


def configured():
    return not missing_configuration()


def _base():
    base = os.environ.get("NUVEMIXA_WOO_URL", "").strip().rstrip("/")
    lock = os.environ.get("NUVEMIXA_WOO_HOST", "").strip().lower()
    try:
        url = urlsplit(base)
        port = url.port
    except ValueError:
        raise WriteError("WooCommerce-adres is ongeldig.") from None
    if (url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment
            or port not in (None, 443) or any(p in (".", "..") for p in url.path.split("/")) or "%" in url.path):
        raise WriteError("WooCommerce-adres is ongeldig: gebruik een https-adres zonder extra onderdelen.")
    if not lock or url.hostname.lower() != lock:
        raise WriteError("WooCommerce-hostnaam is niet expliciet bevestigd.")
    return base


def build_sender(http=None):
    """Geeft een zender(payload)->dict terug, of None zolang de schrijfkoppeling niet is ingesteld."""
    if not configured():
        return None
    base = _base()
    auth = (os.environ["NUVEMIXA_WOO_WRITE_KEY"].strip(), os.environ["NUVEMIXA_WOO_WRITE_SECRET"].strip())
    http = http or requests

    def send(payload):
        if payload.get("status") != "draft":
            raise WriteError("Alleen conceptproducten (draft) worden aangemaakt.")
        sku = str(payload.get("sku", ""))
        if not sku:
            raise WriteError("SKU ontbreekt.")
        endpoint = base + "/wp-json/wc/v3/products"
        try:
            found = http.get(endpoint, params={"sku": sku}, auth=auth, timeout=TIMEOUT, allow_redirects=False)
            if found.status_code != 200 or not isinstance(found.json(), list):
                raise WriteError("WooCommerce gaf een onverwacht antwoord bij de SKU-controle. Er is niets aangemaakt.")
            if found.json():
                raise WriteError("Deze SKU bestaat al in WooCommerce. Er is niets aangemaakt.")
            created = http.post(endpoint, json=payload, auth=auth, timeout=TIMEOUT, allow_redirects=False)
            body = created.json()
        except (requests.RequestException, ValueError):
            raise WriteError("WooCommerce niet bereikbaar of ongeldig antwoord. Controleer in WooCommerce of er een concept is aangemaakt.") from None
        if created.status_code not in (200, 201) or not isinstance(body, dict):
            raise WriteError(f"WooCommerce weigerde het concept (status {created.status_code}). Er is niets gepubliceerd.")
        if body.get("status") != "draft":
            raise WriteError("WooCommerce meldt geen concept-status. Controleer het product direct in WooCommerce.")
        return {"id": body.get("id"), "status": body.get("status"), "sku": body.get("sku", sku)}

    return send
