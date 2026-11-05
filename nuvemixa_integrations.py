"""NUVEMIXA optional integrations: safe read-only checks and verified export.

Never creates Mollie payments, RankFix scans, supplier orders or Google publications.
"""
import json
import csv
import io
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation


def rankfix_scan_url(site_url=None):
    """Deep-link to existing RankFix authenticated dashboard, no stored secrets."""
    configured = os.getenv("RANKFIX_BASE_URL", "https://rankfix-app.onrender.com").strip()
    parsed = urllib.parse.urlsplit(configured)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    # Site admin must explicitly choose the actual RankFix server. Never send API tokens in URLs.
    if parsed.path not in ("", "/"):
        return None
    site = (site_url or os.getenv("SITE_URL") or "https://nuvemixa.alwaysdata.net/").strip()
    parsed_site = urllib.parse.urlsplit(site)
    if parsed_site.scheme != "https" or parsed_site.hostname != "nuvemixa.alwaysdata.net":
        return None
    return urllib.parse.urlunsplit(("https", parsed.netloc, "/dashboard/scan", urllib.parse.urlencode({"url": site}), ""))


def mollie_readonly_check():
    """Read-only test of payment provider credentials. Never creates a payment."""
    key = os.getenv("MOLLIE_API_KEY", "").strip()
    if not key:
        return {"state": "not_configured", "message": "Geen Mollie-sleutel ingesteld."}
    if not (key.startswith("test_") or key.startswith("live_")):
        return {"state": "invalid_configuration", "message": "Mollie-sleutelformaat ongeldig."}
    request = urllib.request.Request(
        "https://api.mollie.com/v2/methods?limit=1",
        headers={"Authorization": "Bearer " + key, "Accept": "application/hal+json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8, context=ssl.create_default_context()) as response:
            if response.status != 200:
                return {"state": "unavailable", "message": "Mollie gaf geen geldig antwoord."}
            data = json.loads(response.read(65536))
            if not isinstance(data, dict) or data.get("resource") != "list":
                return {"state": "unexpected_response", "message": "Antwoord niet herkend."}
            return {"state": "connected_test" if key.startswith("test_") else "connected_live_credentials",
                    "message": "API-sleutel geverifieerd met een alleen-lezen aanvraag; betaalproces niet getest."}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {"state": "unavailable", "message": "Mollie-verbinding is niet bevestigd."}


def merchant_feed_preview(items, base_url="https://nuvemixa.alwaysdata.net"):
    """Generate XML of eligible products for private inspection only.

    No feed URL is publicly published, submitted to Google or listed in robots.txt.
    """
    ET.register_namespace("g", "http://base.google.com/ns/1.0")
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "NUVEMIXA interne Merchant-preview (niet gepubliceerd)"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = "Uitsluitend intern gecontroleerde producten."
    count = 0
    for p in items:
        if not isinstance(p, dict) or not p.get("merchant_verified"):
            continue
        # Explicit opt-in plus verified details: never infer compliance from a test catalogue.
        required = ["id", "name", "image", "product_url", "brand"]
        if any(not p.get(k) for k in required):
            continue
        if p.get("stock_status") not in ("in_stock", "out_of_stock"):
            continue
        if not all(p.get(flag) is True for flag in (
            "supplier_verified", "product_data_verified", "price_verified",
            "image_verified", "delivery_verified"
        )):
            continue
        try:
            price = Decimal(str(p.get("price", "")))
            if not price.is_finite() or price <= 0:
                continue
        except (InvalidOperation, ValueError, TypeError):
            continue
        product_url = urllib.parse.urljoin(base_url + "/", str(p["product_url"]).lstrip("/"))
        image_url = urllib.parse.urljoin(base_url + "/", str(p["image"]).lstrip("/"))
        if not all(urllib.parse.urlsplit(url).hostname == urllib.parse.urlsplit(base_url).hostname
                   and urllib.parse.urlsplit(url).scheme == "https"
                   for url in [product_url, image_url]):
            continue
        row = ET.SubElement(channel, "item")
        ET.SubElement(row, "{http://base.google.com/ns/1.0}id").text = str(p["id"])
        ET.SubElement(row, "title").text = str(p["name"])
        ET.SubElement(row, "link").text = product_url
        ET.SubElement(row, "{http://base.google.com/ns/1.0}image_link").text = image_url
        ET.SubElement(row, "{http://base.google.com/ns/1.0}brand").text = str(p["brand"])
        ET.SubElement(row, "{http://base.google.com/ns/1.0}price").text = f"{price:.2f} EUR"
        ET.SubElement(row, "{http://base.google.com/ns/1.0}availability").text = p["stock_status"]
        count += 1
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), count


def supplier_csv_preview(raw):
    """Validate UTF-8 CSV supplier inventory without writing or importing any products.

    Required columns: sku,name,price,stock. All data is considered unverified.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > 60000:
        raise ValueError("CSV moet tussen 1 en 60000 bytes zijn.")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV moet UTF-8 zijn.") from exc
    try:
        rows = csv.DictReader(io.StringIO(decoded), delimiter=",")
        fields = rows.fieldnames or []
        required = {"sku", "name", "price", "stock"}
        if not required.issubset(set(fields)):
            raise ValueError("Verwachte kolommen: sku,name,price,stock.")
        checked = []
        seen = set()
        for i, row in enumerate(rows):
            if i >= 150:
                raise ValueError("Maximaal 150 rijen per controle.")
            sku = str(row.get("sku") or "").strip()[:100]
            name = str(row.get("name") or "").strip()[:200]
            price_text = str(row.get("price") or "").strip()
            stock_text = str(row.get("stock") or "").strip()
            problems = []
            if not sku or sku in seen:
                problems.append("SKU ontbreekt of is dubbel")
            if not name:
                problems.append("Productnaam ontbreekt")
            try:
                amount = Decimal(price_text)
                if not amount.is_finite() or amount <= 0:
                    problems.append("Ongeldige prijs")
            except (InvalidOperation, ValueError):
                problems.append("Ongeldige prijs")
            if not stock_text.isdigit():
                problems.append("Voorraad moet een heel getal zijn")
            seen.add(sku)
            checked.append({"row": i + 2, "sku": sku, "name": name,
                            "problems": problems, "verified": False})
        return {
            "status": "preview_only", "imported": 0, "published": 0,
            "total": len(checked),
            "valid_format": sum(not item["problems"] for item in checked),
            "rows": checked,
            "note": "Formaatcontrole is geen leveranciersverificatie. Er is niets geïmporteerd.",
        }
    except csv.Error as exc:
        raise ValueError("CSV heeft een onjuist formaat.") from exc
