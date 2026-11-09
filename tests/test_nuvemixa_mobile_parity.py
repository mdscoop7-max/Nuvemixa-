"""Regression checks: existing NUVEMIXA template, five categories and responsive app dock."""
import os
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-only-mobile-parity-key")
os.environ.setdefault("NUVEMIXA_COOKIE_SECURE", "false")

from app import app  # noqa: E402


class MobileParityTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.template_dir = Path(__file__).resolve().parent.parent / "templates"

    def test_shared_mobile_templates_compile(self):
        # Regression for the 2026-11-05 malformed Jinja include (%> instead of %}).
        for template in ("_bottomnav.html", "_tm_mobile_extras.html", "_footer.html"):
            with self.subTest(template=template):
                self.assertNotIn("{% include '_tm_mobile_extras.html' %>", (self.template_dir / template).read_text(encoding="utf-8"))
                app.jinja_env.get_template(template)

    def test_five_existing_category_routes_are_public(self):
        for slug in ("gadgets", "smart-home", "beauty-care", "home-living", "lifestyle-sport"):
            with self.subTest(slug=slug):
                response = self.client.get("/" + slug)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"/home-living", response.data)

    def test_five_category_cards_visible_on_homepage(self):
        homepage = self.client.get("/")
        self.assertEqual(homepage.status_code, 200)
        self.assertEqual(homepage.data.count(b'class="categorytile '), 5)
        for slug in ("gadgets", "smart-home", "beauty-care", "home-living", "lifestyle-sport"):
            self.assertIn(('href="/' + slug + '"').encode(), homepage.data)

    def test_preserve_existing_hero_images_and_home_living_special_hero(self):
        template = (self.template_dir / "category.html").read_text(encoding="utf-8")
        for hero in ("gadgets.jpg", "smart-home.png", "beauty-care.png", "lifestyle-sport.jpg"):
            self.assertIn(hero, template)
        self.assertIn("{% else %}<section class=\"hero\">", template)
        self.assertIn("category_slug == 'home-living'", template)

    def test_mobile_dock_has_real_cart_and_accessible_categories_button(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('class="tm-dock"', html)
        self.assertIn('class="tm-dock-categories"', html)
        self.assertIn('data-tm-menu-trigger', html)
        self.assertIn('aria-controls="tmMobileDrawer"', html)
        self.assertIn('href="/winkelwagen"', html)
        self.assertIn('id="tmMobileDrawer"', html)
        self.assertIn('data-tm-language="nl"', html)
        self.assertIn('data-tm-language="en"', html)

    def test_cart_and_checkout_still_accessible_in_test_mode(self):
        self.assertEqual(self.client.get("/winkelwagen").status_code, 200)
        result = self.client.get("/afrekenen")
        self.assertIn(result.status_code, (200, 302))


if __name__ == "__main__":
    unittest.main()
