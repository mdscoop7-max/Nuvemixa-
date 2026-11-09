"""Safe external integration regression tests. Nothing uses live credentials."""
import os
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from nuvemixa_integrations import rankfix_scan_url, mollie_readonly_check, merchant_feed_preview, supplier_csv_preview

class IntegrationSafetyTests(unittest.TestCase):
    def test_rankfix_handoff_with_nuvemixa_address(self):
        with patch.dict(os.environ, {"RANKFIX_BASE_URL": "https://rankfix-app.onrender.com"}):
            url = rankfix_scan_url("https://nuvemixa.alwaysdata.net/")
            self.assertIn("/dashboard/scan?url=", url)
            self.assertIn("nuvemixa.alwaysdata.net", url)

    def test_rankfix_refuses_untrusted_destinations(self):
        cases = (
            "http://rankfix-app.onrender.com",
            "https://someone:password@evil.com",
            "https://rankfix-app.onrender.com.evil.test",
            "https://rankfix-app.onrender.com/path",
            "https://rankfix-app.onrender.com?token=secret",
        )
        for base in cases:
            with self.subTest(base=base), patch.dict(os.environ, {"RANKFIX_BASE_URL": base}):
                self.assertIsNone(rankfix_scan_url())

    def test_rankfix_refuses_other_site(self):
        with patch.dict(os.environ, {"RANKFIX_BASE_URL": "https://rankfix-app.onrender.com"}):
            self.assertIsNone(rankfix_scan_url("https://other-site.example/"))

    def test_mollie_without_credentials_makes_no_request(self):
        with patch.dict(os.environ, {"MOLLIE_API_KEY": ""}), patch("urllib.request.urlopen") as open_mock:
            result = mollie_readonly_check()
            self.assertEqual(result["state"], "not_configured")
            open_mock.assert_not_called()

    def test_mollie_check_is_get_only(self):
        class FakeResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self, size): return b'{"resource":"list","count":0}'
        with patch.dict(os.environ, {"MOLLIE_API_KEY": "test_fake_not_real"}), \
             patch("urllib.request.urlopen", return_value=FakeResponse()) as open_mock:
            result = mollie_readonly_check()
            self.assertEqual(result["state"], "connected_test")
            request = open_mock.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "https://api.mollie.com/v2/methods?limit=1")
            self.assertNotIn("test_fake_not_real", request.full_url)

    def test_merchant_preview_empty_without_verification(self):
        raw, count = merchant_feed_preview([{"id": "unverified", "name": "Example", "price": 100}])
        self.assertEqual(count, 0)
        root = ET.fromstring(raw)
        self.assertEqual(root.findall(".//item"), [])

    def test_verified_product_in_private_preview(self):
        product = {
            "merchant_verified": True, "id": "123", "name": "Verified Test",
            "image": "/static/test-product.jpg", "product_url": "/gadgets/test",
            "brand": "Example", "stock_status": "in_stock", "price": "49.99",
            "supplier_verified": True, "product_data_verified": True,
            "price_verified": True, "image_verified": True, "delivery_verified": True
        }
        raw, count = merchant_feed_preview([product])
        self.assertEqual(count, 1)
        self.assertEqual(len(ET.fromstring(raw).findall(".//item")), 1)
        product["merchant_verified"] = False
        self.assertEqual(merchant_feed_preview([product])[1], 0)

    def test_supplier_feed_checks_without_import(self):
        csv_data = b"sku,name,price,stock\nSKU-1,Test item,12.50,10\nSKU-2,Second item,0,NA\n"
        with self.subTest("rows"):
            result = supplier_csv_preview(csv_data)
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["valid_format"], 1)
            self.assertEqual(result["imported"], 0)
            self.assertEqual(result["published"], 0)

    def test_supplier_feed_rejects_invalid_csv(self):
        with self.assertRaises(ValueError):
            supplier_csv_preview(b"example,missing,headers\n1,2,3\n")
        with self.assertRaises(ValueError):
            supplier_csv_preview(b"x" * 60001)

    def test_admin_routes_reject_anonymous(self):
        os.environ.setdefault("SECRET_KEY", "ci-integration-test-key")
        os.environ.setdefault("NUVEMIXA_COOKIE_SECURE", "false")
        from app import app
        app.config["TESTING"] = True
        client = app.test_client()
        for path in ("/admin/rankfix/open", "/admin/mollie/check",
                     "/admin/merchant-feed-preview.xml"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login", response.location)
        # Upload is POST-only; anonymous requests must be blocked by CSRF/auth.
        response = client.post("/admin/supplier-feed-preview", data={})
        self.assertEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
