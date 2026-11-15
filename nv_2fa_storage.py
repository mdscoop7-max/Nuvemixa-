"""Versleutelde, platformonafhankelijke opslag voor NUVEMIXA 2FA."""
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet
import nv_2fa_postgres as postgres
from nv_storage_paths import TWO_FA_DIR

SLEUTELBESTAND = TWO_FA_DIR / "nv_2fa.key"
OPSLAGBESTAND = TWO_FA_DIR / "nv_2fa_secrets.json"
PENDING_BESTAND = TWO_FA_DIR / "nv_2fa_pending.json"
LOCKBESTAND = TWO_FA_DIR / "nv_2fa_storage.lock"


def _beveilig_bestand(path):
    path = Path(path)
    if path.is_symlink():
        raise PermissionError(f"Beveiligd 2FA-bestand mag geen symbolische link zijn: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Beveiligd 2FA-bestand ontbreekt: {path}")
    if os.name != "nt":
        os.chmod(path, 0o600)
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise PermissionError(f"Onvoldoende bestandsrechten voor 2FA-opslag: {path}")


def _fernet():
    # De bestaande sleutel blijft extern/lokaal beheerd; genereer nooit stilzwijgend een nieuwe.
    _beveilig_bestand(SLEUTELBESTAND)
    return Fernet(SLEUTELBESTAND.read_bytes())


@contextmanager
def _bestandsslot():
    LOCKBESTAND.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if LOCKBESTAND.is_symlink():
        raise PermissionError("2FA-lockbestand mag geen symbolische link zijn.")
    with LOCKBESTAND.open("a+b") as slot:
        if os.name != "nt":
            os.fchmod(slot.fileno(), 0o600)
        slot.seek(0, os.SEEK_END)
        if slot.tell() == 0:
            slot.write(b"\0")
            slot.flush()
        slot.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(slot.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                slot.seek(0)
                msvcrt.locking(slot.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(slot.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(slot.fileno(), fcntl.LOCK_UN)


def _atomic_write(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=path.name + ".",
            suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            if os.name != "nt":
                os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_encrypted(path, gegevens):
    encrypted = _fernet().encrypt(json.dumps(gegevens).encode("utf-8"))
    _atomic_write(path, encrypted)


def opslaan(geheime_sleutel, herstel_hashes):
    """Compatibiliteitsfunctie: schrijf een nieuwe, nog niet actieve 2FA-record."""
    gegevens = {
        "totp_secret": geheime_sleutel,
        "recovery_hashes": list(herstel_hashes),
        "enabled": False,
    }
    with _bestandsslot():
        if OPSLAGBESTAND.exists():
            raise FileExistsError("2FA-opslag bestaat al.")
        _write_encrypted(OPSLAGBESTAND, gegevens)


def laden():
    if postgres.enabled():
        return postgres.load()

    _beveilig_bestand(OPSLAGBESTAND)
    encrypted = OPSLAGBESTAND.read_bytes()
    return json.loads(_fernet().decrypt(encrypted))


def bewaar_pending(token, geheime_sleutel, aangemaakt):
    """Bewaar een tijdelijke activatiesleutel versleuteld, nooit in de browsercookie."""
    if postgres.enabled():
        return postgres.store_pending(token, geheime_sleutel)

    gegevens = {
        "token": token,
        "totp_secret": geheime_sleutel,
        "created_at": float(aangemaakt),
    }
    with _bestandsslot():
        _write_encrypted(PENDING_BESTAND, gegevens)


def laad_pending(token, nu):
    if postgres.enabled():
        return postgres.load_pending(token)

    try:
        _beveilig_bestand(PENDING_BESTAND)
        gegevens = json.loads(_fernet().decrypt(PENDING_BESTAND.read_bytes()))
    except FileNotFoundError:
        return None
    if not isinstance(gegevens, dict):
        return None
    if not hmac_compare(str(gegevens.get("token", "")), str(token or "")):
        return None
    if float(nu) - float(gegevens.get("created_at", 0)) > 600:
        wis_pending()
        return None
    return gegevens


def wis_pending():
    with _bestandsslot():
        PENDING_BESTAND.unlink(missing_ok=True)


def activeer(geheime_sleutel, herstel_hashes):
    """Activeer 2FA atomair; schrijft de actieve record pas na codebevestiging."""
    gegevens = {
        "totp_secret": geheime_sleutel,
        "recovery_hashes": list(herstel_hashes),
        "enabled": True,
    }
    from nv_2fa_status import maak_verplicht

    with _bestandsslot():
        previous = OPSLAGBESTAND.read_bytes() if OPSLAGBESTAND.exists() else None
        if previous is not None:
            bestaand = json.loads(_fernet().decrypt(previous))
            if bestaand.get("enabled") is True:
                raise FileExistsError("2FA is al actief.")
        _write_encrypted(OPSLAGBESTAND, gegevens)
        try:
            maak_verplicht()
        except FileExistsError:
            pass
        except OSError:
            # Roll back the encrypted record if the fail-closed marker cannot be written.
            if previous is None:
                OPSLAGBESTAND.unlink(missing_ok=True)
            else:
                _atomic_write(OPSLAGBESTAND, previous)
            raise


def hmac_compare(a, b):
    import hmac
    return hmac.compare_digest(a, b)


def verbruik_herstelcode(code):
    """Verbruik een herstelcode atomair en cross-platform vergrendeld."""
    if postgres.enabled():
        return postgres.consume_recovery_code(code)

    from nv_2fa import gebruik_herstelcode

    with _bestandsslot():
        gegevens = laden()
        if gegevens.get("enabled") is not True:
            return False
        hashes = gegevens.get("recovery_hashes", [])
        if not gebruik_herstelcode(code, hashes):
            return False
        _write_encrypted(OPSLAGBESTAND, gegevens)
        return True
