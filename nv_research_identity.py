"""Supplier identity and offer keys. Names alone cannot identify a company."""
import re
import unicodedata
from urllib.parse import urlsplit


def canonical_name(name):
    name = unicodedata.normalize("NFKC", name).casefold()
    return " ".join(re.findall(r"[^\W_]+", name))


def company_key(profile):
    if profile.get("registration"):
        jurisdiction, number = profile["registration"]
        return ("registered", jurisdiction.upper(), re.sub(r"[^A-Z0-9]+", "", number.upper()))
    if profile.get("identity"):
        return ("source", profile["identity"])
    # Keep legal suffixes and the provider path. A shared domain can serve
    # different companies, especially a marketplace or a group website.
    url = urlsplit(profile["website"])
    return ("listed", url.hostname, url.path.rstrip("/"), profile.get("origin"), canonical_name(profile["name"]))


def offer_key(item):
    # GTINs identify an exact product variant. Item IDs are scoped to their source.
    if item.get("gtin"):
        return ("gtin", item["gtin"])
    if item.get("catalogue_id"):
        return ("catalogue", *item["catalogue_id"])
    url = urlsplit(item["url"])
    return ("url", url.hostname, url.path.rstrip("/"), url.query)


def approved_catalogue_identity(name):
    # These regional stores are paired in the catalogue configuration with the
    # same published business programme. Hama's separate national entities use
    # their own keys in the Hama adapter.
    names = {alias: identity for identity, variants in {
        "ugreen": ("ugreen", "ugreen eu", "ugreen us"),
        "baseus": ("baseus", "baseus eu", "baseus us"),
        "xtorm": ("xtorm", "xtorm eu"),
        "nedis": ("nedis", "nedis b v"),
        "eufy": ("eufy", "eufy europe", "eufy us"),
        "ferm-living": ("ferm living",),
        "manduka-europe": ("manduka", "manduka europe"),
    }.items() for alias in variants}
    return names.get(canonical_name(name))
