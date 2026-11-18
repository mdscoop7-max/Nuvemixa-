from unittest.mock import Mock
import json

import pytest
import requests

from nv_product_discovery import discover, product_groups
from nv_research_intent import candidate_queries, offer_match
from test_nv_product_discovery import CATEGORIES, Response, catalogue, item


@pytest.mark.parametrize(("query", "english"), (
    ("Pure Argan Huidolie - 100ml", "argan oil"),
    ("Elektrische siliconen gezichtsreinigingsborstel met USB-C", "facial cleansing brush"),
    ("Arganolie Puur & Koudgeperst", "cold pressed"),
    ("WiFi slimme stekker 16A met energiemeter", "smart plug"),
    ("Weerstandsbanden fitness set", "resistance bands"),
    ("Draadloze LED tafellamp oplaadbaar USB-C", "rechargeable table lamp"),
    ("NIVEA Soft Hydraterende Crème 200 ml", "nivea soft"),
))
def test_domain_variants(query, english):
    variants = candidate_queries(query)
    assert variants[0] == query
    assert any(english in variant.casefold() for variant in variants)


def test_security_camera_search_excludes_replicas_unless_requested():
    for query in ("security camera", "beveiligingscamera"):
        for title in ("Dummy Beveiligingscamera Bullet - IP44", "Dummy Security Camera",
                      "Fake Security Camera", "Decoy Security Camera"):
            assert offer_match(query, title)[0] == ""
        assert offer_match(query, "Outdoor Wireless Security Camera")[0] == "exact"
    assert offer_match("dummy security camera", "Dummy Security Camera")[0] == "exact"


def test_sizes_brand_formula_and_connector_stay_distinct():
    query = "NIVEA Soft Hydraterende Crème 200 ml"
    assert offer_match(query, "Nivea Soft Moisturiser 200ml")[0] == "exact"
    assert offer_match(query, "OtherBrand Soft Moisturiser 200ml", "Like Nivea")[0] == ""
    assert offer_match(query, "Nivea Intensive Soft Moisturiser 200ml")[0] == ""
    assert offer_match(query, "Nivea Soft Daily UV SPF15 200ml Cream")[0] == "similar"
    assert offer_match(query, "Nivea Soft Moisturiser 75ml", "Also sold in 200 ml")[0] == "similar"
    assert offer_match("WiFi slimme stekker 16A met energiemeter", "Smart Plug Wi-Fi, 10A",
                       "Energy monitoring. Other model: 16 A")[0] == "similar"
    assert offer_match("WiFi slimme stekker 16A met energiemeter", "Smart Plug Wi-Fi / Zigbee, 16A",
                       "Energy monitoring", "EU Wi-Fi")[0] == "exact"
    assert offer_match("WiFi slimme stekker 16A met energiemeter", "Smart Plug Zigbee, 16A",
                       "Compatible with a Wi-Fi bridge. Energy monitoring")[0] == ""
    assert offer_match("Elektrische siliconen gezichtsreinigingsborstel met USB-C",
                       "Sonic Silicone Facial Cleansing Brush", "Rechargeable by USB-C")[0] == "exact"
    assert offer_match("Elektrische siliconen gezichtsreinigingsborstel met USB-C",
                       "Sonic Silicone Facial Cleansing Brush", "USB-C cable optional. Internal port is micro-USB.")[0] == "similar"
    assert offer_match("Weerstandsbanden fitness set", "Resistance Band 30 kg",
                       "See our resistance bands set")[0] == "similar"


def test_fallback_checks_selected_variant_and_reports_catalogue_timeouts():
    oil = item("Argan Oil (100% Pure & Cold Pressed)", "argan-oil", body="Cosmetic oil for the skin")
    def fetch(url, **options):
        if "/collections/" in url:
            return Response()
        if url.startswith("https://www.cocunat.com/"):
            raise requests.Timeout()
        if url == "https://pureoil.nl/products/argan-oil.js":
            return Response(json.dumps({"id": oil["id"], "variants": [
                {"id": 45, "title": "50ml"},
                {"id": 46, "title": "100ml"},
            ]}).encode())
        if url.startswith("https://pureoil.nl/"):
            return Response(catalogue(oil) if options["params"]["q"] == "argan oil" else catalogue())
        if "/wp-json/" in url:
            return Response(b"[]")
        return Response(catalogue())
    result = discover("Pure Argan Huidolie - 100ml", category="beauty-care", categories=CATEGORIES,
                      platforms=["Productcatalogi"], mode="products", fetch=Mock(side_effect=fetch))
    assert [p["url"] for p in result["products"]] == ["https://pureoil.nl/products/argan-oil?variant=46"]
    assert "Cocunat" in result["unavailable_sources"]
    assert any(a.get("error") == "time-out" for a in result["search_attempts"])
    assert [a["raw"] for a in result["search_attempts"] if a["source"] == "Pureoil"][-1] == 1
    assert any(a["source"] == "Pureoil" and a["raw"] == 0 for a in result["search_attempts"])


def test_similar_results_are_separate_from_exact_products_and_suppliers():
    lamp = item("LED Table Lamp", "led-table-lamp", body="Rechargeable by micro USB. Cordless without cable.")
    def fetch(url, **options):
        if "/collections/" in url:
            return Response()
        return Response(catalogue(lamp) if "fermliving.com" in url else catalogue())
    result = discover("Draadloze LED tafellamp oplaadbaar USB-C", category="home-living", categories=CATEGORIES,
                      platforms=["Productcatalogi"], mode="products", fetch=Mock(side_effect=fetch))
    assert result["products"] == result["suppliers"] == []
    assert [p["match_missing"] for p in result["alternatives"]] == [("USB-C",)]


def test_barcode_dedup_keeps_separate_offer_links_and_similar_titles_remain_separate():
    a = {"source": "EU store", "title": "Argan Oil", "url": "https://eu.example/oil", "gtin": "04006381333931"}
    b = {**a, "source": "International store", "url": "https://intl.example/oil"}
    c = {**a, "url": "https://eu.example/other-oil", "gtin": None}
    grouped = product_groups([a, b, c, a])
    assert len(grouped) == 2
    assert grouped[0]["other_sources"] == [{"name": b["source"], "url": b["url"]}]


def test_public_woocommerce_catalogue_accepts_only_its_own_product_links():
    slug = "arganolie-100ml"
    accepted_url = f"https://aurgan.nl/product/{slug}/"
    body = {"id": 10, "name": "Pure cosmetische arganolie &ndash; 100 ml", "slug": slug,
            "permalink": accepted_url, "description": "Koudgeperst."}

    def fetch(url, **options):
        if "/wp-json/" in url:
            return Response(json.dumps([body, {**body, "id": 11,
                                              "permalink": f"https://other.example/product/{slug}/"}]).encode())
        if "/collections/" in url:
            return Response()
        return Response(catalogue())

    result = discover("Pure Argan Huidolie - 100ml", category="beauty-care", categories=CATEGORIES,
                      platforms=["Productcatalogi"], mode="products", fetch=Mock(side_effect=fetch))
    assert [p["url"] for p in result["products"]] == [accepted_url]
    attempt = next(a for a in result["search_attempts"] if a["source"] == "Aurgan")
    assert attempt["raw"] == 2 and attempt["exact"] == 1


def test_live_findings_speaker_parts_and_cleanser_oils_are_excluded():
    rejected = [("Bluetooth-speaker", "Travel charger for bluetooth speaker"),
                ("bluetooth speaker", "Bluetooth speaker mounting strap"),
                ("bluetooth speaker", "Reislader voor JBL bluetooth speaker"),
                ("Facial cleanser", "Facial cleansing oil 100ml"),
                ("Facial cleanser", "Facial cleansing brush silicone"),
                ("Security camera", "Dummy security camera with LED")]
    for query, title in rejected:
        assert offer_match(query, title)[0] == "", (query, title)
    kept = [("bluetooth speaker", "Portable Bluetooth Speaker 10W"),
            ("bluetooth speaker", "Bluetooth speaker with carrying strap"),
            ("facial cleanser", "CeraVe Hydrating Facial Cleanser"),
            ("Gezichtsreiniger", "Facial cleanser gel"),
            ("Automatische kattenvoerbak", "Automatic cat feeder 4L"),
            ("Keukenorganizer", "Kitchen organizer rack"),
            ("power bank 10000mah", "Power bank charger 10000mAh")]
    for query, title in kept:
        assert offer_match(query, title)[0] == "exact", (query, title)
