"""Verify screened articles render with attribution in the real dashboard."""
import unittest
from unittest.mock import patch

from app import app
from test_nv_product_discovery import Response, editorial_card


class ResearchTemplateRegression(unittest.TestCase):
    def test_supplier_search_entry_works_without_ai_and_defaults_to_eu(self):
        with patch("app.admin_is_authenticated", return_value=True):
            response = app.test_client().get("/dashboard?section=leveranciers")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        form = html.split("data-research-search>", 1)[1].split("</form>", 1)[0]
        self.assertIn('name="section" value="onderzoek"', form)
        self.assertIn('name="research_platform" value="Productcatalogi"', form)
        self.assertIn('<option value="eu">Binnen EU</option>', form)
        self.assertIn('<option value="all">Alle landen</option>', form)
        self.assertIn('role="status"', form)

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

    def test_google_trends_shows_category_source_date_and_approximate_searches(self):
        from datetime import datetime, timezone
        from email.utils import format_datetime

        stamp = format_datetime(datetime.now(timezone.utc))
        xml = f"""<rss xmlns:ht="https://trends.google.com/trending/rss"><channel>
          <item><title>Facial cleanser</title><pubDate>{stamp}</pubDate><ht:approx_traffic>500+</ht:approx_traffic></item>
          <item><title>Kitchen organizer</title><pubDate>{stamp}</pubDate></item>
          <item><title>Retro game console</title><pubDate>{stamp}</pubDate></item>
        </channel></rss>"""

        def fetch(url, **kwargs):
            self.assertEqual(url, "https://trends.google.com/trending/rss")
            self.assertEqual(kwargs["params"], {"geo": "NL"})
            return Response(xml.encode())

        with patch("app.admin_is_authenticated", return_value=True), patch("nv_product_discovery.requests.get", fetch):
            response = app.test_client().get("/dashboard", query_string={
                "section": "onderzoek", "research_run": 1, "research_mode": "trends",
                "research_term": "Trending beautyproducten", "research_platform": "Google Trends",
            })
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Facial cleanser</a>", html)
        self.assertIn("500+ zoekopdrachten", html)
        self.assertNotIn("Kitchen organizer</a>", html)
        self.assertNotIn("Retro game console</a>", html)
