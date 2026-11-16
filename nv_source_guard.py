"""Beschermt externe bronnen tegen overbelasting en respecteert blokkades.

- Gedeelde cache (10 minuten): dezelfde aanvraag door AI Productonderzoek, Viral en Internationaal
  wordt maar één keer bij de bron opgehaald. Gelijktijdige identieke aanvragen delen één verzoek.
- Maximaal aantal gelijktijdige verzoeken per bron en in totaal.
- Bij HTTP 429 en 503 wordt Retry-After gerespecteerd; bij 403 en 429 wordt de bron gepauzeerd.
  Er wordt niets omzeild: een gepauzeerde bron krijgt geen verzoeken tot de pauze voorbij is.
"""
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TIMEZONE = ZoneInfo("Europe/Amsterdam")
CACHE_TTL = 600
CACHE_MAX_BYTES = 48_000_000
GLOBAL_LIMIT = 16
DEFAULT_HOST_LIMIT = 2
SLOT_WAIT = 4.0
PAUSES = {403: 1800, 429: 300, 503: 120}
MAX_PAUSE = 900

_lock = threading.Lock()
_blocked = {}
_semaphores = {}
_cache = OrderedDict()
_cache_bytes = 0
_key_locks = {}
_global = threading.BoundedSemaphore(GLOBAL_LIMIT)


class SourceBlocked(requests.RequestException):
    """De bron is gepauzeerd of er was geen vrije verbinding. Er is geen verzoek verstuurd."""


def reset():
    global _cache_bytes, _global
    with _lock:
        _blocked.clear()
        _semaphores.clear()
        _cache.clear()
        _key_locks.clear()
        _cache_bytes = 0
        _global = threading.BoundedSemaphore(GLOBAL_LIMIT)


def host_limit(host):
    return 4 if host == "syncee.com" or host.endswith(".syncee.com") else DEFAULT_HOST_LIMIT


def clock(seconds):
    return datetime.fromtimestamp(time.time() + seconds, TIMEZONE).strftime("%H:%M")


def pause_for(status, retry_after=None):
    if status not in PAUSES:
        return 0
    if retry_after is not None and 0 <= retry_after <= MAX_PAUSE:
        return max(retry_after, 1)
    return PAUSES[status]


def block(host, status, retry_after=None):
    seconds = pause_for(status, retry_after)
    if seconds:
        with _lock:
            _blocked[host] = (time.monotonic() + seconds, time.time() + seconds, status)


def check(host):
    with _lock:
        entry = _blocked.get(host)
        if entry and entry[0] <= time.monotonic():
            del _blocked[host]
            entry = None
    if entry:
        left = entry[1] - time.time()
        raise SourceBlocked(f"gepauzeerd tot {clock(left)} na HTTP {entry[2]}: bron beperkt of blokkeert verzoeken")


def retry_after(error):
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    try:
        return float(headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None


@contextmanager
def slot(host):
    with _lock:
        semaphore = _semaphores.setdefault(host, threading.BoundedSemaphore(host_limit(host)))
    if not semaphore.acquire(timeout=SLOT_WAIT):
        raise SourceBlocked("bron is druk bezet, later opnieuw proberen")
    try:
        if not _global.acquire(timeout=SLOT_WAIT):
            raise SourceBlocked("te veel gelijktijdige zoekopdrachten, later opnieuw proberen")
        try:
            yield
        finally:
            _global.release()
    finally:
        semaphore.release()


def cache_get(key):
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] > time.monotonic():
            _cache.move_to_end(key)
            return entry[1]
        if entry:
            _drop(key)
    return None


def _drop(key):
    global _cache_bytes
    entry = _cache.pop(key, None)
    if entry:
        _cache_bytes -= len(entry[1])


def cache_put(key, body):
    global _cache_bytes
    if len(body) > CACHE_MAX_BYTES // 2:
        return
    with _lock:
        _drop(key)
        _cache[key] = (time.monotonic() + CACHE_TTL, body)
        _cache_bytes += len(body)
        while _cache_bytes > CACHE_MAX_BYTES and _cache:
            _drop(next(iter(_cache)))


def shared(key, produce):
    """Geef een gecachet antwoord of laat precies één thread het ophalen. Fouten worden niet gecachet."""
    hit = cache_get(key)
    if hit is not None:
        return hit
    with _lock:
        key_lock = _key_locks.setdefault(key, threading.Lock())
    with key_lock:
        hit = cache_get(key)
        if hit is not None:
            return hit
        try:
            body = produce()
            cache_put(key, body)
        finally:
            with _lock:
                _key_locks.pop(key, None)
        return body
