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
            if raw.get("hidden") and not raw.get("extra"):
                result.append(dict(raw))
                continue
            if not raw.get("id") or not raw.get("name"):
                continue

            item = dict(raw)
            item["extra"] = raw.get("extra", True)
            item["id"] = ("extra-" if item["extra"] else "") + str(raw["id"])
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
            _cache_until = monotonic()  # Prices and offers always come from the current permanent source.
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
                def slug(row):
                    import re
                    value = str(row.get('name', '')).lower().replace('+', ' plus ').replace('&', ' en ')
                    return row.get('slug') or re.sub(r'[-\s]+', '-', re.sub(r'[^a-z0-9\s-]', '', value).strip())
                position = next((i for i, row in enumerate(catalog[category]) if slug(row) == item['slug']), None)
                if item.get('hidden'):
                    if position is not None:
                        catalog[category].pop(position)
                elif position is None:
                    if item.get('extra'):
                        catalog[category].append(item)
                else:
                    original = catalog[category][position]
                    # Keep the supplied base ID and all fields not present in the public edit.
                    catalog[category][position] = {**original, **item, 'id': original.get('id', item['id'])}

        g.nv_public_products = catalog

    return g.nv_public_products
