"""Regression coverage for rendering screened editorial results."""
import unittest
from unittest.mock import patch

from app import app
from test_nv_product_discovery import Response, rss


class ResearchTemplateRegression(unittest.TestCase):
    def test_screened_news_renders_and_unsafe_link_is_absent(self):
        approved = "https://tweakers.net/nieuws/12345/magnetische-powerbank-trends.html"
        unwanted = "https://login.microsoftonline.com/"
        feed = rss(("Trend: magnetische powerbank", approved), ("Magnetische powerbank", unwanted))
        with patch("app.admin_is_authenticated", return_value=True), patch(
            "nv_product_discovery.requests.get", return_value=Response(feed)
        ):
            response = app.test_client().get("/dashboard", query_string={
                "section": "onderzoek", "research_run": 1, "research_category": "gadgets",
                "research_mode": "trends", "research_term": "magnetische powerbank",
                "research_platform": "Bing",
            })
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual(html.count(approved), 2)
        self.assertNotIn(unwanted, html)
        self.assertIn('id="nv-research-results"', html)


if __name__ == "__main__":
    unittest.main()
