"""Eenmalige, ondertekende inloglink van het NUVEMIXA-dashboard (Render) naar het
reviewbeheer van de webshop (Alwaysdata).

Beide sites delen de geheime sleutel NUVEMIXA_REVIEWS_SSO_SECRET. Een link is
60 seconden geldig, kan maar één keer gebruikt worden en geeft alleen toegang
als de handtekening klopt. Zonder sleutel is de functie uitgeschakeld.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

GELDIGHEID = 60
DOEL = "nuvemixa-reviews-sso-v1"


SLEUTELBESTAND = Path(__file__).resolve().parent / ".nv_reviews_sso_secret"


def _sleutel():
    waarde = os.environ.get("NUVEMIXA_REVIEWS_SSO_SECRET", "").strip()
    if not waarde:
        try:
            waarde = SLEUTELBESTAND.read_text(encoding="utf-8").strip()
        except OSError:
            waarde = ""
    return waarde if len(waarde) >= 32 else ""


def ingeschakeld():
    return bool(_sleutel())


def _handtekening(sleutel, verloopt, nonce):
    bericht = f"{DOEL}|{verloopt}|{nonce}".encode()
    return hmac.new(sleutel.encode(), bericht, hashlib.sha256).hexdigest()


def maak_token(nu=None):
    sleutel = _sleutel()
    if not sleutel:
        raise RuntimeError("Reviews-SSO niet geconfigureerd")
    verloopt = int(nu if nu is not None else time.time()) + GELDIGHEID
    nonce = secrets.token_urlsafe(18)
    return f"{verloopt}.{nonce}.{_handtekening(sleutel, verloopt, nonce)}"


def _registreer_eenmalig(database, nonce, verloopt, nu):
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database, timeout=10)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS gebruikt (nonce TEXT PRIMARY KEY, verloopt INTEGER NOT NULL)")
        db.execute("DELETE FROM gebruikt WHERE verloopt < ?", (int(nu) - 5,))
        try:
            db.execute("INSERT INTO gebruikt (nonce, verloopt) VALUES (?, ?)", (nonce, verloopt))
        except sqlite3.IntegrityError:
            return False
        db.commit()
        return True
    finally:
        db.close()


def controleer_token(token, database, nu=None):
    """True alleen bij een geldige, niet-verlopen en nog niet gebruikte link."""
    sleutel = _sleutel()
    if not sleutel or not isinstance(token, str) or len(token) > 300:
        return False
    delen = token.split(".")
    if len(delen) != 3:
        return False
    verloopt_tekst, nonce, handtekening = delen
    if not verloopt_tekst.isdigit() or not nonce or len(nonce) > 64:
        return False
    verloopt = int(verloopt_tekst)
    nu = int(nu if nu is not None else time.time())
    if verloopt < nu or verloopt > nu + GELDIGHEID + 5:
        return False
    if not hmac.compare_digest(_handtekening(sleutel, verloopt, nonce), handtekening):
        return False
    return _registreer_eenmalig(database, nonce, verloopt, nu)


def registreer_ontvanger(app, database):
    """Voeg de ontvangende route toe aan de webshop (Alwaysdata)."""
    from flask import abort, redirect, request, session

    @app.route("/admin/reviews/sso")
    def nv_reviews_sso_ontvang():
        if not ingeschakeld():
            abort(404)
        if not controleer_token(request.args.get("t", ""), database):
            abort(403)
        session.clear()
        session["nv_admin"] = True
        response = redirect("/admin/reviews")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return nv_reviews_sso_ontvang
