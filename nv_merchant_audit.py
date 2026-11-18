from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from nuvemixa_integrations import MERCHANT_PREVIEW_ORIGIN, merchant_product_checks

GUIDANCE = {
    "interne goedkeuring": ("merchant_verified", "Laat het product na broncontrole intern goedkeuren."),
    "leverancier": ("supplier_verified", "Bevestig de leverancier en het leverbare artikel."),
    "productgegevens": ("product_data_verified", "Vergelijk de specificaties met de leveranciersbron en productpagina."),
    "prijsverificatie": ("price_verified", "Bevestig de verkoopprijs in EUR op de productpagina en in de checkout."),
    "beeldverificatie": ("image_verified", "Controleer of de afbeelding het geleverde artikel toont."),
    "verzending": ("delivery_verified", "Bevestig levertijd, verzendkosten en verkoopland."),
    "product-ID": ("id", "Gebruik een stabiele, unieke product-ID van maximaal 50 tekens."),
    "titel": ("title", "Gebruik de productnaam op de landingspagina, maximaal 150 tekens."),
    "beschrijving": ("description", "Gebruik een geverifieerde beschrijving van maximaal 5000 tekens."),
    "prijs": ("price", "Controleer het positieve bedrag. De XML-preview gebruikt EUR."),
    "valuta": ("currency", "Controleer of de geverifieerde verkoopprijs in EUR staat."),
    "voorraad": ("availability", "Vraag de leverancier om een actuele voorraadstatus."),
    "GTIN": ("gtin", "Controleer de barcode en het controlecijfer bij de fabrikant."),
    "merk en GTIN of MPN": ("brand, gtin, mpn", "Neem merk en productcodes over uit een geverifieerde bron."),
    "tegenstrijdige productidentificatie": ("identifier_exists", "Controleer of de fabrikant productcodes heeft toegewezen."),
    "productlink": ("link", "Gebruik de HTTPS-landingspagina op het geverifieerde winkeldomein."),
    "afbeeldingslink": ("image_link", "Controleer het afbeeldingspad en gebruik een foto van het product."),
    "gegenereerde tijdelijke afbeelding": ("image_link", "Vervang de tijdelijke illustratie door een gecontroleerde afbeelding van het artikel."),
    "dubbele product-ID": ("id", "Gebruik voor ieder product een eigen stabiele ID."),
    "lokaal afbeeldingsbestand ontbreekt": ("image_link", "Herstel het bestand of kies een geverifieerde productafbeelding."),
}
SPECIFICATION = "https://support.google.com/merchants/answer/7052112?hl=nl"


def product_issues(product, static_folder):
    reasons = merchant_product_checks(product)
    if "afbeeldingslink" not in reasons:
        image = urlsplit(urljoin(MERCHANT_PREVIEW_ORIGIN + "/", str(product["image"])))
        path = unquote(image.path)
        if image.netloc.lower() == urlsplit(MERCHANT_PREVIEW_ORIGIN).netloc and path.startswith("/static/"):
            directory = Path(static_folder).resolve()
            try:
                file = (directory / path.removeprefix("/static/")).resolve()
                if not file.is_relative_to(directory) or not file.is_file():
                    reasons.append("lokaal afbeeldingsbestand ontbreekt")
            except (OSError, ValueError):
                reasons.append("lokaal afbeeldingsbestand ontbreekt")
    details = {}
    for key, label, limit in (("id", "product-ID", 50), ("name", "titel", 150),
                              ("description", "beschrijving", 5000)):
        if label in reasons:
            length = len(str(product.get(key) or "").strip())
            details[label] = f"Waarde telt {length} tekens, maximum {limit}." if length else "Waarde ontbreekt."
    if "prijs" in reasons:
        details["prijs"] = "Verwacht een positief bedrag dat exact in centen kan worden weergegeven."
    if "voorraad" in reasons:
        details["voorraad"] = "Geen bevestigde status op voorraad of uitverkocht."
    if "merk en GTIN of MPN" in reasons:
        missing = [label for absent, label in (
            (not str(product.get("brand") or "").strip(), "merk"),
            (not any(str(product.get(key) or "").strip() for key in ("gtin", "mpn")), "GTIN of MPN"),
        ) if absent]
        details["merk en GTIN of MPN"] = "Ontbreekt: " + " en ".join(missing) + "."
    return [issue(reason, details.get(reason)) for reason in reasons]


def issue(reason, detail=None):
    field, solution = GUIDANCE[reason]
    return dict(field=field, reason=reason, solution=solution, detail=detail)


def audit(items, static_folder):
    items = list(items)
    id_counts = Counter(str(item.get("id") or "").strip() for item in items)
    products = []
    counts = Counter()
    for item in items:
        issues = product_issues(item, static_folder)
        identifier = str(item.get("id") or "").strip()
        if identifier and id_counts[identifier] > 1:
            issues.append(issue("dubbele product-ID", f"Deze ID komt {id_counts[identifier]} keer voor."))
        counts.update(issue["reason"] for issue in issues)
        products.append({
            "id": str(item.get("id") or ""), "name": item.get("name"), "price_eur": item.get("price"),
            "category": item.get("category_name"), "product_url": item.get("product_url"),
            "temporary_image": any(i["reason"] == "gegenereerde tijdelijke afbeelding" for i in issues),
            "availability": item.get("stock_status"), "currency": item.get("currency", "EUR"),
            "missing": [issue["reason"] for issue in issues], "issues": issues,
        })
    return {
        "status": "internal_preview_only", "published": False, "google_review": "not_checked",
        "shipping_settings": "not_checked",
        "specification": SPECIFICATION, "total": len(products),
        "ready": sum(not row["issues"] for row in products), "reason_counts": dict(counts),
        "products": products,
    }
