import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nv_storage_paths


class StoragePathTests(unittest.TestCase):
    def test_defaults_keep_existing_project_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(nv_storage_paths.data_directory(), nv_storage_paths.BASE_DIR)
            self.assertEqual(
                nv_storage_paths.database_path("CUSTOMER_DB", "nuvemixa_customers.sqlite3"),
                nv_storage_paths.BASE_DIR / "nuvemixa_customers.sqlite3",
            )
            self.assertEqual(nv_storage_paths.two_fa_directory(), nv_storage_paths.BASE_DIR)

    def test_data_directory_sets_independent_defaults(self):
        # Use a native absolute path on Windows and Linux CI runners.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(os.environ, {"NUVEMIXA_DATA_DIR": str(root)}, clear=True):
                self.assertEqual(
                    nv_storage_paths.database_path("CUSTOMER_DB", "nuvemixa_customers.sqlite3"),
                    root / "nuvemixa_customers.sqlite3",
                )
                self.assertEqual(
                    nv_storage_paths.database_path("DASHBOARD_DB", "nuvemixa_dashboard.sqlite3"),
                    root / "nuvemixa_dashboard.sqlite3",
                )
                self.assertEqual(
                    nv_storage_paths.database_path("ADMIN_DB", "nuvemixa_admin.sqlite3"),
                    root / "nuvemixa_admin.sqlite3",
                )
                self.assertEqual(nv_storage_paths.two_fa_directory(), root)

    def test_explicit_and_legacy_database_paths_are_honored(self):
        with patch.dict(
            os.environ,
            {
                "DASHBOARD_DB": r"C:\primary\dashboard.sqlite3",
                "NUVEMIXA_DASHBOARD_DB": r"C:\legacy\dashboard.sqlite3",
            },
            clear=True,
        ):
            self.assertEqual(
                nv_storage_paths.database_path(
                    "DASHBOARD_DB", "nuvemixa_dashboard.sqlite3", "NUVEMIXA_DASHBOARD_DB"
                ),
                Path(r"C:\primary\dashboard.sqlite3"),
            )
        with patch.dict(
            os.environ, {"NUVEMIXA_DASHBOARD_DB": r"C:\legacy\dashboard.sqlite3"}, clear=True
        ):
            self.assertEqual(
                nv_storage_paths.database_path(
                    "DASHBOARD_DB", "nuvemixa_dashboard.sqlite3", "NUVEMIXA_DASHBOARD_DB"
                ),
                Path(r"C:\legacy\dashboard.sqlite3"),
            )

    def test_two_fa_directory_has_explicit_deployment_override(self):
        with patch.dict(os.environ, {"NUVEMIXA_2FA_DIR": r"C:\disk\2fa"}, clear=True):
            self.assertEqual(nv_storage_paths.two_fa_directory(), Path(r"C:\disk\2fa"))
        with patch.dict(os.environ, {"2FA_DIR": r"C:\disk\legacy-2fa"}, clear=True):
            self.assertEqual(nv_storage_paths.two_fa_directory(), Path(r"C:\disk\legacy-2fa"))

    def test_prefixed_database_variables_take_precedence_and_keep_old_aliases(self):
        with patch.dict(
            os.environ,
            {
                "NUVEMIXA_CUSTOMER_DB": r"C:\preferred\customers.sqlite3",
                "CUSTOMER_DB": r"C:\legacy\customers.sqlite3",
            },
            clear=True,
        ):
            self.assertEqual(
                nv_storage_paths.database_path(
                    "NUVEMIXA_CUSTOMER_DB", "nuvemixa_customers.sqlite3", "CUSTOMER_DB"
                ),
                Path(r"C:\preferred\customers.sqlite3"),
            )
        with patch.dict(
            os.environ, {"CUSTOMER_DB": r"C:\legacy\customers.sqlite3"}, clear=True
        ):
            self.assertEqual(
                nv_storage_paths.database_path(
                    "NUVEMIXA_CUSTOMER_DB", "nuvemixa_customers.sqlite3", "CUSTOMER_DB"
                ),
                Path(r"C:\legacy\customers.sqlite3"),
            )

    def test_module_uses_alwaysdata_variable_names(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            customer_path = data_dir / "custom-customer.sqlite3"
            environment = {
                "NUVEMIXA_REQUIRE_DATA_DIR": "1",
                "NUVEMIXA_DATA_DIR": str(data_dir),
                "NUVEMIXA_CUSTOMER_DB": str(customer_path),
            }
            try:
                with patch.dict(os.environ, environment, clear=True):
                    importlib.reload(nv_storage_paths)
                    self.assertEqual(nv_storage_paths.CUSTOMER_DB, customer_path)
                    self.assertEqual(
                        nv_storage_paths.DASHBOARD_DB,
                        data_dir / "nuvemixa_dashboard.sqlite3",
                    )
                    self.assertEqual(
                        nv_storage_paths.ADMIN_DB,
                        data_dir / "nuvemixa_admin.sqlite3",
                    )
                    self.assertEqual(nv_storage_paths.TWO_FA_DIR, data_dir)
            finally:
                importlib.reload(nv_storage_paths)

    def test_required_data_directory_must_be_explicit_external_and_writable(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(
                os.environ,
                {"NUVEMIXA_REQUIRE_DATA_DIR": "1", "NUVEMIXA_DATA_DIR": temp},
                clear=True,
            ):
                self.assertEqual(nv_storage_paths.data_directory(), Path(temp))
        with patch.dict(os.environ, {"NUVEMIXA_REQUIRE_DATA_DIR": "1"}, clear=True):
            with self.assertRaises(RuntimeError):
                nv_storage_paths.data_directory()
        with patch.dict(
            os.environ,
            {
                "NUVEMIXA_REQUIRE_DATA_DIR": "1",
                "NUVEMIXA_DATA_DIR": str(nv_storage_paths.BASE_DIR),
            },
            clear=True,
        ):
            with self.assertRaises(ValueError):
                nv_storage_paths.data_directory()
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(
                os.environ,
                {
                    "NUVEMIXA_REQUIRE_DATA_DIR": "1",
                    "NUVEMIXA_DATA_DIR": temp,
                    "NUVEMIXA_CUSTOMER_DB": "relative/customers.sqlite3",
                },
                clear=True,
            ):
                with self.assertRaises(ValueError):
                    nv_storage_paths.database_path(
                        "NUVEMIXA_CUSTOMER_DB", "nuvemixa_customers.sqlite3", "CUSTOMER_DB"
                    )


if __name__ == "__main__":
    unittest.main()
