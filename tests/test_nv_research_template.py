"""Verify screened articles render with attribution in the real dashboard."""
import unittest
from unittest.mock import patch

from app import app
from test_nv_product_discovery import Response, editorial_card


class ResearchTemplateRegression(unittest.TestCase):
    def test_screened_news_renders_and_unsafe_link_is_absent(self):
        approved = "https://www.techradar.com/phones/phone-accessories/magnetic-powerbank-trends"
        unwanted = "https://login.microsoftonline.com/"
        body = (editorial_card(approved, "Trend: magnetische powerbank", "new charger")
                + editorial_card(unwanted, "Magnetische powerbank", "sign in")).encode()
        def fetch(url, **kwargs):
            return Response(body if "techradar" in url else b"<rss><channel/></rss>")
        with patch("app.admin_is_authenticated", return_value=True), patch("nv_product_discovery.requests.get", fetch):
            response = app.test_client().get("/dashboard", query_string={
                "section": "onderzoek", "research_run": 1, "research_category": "gadgets",
                "research_mode": "trends", "research_term": "magnetische powerbank",
                "research_platform": "Publicaties",
            })
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual(html.count(approved), 2)
        self.assertNotIn(unwanted, html)
        self.assertIn("Publicatie ", html)
        self.assertIn('id="nv-research-results"', html)
