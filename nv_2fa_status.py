
"""Permanente markering voor verplichte 2FA."""

import os

import nv_2fa_postgres as postgres
from nv_storage_paths import TWO_FA_DIR

MARKERING = TWO_FA_DIR / "nv_2fa_verplicht.flag"


def is_verplicht():
    return postgres.enabled() or MARKERING.exists()


def maak_verplicht():
    MARKERING.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(MARKERING, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as bestand:
            bestand.write("2FA_REQUIRED\n")
            bestand.flush()
            os.fsync(bestand.fileno())
    finally:
        os.close(descriptor)
    if os.name != "nt":
        directory_fd = os.open(MARKERING.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
