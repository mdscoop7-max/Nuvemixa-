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
            if url.startswith(("https://syncee.com/collections/", "https://hurtel.com/")):
                return Response()
            if url.startswith("https://nedis-shop.nl/"):
                return Response(catalogue())
            self.assertIn(url, {
                "https://eu.switch-bot.com/search/suggest.json", "https://eu.eufy.com/search/suggest.json",
            })
            self.assertIn("lamp", kwargs["params"]["q"])
            return Response(catalogue(item("SwitchBot RGBICWW Floor Lamp", "switchbot-rgbicww-floor-lamp")))
        query = {
            "section": "onderzoek", "research_run": "1", "research_category": "smart-home",
            "research_mode": "niche", "research_country": "BE", "research_term": "lamp",
            "research_platform": "Productcatalogi", "research_supplier_filter": "international",
        }
        with patch("app.admin_is_authenticated", return_value=True), patch("nv_product_discovery.requests.get", fetch):
            client = app.test_client()
            response = client.get("/dashboard", query_string=query)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        form = html.split('name="research_category"', 1)[1].split("</select>", 1)[0]
        for name in ("Gadgets", "Smart Home", "Beauty &amp; Care", "Home &amp; Living", "Lifestyle &amp; Sport", "Huisdieren", "All products"):
            self.assertIn(f">{name}</option>", form)
        self.assertEqual(form.count("<option "), 7)
        self.assertIn('value="smart-home" selected', form)
        self.assertIn('value="BE" selected', html)
        self.assertIn('value="niche" selected', html)
        self.assertIn('value="international" selected', html)
        for label in ("Producten zoeken", "Trends en nichekansen", "Direct nicheproducten zoeken", "Specifiek product zoeken",
                      "Leveranciers zoeken", "Dropshippingpartners zoeken", "Groothandels en fabrikanten zoeken",
                      "Nieuws en productreviews zoeken"):
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


    def test_topbar_search_routes_to_existing_management_catalogue(self):
        from app import load_all_products

        name = load_all_products()[0]["name"]
        with patch("app.admin_is_authenticated", return_value=True), patch("app.allowed", return_value=True), patch(
            "nv_product_discovery.requests.get"
        ) as fetch:
            client = app.test_client()
            research = client.get("/dashboard?section=onderzoek").get_data(as_text=True)
            search = client.get("/dashboard", query_string={"section": "producten", "q": name})
        self.assertNotIn('class="top-search"', research)
        self.assertNotIn("Zoek producten in beheer", research)
        self.assertIn('name="research_term"', research)
        topbar = search.get_data(as_text=True).split('class="top-search"', 1)[1].split("</form>", 1)[0]
        self.assertIn('name="section" value="producten"', topbar)
        self.assertIn('type="submit"', topbar)
        self.assertNotIn("research_term", topbar)
        self.assertEqual(search.status_code, 200)
        self.assertIn("Bekijk productpagina", search.get_data(as_text=True))
        self.assertIn('<details class="panel-after" open>', search.get_data(as_text=True))
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
