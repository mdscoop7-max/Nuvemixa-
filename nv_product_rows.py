"""Compacte productrijen voor de zoekresultaten (Productonderzoek, Viral Product Finder, Internationaal).

Alleen een andere weergave van bestaande gegevens: niets wordt toegevoegd of geschat. Prijzen verschijnen
alleen als een bron er werkelijk een levert; leverancier en land alleen als ze bekend zijn.
"""
import re

UNKNOWN = "Onbekend"


def _norm(text):
    return re.sub(r"[^0-9a-z]+", " ", str(text or "").casefold()).strip()


def _price(item):
    facts = item.get("facts") or {}
    for key, label in (("purchase", "Inkoop"), ("market_price", "Verkoopprijs")):
        fact = facts.get(key)
        value = getattr(fact, "value", None)
        if fact is not None and getattr(fact, "unit", "") == "EUR" and value not in (None, True, False, ""):
            return f"{label} € {str(value).replace('.', ',')}"
    return None


def build(products, suppliers=None, categories=None):
    """Zet productresultaten om in rijen. Ontdubbelt producten met dezelfde bron en dezelfde naam."""
    from nv_market_search import attach_supplier_refs, dropship_label

    categories = categories or {}
    by_url = {}
    for company in suppliers or []:
        for product in company.get("products") or []:
            by_url.setdefault(product.get("url"), company)
    items = products
    if items and "supplier_refs" not in items[0]:
        items = attach_supplier_refs(items, suppliers or [])
    rows, seen = [], {}
    for item in items:
        key = (item.get("source"), _norm(item.get("title")))
        if key in seen:
            seen[key]["duplicates"] += 1
            continue
        refs = item.get("supplier_refs") or []
        company = by_url.get(item.get("url"))
        ref = refs[0] if refs else None
        supplier = ref["name"] if ref else (company or {}).get("name") or item.get("source") or UNKNOWN
        origin = (company or {}).get("origin_name") or {"eu": "EU (land onbekend)"}.get((ref or {}).get("region"), UNKNOWN)
        dropship = ref["dropshipping"] if ref else (dropship_label(company) if company else "Niet bevestigd")
        assessment = item.get("assessment") or {}
        row = {"item": item, "title": item.get("title") or "", "url": item.get("url") or "",
               "image": item.get("image") or "", "category": categories.get(item.get("category"), item.get("category") or ""),
               "supplier": supplier, "origin": origin or UNKNOWN, "dropship": dropship, "price": _price(item),
               "source": item.get("source") or "", "status": assessment.get("status") or "",
               "reason": assessment.get("reason") or "", "refs": refs, "duplicates": 0}
        seen[key] = row
        rows.append(row)
    return rows
