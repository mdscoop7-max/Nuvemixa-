"""Google Authenticator (TOTP) voor NUVEMIXA."""

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
