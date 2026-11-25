import json
import logging
from urllib.request import urlopen
from urllib.parse import urljoin, urlsplit

BASE_URL = "https://trendmix.onrender.com/"
FEED_URL = BASE_URL + "api/public/catalog"


def image_url(value):
    if not isinstance(value, str) or not value:
        return ""
    url = urljoin(BASE_URL, value)
    if urlsplit(url).scheme != "https":
        return ""
    return url


def _fetch_extra_products():
    try:
        with urlopen(FEED_URL, timeout=5) as response:
            data = json.loads(response.read(4_000_000))

        if data.get("version") != 1:
            return []

        result = []
        for raw in data["products"]:
            if not raw.get("id") or not raw.get("name"):
                continue

            item = dict(raw)
            item["id"] = "extra-" + str(raw["id"])
            item["extra"] = True
            item["price"] = float(raw["price"])
            item["image"] = image_url(raw.get("image"))
            item["images"] = [
                url for value in raw.get("images", [])
                if (url := image_url(value))
            ]
            result.append(item)

        return result

    except Exception:
        logging.getLogger(__name__).warning(
            "NUVEMIXA productfeed niet beschikbaar"
        )
        return []
from time import monotonic
from threading import Lock
from copy import deepcopy

_cache_lock = Lock()
_cache_products = []
_cache_until = 0.0

def fetch_extra_products():
    global _cache_products, _cache_until
    with _cache_lock:
        if monotonic() >= _cache_until:
            _cache_products = _fetch_extra_products()
            _cache_until = monotonic() + 30
        return deepcopy(_cache_products)

from flask import g, has_request_context


def merged_catalog(base):
    if not has_request_context():
        return base

    if "nv_public_products" not in g:
        catalog = {
            key: list(items)
            for key, items in base.items()
        }

        for item in fetch_extra_products():
            category = item.get("category_slug")
            if category in catalog:
                catalog[category].append(item)

        g.nv_public_products = catalog

    return g.nv_public_products