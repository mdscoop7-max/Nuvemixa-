"""Offline regression coverage for category, source, article and supplier selection."""
from datetime import date
import json
from unittest.mock import Mock
import unittest

import requests

from nv_product_discovery import COUNTRIES, EMPTY_RESULTS, MODES, discover
from nv_research_sources import CJ_PRODUCT, syncee_product_details

CATEGORIES = {
    "gadgets": "Gadgets", "smart-home": "Smart Home", "beauty-care": "Beauty & Care",
    "home-living": "Home & Living", "lifestyle-sport": "Lifestyle & Sport",
}
TERM = "Magnetische powerbank 10000mAh"
SYNCEE_PRODUCT = "https://syncee.com/product/253317_83365_123/powerbank-magnetic-10000mah"


def item(title, handle, **overrides):
    return {"id": 123, "title": title, "handle": handle, "type": "",
            "url": f"/products/{handle}?_pos=1", **overrides}


def catalogue(*items):
    return json.dumps({"resources": {"results": {"products": items}}}).encode()


def syncee_card(title="Magnetic Power Bank 10000mAh"):
    return (
        '<app-product-card><a href="/supplier/253317/nne-living">NNE Living</a>'
        f'<a href="{SYNCEE_PRODUCT.removeprefix("https://syncee.com")}">'
        f'<div class="h5 title cursor-pointer">{title}</div></a></app-product-card>'
    ).encode()


def syncee_details(destinations):
    product_id = "253317_83365_123"
    body = {"ID": product_id, "SHIPPING": [{"locations": destinations, "minShippingDays": 4, "maxShippingDays": 7}],
            "SETTINGS": {"warehouseLocation": "Australia"}}
    state = {"1": {"u": "https://entry.syncee.com/syncee-product-service/api/v1/products/" + product_id, "b": body}}
    return ('<script id="ng-state" type="application/json">' + json.dumps(state) + "</script>").encode()


def editorial_card(url, title, summary, published=None):
    published = published or date.today().isoformat()
    return (
        f'<a href="{url}" class="article-link" aria-label="{title}">'
        f'<article><header>Published <time datetime="{published}T12:00:00Z">Today</time></header>'
        f'<p class="synopsis">{summary}</p></article></a>'
    )


class Response:
    def __init__(self, content=b"", status_code=200):
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

    def supplier_fetch(self, url, **options):
        if "search/suggest.json" in url:
            return Response(catalogue(
                item("Magnetic Power Bank 10000mAh", "magnetic-power-bank-10000", type="Power Bank"),
                item("Magnetic Wireless Power Bank 10000 mAh", "wireless-power-bank-10000", type="Power Bank"),
                item("Magnetic Power Bank 5000mAh", "magnetic-power-bank-5000"),
                item("XXX Magnetic Power Bank 10000mAh", "adult-video"),
                item("Magnetic Power Bank 10000mAh", "fake", url="https://login.microsoft.com/"),
                item("Magnetic Power Bank 10000mAh", "not-a-product", url="/pages/search"),
            ))
        if "catalogsearch/result/" in url:
            return Response(b'<a class="product-item-info" href="https://www.hama.com/nl/nl/magnetic-power-bank-12345678"><strong class="product name product-item-name">Magnetic Power Bank 10000mAh</strong></a>')
        if "hama.com" in url:
            return Response(status_code=404)
        if "syncee.com/collections" in url:
            return Response(syncee_card() * 3)
        if url == SYNCEE_PRODUCT:
            return Response(syncee_details(["AU"]))
        raise AssertionError(url)

    def test_product_uses_verified_catalogue_and_strict_capacity_matching(self):
        fetch = Mock(side_effect=self.supplier_fetch)
        r = self.search(TERM, category="gadgets", mode="product", platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual(len(r["products"]), 5)
        self.assertNotIn("NNE Living", [c["name"] for c in r["suppliers"]])
        self.assertTrue(all("10000" in p["title"] for p in r["products"]))
        self.assertFalse(any("stock" in p or "price" in p for p in r["products"]))
        store_calls = [c for c in fetch.call_args_list if "/search/suggest.json" in c.args[0]]
        self.assertEqual(len(store_calls), 2)
        for c in store_calls:
            self.assertEqual(c.kwargs["params"]["q"], "magnetic power bank 10000mah")
            self.assertFalse(c.kwargs["allow_redirects"])

    def test_category_and_market_determine_provider(self):
        valid = item("SwitchBot RGBICWW Floor Lamp", "switchbot-rgbicww-floor-lamp", type="LIGHTING")
        fetch = Mock(return_value=Response(catalogue(valid, item("Table Lamp", "table-lamp"))))
        result = self.search("lamp", category="smart-home", mode="niche",
                             platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual([p["title"] for p in result["products"]], [valid["title"]])
        self.assertFalse(any("ugreen" in c.args[0] for c in fetch.call_args_list))

        fetch.reset_mock()
        fetch.return_value = Response(catalogue(item("Security Camera", "security-camera")))
        result = self.search("", category="smart-home", mode="niche", country="US",
                             platforms=["Productcatalogi"], fetch=fetch)
        self.assertEqual(result["country_name"], "Verenigde Staten")
        self.assertIn("https://us.eufy.com/search/suggest.json", [c.args[0] for c in fetch.call_args_list])
        self.assertTrue(result["products"])

        fetch.reset_mock()
        fetch.return_value = Response(catalogue(valid, item("Table Lamp", "table-lamp")))
        result = self.search("lamp", category="shop", mode="products", platforms=["Productcatalogi"], fetch=fetch)
        storefronts = [c.args[0] for c in fetch.call_args_list if "/search/suggest.json" in c.args[0]]
        self.assertGreater(len(storefronts), 5)
        self.assertTrue(result["products"])

    def test_unique_company_count_and_region_filters(self):
        expected = {
            "all": {"UGREEN", "Baseus", "Hama B.V.", "CJdropshipping"},
            "eu": {"Hama B.V."},
            "international": {"UGREEN", "Baseus", "CJdropshipping"},
            "dropship": {"CJdropshipping"},
            "trade": {"UGREEN", "Baseus", "Hama B.V."},
        }
        for scope, names in expected.items():
            with self.subTest(scope=scope):
                result = self.search(TERM, category="gadgets", mode="suppliers", supplier_filter=scope,
                                     platforms=["Productcatalogi"], fetch=self.supplier_fetch)
                self.assertEqual({c["name"] for c in result["suppliers"]}, names)
                self.assertEqual(len(result["suppliers"]), len(names))
                self.assertEqual(result["products"], [])
                if "UGREEN" in names:
                    self.assertEqual(next(c for c in result["suppliers"] if c["name"] == "UGREEN")["product_count"], 2)

    def test_shipping_for_the_actual_item_controls_dropship_results(self):
        for country, names in (("NL", {"CJdropshipping"}), ("AU", {"CJdropshipping", "NNE Living"})):
            result = self.search(TERM, category="gadgets", mode="dropship", country=country,
                                 platforms=["Productcatalogi"], fetch=self.supplier_fetch)
            self.assertEqual({c["name"] for c in result["suppliers"]}, names)
            self.assertEqual(result["preferred_tab"], "suppliers")
            cj = next(c for c in result["suppliers"] if c["name"] == "CJdropshipping")
            self.assertEqual(cj["products"][0]["url"], CJ_PRODUCT)
            self.assertEqual(cj["shipping"], "Niet bevestigd")
            if country == "AU":
                nne = next(c for c in result["suppliers"] if c["name"] == "NNE Living")
                self.assertEqual(nne["product_count"], 1)
                self.assertIn("Geverifieerd", nne["shipping"])
                self.assertIn("4–7", nne["products"][0]["lead_time"])
        self.assertEqual(syncee_product_details(None, SYNCEE_PRODUCT, "NL", lambda *a, **k: syncee_details(["EU"])),
                         {"warehouse": "Australia"})

    def test_all_eight_search_modes_select_a_result_type(self):
        url = "https://www.techradar.com/phones/phone-accessories/magnetic-power-bank-news"
        feed = editorial_card(url, "New magnetic power bank 10000mAh launches", "Magnetic power bank").encode()
        def fetch(url, **kwargs):
            if url == "https://www.techradar.com/search":
                return Response(feed)
            if url == "https://9to5mac.com/":
                return Response(b"<rss><channel/></rss>")
            return self.supplier_fetch(url, **kwargs)
        for mode in MODES:
            with self.subTest(mode=mode):
                result = self.search(TERM, category="gadgets", mode=mode, fetch=fetch)
                if mode in {"suppliers", "dropship", "wholesale"}:
                    self.assertTrue(result["suppliers"])
                    self.assertEqual(result["news"], [])
                    self.assertEqual(result["products"], [])
                elif mode == "news":
                    self.assertEqual(result["preferred_tab"], "news")
                    self.assertTrue(result["news"])
                    self.assertEqual(result["suppliers"], [])
                    self.assertEqual(result["products"], [])
                else:
                    self.assertTrue(result["products"])
            if mode == "trends":
                self.assertTrue(result["trends"])
                self.assertEqual(result["preferred_tab"], "trends")

    def test_publications_require_source_subject_and_dates(self):
        base = "https://www.techradar.com/phones/phone-accessories/"
        title = "New magnetic power bank 10000mAh"
        feed = "".join([
            editorial_card(base + "deliberate-powerbank", title, "An independent story"),
            editorial_card(base + "varied-powerbank", "A magnetic power bank recall", "10000mAh lithium battery"),
            editorial_card(base + "nestle", "Nestlé opens a factory", "magnetic power bank 10000mAh as a giveaway"),
            editorial_card(base + "login", "Microsoft login for " + title, "sign in"),
            editorial_card(base + "unsafe", "XXX video for " + title, "unsafe"),
            editorial_card(base + "redirect?next=https://example.com/", title, "a story"),
            editorial_card("https://example.com/phones/accessories", title, "wrong publisher"),
            editorial_card(base + "future", title, "story", "2099-02-01"),
        ]).encode()
        fetch = Mock(side_effect=lambda url, **kwargs: Response(feed if "techradar" in url else b"<rss><channel/></rss>"))
        r = self.search(TERM, category="gadgets", mode="trends", country="NL", platforms=["Publicaties"], fetch=fetch)
        self.assertEqual([x["url"] for x in r["news"]], [base + "deliberate-powerbank", base + "varied-powerbank"])
        self.assertEqual(len(r["trends"]), 2)
        self.assertEqual(r["news"][1]["kind"], "Veiligheid en terugroepacties")
        self.assertEqual(r["news"][0]["date"], date.today().isoformat())
        self.assertTrue(all(c.kwargs["headers"]["Accept-Language"] == "nl-NL" for c in fetch.call_args_list))

    def test_manual_platforms_and_invalid_input_do_not_request_sources(self):
        fetch = Mock()
        for country in COUNTRIES:
            result = self.search("lamp", country=country, platforms=["Google", "TikTok"], fetch=fetch)
            self.assertEqual([name for name, _ in result["links"]], ["Google", "TikTok"])
            self.assertIn(f"gl={country}", result["links"][0][1])
            self.assertEqual(result["products"], [])
        for kwargs in ({"category": "unknown"}, {"country": "unknown"}, {"mode": "unknown"},
                       {"platforms": []}, {"supplier_filter": "unknown"}):
            self.assertTrue(self.search("lamp", fetch=fetch, **kwargs)["error"])
        self.assertEqual(self.search("XXX casino", fetch=fetch)["error"], EMPTY_RESULTS)
        fetch.assert_not_called()

    def test_provider_failure_keeps_empty_state(self):
        fetch = Mock(side_effect=requests.Timeout)
        r = self.search("unfindable-term", category="gadgets", fetch=fetch)
        self.assertTrue(r["source_unavailable"])
        self.assertEqual(r["products"], [])
        self.assertEqual(r["suppliers"], [])
        self.assertEqual(r["news"], [])
