"""Taaloverzicht: leest uit de echte winkelbestanden welke talen beschikbaar zijn."""
import re
from pathlib import Path

NAMEN = {"nl": "Nederlands", "en": "Engels", "fr": "Frans", "it": "Italiaans", "es": "Spaans", "de": "Duits"}
_STATIC = Path(__file__).resolve().parent / "static"


def winkel_talen(static=_STATIC):
    """Talen met interface-teksten in de webshop (static/app.js + static/languages.js)."""
    try:
        app_js = (static / "app.js").read_text(encoding="utf-8")
        extra = (static / "languages.js").read_text(encoding="utf-8")
    except OSError:
        return []
    codes = list(dict.fromkeys(re.findall(r"^\s{1,4}([a-z]{2}):\{", app_js, re.M) + re.findall(r"translations\.([a-z]{2})\s*=\s*\{", extra)))
    rows = []
    for code in codes:
        rows.append({"code": code, "naam": NAMEN.get(code, code.upper()),
                     "interface": f"translations.{code}" in extra or bool(re.search(rf"^\s{{1,4}}{code}:\{{[^\n]*heroTitle", app_js, re.M))})
    return rows


NIET_GEKOPPELD = [
    "Automatisch vertalen van producttitels en productbeschrijvingen (productteksten staan alleen in het Nederlands).",
    "Taalspecifieke SEO-teksten en hreflang-links per taal.",
    "Een vertaaldienst of vertaalabonnement (bewust niet toegevoegd).",
]
