"""Google Authenticator (TOTP) voor NUVEMIXA."""

import hashlib
import hmac
import secrets

import pyotp


def maak_geheime_sleutel():
    return pyotp.random_base32()


def controleer_code(geheime_sleutel, code):
    if not isinstance(code, str):
        return False

    code = code.strip()

    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False

    try:
        return pyotp.TOTP(geheime_sleutel).verify(
            code,
            valid_window=1,
        )
    except (TypeError, ValueError):
        return False


def maak_herstelcodes(aantal=10):
    """Maak herstelcodes en hun SHA-256-hashes."""
    codes = [secrets.token_hex(16) for _ in range(aantal)]
    hashes = [hashlib.sha256(code.encode("ascii")).hexdigest() for code in codes]
    return codes, hashes


def gebruik_herstelcode(code, opgeslagen_hashes):
    """Controleer een herstelcode en verwijder de gebruikte hash."""
    if not isinstance(code, str):
        return False

    code = code.strip().lower()
    if len(code) != 32 or any(c not in "0123456789abcdef" for c in code):
        return False

    kandidaat = hashlib.sha256(code.encode("ascii")).hexdigest()

    for index, opgeslagen in enumerate(opgeslagen_hashes):
        if hmac.compare_digest(kandidaat, opgeslagen):
            opgeslagen_hashes.pop(index)
            return True

    return False
