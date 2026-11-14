import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nv_2fa_rate_limit
import nv_2fa_replay
import nv_2fa_status
import nv_2fa_storage


class TwoFaStoragePermissionTests(unittest.TestCase):
    def assert_private_file(self, path):
        self.assertTrue(Path(path).is_file())
        if os.name != "nt":
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)

    def test_atomic_secret_write_uses_private_file_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "secrets.enc"
            nv_2fa_storage._atomic_write(path, b"encrypted-fixture")
            self.assert_private_file(path)
            self.assertEqual(path.read_bytes(), b"encrypted-fixture")

    def test_storage_lock_is_private_and_existing_key_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            lock_path = Path(temp) / "nv_2fa_storage.lock"
            key_path = Path(temp) / "nv_2fa.key"
            key = b"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
            key_path.write_bytes(key)
            with patch.object(nv_2fa_storage, "LOCKBESTAND", lock_path):
                with nv_2fa_storage._bestandsslot():
                    pass
            with patch.object(nv_2fa_storage, "SLEUTELBESTAND", key_path):
                nv_2fa_storage._fernet()
            self.assert_private_file(lock_path)
            self.assertEqual(key_path.read_bytes(), key)

    def test_required_2fa_flag_is_created_exclusively_with_private_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "required.flag"
            with patch.object(nv_2fa_status, "MARKERING", marker):
                nv_2fa_status.maak_verplicht()
            self.assert_private_file(marker)
            self.assertEqual(marker.read_text(encoding="utf-8"), "2FA_REQUIRED\n")

    def test_rate_limit_database_is_private(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "attempts.sqlite3"
            with patch.object(nv_2fa_rate_limit, "DATABASE", database):
                self.assertTrue(nv_2fa_rate_limit.registreer_en_controleer("test-hash"))
            self.assert_private_file(database)

    def test_replay_database_is_private(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "replay.sqlite3"
            with patch.object(nv_2fa_replay, "DATABASE", database):
                self.assertTrue(nv_2fa_replay.registreer_eenmalig(12345))
            self.assert_private_file(database)


if __name__ == "__main__":
    unittest.main()
