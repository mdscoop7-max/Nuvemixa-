"""Tests for the optional private NUVEMIXA supplier/research database."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nuvemixa_admin_store import (
    database_path, list_suppliers, add_supplier, list_research, add_research,
)


class TestAdminStore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "admin.sqlite3")
        self.patch = patch.dict(os.environ, {"NUVEMIXA_ADMIN_DB": self.path})
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_database_starts_empty(self):
        self.assertEqual(list_suppliers(), [])
        self.assertEqual(list_research(), [])

    def test_supplier_write_and_persistence(self):
        add_supplier("EU Test Supplier", "contact@example.com", "https://example.com", "Draft")
        result = list_suppliers()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "EU Test Supplier")
        self.assertEqual(result[0]["status"], "onderzoek")
        self.assertEqual(list_suppliers()[0]["name"], "EU Test Supplier")

    def test_duplicate_supplier_rejected(self):
        import sqlite3
        add_supplier("Same Supplier")
        with self.assertRaises(sqlite3.IntegrityError):
            add_supplier("Same Supplier")

    def test_reject_untrusted_input(self):
        with self.assertRaises(ValueError):
            add_supplier(" ")
        with self.assertRaises(ValueError):
            add_supplier("Supplier", website="javascript:alert(1)")
        with self.assertRaises(ValueError):
            add_research("X", "Name")
        self.assertEqual(list_suppliers(), [])
        self.assertEqual(list_research(), [])

    def test_research_does_not_invent_metrics(self):
        add_research("Gadgets", "Interesting gadget", "https://example.org", "Verify suppliers")
        rows = list_research()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_name"], "Interesting gadget")
        self.assertIsNone(rows[0]["purchase_cost_cents"])
        self.assertIsNone(rows[0]["selling_price_cents"])

    def test_unconfigured_database_fails_closed(self):
        with patch.dict(os.environ, {"NUVEMIXA_ADMIN_DB": ""}):
            self.assertIsNone(database_path())
            with self.assertRaises(RuntimeError):
                list_suppliers()


if __name__ == "__main__":
    unittest.main()
