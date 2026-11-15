"""Google Authenticator-koppeling voor het NUVEMIXA-dashboard."""
import time
import pyotp

import nv_2fa_postgres as postgres

from nv_2fa import controleer_code
from nv_2fa_storage import laden, verbruik_herstelcode


def is_2fa_actief():
    """Controleer actieve 2FA en fail-closed bij een verplichte ontbrekende opslag."""
    if postgres.enabled():
        return postgres.is_active()

    from nv_2fa_status import is_verplicht

    verplicht = is_verplicht()
    try:
        gegevens = laden()
    except FileNotFoundError:
        if verplicht:
            raise RuntimeError("Verplichte 2FA-opslag ontbreekt")
        return False
    except Exception:
        if verplicht:
            raise
        raise

    if verplicht and gegevens.get("enabled") is not True:
        raise RuntimeError("Verplichte 2FA is niet actief in opslag")
    return gegevens.get("enabled") is True


def controleer_tweede_stap(code):
    """Controleer TOTP (eenmalige tijdstap) of een eenmalige herstelcode."""
    gegevens = laden()
    if gegevens.get("enabled") is not True:
        return False

    if controleer_code(gegevens["totp_secret"], code):
        from nv_2fa_replay import registreer_eenmalig
        totp = pyotp.TOTP(gegevens["totp_secret"])
        huidige_stap = int(time.time()) // totp.interval
        genormaliseerd = str(code).strip()
        for stap in (huidige_stap - 1, huidige_stap, huidige_stap + 1):
            if hmac_compare(totp.at(stap * totp.interval), genormaliseerd):
                return registreer_eenmalig(stap)
        return False

    return verbruik_herstelcode(code)


def hmac_compare(a, b):
    import hmac
    return hmac.compare_digest(str(a), str(b))
