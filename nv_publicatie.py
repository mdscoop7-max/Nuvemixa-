"""Veilige voorbereiding van productpublicatie naar WooCommerce.

Wat dit doet: controleren (prijzen, marge, gegevens, afbeeldingen, dubbele producten), een
WooCommerce-voorbeeld bouwen en een goedkeuring vastleggen die aan de exacte inhoud gebonden is.
Wat dit NIET doet: verzenden. Het enige verzendpunt is ``publish()``; dat weigert zolang er geen
schrijfkoppeling is ingesteld en gebruikt altijd een meegegeven (test)zender. Er is geen echte
WooCommerce-schrijfsleutel of schrijfaanroep aanwezig.
"""
import hashlib
import hmac
import json
import os
import re
import time
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit

BTW = Decimal("0.21")
MIN_MARGE = Decimal("20")          # minimale nettomarge in procent
BETAALKOSTEN = Decimal("0.019")
APPROVAL_VALID_SECONDS = 3600
WRITE_SWITCH = "NUVEMIXA_WOO_WRITE"   # moet expliciet "on" zijn; er bestaat nog geen schrijfsleutelconfiguratie

# TESTDATA: bedragen in centen, verkoopprijs inclusief btw.
TEST_CANDIDATES = {
    "TEST-P1": {"sku": "TEST-P1", "titel": "Testproduct Mini-ventilator USB", "beschrijving": "Compacte USB-ventilator voor bureau en reis. Stil, oplaadbaar en eenvoudig te bevestigen. Voorbeeldtekst voor de voorbereiding.",
                "afbeeldingen": ["https://images.example.invalid/ventilator-1.jpg", "https://images.example.invalid/ventilator-2.jpg"],
                "inkoop": 1150, "verzend": 295, "verkoop": 2995, "leverancier": "Testleverancier A (EU)", "categorie": "Gadgets"},
    "TEST-P2": {"sku": "TEST-P2", "titel": "Testproduct Slimme Plug", "beschrijving": "Slimme stekker met app-bediening. Voorbeeldtekst voor een product dat al in de webshop bestaat.",
                "afbeeldingen": ["https://images.example.invalid/plug-1.jpg"],
                "inkoop": 900, "verzend": 250, "verkoop": 1995, "leverancier": "Testleverancier B (EU)", "categorie": "Smart Home"},
    "TEST-P3": {"sku": "TEST-P3", "titel": "Test", "beschrijving": "Kort.",
                "afbeeldingen": [], "inkoop": 2500, "verzend": 600, "verkoop": 3000, "leverancier": "Testleverancier C", "categorie": "Lifestyle & Sport"},
}
# TESTDATA: producten die "al in WooCommerce staan" wanneer er geen echte leesverbinding is.
TEST_EXISTING = [{"id": 9001, "sku": "TEST-P2", "name": "Testproduct Slimme Plug"}]


def _cents(value):
    return int(Decimal(value).quantize(Decimal("1"), ROUND_HALF_UP))


def margin(candidate):
    """Netto marge: (verkoop excl. btw - inkoop - verzend - betaalkosten) / verkoop excl. btw."""
    verkoop, inkoop = candidate.get("verkoop") or 0, candidate.get("inkoop") or 0
    if verkoop <= 0:
        return None
    net = Decimal(verkoop) / (1 + BTW)
    kosten = Decimal(inkoop) + Decimal(candidate.get("verzend") or 0) + Decimal(verkoop) * BETAALKOSTEN
    winst = net - kosten
    return {"netto_verkoop": _cents(net), "kosten": _cents(kosten), "winst": _cents(winst),
            "procent": (winst * 100 / net).quantize(Decimal("0.1"), ROUND_HALF_UP)}


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def find_duplicates(candidate, existing):
    hits = []
    for item in existing or []:
        same_sku = candidate.get("sku") and _norm(item.get("sku", "")) == _norm(candidate["sku"])
        same_name = _norm(item.get("name", "")) == _norm(candidate.get("titel", ""))
        if same_sku or same_name:
            hits.append({"id": item.get("id"), "reden": "zelfde SKU" if same_sku else "zelfde titel"})
    return hits


def _https_image(url):
    try:
        parts = urlsplit(str(url))
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.hostname) and not parts.username and bool(re.search(r"\.(jpe?g|png|webp)$", parts.path, re.I))


def check(candidate, existing):
    """Geeft de controlelijst terug: elke regel heeft stap, status ('ok', 'let op', 'fout') en tekst."""
    rows = []

    def add(stap, status, tekst):
        rows.append({"stap": stap, "status": status, "tekst": tekst})

    m = margin(candidate)
    inkoop, verkoop = candidate.get("inkoop") or 0, candidate.get("verkoop") or 0
    add("Inkoopprijs", "ok" if inkoop > 0 else "fout", "Inkoopprijs aanwezig." if inkoop > 0 else "Inkoopprijs ontbreekt of is 0.")
    add("Verkoopprijs", "ok" if verkoop > inkoop > 0 else "fout",
        "Verkoopprijs hoger dan inkoopprijs." if verkoop > inkoop > 0 else "Verkoopprijs ontbreekt of ligt niet boven de inkoopprijs.")
    if m is None:
        add("Winstmarge", "fout", "Marge kan niet worden berekend.")
    elif m["procent"] >= MIN_MARGE:
        add("Winstmarge", "ok", f"Netto marge {m['procent']}% (minimum {MIN_MARGE}%).")
    elif m["procent"] > 0:
        add("Winstmarge", "let op", f"Netto marge {m['procent']}% ligt onder het minimum van {MIN_MARGE}%.")
    else:
        add("Winstmarge", "fout", f"Verlies: netto marge {m['procent']}%.")
    titel, tekst = str(candidate.get("titel", "")).strip(), str(candidate.get("beschrijving", "")).strip()
    add("Producttitel", "ok" if 10 <= len(titel) <= 120 else "fout", "Titel heeft een goede lengte." if 10 <= len(titel) <= 120 else "Titel moet 10 tot 120 tekens zijn.")
    add("Beschrijving", "ok" if len(tekst) >= 40 else "fout", "Beschrijving is voldoende uitgebreid." if len(tekst) >= 40 else "Beschrijving is korter dan 40 tekens.")
    images = candidate.get("afbeeldingen") or []
    good = [u for u in images if _https_image(u)]
    add("Afbeeldingen", "ok" if good and len(good) == len(images) else "fout",
        f"{len(good)} geldige https-afbeelding(en)." if good and len(good) == len(images) else "Minstens één geldige https-afbeelding (jpg, png of webp) nodig; ongeldige links gevonden of geen afbeeldingen.")
    add("SKU", "ok" if re.fullmatch(r"[A-Za-z0-9._-]{3,64}", str(candidate.get("sku", ""))) else "fout",
        "SKU is geldig." if re.fullmatch(r"[A-Za-z0-9._-]{3,64}", str(candidate.get("sku", ""))) else "SKU ontbreekt of is ongeldig.")
    dup = find_duplicates(candidate, existing)
    add("Bestaat al in WooCommerce", "fout" if dup else "ok",
        ("Bestaat al (" + ", ".join(f"#{d['id']}: {d['reden']}" for d in dup) + ").") if dup else "Geen dubbel product gevonden.")
    return rows


def blocking(rows):
    return [r for r in rows if r["status"] == "fout"]


def payload(candidate):
    """WooCommerce-voorbeeld. Altijd status 'draft': publiceren is een aparte, door de eigenaar goedgekeurde stap."""
    return {
        "name": str(candidate["titel"]).strip(), "type": "simple", "status": "draft", "sku": candidate["sku"],
        "regular_price": f"{Decimal(candidate['verkoop']) / 100:.2f}",
        "description": str(candidate["beschrijving"]).strip(),
        "images": [{"src": u} for u in candidate.get("afbeeldingen", [])],
        "meta_data": [{"key": "_nuvemixa_leverancier", "value": candidate.get("leverancier", "")}],
    }


def digest(candidate):
    return hashlib.sha256(json.dumps(payload(candidate), sort_keys=True).encode()).hexdigest()


def sign_approval(secret, candidate, now=None):
    stamp = int(now if now is not None else time.time())
    mac = hmac.new(secret.encode(), f"{candidate['sku']}|{digest(candidate)}|{stamp}".encode(), hashlib.sha256).hexdigest()
    return f"{stamp}.{mac}"


def approval_valid(secret, candidate, token, now=None):
    try:
        stamp, mac = str(token).split(".", 1)
        stamp_value = int(stamp)
    except (ValueError, AttributeError):
        return False
    current = int(now if now is not None else time.time())
    if not 0 <= current - stamp_value <= APPROVAL_VALID_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{candidate['sku']}|{digest(candidate)}|{stamp_value}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, expected)


class PublishRefused(Exception):
    """Publicatie is geweigerd; de tekst is veilig om te tonen."""


def write_connection_ready():
    return os.getenv(WRITE_SWITCH, "off").strip().lower() == "on"


def publish(candidate, existing, secret, token, sender=None):
    """Het enige verzendpunt. ``sender`` is een functie(payload) -> dict; zonder zender wordt nooit verzonden."""
    rows = check(candidate, existing)
    if blocking(rows):
        raise PublishRefused("Er zijn nog fouten in de controle: " + ", ".join(r["stap"] for r in blocking(rows)) + ".")
    if not approval_valid(secret, candidate, token):
        raise PublishRefused("Geen geldige goedkeuring voor precies deze productgegevens (verlopen of gewijzigd).")
    if not write_connection_ready() or sender is None:
        raise PublishRefused("Niet verzonden: de WooCommerce-schrijfkoppeling is niet ingesteld.")
    return sender(payload(candidate))


def existing_products():
    """Bestaande WooCommerce-producten (alleen lezen). Zonder leesverbinding worden TESTDATA-producten gebruikt."""
    from nv_woo_bridge import CommerceConnectionError, _config, _fetch
    try:
        config = _config()
        if config:
            base, key, secret, host = config
            rows = _fetch(base, (key, secret), "products?per_page=100&orderby=date&order=desc", host)
            return [{"id": r.get("id"), "sku": r.get("sku", ""), "name": r.get("name", "")} for r in rows if isinstance(r, dict)], "echt", None
    except CommerceConnectionError as exc:
        return TEST_EXISTING, "test", str(exc)
    return TEST_EXISTING, "test", None
