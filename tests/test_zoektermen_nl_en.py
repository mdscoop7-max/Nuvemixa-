"""Nederlandse zoekwoorden → Engelse catalogustermen zonder AI (nv_search_terms + nv_research_intent)."""
import pytest

from nv_research_intent import index_query, infer_categories, matches, normalize, offer_match
from nv_search_terms import translate_word


@pytest.mark.parametrize("term,expected,category", [
    ("keukenorganizer", "kitchen organizer", "home-living"),
    ("automatische kattenvoerbak", "automatic cat feeder", "pets"),
    ("gezichtsreiniger", "facial cleanser", "beauty-care"),
    ("Bluetooth-speaker", "bluetooth speaker", "gadgets"),
    ("arganolie", "argan oil", "beauty-care"),
    ("slimme stekker", "smart plug", "smart-home"),
    ("hondenriem", "dog leash", "pets"),
    ("kattenkrabpaal", "cat scratching post", "pets"),
    ("kruidenrek", "spice rack", "home-living"),
    ("badkamerorganizer", "bathroom organizer", "home-living"),
    ("vaatwasborstel", "dish brush", "home-living"),
    ("bewegingssensor", "motion sensor", "smart-home"),
    ("lipbalsem", "lip balm", "beauty-care"),
    ("yogablok", "yoga block", "lifestyle-sport"),
    ("hondenspeelgoed", "dog toy", "pets"),
    ("waterdichte bluetooth speaker", "waterproof bluetooth speaker", "gadgets"),
    ("grote opbergmand", "large storage basket", "home-living"),
])
def test_dutch_terms_get_english_catalogue_query_and_category(term, expected, category):
    assert index_query(term) == expected
    assert category in infer_categories(term)


@pytest.mark.parametrize("word", [
    "doorbell", "bedroom", "cupboard", "bandage", "handbag", "organizer", "speaker", "kitchen", "powerbank",
    "smartwatch", "setbox", "sunglasses", "laptop", "onbekendwoord", "wand", "deur", "slot",
])
def test_english_and_unknown_words_are_never_guessed(word):
    # Een Engels woord of onbekende samenstelling blijft onvertaald; dubbelzinnige losse woorden ook.
    assert translate_word(word) == ""


def test_compound_translates_only_when_every_part_is_known():
    assert translate_word("hondenmand") == "dog basket"
    assert translate_word("hondenxyzmand") == ""


def test_category_comes_from_word_parts_not_from_substrings():
    # 'desk chair' bevat 'hair', maar een bureaustoel is geen beautyproduct.
    assert infer_categories("bureaustoel") == ("home-living",)
    assert infer_categories("zwarte bureaustoel") == ("home-living",)


def test_dutch_and_english_titles_match_the_same_search():
    assert offer_match("hondenriem", "Reflective Dog Leashes 1.5m")[0] == "exact"
    assert offer_match("hondenriem rood", "Dog Leash Red")[0] == "exact"
    assert offer_match("kruidenrek", "Bamboo Spice Rack Organizer")[0] == "exact"
    assert offer_match("kattenbak", "Self-cleaning Cat Litter Box")[0] == "exact"
    assert normalize("Rode Hondenriem") == "red dog leash"


def test_unrelated_products_still_do_not_match():
    assert offer_match("hondenriem", "Cat Scratching Post")[0] == ""
    assert offer_match("kruidenrek", "Wine Glass Set")[0] == ""
    assert not matches("koffiebekers", "Tea Pot Glass")


def test_plural_tolerance_only_widens_english_plurals():
    assert matches("dog leash", "dog leashes")
    assert matches("coffee cup", "Coffee Cups 4 pack")
    assert not matches("dog leash", "dog collar")
