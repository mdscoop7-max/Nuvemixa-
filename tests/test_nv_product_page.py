"""Verify the actual dashboard route and form wiring."""
import unittest
from unittest.mock import patch

from app import app
from nv_product_discovery import EMPTY_RESULTS
from test_nv_product_discovery import Response, catalogue, item


class ProductResearchPageTests(unittest.TestCase):
    def test_unauthenticated_requests_do_not_reach_any_source(self):
        with patch("nv_product_discovery.requests.get") as fetch:
            response = app.test_client().get("/dashboard?section=onderzoek&research_run=1&research_term=lamp")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.location)
        fetch.assert_not_called()

    def test_form_choices_and_rendered_results(self):
        def fetch(url, **kwargs):
            self.assertIn(url, {
                "https://eu.switch-bot.com/search/suggest.json", "https://eu.eufy.com/search/suggest.json",
            })
            self.assertIn("lamp", kwargs["params"]["q"])
            return Response(catalogue(item("SwitchBot RGBICWW Floor Lamp", "switchbot-rgbicww-floor-lamp")))
        query = {
            "section": "onderzoek", "research_run": "1", "research_category": "smart-home",
            "research_mode": "niche", "research_country": "BE", "research_term": "lamp",
            "research_platform": "Productcatalogi",
        }
        with patch("app.admin_is_authenticated", return_value=True), patch("nv_product_discovery.requests.get", fetch):
            client = app.test_client()
            response = client.get("/dashboard", query_string=query)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        form = html.split('name="research_category"', 1)[1].split("</select>", 1)[0]
        for name in ("Gadgets", "Smart Home", "Beauty &amp; Care", "Home &amp; Living", "Lifestyle &amp; Sport", "All products"):
            self.assertIn(f">{name}</option>", form)
        self.assertEqual(form.count("<option "), 6)
        self.assertIn('value="smart-home" selected', form)
        self.assertIn('value="BE" selected', html)
        self.assertIn('value="niche" selected', html)
        for label in ("Trends en nichekansen", "Direct nicheproducten zoeken", "Specifiek product zoeken", "Leveranciers zoeken"):
            self.assertIn(label, html)
        for label in ("Productresultaten", "Trends &amp; inzichten", "Leveranciers", "Nieuws &amp; reviews"):
            self.assertIn(label, html)
        self.assertIn("SwitchBot RGBICWW Floor Lamp", html)
        self.assertIn("België", html)

    def test_empty_results_and_margin_calculator(self):
        with patch("app.admin_is_authenticated", return_value=True):
            client = app.test_client()
            response = client.get("/dashboard?section=onderzoek&research_run=1&research_term=lamp&research_platform=TikTok")
            self.assertEqual(response.status_code, 200)
            self.assertIn(EMPTY_RESULTS, response.get_data(as_text=True))
            margin = client.get("/dashboard?section=onderzoek&margin_run=1&purchase_cost=12.50")
            self.assertEqual(margin.status_code, 200)
            self.assertIn("Adviesverkoopprijs incl. btw", margin.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
