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
    trusted_host = os.getenv("RANKFIX_TRUSTED_HOST", "rankfix-app.onrender.com").strip().lower()
    if parsed.hostname.lower() != trusted_host:
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


def merchant_product_checks(item, base_url="https://nuvemixa.alwaysdata.net"):
    missing = []
    verification = {
        "merchant_verified": "interne goedkeuring",
        "supplier_verified": "leverancier",
        "product_data_verified": "productgegevens",
        "price_verified": "prijsverificatie",
        "image_verified": "beeldverificatie",
        "delivery_verified": "verzending",
    }
    missing.extend(label for key, label in verification.items() if item.get(key) is not True)
    for key, limit, label in (("id", 50, "product-ID"), ("name", 150, "titel"),
                              ("description", 5000, "beschrijving")):
        if not 1 <= len(str(item.get(key) or "").strip()) <= limit:
            missing.append(label)
    try:
        price = Decimal(str(item.get("price")))
        if not price.is_finite() or price <= 0 or price != price.quantize(Decimal("0.01")):
            missing.append("prijs")
    except (InvalidOperation, ValueError):
        missing.append("prijs")
    if item.get("currency", "EUR") != "EUR":
        missing.append("valuta")
    if item.get("stock_status") not in ("in_stock", "out_of_stock"):
        missing.append("voorraad")
    gtin = str(item.get("gtin") or "")
    if gtin:
        valid_gtin = (bool(re.fullmatch(r"[0-9]+", gtin)) and len(gtin) in {8, 12, 13, 14}
                      and sum(int(digit) * (1 if index % 2 == 0 else 3)
                              for index, digit in enumerate(reversed(gtin))) % 10 == 0)
        if not valid_gtin:
            missing.append("GTIN")
    no_identifiers = item.get("identifier_exists_verified") is True
    if not no_identifiers and (not item.get("brand") or not (gtin or item.get("mpn"))):
        missing.append("merk en GTIN of MPN")
    if no_identifiers and (gtin or item.get("mpn")):
        missing.append("tegenstrijdige productidentificatie")
    for key, label in (("product_url", "productlink"), ("image", "afbeeldingslink")):
        value = str(item.get(key) or "")
        try:
            url = urllib.parse.urlsplit(urllib.parse.urljoin(base_url.rstrip("/") + "/", value))
            if (not value or any(char.isspace() for char in value) or url.scheme != "https"
                    or not url.hostname or url.username or url.password
                    or (key == "product_url" and url.netloc.lower() != urllib.parse.urlsplit(base_url).netloc.lower())):
                missing.append(label)
            elif key == "image" and url.path.startswith("/img/product/"):
                missing.append("gegenereerde tijdelijke afbeelding")
        except ValueError:
            missing.append(label)
    return missing


def merchant_feed_preview(items, base_url="https://nuvemixa.alwaysdata.net"):
    """Generate the private XML preview from the same checks as the JSON report."""
    namespace = "http://base.google.com/ns/1.0"
    ET.register_namespace("g", namespace)
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "NUVEMIXA interne Merchant-preview"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = "Intern gecontroleerde producten."
    count = 0
    for product in items:
        if merchant_product_checks(product, base_url):
            continue
        attributes = {
            "id": product["id"],
            "title": product["name"],
            "description": product["description"],
            "link": urllib.parse.urljoin(base_url.rstrip("/") + "/", product["product_url"]),
            "image_link": urllib.parse.urljoin(base_url.rstrip("/") + "/", product["image"]),
            "price": f"{Decimal(str(product['price'])):.2f} EUR",
            "availability": product["stock_status"],
        }
        for key in ("brand", "gtin", "mpn"):
            if product.get(key):
                attributes[key] = product[key]
        if product.get("identifier_exists_verified") is True:
            attributes["identifier_exists"] = "no"
        row = ET.SubElement(channel, "item")
        for key, value in attributes.items():
            ET.SubElement(row, f"{{{namespace}}}{key}").text = str(value)
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
