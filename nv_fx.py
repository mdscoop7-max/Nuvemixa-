"""Omrekening naar euro met de officiële ECB-referentiekoersen (gratis, geen account of abonnement).

Bron: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml (werkdagen rond 16:00 CET bijgewerkt).
Elke omrekening geeft de oorspronkelijke prijs, de valuta, de koers en de koersdatum terug, zodat de margecalculator
nooit een stil omgerekend bedrag toont. Lukt het ophalen niet, dan wordt er NIET omgerekend (geen geschatte koers).
"""
import threading
import time
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_LABEL = "ECB-referentiekoers"
CACHE_SECONDS = 6 * 3600
_lock = threading.Lock()
_state = {"at": 0.0, "date": "", "rates": {}}


class RateUnavailable(Exception):
    pass


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    rates, date = {}, ""
    for node in root.iter():
        if node.tag.endswith("Cube") and node.get("time"):
            date = node.get("time")
        if node.tag.endswith("Cube") and node.get("currency") and node.get("rate"):
            rates[node.get("currency").upper()] = Decimal(node.get("rate"))
    if not rates or not date:
        raise RateUnavailable("ECB-bestand zonder koersen")
    return date, rates


def rates(fetch=None, now=None):
    now = now or time.time()
    with _lock:
        if _state["rates"] and now - _state["at"] < CACHE_SECONDS:
            return _state["date"], dict(_state["rates"])
    try:
        reply = (fetch or requests.get)(ECB_URL, timeout=6, headers={"User-Agent": "NUVEMIXA-dashboard/1.0"})
        reply.raise_for_status()
        date, found = parse(reply.content)
    except (requests.RequestException, ET.ParseError, RateUnavailable, InvalidOperation, AttributeError) as exc:
        with _lock:
            if _state["rates"]:  # liever een koers van eerder vandaag dan geen; de datum staat er altijd bij
                return _state["date"], dict(_state["rates"])
        raise RateUnavailable("ECB-koersen niet bereikbaar") from exc
    with _lock:
        _state.update(at=now, date=date, rates=found)
    return date, dict(found)


def to_eur(amount, currency, fetch=None):
    """Geeft {'eur', 'amount', 'currency', 'rate', 'date', 'source'} of gooit RateUnavailable/ValueError."""
    currency = (currency or "").strip().upper()
    try:
        value = Decimal(str(amount).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Ongeldig bedrag") from exc
    if value < 0 or len(currency) != 3 or not currency.isalpha():
        raise ValueError("Ongeldig bedrag of valuta")
    if currency == "EUR":
        return {"eur": float(value.quantize(Decimal("0.01"))), "amount": float(value), "currency": "EUR",
                "rate": 1.0, "date": "", "source": "Geen omrekening nodig"}
    date, table = rates(fetch)
    if currency not in table:
        raise RateUnavailable(f"Geen ECB-koers voor {currency}")
    rate = table[currency]  # 1 EUR = rate CUR
    eur = (value / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"eur": float(eur), "amount": float(value), "currency": currency, "rate": float(rate), "date": date,
            "source": ECB_LABEL}


def describe(conversion):
    """Korte Nederlandse uitleg, bijv. 'AUD 73,59 = € 41,23 (1 EUR = 1,7849 AUD, ECB-referentiekoers 27-11-2026)'."""
    if conversion["currency"] == "EUR":
        return "Prijs is al in euro; geen omrekening."
    day = "-".join(reversed(conversion["date"].split("-"))) if conversion["date"] else "onbekende datum"
    amount = f"{conversion['amount']:.2f}".replace(".", ",")
    eur = f"{conversion['eur']:.2f}".replace(".", ",")
    rate = f"{conversion['rate']:.4f}".replace(".", ",")
    return (f"{conversion['currency']} {amount} = € {eur} (1 EUR = {rate} {conversion['currency']}, "
            f"{conversion['source']} {day})")
