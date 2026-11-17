"""Regressies uit de live test van 18-11-2026 (echte resultaten van trendmix.onrender.com)."""
import pytest

from nv_research_intent import offer_match
from nv_product_discovery import coverage_note

ACCEPT = [
    ("Draadloze oordopjes", "Baseus Bowie MC2 Open-Ear True Wireless Earbud"),
    ("Bluetooth speaker", "QCY SP2 IP67 Bluetooth Speaker with RGB Backlight"),
    ("Gezichtsreiniger", "Gentle Facial Cleanser gel"),
    ("Keukenorganizer", "Bamboo Kitchen Organizer"),
    ("Opbergrek", "Metal storage rack 4 tier"),
    ("Fitness elastieken", "Resistance Bands Set 5 pcs"),
    ("Automatische kattenvoerbak", "Automatic Cat Feeder 4L"),
    ("Drinkfontein voor katten", "Cat Water Fountain 2L"),
    ("Slimme LED-verlichting", "SmartLife LED Sfeerverlichting Strip Wi-Fi"),
    ("Elektrische gezichtsborstel", "Sonic Silicone Facial Cleansing Brush"),
]
REJECT = [
    ("Draadloze oordopjes", "LINQ 3in1 Qi2 Draadloze oplader", "compatible with earbuds"),
    ("Bluetooth speaker", "65W Fast Travel Charger Kit", "charge your speaker"),
    ("Bluetooth speaker", "Rockbros Velcro Bike Strap for Bluetooth Speaker", ""),
    ("Yogamat", "Yoga Mat Cleanser", ""),
]


@pytest.mark.parametrize("term,title", ACCEPT)
def test_nederlandse_zoektermen_vinden_de_engelse_productnaam(term, title):
    assert offer_match(term, title, "")[0] == "exact"


@pytest.mark.parametrize("term,title,body", REJECT)
def test_hoofdwoord_moet_in_de_titel_staan_en_accessoires_vallen_af(term, title, body):
    assert offer_match(term, title, body)[0] == ""


def test_dekkingsmelding_voor_huisdieren_en_niet_voor_andere_producten():
    assert "Huisdierproducten" in coverage_note("Automatische kattenvoerbak")
    assert coverage_note("Yogamat") == ""
