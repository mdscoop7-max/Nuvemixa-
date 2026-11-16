"""Offline, deterministic margin tests for Productonderzoek."""
import unittest
from nv_product_margin import calculate_margin


class MarginTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "selling_price": "121.00", "purchase_cost": "40.00",
            "shipping_cost": "5.00", "advertising_cost": "10.00",
            "platform_fee": "3.00", "returns_reserve": "2.00",
            "other_cost": "0.00", "vat_rate": "21.00",
        }

    def test_exact_vat_and_profit(self):
        result = calculate_margin(self.values)
        self.assertEqual(result["revenue_ex_vat"], "100.00")
        self.assertEqual(result["vat_amount"], "21.00")
        self.assertEqual(result["total_cost"], "60.00")
        self.assertEqual(result["profit"], "40.00")
        self.assertEqual(result["margin_pct"], "40.00")

    def test_rejects_negative_nan_and_excess_precision(self):
        for invalid in ("-1", "NaN", "Infinity", "1.234", "1000001"):
            values = dict(self.values, purchase_cost=invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                calculate_margin(values)

    def test_rejects_invalid_vat(self):
        with self.assertRaises(ValueError):
            calculate_margin(dict(self.values, vat_rate="101"))

    def test_zero_sale(self):
        result = calculate_margin(dict(self.values, selling_price="0"))
        self.assertEqual(result["margin_pct"], "0.00")
        self.assertEqual(result["profit"], "-60.00")


if __name__ == "__main__":
    unittest.main()
