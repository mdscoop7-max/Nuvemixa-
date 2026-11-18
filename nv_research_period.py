"""Tijdsfilter voor productonderzoek: 7, 14, 30 dagen of 'Slim'.

Het filter werkt alleen op resultaten met een betrouwbare publicatiedatum (publicaties en trendartikelen).
Productcatalogi en leveranciers hebben geen betrouwbare datum en worden daarom nooit door het filter verwijderd.
"""
from datetime import date, timedelta

CHOICES = {"slim": "Slim", "7": "7 dagen", "14": "14 dagen", "30": "30 dagen"}
# 'Slim': viral en trends kort, niches circa een maand, leveranciers zonder tijdsbeperking.
SMART = {"trends": 14, "news": 30, "niche": 30, "products": 30, "product": 30,
         "suppliers": None, "dropship": None, "wholesale": None, "viral": 14, "internationaal": 30}
REASONS = {14: "recente trends en viral onderzoek", 30: "niche- en productonderzoek",
           None: "leveranciersonderzoek: geen tijdsbeperking nodig"}


def resolve(choice, mode):
    """Geeft (dagen of None, uitleg) terug."""
    choice = choice if choice in CHOICES else "slim"
    if choice != "slim":
        return int(choice), f"{choice} dagen (zelf gekozen)"
    days = SMART.get(mode, 30)
    label = "geen tijdsbeperking" if days is None else f"{days} dagen"
    return days, f"Slim: {label} ({REASONS[days]})"


def apply(result, days):
    """Filtert alleen gedateerde publicaties en trendartikelen. Geeft een samenvatting voor de interface."""
    summary = {"days": days, "removed": 0, "undated": 0}
    if not isinstance(result, dict) or result.get("error") or days is None:
        return summary
    start = (date.today() - timedelta(days=days)).isoformat()
    for key in ("news", "trends"):
        kept = []
        for item in result.get(key) or []:
            stamp = str(item.get("date") or "")
            if not stamp:
                summary["undated"] += 1
                continue  # zonder datum nooit als recente trend tonen
            if stamp[:10] >= start:
                kept.append(item)
            elif key == "news":
                summary["removed"] += 1
        result[key] = kept
    return summary
