import hashlib
import os
import struct
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from cryptography.fernet import Fernet

from migrate_nuvemixa_data import (
    DATABASE_FILENAMES,
    OPTIONAL_2FA_FILES,
    REQUIRED_2FA_FILES,
    backup_database,
    check_integrity,
    copy_bytes_exclusive,
    create_private_directory,
    install_exclusive,
    inventory_target,
    process_is_application,
    read_verified_manifest,
    secure_permissions,
    table_summary,
    validate_process_inventory,
    wal_report,
    write_manifest,
)


class WalReportTests(unittest.TestCase):
    def test_missing_and_empty_wal_are_reported_without_database_access(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sample.sqlite3"
            self.assertEqual(wal_report(database)["state"], "missing")

            Path(str(database) + "-wal").write_bytes(b"")
            report = wal_report(database)
            self.assertEqual(report["state"], "empty")
            self.assertEqual(report["frames"], 0)

    def test_committed_wal_frame_is_counted_structurally(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sample.sqlite3"
            wal = Path(str(database) + "-wal")
            page_size = 512
            salts = b"12345678"
            header = struct.pack(">III", 0x377F0682, 3007000, page_size)
            header += struct.pack(">I", 0) + salts + bytes(8)
            frame = struct.pack(">II", 1, 1) + salts + bytes(8) + bytes(page_size)
            wal.write_bytes(header + frame)

            report = wal_report(database)
            self.assertEqual(report["frames"], 1)
            self.assertEqual(report["salt_matched_frames"], 1)
            self.assertEqual(report["commit_frames"], 1)
            self.assertEqual(report["trailing_bytes"], 0)


class SqliteBackupTests(unittest.TestCase):
    def test_backup_api_creates_a_consistent_independent_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.sqlite3"
            destination = Path(temp) / "snapshot.sqlite3"
            db = sqlite3.connect(source)
            try:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE sample(value TEXT)")
                db.execute("INSERT INTO sample VALUES ('fixture')")
                db.commit()

                wal_before = wal_report(source)
                self.assertGreater(wal_before["frames"], 0)
                entry = backup_database("fixture", source, destination)
                self.assertEqual(entry["kind"], "sqlite_backup_api")
                self.assertEqual(entry["tables_and_row_counts"], {"sample": 1})
                self.assertEqual(entry["source_wal_before"]["bytes"], wal_before["bytes"])
                self.assertEqual(entry["source_wal_after"]["bytes"], wal_before["bytes"])
                with closing(sqlite3.connect(destination)) as snapshot:
                    self.assertEqual(
                        snapshot.execute("SELECT value FROM sample").fetchone()[0], "fixture"
                    )
            finally:
                db.close()

    def test_backup_api_refuses_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.sqlite3"
            destination = Path(temp) / "snapshot.sqlite3"
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE sample(value TEXT)")
                db.commit()
            destination.write_bytes(b"keep")

            with self.assertRaises(FileExistsError):
                backup_database("fixture", source, destination)
            self.assertEqual(destination.read_bytes(), b"keep")


class InstallTests(unittest.TestCase):
    def test_install_exclusive_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "snapshot.bin"
            destination = Path(temp) / "existing.bin"
            source.write_bytes(b"snapshot")
            destination.write_bytes(b"existing data")
            expected_hash = hashlib.sha256(b"snapshot").hexdigest()

            with self.assertRaises(FileExistsError):
                install_exclusive(source, destination, expected_hash)

            self.assertEqual(destination.read_bytes(), b"existing data")

    def test_install_exclusive_creates_missing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "snapshot.bin"
            destination = Path(temp) / "new.bin"
            source.write_bytes(b"snapshot")

            install_exclusive(
                source,
                destination,
                hashlib.sha256(b"snapshot").hexdigest(),
            )

            self.assertEqual(destination.read_bytes(), b"snapshot")


class MigrationSecurityTests(unittest.TestCase):
    def test_created_backup_file_has_restrictive_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "secret.bin"
            copy_bytes_exclusive(path, b"private fixture")
            secure_permissions(path)
            self.assertTrue(path.is_file())
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_process_check_requires_known_pids_and_refuses_live_pid(self):
        with self.assertRaises(ValueError):
            validate_process_inventory([], "bron", set(), [], (), ())
        with self.assertRaises(RuntimeError):
            validate_process_inventory([42], "bron", {42}, [], (), ())

    def test_process_check_refuses_detected_web_application(self):
        process = {"pid": 88, "name": "python", "command": "python -m flask run", "cwd": ""}
        with self.assertRaises(RuntimeError):
            validate_process_inventory([42], "bron", set(), [process], (), ())

    def test_process_check_ignores_migration_command(self):
        process = {
            "pid": os.getpid(),
            "name": "python",
            "command": "python migrate_nuvemixa_data.py install --apply",
            "cwd": "",
        }
        self.assertFalse(process_is_application(process, (), ()))

    def test_target_inventory_allows_only_exact_manifested_files(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            path = target / "data.bin"
            content = b"expected"
            copy_bytes_exclusive(path, content)
            entry = {
                "name": "data.bin",
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            expected = {"data.bin": (entry, path)}
            existing, _ = inventory_target(target, expected)
            self.assertEqual(existing, {"data.bin"})

            unexpected = target / "unexpected.bin"
            copy_bytes_exclusive(unexpected, b"unexpected")
            with self.assertRaises(ValueError):
                inventory_target(target, expected)

    def test_target_inventory_rejects_existing_file_with_different_content(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            path = target / "data.bin"
            copy_bytes_exclusive(path, b"wrong")
            entry = {
                "name": "data.bin",
                "size": len(b"expected"),
                "sha256": hashlib.sha256(b"expected").hexdigest(),
            }
            with self.assertRaises(FileExistsError):
                inventory_target(target, {"data.bin": (entry, path)})

    def test_independent_manifest_hash_and_bundle_integrity_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "bundle"
            hash_directory = root / "independent"
            create_private_directory(bundle)
            create_private_directory(hash_directory)
            hash_path = hash_directory / "manifest.sha256"
            entries = []

            for logical_name, filename in DATABASE_FILENAMES.items():
                database = bundle / filename
                with closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture(value TEXT)")
                    connection.execute("INSERT INTO fixture VALUES ('preserved')")
                secure_permissions(database)
                with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                    check_integrity(connection)
                    tables = table_summary(connection)
                entries.append({
                    "name": filename,
                    "kind": "sqlite_backup_api",
                    "logical_name": logical_name,
                    "present": True,
                    "size": database.stat().st_size,
                    "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
                    "tables_and_row_counts": tables,
                })

            test_key = b"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
            test_fernet = Fernet(test_key)
            file_contents = {
                "nv_2fa.key": test_key,
                "nv_2fa_secrets.json": test_fernet.encrypt(b"{}"),
                "nv_2fa_verplicht.flag": b"required",
            }
            for name in REQUIRED_2FA_FILES:
                content = file_contents[name]
                copy_bytes_exclusive(bundle / name, content)
                entries.append({
                    "name": name,
                    "kind": "2fa_file",
                    "present": True,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                })
            for name in OPTIONAL_2FA_FILES:
                entries.append({"name": name, "kind": "optional", "present": False})

            write_manifest(bundle, {"format": 1, "entries": entries}, hash_path)
            manifest = read_verified_manifest(bundle, hash_path)
            self.assertEqual(len(manifest["entries"]), len(DATABASE_FILENAMES) + len(REQUIRED_2FA_FILES) + len(OPTIONAL_2FA_FILES))

            hash_path.write_text("0" * 64 + "  manifest.json\n", encoding="ascii")
            with self.assertRaises(RuntimeError):
                read_verified_manifest(bundle, hash_path)


if __name__ == "__main__":
    unittest.main()
