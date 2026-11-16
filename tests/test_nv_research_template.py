"""Regression: a populated research result must not call dict.items as a loop."""
import unittest
from pathlib import Path
from jinja2 import Environment


class ResearchTemplateRegression(unittest.TestCase):
    def test_research_result_uses_dict_key_not_items_method(self):
        template = Path("templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("product_discovery['items']", template)
        self.assertNotIn("product_discovery.items", template)
        self.assertIn('id="onderzoeksresultaten"', template)
        Environment().parse(template)

    def test_research_results_render_with_fake_context(self):
        # Isolate the research panel from unrelated dashboard sections.
        html = Path("templates/dashboard.html").read_text(encoding="utf-8")
        start = html.index('<section class="panel nv-research-panel">')
        end = html.index('</section>', start) + len('</section>')
        snippet = html[start:end]
        from flask import Flask, request
        app = Flask(__name__)
        app.add_url_rule("/dashboard", endpoint="control", view_func=lambda: "")
        with app.test_request_context("/dashboard?section=onderzoek&research_run=1"):
            rendered = app.jinja_env.from_string(snippet).render(
                product_research_countries={"NL": ("Nederland", "nl")},
                product_discovery={
                    "error": None, "term": "ddr5 32gb", "country_name": "Nederland",
                    "checked_at": "2026-11-16", "links": [("Google", "https://google.com")],
                    "items": [{"url": "https://example.com", "title": "DDR5 article",
                               "source": "Testbron", "published": "2026-11-16"}],
                    "supplier_directories": [],
                },
            )
        self.assertIn("DDR5 article", rendered)
        self.assertIn("onderzoeksresultaten", rendered)


if __name__ == "__main__":
    unittest.main()
