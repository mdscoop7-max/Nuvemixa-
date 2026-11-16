"""Offline tests: Viral Product Finder, Internationaal marktonderzoek, rollen en AI Productonderzoek."""
from unittest.mock import Mock

import pytest

import nv_market_search as market
from nv_product_discovery import discover, supplier_role
from test_nv_product_discovery import CATEGORIES, Response, catalogue, item
from test_system_check import administrator  # noqa: F401  (fixture)


def store_fetch(*items):
    def fetch(url, **options):
        if "search/suggest.json" in url:
            return Response(catalogue(*items))
        return Response(b"")
    return Mock(side_effect=fetch)


POWERBANK = [item("Magnetic Power Bank 10000mAh USB-C", "magnetic-power-bank-10000", type="Power Bank")]


def view(kind, fetch, **args):
    return market.search_view(kind, CATEGORIES, {"mrun": "1", **args}, fetch=fetch)


def test_form_without_run_makes_no_request():
    fetch = store_fetch()
    result = market.search_view("viral", CATEGORIES, {}, fetch=fetch)
    assert not result["ran"] and not fetch.called


def test_empty_query_gives_message():
    assert "Vul een product" in view("internationaal", store_fetch(), mq="  ")["error"]


def test_invalid_filters_fall_back():
    form = market.parse("viral", {"mland": "XX", "mregio": "mars", "mtype": "x", "mcat": "nope"}, CATEGORIES)
    assert (form["country"], form["region"], form["supplier_type"]) == ("NL", "all", "all")


@pytest.mark.parametrize("term", ["Magnetic Power Bank 10000mAh USB-C", "magnetische powerbank 10.000 mAh USB-C"])
def test_international_free_product_finds_products(term):
    result = view("internationaal", store_fetch(*POWERBANK), mq=term, mcat="gadgets")
    assert result["ran"] and not result["error"]
    assert result["opportunities"] is not None and result["risks"]
    assert "niet getoond of geschat" in result["price_note"]
    assert result["products"], "bevestigde productmatch verwacht"


def test_no_result_product_is_honest():
    result = view("viral", store_fetch(), mq="zzqx unobtainium gadget", mcat="gadgets")
    assert result["ran"] and not result["products"]
    assert "Geen bevestigde producten" in result["empty_message"]


@pytest.mark.parametrize("country", ["NL", "DE", "AU"])
def test_countries_do_not_crash(country):
    result = view("internationaal", store_fetch(*POWERBANK), mq="Magnetic Power Bank 10000mAh", mland=country, mcat="gadgets")
    assert result["ran"] and not result["error"]


def test_filters_keep_only_matching_suppliers():
    company = {"region": "eu", "role": "Groothandel", "dropshipping": None, "shipping_nl": "Bevestigd", "shipping": "x"}
    other = {"region": "international", "role": "Fabrikant of merk", "dropshipping": True, "shipping_nl": "Niet bevestigd", "shipping": "x"}
    form = market.parse("viral", {"mregio": "eu"}, CATEGORIES)
    assert market.filter_suppliers([company, other], form) == [company]
    form = market.parse("viral", {"mtype": "dropship"}, CATEGORIES)
    assert market.filter_suppliers([company, other], form) == [other]
    form = market.parse("viral", {"mnl": "1"}, CATEGORIES)
    assert market.filter_suppliers([company, other], form) == [company]


def test_manufacturer_is_not_automatically_dropshipper():
    assert supplier_role({"kind": "Fabrikant of merk", "name": "X", "dropshipping": None}) == "Fabrikant of merk"
    assert supplier_role({"kind": "Fabrikant of merk", "name": "X", "dropshipping": None}) != "Dropshippingleverancier"
    assert supplier_role({"kind": "Groothandel", "name": "Y", "dropshipping": None}) == "Groothandel"


def test_unconfirmed_webshop_lead_is_labelled():
    r = discover("Magnetic Power Bank 10000mAh USB-C", categories=CATEGORIES, category="gadgets", mode="product",
                 platforms=["Productcatalogi"], fetch=store_fetch(*POWERBANK))
    assert r["products"]
    for company in r["suppliers"]:
        assert company["role"]
        if company["business"] is not True:
            assert company["dropshipping"] is not True


@pytest.mark.parametrize("term,cat", [("LED tafellamp", "home-living"), ("yogamat", "lifestyle-sport"),
                                      ("slimme beveiligingscamera", "smart-home")])
def test_ai_research_other_products_no_crash(term, cat):
    r = discover(term, categories=CATEGORIES, category=cat, mode="product", platforms=["Productcatalogi"], fetch=store_fetch())
    assert "products" in r and "suppliers" in r


@pytest.fixture
def offline(monkeypatch):
    real = market.discover
    fetch = store_fetch(*POWERBANK)
    monkeypatch.setattr(market, "discover", lambda *a, **k: real(*a, **{**k, "fetch": fetch}))


@pytest.mark.parametrize("section,button", [("viral", "Zoek viral producten"), ("internationaal", "Start internationaal onderzoek")])
def test_dashboard_pages_render(administrator, offline, section, button):
    page = administrator.get(f"/dashboard?section={section}")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert button in text and "Zoek producten in beheer" not in text
    run = administrator.get(f"/dashboard?section={section}&mq=Magnetic+Power+Bank+10000mAh&mcat=gadgets&mrun=1")
    assert run.status_code == 200
    assert "nv-market-results" in run.get_data(as_text=True)
    bad = administrator.get(f"/dashboard?section={section}&mq=x&mland=ZZ&mregio=zz&mrun=1")
    assert bad.status_code == 200


def test_top_search_only_on_products(administrator):
    assert "Zoek producten in beheer" in administrator.get("/dashboard?section=producten").get_data(as_text=True)
    for section in ("onderzoek", "viral", "internationaal"):
        assert "Zoek producten in beheer" not in administrator.get(f"/dashboard?section={section}").get_data(as_text=True)
