"""Regression tests for inline product research results and public RSS parsing."""
import unittest
from pathlib import Path
from jinja2 import Environment
from nv_product_discovery import discover


class FakeResponse:
    content = b'<rss><channel><item><title>DDR5 leverancier</title><link>https://example.com/ddr5</link></item></channel></rss>'
    def raise_for_status(self):
        pass


class ProductResearchPageTests(unittest.TestCase):
    def test_results_template_uses_dictionary_index_not_items_method(self):
        source = Path("templates/dashboard.html").read_text(encoding="utf-8")
        self.assertNotIn("product_discovery.items", source)
        self.assertIn("product_discovery['items']", source)
        self.assertIn('id="nv-research-results"', source)
        self.assertIn("supplier_items", source)
        Environment().parse(source)

    def test_public_search_and_suppliers_have_real_links(self):
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            return FakeResponse()
        result = discover("DDR5 32GB", country="NL", platforms=["Google"], fetch=fetch)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(len(result["web_items"]), 1)
        self.assertEqual(len(result["supplier_items"]), 1)
        self.assertEqual(result["supplier_items"][0]["url"], "https://example.com/ddr5")

    def test_unavailable_sources_show_empty_results(self):
        import requests
        def fail(*args, **kwargs):
            raise requests.Timeout()
        result = discover("DDR5 32GB", fetch=fail)
        self.assertEqual(result["web_items"], [])
        self.assertEqual(result["supplier_items"], [])
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
