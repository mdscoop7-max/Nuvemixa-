"""Create a checked migration bundle and install it without overwriting files."""
import argparse
import csv
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import struct
import subprocess
import sys
import uuid

from cryptography.fernet import Fernet, InvalidToken

from nv_storage_paths import ADMIN_DB, CUSTOMER_DB, DASHBOARD_DB, TWO_FA_DIR


DATABASES = {
    "admin": ADMIN_DB,
    "dashboard": DASHBOARD_DB,
    "customers": CUSTOMER_DB,
    "2fa_rate_limit": TWO_FA_DIR / "nv_2fa_attempts.sqlite3",
    "2fa_replay": TWO_FA_DIR / "nv_2fa_replay.sqlite3",
}
DATABASE_FILENAMES = {
    "admin": "nuvemixa_admin.sqlite3",
    "dashboard": "nuvemixa_dashboard.sqlite3",
    "customers": "nuvemixa_customers.sqlite3",
    "2fa_rate_limit": "nv_2fa_attempts.sqlite3",
    "2fa_replay": "nv_2fa_replay.sqlite3",
}
REQUIRED_2FA_FILES = ("nv_2fa.key", "nv_2fa_secrets.json", "nv_2fa_verplicht.flag")
OPTIONAL_2FA_FILES = ("nv_2fa_pending.json", "nv_2fa_storage.lock")
MANIFEST_NAME = "manifest.json"
MANIFEST_HASH_NAME = "manifest.sha256"
APP_PROCESS_MARKERS = ("flask", "gunicorn", "uwsgi", "waitress", "uvicorn", "app.py", "app:app")
MIGRATION_COMMAND = re.compile(r"(?:^|[\s/\\])migrate_nuvemixa_data\.py(?:\s|$)", re.IGNORECASE)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_is_within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _windows_user_sid():
    result = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = list(csv.reader(io.StringIO(result.stdout)))
    if not rows or len(rows[0]) < 2 or not re.fullmatch(r"S-1-[0-9-]+", rows[0][-1]):
        raise RuntimeError("Windows-account-SID kon niet veilig worden vastgesteld.")
    return rows[0][-1]


def secure_permissions(path, directory=False):
    path = Path(path)
    if os.name == "nt":
        rights = "(OI)(CI)F" if directory else "F"
        result = subprocess.run(
            ["icacls.exe", str(path), "/inheritance:r", "/grant:r", f"*{_windows_user_sid()}:{rights}"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(f"Windows-toegangsrechten konden niet worden beperkt: {path}")
        return

    mode = 0o700 if directory else 0o600
    os.chmod(path, mode)
    if stat.S_IMODE(path.stat().st_mode) != mode:
        raise RuntimeError(f"Restrictieve bestandsrechten konden niet worden afgedwongen: {path}")


def copy_bytes_exclusive(destination, content):
    destination = Path(destination)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        secure_permissions(destination)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def create_private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700)
    secure_permissions(path, directory=True)


def permissions_are_private(path, directory=False):
    if os.name == "nt":
        environment = os.environ.copy()
        environment["NUVEMIXA_ACL_PATH"] = str(Path(path))
        command = (
            "$acl = Get-Acl -LiteralPath $env:NUVEMIXA_ACL_PATH; "
            "$items = @($acl.Access | ForEach-Object { "
            "$sid = $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value; "
            "[pscustomobject]@{Sid=$sid; Type=$_.AccessControlType.ToString(); "
            "Rights=$_.FileSystemRights.ToString(); Inherited=$_.IsInherited} }); "
            "ConvertTo-Json -Compress -InputObject $items"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            entries = json.loads(result.stdout)
            entries = entries if isinstance(entries, list) else [entries]
            sid = _windows_user_sid()
            trusted_sids = {sid, "S-1-3-4", "S-1-5-18", "S-1-5-32-544"}
            return bool(entries) and all(
                entry.get("Sid") in trusted_sids
                and entry.get("Type") == "Allow"
                and "FullControl" in entry.get("Rights", "")
                for entry in entries
            )
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            return False
    expected_mode = 0o700 if directory else 0o600
    return stat.S_IMODE(Path(path).stat().st_mode) == expected_mode


def enumerate_processes():
    if os.name == "nt":
        command = (
            "$ErrorActionPreference='Stop'; "
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        processes = payload if isinstance(payload, list) else [payload]
        normalized = []
        pids = set()
        for process in processes:
            pid = int(process["ProcessId"])
            pids.add(pid)
            normalized.append({
                "pid": pid,
                "name": process.get("Name") or "",
                "command": process.get("CommandLine") or "",
                "cwd": "",
                "open_files": (),
            })
        return pids, normalized

    proc = Path("/proc")
    if not proc.is_dir():
        raise RuntimeError("Procesinventarisatie wordt op dit besturingssysteem niet ondersteund.")
    pids = set()
    processes = []
    current_uid = os.geteuid()
    with os.scandir(proc) as proc_entries:
        for item in proc_entries:
            if not item.name.isdigit():
                continue
            pid = int(item.name)
            pids.add(pid)
            process_dir = proc / item.name
            try:
                status = (process_dir / "status").read_text(encoding="ascii", errors="replace")
                uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
                if int(uid_line.split()[2]) != current_uid:
                    continue
                command = (process_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                    "utf-8", errors="replace"
                ).strip()
                cwd = os.readlink(process_dir / "cwd")
                open_files = []
                with os.scandir(process_dir / "fd") as descriptors:
                    for descriptor in descriptors:
                        try:
                            open_file = os.readlink(descriptor.path)
                            if open_file.endswith(" (deleted)"):
                                open_file = open_file[:-10]
                            open_files.append(open_file)
                        except FileNotFoundError:
                            continue
                name = (process_dir / "comm").read_text(encoding="utf-8", errors="replace").strip()
            except FileNotFoundError:
                pids.discard(pid)
                continue
            except (PermissionError, OSError) as exc:
                raise RuntimeError(f"Procesinventarisatie is onvolledig voor PID {pid}.") from exc
            processes.append({
                "pid": pid,
                "name": name,
                "command": command,
                "cwd": cwd,
                "open_files": tuple(open_files),
            })
    return pids, processes


def process_is_application(process, roots, protected_paths):
    command = str(process.get("command", ""))
    name = str(process.get("name", "")).casefold()
    runtime = name.startswith(("python", "pypy", "gunicorn", "uwsgi", "flask", "waitress", "uvicorn"))
    if int(process.get("pid", -1)) == os.getpid():
        return False
    if MIGRATION_COMMAND.search(command) and runtime:
        return True
    lower_command = command.casefold()
    if any(marker in lower_command or marker in name for marker in APP_PROCESS_MARKERS):
        return True

    if runtime:
        for root in roots:
            try:
                if path_is_within(process.get("cwd", ""), root):
                    return True
            except (OSError, ValueError):
                raise RuntimeError("Werkmap van een proces kon niet volledig worden gecontroleerd.")

    protected = {str(Path(path).resolve()) for path in protected_paths}
    for open_file in process.get("open_files", ()):
        if str(Path(open_file).resolve()) in protected:
            return True
    return False


def validate_process_inventory(pids_to_check, role, running_pids, processes, roots, protected_paths):
    pids_to_check = {int(pid) for pid in pids_to_check}
    if any(pid <= 0 for pid in pids_to_check):
        raise ValueError(f"Ongeldige PID in {role}-controle.")
    if not pids_to_check:
        raise ValueError(f"Geef minstens één vooraf vastgelegde {role}-PID op.")
    still_running = sorted(pids_to_check & running_pids)
    if still_running:
        raise RuntimeError(f"{role.capitalize()}processen draaien nog: {still_running}")
    active = [
        f"{process['pid']}:{process['name']}"
        for process in processes
        if process_is_application(process, roots, protected_paths)
    ]
    if active:
        raise RuntimeError(
            f"Actieve app-processen gevonden tijdens {role}-controle: {', '.join(active)}"
        )


def require_processes_stopped(pids_to_check, role, roots, protected_paths):
    running_pids, processes = enumerate_processes()
    validate_process_inventory(pids_to_check, role, running_pids, processes, roots, protected_paths)
    print(f"STOP_CHECK={role}: bekende PID's gestopt; procesinventarisatie compleet.")


def wal_report(database_path):
    path = Path(str(database_path) + "-wal")
    if not path.is_file():
        return {
            "present": False,
            "bytes": 0,
            "frames": 0,
            "commit_frames": 0,
            "trailing_bytes": 0,
            "state": "missing",
        }

    size = path.stat().st_size
    result = {
        "present": True,
        "bytes": size,
        "frames": 0,
        "salt_matched_frames": 0,
        "commit_frames": 0,
        "trailing_bytes": 0,
        "state": "empty" if size == 0 else "unparsed",
    }
    if size == 0:
        return result

    with path.open("rb") as stream:
        header = stream.read(32)
        if len(header) != 32:
            result["state"] = "short-header"
            return result
        magic, version, page_size = struct.unpack(">III", header[:12])
        page_size = 65536 if page_size == 1 else page_size
        if magic not in (0x377F0682, 0x377F0683) or version != 3007000 or page_size < 512:
            result["state"] = "invalid-header"
            return result

        frame_size = 24 + page_size
        frame_bytes = size - 32
        frames, trailing_bytes = divmod(frame_bytes, frame_size)
        salt_matched = 0
        commit_frames = 0
        for index in range(frames):
            stream.seek(32 + index * frame_size)
            frame = stream.read(24)
            if len(frame) != 24:
                break
            page_number, committed_page_count = struct.unpack(">II", frame[:8])
            if page_number and frame[8:16] == header[16:24]:
                salt_matched += 1
                if committed_page_count:
                    commit_frames += 1

    result.update({
        "frames": frames,
        "salt_matched_frames": salt_matched,
        "commit_frames": commit_frames,
        "trailing_bytes": trailing_bytes,
        "state": f"{frames}-frames" if not trailing_bytes else f"{frames}-frames-plus-{trailing_bytes}-trailing-bytes",
    })
    return result


def sidecar_fingerprints(database_path):
    results = {}
    for suffix in ("-wal", "-shm"):
        path = Path(str(database_path) + suffix)
        if not path.is_file():
            results[suffix] = {"present": False, "size": 0, "sha256": None}
            continue
        before = path.stat()
        digest = sha256_file(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"SQLite-sidecar veranderde tijdens inspectie: {path.name}")
        results[suffix] = {"present": True, "size": after.st_size, "sha256": digest}
    return results


def open_read_only(path, immutable=False):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    if immutable:
        uri += "&immutable=1"
    return sqlite3.connect(uri, uri=True, timeout=30)


def table_summary(connection):
    tables = [
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    summary = {}
    for name in tables:
        escaped_name = name.replace('"', '""')
        summary[name] = connection.execute(f'SELECT COUNT(*) FROM "{escaped_name}"').fetchone()[0]
    return summary


def check_integrity(connection):
    results = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    if results != ["ok"]:
        raise RuntimeError(f"SQLite-integriteitscontrole mislukt: {'; '.join(results)}")
    return "ok"


def read_stable_file(source):
    source = Path(source)
    with source.open("rb") as stream:
        before = os.fstat(stream.fileno())
        content = stream.read()
        after = os.fstat(stream.fileno())
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if before_identity != after_identity:
        raise RuntimeError(f"Bestand veranderde tijdens de snapshot: {source.name}")
    return content


def copy_2fa_files(bundle):
    entries = []
    contents = {}
    for name in REQUIRED_2FA_FILES + OPTIONAL_2FA_FILES:
        source = TWO_FA_DIR / name
        if source.is_file():
            contents[name] = read_stable_file(source)
        elif name in REQUIRED_2FA_FILES:
            raise FileNotFoundError(f"Verplicht 2FA-bestand ontbreekt: {source}")

    key = contents["nv_2fa.key"]
    secrets_blob = contents["nv_2fa_secrets.json"]
    fernet = Fernet(key)
    try:
        secrets_data = json.loads(fernet.decrypt(secrets_blob))
        if not isinstance(secrets_data, dict):
            raise ValueError("2FA-opslag moet een JSON-object bevatten.")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise RuntimeError("De bestaande versleutelde 2FA-opslag is ongeldig.") from exc

    for name in REQUIRED_2FA_FILES + OPTIONAL_2FA_FILES:
        if name not in contents:
            entries.append({"name": name, "kind": "optional", "present": False})
            continue
        content = contents[name]
        if name == "nv_2fa_pending.json":
            try:
                pending_data = json.loads(fernet.decrypt(content))
                if not isinstance(pending_data, dict):
                    raise ValueError("Pending-opslag moet een JSON-object bevatten.")
            except (InvalidToken, ValueError, TypeError) as exc:
                raise RuntimeError("De bestaande pending-2FA-opslag is ongeldig.") from exc
        destination = bundle / name
        copy_bytes_exclusive(destination, content)
        entries.append({
            "name": name,
            "kind": "2fa_file",
            "present": True,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    return entries


def backup_database(name, source_path, destination):
    source_path = Path(source_path)
    destination = Path(destination)
    if not source_path.is_file():
        raise FileNotFoundError(f"Database ontbreekt: {source_path}")
    wal_before = wal_report(source_path)
    if wal_before["state"] in ("short-header", "invalid-header", "unparsed") or (
        wal_before.get("trailing_bytes", 0)
        or wal_before.get("salt_matched_frames", wal_before["frames"]) != wal_before["frames"]
    ):
        raise RuntimeError(f"WAL kan niet volledig worden gecontroleerd voor {name}: {wal_before}")
    sidecars_before = sidecar_fingerprints(source_path)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    secure_permissions(destination)
    with closing(open_read_only(source_path)) as source:
        check_integrity(source)
        source_tables = table_summary(source)
        with closing(sqlite3.connect(destination, timeout=30)) as target:
            source.backup(target, pages=128, sleep=0.1)
            check_integrity(target)
            target_tables = table_summary(target)
        wal_after = wal_report(source_path)
        sidecars_after = sidecar_fingerprints(source_path)
    if source_tables != target_tables:
        raise RuntimeError(f"Back-upcontrole mislukt voor {name}: tabellen of aantallen wijken af.")
    if sidecars_before["-wal"] != sidecars_after["-wal"]:
        raise RuntimeError(f"WAL veranderde tijdens de back-up van {name}; bron blijft behouden.")

    return {
        "name": Path(destination).name,
        "kind": "sqlite_backup_api",
        "present": True,
        "size": Path(destination).stat().st_size,
        "sha256": sha256_file(destination),
        "tables_and_row_counts": target_tables,
        "source_wal_before": wal_before,
        "source_wal_after": wal_after,
        "source_sidecars_sha256_before": sidecars_before,
        "source_sidecars_sha256_during_snapshot": sidecars_after,
    }


def validate_independent_hash_path(path, bundle):
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ValueError("De onafhankelijke manifesthash mag geen symbolische link zijn.")
    path = path.resolve()
    bundle = Path(bundle).resolve()
    if path == bundle or path_is_within(path, bundle):
        raise ValueError("De onafhankelijke manifesthash moet buiten de migratiebundel staan.")
    if path.exists():
        raise FileExistsError(f"Manifesthash-bestand bestaat al; niets overschreven: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Map voor onafhankelijke manifesthash ontbreekt: {path.parent}")
    if not permissions_are_private(path.parent, directory=True):
        raise PermissionError(f"Map voor onafhankelijke manifesthash is niet privé: {path.parent}")
    for source in [*DATABASES.values(), TWO_FA_DIR]:
        source_path = Path(source).resolve()
        source_root = source_path if source_path.is_dir() else source_path.parent
        if path == source_root or path_is_within(path, source_root):
            raise ValueError("Bewaar de onafhankelijke manifesthash buiten brongegevensmappen.")
    return path


def write_manifest(bundle, manifest, independent_hash_path):
    manifest_path = bundle / MANIFEST_NAME
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    copy_bytes_exclusive(manifest_path, payload)
    digest = hashlib.sha256(payload).hexdigest()
    checksum = f"{digest}  {MANIFEST_NAME}\n".encode("ascii")
    copy_bytes_exclusive(bundle / MANIFEST_HASH_NAME, checksum)
    copy_bytes_exclusive(independent_hash_path, checksum)
    return digest


def source_plan():
    rows = []
    for label, path in DATABASES.items():
        rows.append((label, path, path.is_file(), wal_report(path)))
    return rows


def inspect(args):
    print("Alleen-lezen inspectie; er worden geen databaseverbindingen of bestandskopieën gemaakt.")
    print(f"2FA_DIR: {TWO_FA_DIR}")
    for label, path, exists, wal in source_plan():
        size = path.stat().st_size if exists else "n/a"
        print(f"DB {label}: {path} | present={exists} | bytes={size} | WAL={wal}")
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            if sidecar.is_file():
                print(f"  SIDECAR {sidecar.name}: present bytes={sidecar.stat().st_size}")
            else:
                print(f"  SIDECAR {sidecar.name}: missing")
    for name in REQUIRED_2FA_FILES + OPTIONAL_2FA_FILES:
        path = TWO_FA_DIR / name
        print(f"2FA {path}: {'present bytes=' + str(path.stat().st_size) if path.is_file() else 'missing'}")
    if args.target:
        print(f"TARGET (not modified): {args.target}")


def export_bundle(args):
    bundle = args.bundle.expanduser().resolve()
    if bundle.exists():
        raise FileExistsError(f"Back-upmap bestaat al; niets overschreven: {bundle}")
    if not bundle.parent.is_dir():
        raise FileNotFoundError(f"De bovenliggende map bestaat niet: {bundle.parent}")
    for path in [*DATABASES.values(), TWO_FA_DIR]:
        source_dir = Path(path).resolve() if Path(path).is_dir() else Path(path).resolve().parent
        if bundle == source_dir or path_is_within(bundle, source_dir):
            raise ValueError("Back-upmap mag niet in een brongegevensmap staan.")
    missing = [str(path) for path in DATABASES.values() if not Path(path).is_file()]
    missing.extend(
        str(TWO_FA_DIR / name) for name in REQUIRED_2FA_FILES
        if not (TWO_FA_DIR / name).is_file()
    )
    if missing:
        raise FileNotFoundError("Bronbestanden ontbreken: " + ", ".join(missing))

    if not args.apply:
        print("DRY-RUN: er is niets geschreven.")
        for label, path, exists, wal in source_plan():
            print(f"Zou SQLite Backup API gebruiken: {label} | {path} | exists={exists} | WAL={wal}")
        print(f"Zou de 2FA-bestanden veilig kopiëren naar een nieuwe map: {bundle}")
        if args.manifest_hash_out:
            print(f"Onafhankelijke manifesthash komt buiten de bundel: {args.manifest_hash_out}")
        return

    if not args.manifest_hash_out:
        raise ValueError("Geef voor export --manifest-hash-out op buiten de bundel.")
    independent_hash_path = validate_independent_hash_path(args.manifest_hash_out, bundle)
    source_paths = [Path(path).resolve() for path in DATABASES.values()]
    source_paths.extend(TWO_FA_DIR / name for name in REQUIRED_2FA_FILES + OPTIONAL_2FA_FILES)
    protected_paths = []
    for path in source_paths:
        protected_paths.extend((path, Path(str(path) + "-wal"), Path(str(path) + "-shm")))
    roots = {Path(__file__).resolve().parent, TWO_FA_DIR.resolve()}
    for path in DATABASES.values():
        roots.add(Path(path).resolve().parent)
    require_processes_stopped(args.source_pid, "bron", roots, protected_paths)

    create_private_directory(bundle)
    entries = []
    for label, source in DATABASES.items():
        require_processes_stopped(args.source_pid, "bron", roots, protected_paths)
        target = bundle / DATABASE_FILENAMES[label]
        entry = backup_database(label, source, target)
        entry["logical_name"] = label
        entry["source"] = str(source)
        entries.append(entry)
        print(f"SQLite Backup API: {label} -> {target} | sha256={entry['sha256']}")
    require_processes_stopped(args.source_pid, "bron", roots, protected_paths)
    entries.extend(copy_2fa_files(bundle))
    require_processes_stopped(args.source_pid, "bron", roots, protected_paths)
    manifest = {
        "format": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_project_directory": str(Path(__file__).resolve().parent),
        "entries": entries,
        "notes": [
            "SQLite databases are snapshots made with sqlite3.Connection.backup().",
            "WAL and SHM sidecars are fingerprinted before and during snapshots; the WAL must remain byte-identical.",
            "The script does not copy, checkpoint, or explicitly delete WAL/SHM sidecars; SQLite may update its derived SHM index.",
            "2FA key and encrypted 2FA files are copied byte-for-byte.",
            "Every created file and directory has restrictive permissions.",
        ],
    }
    manifest_hash = write_manifest(bundle, manifest, independent_hash_path)
    read_verified_manifest(bundle, independent_hash_path)
    print(f"BACKUP_BUNDLE={bundle}")
    print(f"MANIFEST_SHA256={manifest_hash}")
    print(f"INDEPENDENT_MANIFEST_HASH={independent_hash_path}")


def _read_manifest_hash(path):
    parts = Path(path).read_text(encoding="ascii").split()
    if not parts or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
        raise ValueError("Onafhankelijke manifesthash ontbreekt of is ongeldig.")
    return parts[0]


def verify_manifest_digest(payload, hash_path):
    actual = hashlib.sha256(payload).hexdigest()
    if _read_manifest_hash(hash_path) != actual:
        raise RuntimeError("Onafhankelijke manifesthash klopt niet.")
    return actual


def _validate_bundle_inventory(bundle, manifest):
    allowed = {
        MANIFEST_NAME,
        MANIFEST_HASH_NAME,
        *(entry["name"] for entry in manifest["entries"] if entry.get("present") is not False),
    }
    with os.scandir(bundle) as items:
        actual_names = set()
        for item in items:
            actual_names.add(item.name)
            if item.is_symlink() or not item.is_file(follow_symlinks=False) or item.name not in allowed:
                raise ValueError(f"Bundel bevat een niet-gemanifesteerd bestand of map: {item.name}")
    if actual_names != allowed:
        raise ValueError("Bestandsinventaris van de back-upbundel is onvolledig.")


def read_verified_manifest(bundle, independent_hash_path):
    bundle = Path(bundle).resolve()
    independent_hash_path = Path(independent_hash_path)
    if independent_hash_path.is_symlink():
        raise ValueError("Onafhankelijke manifesthash mag geen symbolische link zijn.")
    independent_hash_path = independent_hash_path.resolve()
    if independent_hash_path == bundle or path_is_within(independent_hash_path, bundle):
        raise ValueError("Manifesthash staat niet onafhankelijk van de bundel.")
    if not permissions_are_private(bundle, directory=True):
        raise PermissionError(f"Back-upmap heeft geen restrictieve toegangsrechten: {bundle}")
    manifest_path = bundle / MANIFEST_NAME
    internal_hash = bundle / MANIFEST_HASH_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file() or internal_hash.is_symlink():
        raise ValueError("Manifestbestanden ontbreken of bevatten symbolische links.")
    if not permissions_are_private(independent_hash_path.parent, directory=True):
        raise PermissionError("Map met de onafhankelijke manifesthash is niet privé.")
    payload = manifest_path.read_bytes()
    actual = verify_manifest_digest(payload, independent_hash_path)
    if internal_hash.exists() and _read_manifest_hash(internal_hash) != actual:
        raise RuntimeError("Interne manifesthash wijkt af van de onafhankelijke hash.")
    if not permissions_are_private(manifest_path) or (
        internal_hash.exists() and not permissions_are_private(internal_hash)
    ) or not permissions_are_private(independent_hash_path):
        raise PermissionError("Manifest- of hashbestand heeft geen restrictieve toegangsrechten.")

    manifest = json.loads(payload)
    if (not isinstance(manifest, dict) or manifest.get("format") != 1
            or not isinstance(manifest.get("entries"), list)):
        raise ValueError("Onbekend migratiebundelformaat.")
    database_names = set(DATABASE_FILENAMES.values())
    database_labels = {filename: label for label, filename in DATABASE_FILENAMES.items()}
    allowed = database_names | set(REQUIRED_2FA_FILES + OPTIONAL_2FA_FILES)
    seen = set()
    for entry in manifest["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("Ongeldig item in manifest.")
        name = entry.get("name")
        if (not isinstance(name, str) or Path(name).name != name or name not in allowed or name in seen):
            raise ValueError("Ongeldige bestandsnaam in manifest.")
        seen.add(name)
        present = entry.get("present", True)
        if not isinstance(present, bool):
            raise ValueError(f"Ongeldige aanwezigheidsmarkering: {name}")
        if not present:
            if name not in OPTIONAL_2FA_FILES:
                raise ValueError(f"Verplicht bestand ontbreekt volgens manifest: {name}")
            continue
        if name in database_names:
            logical_name = entry.get("logical_name") or database_labels[name]
            if (entry.get("kind") != "sqlite_backup_api"
                    or logical_name not in DATABASE_FILENAMES
                    or DATABASE_FILENAMES[logical_name] != name):
                raise ValueError(f"Ongeldige databaseverwijzing in manifest: {name}")
        elif entry.get("kind") != "2fa_file":
            raise ValueError(f"Ongeldig 2FA-bestandstype in manifest: {name}")
        if (not isinstance(entry.get("size"), int) or isinstance(entry.get("size"), bool)
                or entry["size"] < 0 or not isinstance(entry.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
            raise ValueError(f"Ongeldige grootte of checksum in manifest: {name}")
        path = bundle / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["size"]:
            raise RuntimeError(f"Back-upbestand ontbreekt, is een link of heeft een andere grootte: {name}")
        if sha256_file(path) != entry["sha256"]:
            raise RuntimeError(f"Back-upchecksum klopt niet: {name}")
        if not permissions_are_private(path):
            raise PermissionError(f"Back-upbestand heeft geen restrictieve toegangsrechten: {name}")

    expected_names = allowed
    if seen != expected_names:
        raise ValueError("Manifest bevat geen volledige inventaris van databases en 2FA-bestanden.")
    _validate_bundle_inventory(bundle, manifest)

    entry_by_name = {entry["name"]: entry for entry in manifest["entries"]}
    for name in database_names:
        entry = entry_by_name[name]
        path = bundle / name
        with closing(open_read_only(path, immutable=True)) as connection:
            check_integrity(connection)
            if table_summary(connection) != entry.get("tables_and_row_counts"):
                raise RuntimeError(f"SQLite-tabel- of rijaantallen wijken af: {name}")

    key = (bundle / "nv_2fa.key").read_bytes()
    fernet = Fernet(key)
    try:
        secrets = json.loads(fernet.decrypt((bundle / "nv_2fa_secrets.json").read_bytes()))
        if not isinstance(secrets, dict):
            raise ValueError("2FA-opslag moet een JSON-object bevatten.")
        pending_entry = entry_by_name["nv_2fa_pending.json"]
        if pending_entry.get("present") is True:
            pending = json.loads(fernet.decrypt((bundle / "nv_2fa_pending.json").read_bytes()))
            if not isinstance(pending, dict):
                raise ValueError("Pending-opslag moet een JSON-object bevatten.")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise RuntimeError("2FA-sleutel en versleutelde opslag konden niet worden gevalideerd.") from exc
    return manifest


def destination_map(manifest, target):
    target = Path(target).resolve()
    destinations = {}
    seen = set()
    for entry in manifest["entries"]:
        if entry.get("present") is False:
            continue
        name = entry["name"]
        if name in DATABASE_FILENAMES.values():
            label = entry.get("logical_name") or next(
                key for key, filename in DATABASE_FILENAMES.items() if filename == name
            )
            destination = Path(DATABASES[label]).resolve()
        else:
            destination = (TWO_FA_DIR / name).resolve()
        if not path_is_within(destination, target):
            raise ValueError(f"Doel valt buiten de Persistent Disk-map: {destination}")
        normalized = os.path.normcase(str(destination))
        if normalized in seen:
            raise ValueError(f"Meerdere bundelbestanden wijzen naar hetzelfde doel: {destination}")
        seen.add(normalized)
        destinations[name] = destination
    return destinations


def inventory_target(target, expected_files):
    target = Path(target).resolve()
    expected_by_path = {
        os.path.normcase(str(Path(path).resolve())): (name, entry, Path(path).resolve())
        for name, (entry, path) in expected_files.items()
    }
    expected_directories = {os.path.normcase(str(target))}
    for _, _, path in expected_by_path.values():
        parent = path.parent
        while parent != target:
            if not path_is_within(parent, target):
                raise ValueError(f"Doelmap valt buiten de Persistent Disk-map: {parent}")
            expected_directories.add(os.path.normcase(str(parent)))
            parent = parent.parent

    present = set()

    def visit(directory):
        with os.scandir(directory) as items:
            for item in items:
                path = Path(item.path).resolve()
                normalized = os.path.normcase(str(path))
                if item.is_symlink():
                    raise ValueError(f"Doel bevat een symbolische link; inventaris niet veilig: {item.path}")
                if item.is_dir(follow_symlinks=False):
                    if normalized not in expected_directories:
                        raise ValueError(f"Doel bevat een niet-gemanifesteerde map: {item.path}")
                    if normalized != os.path.normcase(str(target)) and not permissions_are_private(path, directory=True):
                        raise PermissionError(f"Doelmap heeft geen restrictieve rechten: {path}")
                    visit(path)
                    continue
                if not item.is_file(follow_symlinks=False) or normalized not in expected_by_path:
                    raise ValueError(f"Doel bevat een niet-gemanifesteerd bestand: {item.path}")
                name, entry, expected_path = expected_by_path[normalized]
                if path.stat().st_size != entry["size"] or sha256_file(path) != entry["sha256"]:
                    raise FileExistsError(f"Doelbestand wijkt af; niets wordt overschreven: {expected_path}")
                if not permissions_are_private(path):
                    raise PermissionError(f"Doelbestand heeft geen restrictieve rechten: {expected_path}")
                present.add(name)

    visit(target)
    return present, expected_directories


def install_exclusive(source, destination, expected_hash):
    source = Path(source)
    destination = Path(destination)
    temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        secure_permissions(temporary)
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb", closefd=False) as output_stream:
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        if sha256_file(temporary) != expected_hash:
            raise RuntimeError(f"Tijdelijke kopiechecksum klopt niet: {source.name}")
        os.link(temporary, destination)
    finally:
        os.close(descriptor)
        if temporary.exists():
            temporary.unlink()
    secure_permissions(destination)
    if sha256_file(destination) != expected_hash:
        raise RuntimeError(f"Doelchecksum klopt niet: {destination.name}")
    if os.name != "nt":
        directory_descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)


def verify_installed_bundle(bundle, manifest, destinations):
    for entry in manifest["entries"]:
        if entry.get("present") is False:
            continue
        destination = destinations[entry["name"]]
        if (not destination.is_file() or destination.stat().st_size != entry["size"]
                or sha256_file(destination) != entry["sha256"]):
            raise RuntimeError(f"Post-install checksumcontrole mislukt: {destination}")
        if not permissions_are_private(destination):
            raise PermissionError(f"Post-install rechtencontrole mislukt: {destination}")
        if entry["name"] in DATABASE_FILENAMES.values():
            with closing(open_read_only(destination, immutable=True)) as connection:
                check_integrity(connection)
                if table_summary(connection) != entry.get("tables_and_row_counts"):
                    raise RuntimeError(f"Post-install SQLite-controle mislukt: {destination}")


def install_bundle(args):
    bundle = args.bundle.expanduser().resolve()
    target = args.target.expanduser().resolve()
    if not bundle.is_dir():
        raise FileNotFoundError(f"Migratiebundel ontbreekt: {bundle}")
    if not target.is_dir():
        raise FileNotFoundError(f"Doelmap ontbreekt; mount de Persistent Disk eerst: {target}")
    if not args.manifest_hash:
        raise ValueError("Geef de onafhankelijk bewaarde manifesthash op met --manifest-hash.")
    manifest = read_verified_manifest(bundle, args.manifest_hash)
    destinations = destination_map(manifest, target)
    expected_files = {
        entry["name"]: (entry, destinations[entry["name"]])
        for entry in manifest["entries"] if entry.get("present") is not False
    }
    existing, expected_directories = inventory_target(target, expected_files)
    pending = [
        (entry, destinations[entry["name"]])
        for entry in manifest["entries"]
        if entry.get("present") is not False and entry["name"] not in existing
    ]

    if not args.apply:
        print("DRY-RUN: doelinventaris volledig; er zijn geen bestanden gewijzigd.")
        print(f"Gecontroleerde bundel: {bundle}")
        print(f"Doelmap: {target}")
        print(f"Exact overeenkomende doelbestanden: {len(existing)}")
        print("Bestanden die zouden worden geïnstalleerd: " + ", ".join(str(path) for _, path in pending))
        return

    roots = {Path(__file__).resolve().parent, target}
    protected_paths = [
        sidecar
        for path in destinations.values()
        for sidecar in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm"))
    ]
    require_processes_stopped(args.target_pid, "doel", roots, protected_paths)

    try:
        for directory in sorted(expected_directories, key=lambda value: (len(Path(value).parts), value)):
            path = Path(directory)
            if path == target or path.exists():
                continue
            create_private_directory(path)
        for entry, destination in pending:
            install_exclusive(bundle / entry["name"], destination, entry["sha256"])
            print(f"INSTALLED {entry['name']} sha256={entry['sha256']}")
        verify_installed_bundle(bundle, manifest, destinations)
        final_inventory, _ = inventory_target(target, expected_files)
        if final_inventory != set(expected_files):
            raise RuntimeError("Doelinventaris na installatie is onvolledig.")
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        raise RuntimeError(
            "Installatiecontrole is mislukt. Houd de app gestopt, verwijder of overschrijf niets, "
            "bewaar bron en bundel, en herstel naar een nieuwe lege disk/map met dezelfde "
            f"geverifieerde bundel. Details: {exc}"
        ) from exc
    print("Installatie en volledige post-installcontrole geslaagd; bron en bundel behouden.")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect", help="Toon bronpaden en WAL/SHM zonder bestanden te openen")
    inspect_parser.add_argument("--target", type=Path)
    inspect_parser.set_defaults(run=inspect)

    export_parser = commands.add_parser("export", help="Maak een SQLite-Backup-API bundel")
    export_parser.add_argument("--bundle", type=Path, required=True)
    export_parser.add_argument("--manifest-hash-out", type=Path)
    export_parser.add_argument("--apply", action="store_true", help="Schrijf pas met deze expliciete vlag")
    export_parser.add_argument("--source-pid", type=int, action="append", default=[])
    export_parser.set_defaults(run=export_bundle)

    install_parser = commands.add_parser("install", help="Installeer een gecontroleerde bundel zonder overschrijven")
    install_parser.add_argument("--bundle", type=Path, required=True)
    install_parser.add_argument("--target", type=Path, required=True)
    install_parser.add_argument("--manifest-hash", type=Path)
    install_parser.add_argument("--apply", action="store_true", help="Schrijf pas met deze expliciete vlag")
    install_parser.add_argument("--target-pid", type=int, action="append", default=[])
    install_parser.set_defaults(run=install_bundle)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except (
        OSError,
        sqlite3.Error,
        subprocess.SubprocessError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
