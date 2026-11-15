"""Import a verified Windows 2FA backup into an empty PostgreSQL schema."""

import argparse
import hashlib
import hmac
import json
import math
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path

import nv_2fa_postgres as postgres


REQUIRED_FILES = (
    "nv_2fa.key", "nv_2fa_secrets.json", "nv_2fa_verplicht.flag",
    "nv_2fa_attempts.sqlite3", "nv_2fa_replay.sqlite3",
)


def _sqlite_rows(path, content, query):
    for suffix in ("-wal", "-journal"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError("SQLite-back-up bevat een niet-lege journal of WAL.")
    # sqlite3_deserialize needs rollback-mode header bytes, even for a checkpointed WAL snapshot.
    if content[18:20] == b"\x02\x02":
        content = content[:18] + b"\x01\x01" + content[20:]
    with closing(sqlite3.connect(":memory:")) as db:
        db.deserialize(content)
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite-integriteitscontrole mislukt.")
        return db.execute(query).fetchall()


def read_backup(bundle, independent_manifest_hash, encryption_key):
    bundle = bundle.resolve()
    independent_manifest_hash = independent_manifest_hash.resolve()
    if independent_manifest_hash.is_relative_to(bundle):
        raise ValueError("De manifesthash moet onafhankelijk van de bundel staan.")
    manifest = (bundle / "manifest.json").read_bytes()
    expected = independent_manifest_hash.read_text(encoding="ascii").split()[0]
    if not hmac.compare_digest(hashlib.sha256(manifest).hexdigest(), expected):
        raise ValueError("Manifesthash komt niet overeen.")
    spec = json.loads(manifest)
    if spec.get("format") != 1:
        raise ValueError("Onbekend manifestformaat.")
    entries = {entry["name"]: entry for entry in spec["entries"]}
    if len(entries) != len(spec["entries"]):
        raise ValueError("Dubbele manifestvermelding.")
    result = {}
    for name in REQUIRED_FILES:
        path = bundle / name
        if path.is_symlink():
            raise ValueError("Symbolische links zijn niet toegestaan.")
        blob = path.read_bytes()
        entry = entries[name]
        if entry.get("present") is False or len(blob) != entry["size"] or not hmac.compare_digest(
            hashlib.sha256(blob).hexdigest(), entry["sha256"]
        ):
            raise ValueError("Bestand komt niet overeen met het manifest.")
        result[name] = blob
    if not hmac.compare_digest(result["nv_2fa.key"], encryption_key):
        raise ValueError("Decryptiesleutel komt niet overeen met de back-up.")
    if result["nv_2fa_verplicht.flag"].strip() != b"2FA_REQUIRED":
        raise ValueError("Verplichte 2FA-markering ontbreekt.")
    ciphertext = result["nv_2fa_secrets.json"]
    postgres.decode(ciphertext, encryption_key)
    replay = _sqlite_rows(bundle / "nv_2fa_replay.sqlite3", result["nv_2fa_replay.sqlite3"],
                          "SELECT stap FROM gebruikte_stappen")
    attempts = _sqlite_rows(bundle / "nv_2fa_attempts.sqlite3", result["nv_2fa_attempts.sqlite3"],
                             "SELECT sleutel, tijdstip FROM pogingen")
    if any(type(step) is not int or not 0 <= step < 2**63 for (step,) in replay):
        raise ValueError("Ongeldige TOTP-tijdstap.")
    if any(not isinstance(identity, str) or type(ts) not in (float, int) or not math.isfinite(ts)
           for identity, ts in attempts):
        raise ValueError("Ongeldige inlogpoging.")
    return ciphertext, replay, attempts


def restore_backup(bundle, independent_manifest_hash, apply=False):
    encryption_key = postgres.key()
    ciphertext, replay, attempts = read_backup(bundle, independent_manifest_hash, encryption_key)
    if not apply:
        return
    with postgres.transaction() as db:
        db.execute("LOCK TABLE nuvemixa_auth.state, nuvemixa_auth.replay, nuvemixa_auth.attempts "
                   "IN ACCESS EXCLUSIVE MODE")
        exists = db.execute(
            "SELECT EXISTS (SELECT 1 FROM nuvemixa_auth.state UNION ALL "
            "SELECT 1 FROM nuvemixa_auth.replay UNION ALL SELECT 1 FROM nuvemixa_auth.attempts)"
        ).fetchone()[0]
        if exists:
            raise ValueError("Doel bevat beveiligingsgegevens.")
        db.execute("INSERT INTO nuvemixa_auth.state (ciphertext) VALUES (%s)", (ciphertext,))
        now = db.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp())::double precision").fetchone()[0]
        with db.cursor() as cursor:
            cursor.executemany("INSERT INTO nuvemixa_auth.replay (step) VALUES (%s)", replay)
            cursor.executemany(
                "INSERT INTO nuvemixa_auth.attempts (scope, tag, occurred_at, ticket) VALUES ('2fa', %s, %s, %s)",
                [(postgres.attempt_key("2fa", identity, encryption_key), min(ts, now), secrets.token_hex(16))
                 for identity, ts in attempts if ts > now - 300],
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest-hash", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        restore_backup(args.bundle, args.manifest_hash, apply=args.apply)
    except Exception:
        parser.exit(1, "2FA-import geweigerd. Controleer manifest, sleutel, schema en leeg doel.\n")
    print("2FA-import geslaagd." if args.apply else "2FA-back-up geldig. Er is niets geschreven.")


if __name__ == "__main__":
    main()
