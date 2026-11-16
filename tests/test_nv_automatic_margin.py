import unittest
from decimal import Decimal
from pathlib import Path
from jinja2 import Environment
from nv_product_margin import automatic_margin

class SingleInputMarginTests(unittest.TestCase):
    def test_one_purchase_price_generates_all_totals(self):
        result = automatic_margin("12.50")
        self.assertGreater(Decimal(result["selling"]), Decimal("12.50"))
        self.assertGreater(Decimal(result["profit"]), 0)
        self.assertGreater(Decimal(result["vat"]), 0)
        self.assertAlmostEqual(float(result["margin_pct"]), 25.0, delta=0.1)
    def test_invalid_price_rejected(self):
        for price in ["", "-1", "0", "abc"]:
            with self.subTest(price=price), self.assertRaises(ValueError):
                automatic_margin(price)
    def test_dashboard_has_only_one_required_margin_input(self):
        html = Path("templates/dashboard.html").read_text(encoding="utf-8")
        block = html.split("<h2>Automatisch verkoopadvies en winstmarge</h2>")[1].split("</section>")[0]
        self.assertEqual(block.count('type="number"'), 1)
        self.assertIn("Bereken automatisch", block)
        self.assertIn("Productdossier — eigen onderzoeksnotities (optioneel)", html)
        Environment().parse(html)

if __name__ == "__main__":
    unittest.main()
