"""Offline tests for source selection, relevance and untrusted provider data."""
import json
import unittest
from unittest.mock import Mock
from xml.etree.ElementTree import Element, SubElement, tostring

import requests

from nv_product_discovery import COUNTRIES, EMPTY_RESULTS, discover

CATEGORIES = {
    "gadgets": "Gadgets", "smart-home": "Smart Home", "beauty-care": "Beauty & Care",
    "home-living": "Home & Living", "lifestyle-sport": "Lifestyle & Sport",
}


def item(title, handle, **overrides):
    return {
        "id": 123, "title": title, "handle": handle, "type": "",
        "url": f"/products/{handle}?_pos=1", **overrides,
    }


def catalogue(*items):
    return json.dumps({"resources": {"results": {"products": items}}}).encode()


def rss(*items):
    channel = SubElement(root := Element("rss"), "channel")
    for title, url in items:
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = title
        SubElement(entry, "link").text = url
    return tostring(root)


class Response:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.content


class DiscoveryTests(unittest.TestCase):
    def search(self, term, **kwargs):
        return discover(term, categories=CATEGORIES, **kwargs)

    def test_specific_product_matches_required_terms_and_capacity(self):
        valid = item("Magnetic Power Bank 10000mAh", "magnetic-power-bank-10000", type="Power Bank",
                     price="1.00", available=True, image="https://elsewhere.example/image.jpg")
        feed = catalogue(
            valid, dict(valid), item("Magnetic Power Bank 5000mAh", "magnetic-power-bank-5000"),
            item("Powerbank 10000 mAh", "powerbank-10000"),
            item("Magnetic Power Bank 10000 mAh", "fake", url="https://login.microsoft.com/"),
            item("XXX Magnetic Power Bank 10000mAh", "adult-video"),
            item("Magnetic Power Bank login 10000mAh", "login"),
            item("Magnetic Power Bank 10000mAh", "not-a-product", url="/pages/search"),
        )
        fetch = Mock(return_value=Response(feed))
        result = self.search("magnetische powerbank 10.000 mAh", category="gadgets", mode="product",
                             platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual(result["products"], [{
            "title": valid["title"], "url": "https://eu.ugreen.com/products/magnetic-power-bank-10000",
            "source": "UGREEN", "category": "gadgets", "image": "",
            "trade_url": "https://www.ugreen.com/pages/wholesale-program",
        }])
        url = fetch.call_args.args[0]
        self.assertEqual(url, "https://eu.ugreen.com/search/suggest.json")
        self.assertEqual(fetch.call_args.kwargs["params"]["q"], "magnetic power bank 10000 mah")
        self.assertEqual(fetch.call_args.kwargs["params"]["resources[options][fields]"], "title,variants.sku,product_type")
        self.assertIs(fetch.call_args.kwargs["allow_redirects"], False)

    def test_category_limits_sources_and_matches_independently_of_search_words(self):
        fetch = Mock(return_value=Response(catalogue(
            item("SwitchBot RGBICWW Floor Lamp", "switchbot-rgbicww-floor-lamp", type="LIGHTING"),
            item("Table Lamp", "table-lamp"),
        )))
        result = self.search("lamp", category="smart-home", mode="niche",
                             platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual({call.args[0] for call in fetch.call_args_list}, {
            "https://eu.switch-bot.com/search/suggest.json", "https://eu.eufy.com/search/suggest.json",
        })
        self.assertEqual([p["title"] for p in result["products"]], ["SwitchBot RGBICWW Floor Lamp"])

        fetch.reset_mock()
        self.search("lamp", category="shop", platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual(fetch.call_count, 6)

    def test_category_only_discovery_and_market_specific_storefront(self):
        fetch = Mock(return_value=Response(catalogue(item("Camera", "security-camera"))))
        result = self.search("", category="smart-home", mode="niche", country="US",
                             platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual(result["country_name"], "Verenigde Staten")
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], "https://us.eufy.com/search/suggest.json")
        self.assertEqual(fetch.call_args.kwargs["params"]["q"], "camera")

    def test_supplier_requires_product_match_and_trade_channel(self):
        def fetch(url, **kwargs):
            self.assertEqual(url, "https://eu.eufy.com/search/suggest.json")
            return Response(catalogue(item("eufy Security Camera", "security-camera")))
        result = self.search("camera", category="smart-home", mode="suppliers", fetch=fetch)
        self.assertEqual(result["products"], [])
        self.assertEqual([s["source"] for s in result["suppliers"]], ["eufy"])
        self.assertEqual(result["news"], [])
        self.assertEqual(result["suppliers"][0]["trade_url"], "https://www.eufy.com/eu-en/partner-program")

    def test_platforms_limit_network_and_manual_links(self):
        fetch = Mock()
        for country in COUNTRIES:
            with self.subTest(country=country):
                result = self.search("lamp", country=country, platforms=["Google", "TikTok"], fetch=fetch)
                self.assertEqual([name for name, _ in result["links"]], ["Google", "TikTok"])
                self.assertIn(f"gl={country}", result["links"][0][1])
                self.assertEqual(result["products"], [])
        fetch.assert_not_called()

    def test_bing_rejects_unrelated_unsafe_untrusted_and_noneditorial_results(self):
        trusted = "https://tweakers.net/nieuws/12345/trends-voor-powerbanks.html"
        feed = rss(
            ("Trends voor magnetische powerbanks", trusted),
            ("Powerbank video XXX", "https://www.bright.nl/nieuws/12345/nsfw-powerbank.html"),
            ("Powerbank login", "https://login.microsoftonline.com/"),
            ("Powerbank bekijken", "https://tweakers.net/zoeken/"),
            ("Powerbank bekijken", "https://tweakers.net.evil.example/nieuws/42/powerbank.html"),
            ("Powerbank bekijken", "https://tweakers.net/nieuws/42/powerbank.html?next=https://elsewhere.example"),
            ("Nestlé opent fabriek", "https://tweakers.net/nieuws/42/nestle.html"),
            ("Magnetische powerbank", "https://tweakers.net/nieuws/42/redirect%2fpowerbank.html"),
        )
        fetch = Mock(return_value=Response(feed))
        result = self.search("magnetische powerbanks", category="gadgets", platforms=["Bing"], fetch=fetch)
        self.assertEqual([p["url"] for p in result["news"]], [trusted])
        self.assertEqual(result["trends"], result["news"])
        self.assertEqual(result["products"], [])
        params = fetch.call_args.kwargs["params"]
        self.assertEqual((params["mkt"], params["adlt"]), ("nl-NL", "strict"))
        self.assertIn("site:tweakers.net", params["q"])

    def test_unavailable_redirected_and_invalid_inputs(self):
        for fetch in (Mock(side_effect=requests.Timeout), Mock(return_value=Response(b"", 302)),
                      Mock(return_value=Response(b"invalid"))):
            with self.subTest(fetch=fetch):
                result = self.search("powerbank", category="gadgets", fetch=fetch)
                self.assertTrue(result["source_unavailable"])
                self.assertEqual(result["products"], [])
                self.assertEqual(result["suppliers"], [])
                self.assertEqual(result["news"], [])

        fetch = Mock()
        for options in ({"category": "unknown"}, {"country": "unknown"}, {"mode": "unknown"}, {"platforms": []}):
            with self.subTest(options=options):
                self.assertTrue(self.search("lamp", fetch=fetch, **options)["error"])
        self.assertEqual(self.search("XXX casino", fetch=fetch)["error"], EMPTY_RESULTS)
        self.assertTrue(self.search("", mode="product", category="gadgets", fetch=fetch)["error"])
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
