"""Conservative product research: not a forecast and never fake supplier results."""
from decimal import Decimal
import re

NICHES = {
    "gadgets": ["gadgets", "accessoires", "technologie"],
    "smart-home": ["slim wonen", "sensoren", "smart home"],
    "beauty-care": ["verzorging", "beauty", "persoonlijke verzorging"],
    "home-living": ["huis", "organiseren", "wonen"],
    "lifestyle-sport": ["sport", "fitness", "outdoor"],
}

def review_candidate(name, category, supplier, price, shipping, selling, stock, competition, demand):
    name = str(name).strip()
    if len(name) < 3 or len(name) > 120 or category not in NICHES:
        raise ValueError("Vul een geldige productnaam en categorie in")
    def amount(value):
        try:
            n = Decimal(str(value).replace(",", "."))
            if not n.is_finite() or n < 0 or n > 100000:
                raise ValueError
            return n
        except Exception:
            raise ValueError("Ongeldig bedrag")
    cost = amount(price) + amount(shipping)
    sale = amount(selling)
    profit = sale - cost
    margin = (profit / sale * 100).quantize(Decimal("0.1")) if sale else Decimal("0")
    signals = []
    if not supplier.strip():
        signals.append("Leverancier en leveringsvoorwaarden ontbreken")
    if stock not in ("verified", "unknown"):
        stock = "unknown"
    if stock != "verified":
        signals.append("Voorraad en levertijd zijn niet onafhankelijk bevestigd")
    if competition == "unknown":
        signals.append("Concurrentie niet gemeten")
    if demand == "unknown":
        signals.append("Zoekvolume en vraag niet gemeten")
    if margin < Decimal("25"):
        signals.append("Brutomarge is mogelijk te laag; belastingen, retouren en reclame ontbreken nog")
    if sale <= cost:
        signals.append("Verkoopprijs dekt opgegeven inkoop- en verzendkosten niet")
    verdict = "Verder onderzoeken" if signals else "Handmatig beoordelen"
    return {
        "name": name, "category": category, "supplier": supplier.strip()[:120],
        "cost": cost, "sale": sale, "raw_profit": profit, "raw_margin": margin,
        "niches": NICHES[category], "verdict": verdict, "signals": signals,
        "sales_probability": "Niet meetbaar zonder historische verkoop- en marktgegevens",
        "supplier_comparison": "Geen live leveranciersfeed aangesloten",
        "competition": competition, "demand": demand,
    }
