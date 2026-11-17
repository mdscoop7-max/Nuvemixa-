import glob
import json
import re
from pathlib import Path

import app as A

STANDALONE = re.compile(r"(?<![A-Za-z])TrendMix(?![A-Za-z])")


def test_rendered_storefront_has_no_old_brand():
    client = A.app.test_client()
    for path in ("/", "/shop", "/gadgets", "/gadgets/draadloze-oplader-3-in-1", "/smart-home", "/home-living",
                 "/lifestyle-sport", "/beauty-care", "/aanbiedingen", "/winkelwagen", "/over-nuvemixa", "/voorwaarden",
                 "/privacy", "/retouren"):
        assert not STANDALONE.search(client.get(path).get_data(as_text=True)), path


def test_product_data_and_ui_strings_use_new_brand():
    for f in glob.glob("products/*/products.json"):
        data = Path(f).read_text(encoding="utf-8")
        json.loads(data)
        assert not STANDALONE.search(data), f
    for f in ("static/app.js", "static/languages.js", "static/trendmix-english-labels.js", "build_catalog.py", "product_art.py"):
        assert not STANDALONE.search(Path(f).read_text(encoding="utf-8")), f


def test_demo_products_stay_labelled_as_demo():
    data = Path("products/home-living/products.json").read_text(encoding="utf-8")
    assert "voorlopig" in data.lower()  # demo-/voorlopig-aanduiding blijft staan tot echte producten bevestigd zijn


def test_mobile_overlay_fix_present():
    css = Path("static/nuvemixa-refresh.css").read_text(encoding="utf-8")
    assert ".mobile-sticky-cart{bottom:calc(92px" in css and ".tm-assist-fab{width:52px" in css
    assert "20261118-1" in Path("templates/base.html").read_text(encoding="utf-8")


def test_checkout_stays_in_test_mode_without_live_switch(monkeypatch):
    monkeypatch.delenv("NUVEMIXA_LIVE_ORDERS", raising=False)
    assert A.live_orders_enabled() is False
