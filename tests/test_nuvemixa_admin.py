"""NUVEMIXA admin regression checks. Run: python -m unittest discover -s tests -p 'test_nuvemixa_admin.py'"""
import os
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash

os.environ.setdefault("SECRET_KEY", "test-only-stable-secret")
os.environ.setdefault("NUVEMIXA_ADMIN_PASSWORD_HASH", generate_password_hash("unit-test-password-long"))
os.environ.setdefault("NUVEMIXA_COOKIE_SECURE", "false")

from app import app  # noqa: E402


class TestNuvemixaAdmin(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_public_home_remains_available(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirects_to_login(self):
        for path in ("/dashboard", "/control", "/catalogus-overzicht",
                     "/admin/integrations", "/admin/merchant-preview",
                     "/admin/research-preview"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login", response.headers["Location"])

    def test_login_fails_closed_without_credentials(self):
        with patch.dict(os.environ, {"NUVEMIXA_ADMIN_PASSWORD_HASH": ""}):
            response = self.client.get("/admin/login")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_bad_password_rejected(self):
        response = self.client.get("/admin/login")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            token = session["_tm_csrf"]
        response = self.client.post("/admin/login", data={
            "_csrf_token": token, "password": "wrong-password"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Het wachtwoord klopt niet", response.data)

    def test_successful_login_and_logout(self):
        self.client.get("/admin/login")
        with self.client.session_transaction() as session:
            token = session["_tm_csrf"]
        response = self.client.post("/admin/login", data={
            "_csrf_token": token, "password": "unit-test-password-long"
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        report = self.client.get("/admin/merchant-preview")
        self.assertEqual(report.status_code, 200)
        self.assertFalse(report.json["published"])
        self.assertEqual(report.headers["Cache-Control"], "no-store")
        research = self.client.get("/admin/research-preview")
        self.assertFalse(research.json["market_data_connected"])
        self.client.get("/dashboard")
        with self.client.session_transaction() as session:
            token = session["_tm_csrf"]
        response = self.client.post("/admin/logout", data={"_csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_test_catalog_is_not_merchant_ready(self):
        from app import merchant_product_checks
        errors = merchant_product_checks({
            "name": "Test", "stock_status": "unknown",
            "price": 20, "brand": None
        })
        self.assertIn("voorraad", errors)
        self.assertIn("leverancier", errors)
        self.assertIn("prijs", errors)


if __name__ == "__main__":
    unittest.main()
