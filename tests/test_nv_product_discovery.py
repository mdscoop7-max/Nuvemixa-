"""Offline contract tests for source-linked NUVEMIXA product discovery."""
import unittest
from nv_product_discovery import discover

RSS = b"""<?xml version="1.0"?><rss><channel><item>
<title>Testproduct in de markt</title><link>https://example.org/article</link>
<pubDate>Mon, 16 Nov 2026 08:00:00 GMT</pubDate><source>Voorbeeldbron</source>
</item></channel></rss>"""


class Response:
    content = RSS

    def raise_for_status(self):
        return None


class DiscoveryTests(unittest.TestCase):
    def test_source_link_and_no_fabricated_metrics(self):
        result = discover("slimme lamp", country="NL", platforms=["Google"], fetch=lambda *a, **k: Response())
        self.assertEqual(result["items"][0]["url"], "https://example.org/article")
        self.assertEqual(result["country_name"], "Nederland")
        self.assertEqual([name for name, _ in result["links"]], ["Google"])
        self.assertNotIn("trend_growth", result)
        self.assertNotIn("profit", result)
        self.assertTrue(result["supplier_directories"])

    def test_empty_query_and_no_platform(self):
        self.assertTrue(discover("")["error"])
        self.assertTrue(discover("lamp", platforms=[])["error"])

    def test_non_eu_has_no_eu_supplier_shortlist(self):
        result = discover("lamp", country="US", platforms=["TikTok"], fetch=lambda *a, **k: Response())
        self.assertFalse(result["supplier_directories"])
        self.assertEqual(result["links"][0][0], "TikTok")


if __name__ == "__main__":
    unittest.main()
