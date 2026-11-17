"""De productzoekfunctie werkt voor alle vijf webshopcategorieën, niet alleen voor USB-opladers.
Alle leveranciersantwoorden zijn nagebootste TESTDATA (tests/zoek_fixture.py); er wordt niets echt benaderd."""
import pytest
from test_system_check import administrator  # noqa: F401

import app as dashboard
from nv_product_discovery import discover
from nv_research_intent import infer_categories
from zoek_fixture import maak_fetch

CATS = {slug: meta["name"] for slug, meta in dashboard.BASE_CATEGORIES.items()}

# (categorie, zoekterm, verwachte titel-fragment of None = bewust geen bevestigde match)
OPDRACHTEN = [
    ("gadgets", "Sony WH-1000XM5 koptelefoon", "WH-1000XM5"),
    ("gadgets", "Anker Soundcore Bluetooth speaker", "Soundcore"),
    ("gadgets", "Apple AirTag 4-pack", None),
    ("beauty-care", "NIVEA Soft Hydraterende Crème 200 ml", "NIVEA"),
    ("beauty-care", "Philips OneBlade scheerapparaat", "OneBlade"),
    ("beauty-care", "The Ordinary Niacinamide serum", "Niacinamide"),
    ("lifestyle-sport", "Decathlon yogamat 8 mm", "Yogamat"),
    ("lifestyle-sport", "Nike Dri-FIT hardloopshirt", "Dri-FIT"),
    ("lifestyle-sport", "Bidon 750 ml roestvrij staal", "Bidon"),
    ("home-living", "Bamboe opbergbox met deksel", "opbergbox"),
    ("home-living", "Philips Hue woonkamer tafellamp", "tafellamp"),
    ("home-living", "Velvet sierkussen 45x45", "sierkussen"),
    ("smart-home", "Ring Video Doorbell", "Doorbell"),
    ("smart-home", "TP-Link Tapo C200 camera", "Tapo"),
    ("smart-home", "Philips Hue slimme lamp E27", None),
]


@pytest.mark.parametrize("categorie,term,verwacht", OPDRACHTEN)
def test_zoekopdracht_per_categorie(categorie, term, verwacht):
    r = discover(term, "NL", "products", ["Productcatalogi"], maak_fetch(), category=categorie, categories=CATS)
    assert r["error"] is None
    titels = [p["title"] for p in r["products"]]
    if verwacht is None:
        assert titels == [], "een product dat niet in de bronnen staat mag niet verzonnen worden"
        assert r["suppliers"] == []
        assert r["next_steps"], "bij nul resultaten moeten bronnen om verder te zoeken getoond worden"
    else:
        assert any(verwacht.lower() in t.lower() for t in titels), titels
        assert r["suppliers"], "bij een bevestigd product hoort een leverancier"


def test_oplader_is_geen_vaste_standaard():
    """Een zoekterm zonder oplader/USB mag nooit USB-producten opleveren."""
    r = discover("NIVEA Soft Hydraterende Crème 200 ml", "NL", "products", ["Productcatalogi"], maak_fetch(),
                 category="beauty-care", categories=CATS)
    tekst = " ".join(p["title"].lower() for p in r["products"])
    assert "usb" not in tekst and "oplader" not in tekst and "power" not in tekst


def test_niet_overeenkomend_merk_wordt_niet_getoond():
    r = discover("Samsung Galaxy yogamat", "NL", "products", ["Productcatalogi"], maak_fetch(),
                 category="lifestyle-sport", categories=CATS)
    assert r["products"] == []


@pytest.mark.parametrize("term,niet", [
    ("Anker Soundcore Bluetooth speaker", "beauty-care"),
    ("Draagbare portable speaker", "home-living"),
    ("Standaard laptop standaard", "beauty-care"),
    ("Smartphone hoesje", "smart-home"),
])
def test_categorieherkenning_geen_valse_deelstrings(term, niet):
    assert niet not in infer_categories(term)


@pytest.mark.parametrize("term,wel", [
    ("NIVEA crème 200 ml", "beauty-care"), ("yogamat", "lifestyle-sport"), ("sierkussen", "home-living"),
    ("slimme deurbel", "smart-home"), ("bluetooth koptelefoon", "gadgets"), ("tafellamp", "home-living"),
])
def test_categorieherkenning_herkent_echte_producten(term, wel):
    assert wel in infer_categories(term)


def test_zonder_zoekterm_blijft_de_bronwoordenlijst_de_categorie_bewaken():
    from nv_product_discovery import CATALOGUES, catalogue_product
    bron = next(c for c in CATALOGUES if c.name == "Pureoil")
    product = {"id": 5, "title": "Kaarsenset", "handle": "kaarsenset", "type": "Kaars", "url": "/products/kaarsenset"}
    resultaat, reden = catalogue_product(bron, "", maak_fetch(), product, {}, None)
    assert resultaat is None and reden == "categorie buiten selectie"


def test_zoekveld_heeft_geen_oplader_als_voorbeeld(administrator):
    pagina = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    assert "magnetische powerbank" not in pagina
    assert "NIVEA" in pagina


def test_lege_zoekopdracht_toont_verder_zoeken_zonder_nephits(administrator, monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", maak_fetch())
    pagina = administrator.get("/dashboard?section=onderzoek&research_run=1&research_term=Apple+AirTag+4-pack"
                               "&research_category=gadgets&research_mode=products&research_country=NL"
                               "&research_platform=Productcatalogi").get_data(as_text=True)
    assert "Geen bevestigd product en geen bevestigde leverancier" in pagina
    assert "Verder zoeken" in pagina and "handmatige links" in pagina


def test_generiek_eenwoordig_zoekwoord_houdt_de_categoriepoort():
    from nv_product_discovery import CATALOGUES, catalogue_product, specific_term
    assert specific_term("NIVEA crème") and specific_term("Ring Video Doorbell")
    assert not specific_term("lamp") and not specific_term("")
    bron = next(c for c in CATALOGUES if c.name == "Pureoil")
    product = {"id": 5, "title": "Table Lamp", "handle": "table-lamp", "type": "Lamp", "url": "/products/table-lamp"}
    resultaat, reden = catalogue_product(bron, "lamp", maak_fetch(), product, {}, None)
    assert resultaat is None and reden == "categorie buiten selectie"


# Meerwoordige zoekopdrachten die inhoudelijk NIET overeenkomen met het (nagebootste) bronproduct:
# ze mogen nooit als bevestigde match getoond worden.
AFWIJKEND = [
    ("beauty-care", "NIVEA Soft Hydraterende Crème 400 ml"),       # andere inhoud
    ("beauty-care", "NIVEA Soft body lotion 200 ml"),              # ander producttype
    ("beauty-care", "NIVEA Men gezichtscrème 200 ml"),             # andere productlijn
    ("beauty-care", "Philips OneBlade 360 Pro scheerapparaat"),    # ander model
    ("gadgets", "Sony WH-1000XM4 koptelefoon"),                    # ander model
    ("gadgets", "Sony WH-1000XM5 oordopjes"),                      # ander producttype
    ("gadgets", "Bose QuietComfort speaker"),                      # ander merk
    ("smart-home", "Ring Video Doorbell Pro 2"),                   # ander model
    ("smart-home", "TP-Link Tapo C210 camera"),                    # ander model
    ("smart-home", "Ring Video Doorbell Wired"),                   # andere uitvoering
    ("lifestyle-sport", "Nike Dri-FIT hardloopbroek"),             # ander kledingstuk
    ("lifestyle-sport", "Bidon 500 ml roestvrij staal"),           # andere inhoud
    ("lifestyle-sport", "Adidas yogamat 8 mm"),                    # ander merk
    ("home-living", "Velvet sierkussen 60x60"),                    # andere afmeting
    ("home-living", "Philips Hue woonkamer vloerlamp"),            # ander producttype
]


@pytest.mark.parametrize("categorie,term", AFWIJKEND)
def test_afwijkend_product_wordt_nooit_bevestigd(categorie, term):
    r = discover(term, "NL", "products", ["Productcatalogi"], maak_fetch(), category=categorie, categories=CATS)
    assert r["products"] == [], [p["title"] for p in r["products"]]
    assert r["suppliers"] == []


def test_relevantie_bij_specifieke_zoekopdracht_laat_andere_gadgets_toe():
    from nv_product_discovery import category_matches, relevance_for
    assert relevance_for("Xiaomi Mi Band smartwatch")("gadgets", "Xiaomi Smart Band 9")
    assert not relevance_for("Xiaomi Mi Band smartwatch")("gadgets", "xxx porno gift card")  # onveilig blijft geweerd
    assert relevance_for("lamp") is category_matches  # generiek: categorielijst blijft bewaken
    assert category_matches("gadgets", "Smartwatch Pro")
    assert category_matches("gadgets", "Portable projector Full HD")
