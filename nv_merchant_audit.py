from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from nuvemixa_integrations import merchant_product_checks

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
    "lokaal afbeeldingsbestand ontbreekt": ("image_link", "Herstel het bestand of kies een geverifieerde productafbeelding."),
}
SPECIFICATION = "https://support.google.com/merchants/answer/7052112?hl=nl"


def product_issues(product, static_folder):
    reasons = merchant_product_checks(product)
    image = urlsplit(product["image"]) if "afbeeldingslink" not in reasons else None
    if image and not image.netloc and image.path.startswith("/static/"):
        directory = Path(static_folder).resolve()
        file = (directory / image.path.removeprefix("/static/")).resolve()
        if not file.is_relative_to(directory) or not file.is_file():
            reasons.append("lokaal afbeeldingsbestand ontbreekt")
    return [dict(field=GUIDANCE[reason][0], reason=reason, solution=GUIDANCE[reason][1])
            for reason in reasons]


def audit(items, static_folder):
    products = []
    counts = Counter()
    for item in items:
        issues = product_issues(item, static_folder)
        counts.update(issue["reason"] for issue in issues)
        products.append({
            "id": str(item["id"]), "name": item["name"], "price_eur": item["price"],
            "availability": item["stock_status"], "currency": item.get("currency", "EUR"),
            "missing": [issue["reason"] for issue in issues], "issues": issues,
        })
    return {
        "status": "internal_preview_only", "published": False, "google_review": "not_checked",
        "specification": SPECIFICATION, "total": len(products),
        "ready": sum(not row["issues"] for row in products), "reason_counts": dict(counts),
        "products": products,
    }
