"""Korte cache (max. 60 s) voor de statistieken op het dashboard-hoofdscherm.

Waarom: elke databaseverbinding Render (Oregon) -> Neon (Frankfurt) kost ongeveer 2 seconden en het
hoofdscherm las bij elke weergave het klantenaantal en de webshopbezoekers opnieuw.

Grenzen:
* Alleen gebruikt door het hoofdscherm (section=dashboard). Klanten, Statistieken, Monitoring,
  bestellingen en klantberichten lezen altijd live.
* De cache staat uitsluitend in het geheugen van de server (geen cookie, geen browseropslag, geen
  bestand) en wordt alleen getoond via de bestaande, afgeschermde dashboardroute.
* Alleen geslaagde reads worden bewaard; fouten worden nooit gecachet.
"""
import threading
import time

TTL_SECONDS = 60
_lock = threading.Lock()
_entries = {}


def cached(key, loader, *, ok=lambda value: True, ttl=TTL_SECONDS):
    now = time.monotonic()
    with _lock:
        hit = _entries.get(key)
        if hit and now - hit[0] < min(ttl, TTL_SECONDS):
            return hit[1]
    value = loader()
    if ok(value):
        with _lock:
            _entries[key] = (time.monotonic(), value)
    return value


def clear():
    with _lock:
        _entries.clear()
