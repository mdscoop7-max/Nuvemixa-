"""Vertaling, modifiers, categorieherkenning, vermogen en foutredenen (nagebootste bronnen)."""
from unittest.mock import Mock

import pytest

from nv_product_discovery import discover
from nv_research_intent import (candidate_queries, index_query, infer_categories, offer_match)
from test_nv_product_discovery import CATEGORIES, Response, catalogue, item

BEAUTY = {"Elektrische gezichtsreinigingsborstel", "LED-make-upspiegel met verlichting", "Draadloze haartrimmer USB-C",
          "Automatische zeepdispenser met sensor", "Elektrische nagelvijlset", "Draadloze stijltang",
          "Elektrische gezichtsmassager", "Ultrasone sieradenreiniger", "Waterflosser voor mondverzorging",
          "Elektrische hoofdhuidmassageborstel"}
SPORT = {"Antislip yogamat", "Fitnessweerstandsbanden set", "RVS drinkfles 750 ml", "Slimme springtouwteller",
         "Verstelbare dumbbells", "Opvouwbare sporttas", "Massagegun voor spiermassage",
         "Digitale bagageweegschaal", "Hardlooptelefoonhouder voor de arm", "Fitnessmat met draagriem"}


@pytest.mark.parametrize("term", sorted(BEAUTY))
def test_beauty_products_are_recognised(term):
    assert "beauty-care" in infer_categories(term)


@pytest.mark.parametrize("term", sorted(SPORT))
def test_sport_products_are_recognised(term):
    assert "lifestyle-sport" in infer_categories(term)


@pytest.mark.parametrize("term,expected", [
    ("RVS drinkfles 750 ml", "water bottle 750ml"),
    ("Elektrische nagelvijlset", "nail file set"),
    ("Waterflosser voor mondverzorging", "water flosser"),
    ("Draadloze haartrimmer USB-C", "hair trimmer"),
    ("Zelfklevende kabelorganizer voor bureau", "cable organizer"),
])
def test_dutch_terms_are_translated_for_search(term, expected):
    assert expected in index_query(term) or any(expected in q for q in candidate_queries(term))
    assert "voor" not in index_query(term).split()


def test_modifier_is_not_a_brand_but_stays_unverified():
    level, missing = offer_match("Antislip yogamat", "Yoga Mat Pro", "Natural rubber")
    assert level == "similar" and "antislip" in missing
    assert offer_match("Antislip yogamat", "Yoga Mat Pro", "Non-slip grip surface") == ("exact", ())


def test_wattage_and_gan_are_never_silently_confirmed():
    assert offer_match("USB-C snellader 65W GaN", "UGREEN 65W GaN USB-C Fast Charger") == ("exact", ())
    level, missing = offer_match("USB-C snellader 65W GaN", "UGREEN 30W USB-C Fast Charger")
    assert level == "similar" and "65 W" in missing


def test_capacity_and_usbc_checks_remain_strict():
    assert offer_match("Magnetische powerbank 10.000 mAh USB-C", "Magnetic Power Bank 5000mAh USB-C")[0] == ""
    level, missing = offer_match("Draadloze LED tafellamp oplaadbaar USB-C", "Rechargeable LED Table Lamp")
    assert level == "similar" and "USB-C" in missing


def test_unrelated_object_is_rejected():
    assert offer_match("RVS drinkfles 750 ml", "Yoga Mat Pro", "Natural rubber")[0] == ""


def shop(*items):
    def fetch(url, **options):
        if "search/suggest.json" in url and "manduka" in url:
            return Response(catalogue(*items))
        return Response(catalogue())
    return Mock(side_effect=fetch)


def test_similar_product_is_listed_as_comparable_not_exact():
    r = discover("Antislip yogamat", categories=CATEGORIES, mode="product", platforms=["Productcatalogi"],
                 fetch=shop(item("Manduka PRO Yoga Mat", "pro-yoga-mat", type="Yoga Mat")))
    assert not r["products"]
    assert r["alternatives"] and "antislip" in r["alternatives"][0]["match_missing"]


def test_source_failures_show_reasons():
    def fetch(url, **options):
        raise OSError("offline")
    r = discover("yogamat", categories=CATEGORIES, mode="product", platforms=["Productcatalogi"], fetch=fetch)
    assert r["unavailable_sources"] and set(r["unavailable_reasons"]) == set(r["unavailable_sources"])
    assert all(r["unavailable_reasons"].values())
