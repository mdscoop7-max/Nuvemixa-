"""Gecontroleerde Nederlands → Engels woordenschat voor productzoeken, zonder AI.

Webshopcatalogi zijn meestal Engelstalig. Nederlandse zoekwoorden zijn vaak samenstellingen
("hondenriem", "kruidenrek", "vaatwasborstel"). In plaats van een lijst met complete productnamen
staan hier woorddelen per webshopcategorie. Een samenstelling wordt alleen vertaald als ELK deel
bekend is; anders blijft het woord ongewijzigd. Zo ontstaan geen gegokte vertalingen.

Onderhoud: voeg een woorddeel toe aan de juiste categorie. Gebruik de enkelvoudige Engelse
productnaam (catalogusmatching vangt meervouden zelf op). Een woord dat ook een (ander) Engels
woord is, hoort in COLLISIONS: dat wordt dan alleen binnen een samenstelling vertaald.
"""
from functools import lru_cache

# Volledige samenstellingen waarvan de letterlijke vertaling niet de gangbare productnaam is.
UNITS = {
    "kattenbak": "cat litter box", "kattenbakken": "cat litter box", "krabpaal": "scratching post",
    "hondenriem": "dog leash", "hondenriemen": "dog leash", "kattenriem": "cat leash",
    "voerbak": "food bowl", "voerbakken": "food bowl", "drinkbak": "water bowl", "drinkfontein": "water fountain",
    "poepzakjes": "poop bags", "poepzakje": "poop bags", "transportbox": "pet carrier", "nagelknipper": "nail clipper",
    "zonnebril": "sunglasses", "zonnebrillen": "sunglasses", "zonnebrand": "sunscreen", "zonnebrandcreme": "sunscreen",
    "snijplank": "cutting board", "snijplanken": "cutting board", "prullenbak": "trash can", "afvalbak": "trash can",
    "kapstok": "coat rack", "wasmand": "laundry basket", "wasmanden": "laundry basket", "wasknijpers": "clothes pegs",
    "deurslot": "door lock", "rookmelder": "smoke detector", "stofzuiger": "vacuum cleaner",
    "luchtbevochtiger": "humidifier", "luchtreiniger": "air purifier", "stopcontact": "socket",
    "verlengsnoer": "extension cord", "afwasborstel": "dish brush", "vaatwasborstel": "dish brush",
    "haarborstel": "hairbrush", "tandpasta": "toothpaste", "wimperkruller": "eyelash curler",
    "handschoenen": "gloves", "handschoen": "glove", "spiegelkast": "mirror cabinet", "dekbed": "duvet",
}

PARTS = {
    "pets": {
        "hond": "dog", "honden": "dog", "kat": "cat", "katten": "cat", "poes": "cat", "huisdier": "pet",
        "huisdieren": "pet", "vogel": "bird", "vogels": "bird", "konijn": "rabbit", "konijnen": "rabbit",
        "halsband": "collar", "tuigje": "harness", "tuig": "harness", "speelgoed": "toy", "speeltje": "toy",
        "mand": "basket", "kooi": "cage", "fontein": "fountain", "brokjes": "kibble", "snoepjes": "treats",
    },
    "home-living": {
        "keuken": "kitchen", "badkamer": "bathroom", "slaapkamer": "bedroom", "woonkamer": "living room",
        "kruiden": "spice", "rek": "rack", "rekje": "rack", "plank": "shelf", "planken": "shelf",
        "opberg": "storage", "opbergmand": "storage basket", "doos": "box", "dozen": "box", "bakje": "tray",
        "haak": "hook", "haken": "hook", "haakjes": "hook", "lade": "drawer", "laden": "drawer",
        "verdeler": "divider", "pannen": "pan", "deksel": "lid", "beker": "cup", "bekers": "cup", "mok": "mug",
        "mokken": "mug", "koffie": "coffee", "thee": "tea", "glas": "glass", "glazen": "glass", "wijn": "wine",
        "bord": "plate", "borden": "plate", "bestek": "cutlery", "messen": "knife", "schaar": "scissors",
        "vaatwas": "dishwasher", "afwas": "dish", "spons": "sponge", "pomp": "pump", "emmer": "bucket",
        "kleding": "clothes", "schoenen": "shoe", "schoen": "shoe", "kledinghanger": "clothes hanger",
        "kaars": "candle", "kaarsen": "candle", "vaas": "vase", "bloem": "flower", "bloemen": "flower",
        "planten": "plant", "bloempot": "flower pot", "gordijn": "curtain", "gordijnen": "curtain",
        "deken": "blanket", "dekens": "blanket", "kussen": "cushion", "kussens": "cushion", "laken": "sheet",
        "matras": "mattress", "douche": "shower", "toilet": "toilet", "handdoek": "towel", "handdoeken": "towel",
        "tafel": "table", "stoel": "chair", "bureau": "desk", "kast": "cabinet", "licht": "light",
        "verlichting": "lighting", "nacht": "night", "lampje": "lamp", "lampjes": "lights", "sfeer": "mood",
        "klok": "clock", "fotolijst": "photo frame", "tapijt": "rug", "vloerkleed": "rug", "deurmat": "doormat",
        "hout": "wood", "houten": "wooden", "bamboe": "bamboo", "metalen": "metal", "kop": "head", "wand": "wall", "muur": "wall",
    },
    "gadgets": {
        "telefoon": "phone", "koptelefoon": "headphones", "oordopjes": "earbuds", "luidspreker": "speaker",
        "toetsenbord": "keyboard", "muis": "mouse", "muismat": "mouse pad", "fiets": "bike", "scherm": "screen",
        "beschermer": "protector", "statief": "tripod", "accu": "battery", "batterij": "battery",
        "batterijen": "battery", "reis": "travel", "horloge": "watch", "sleutel": "key", "zoeker": "finder",
        "auto": "car", "spelcomputer": "game console", "gaming": "gaming",
    },
    "smart-home": {
        "deurbel": "doorbell", "beweging": "motion", "bewegings": "motion", "raam": "window",
        "thermostaat": "thermostat", "schakelaar": "switch", "ventilator": "fan", "robot": "robot",
        "deur": "door", "slot": "lock", "sensor": "sensor", "stekker": "plug", "lamp": "lamp", "lampen": "lamp",
    },
    "beauty-care": {
        "gezicht": "face", "gezichts": "face", "haar": "hair", "lip": "lip", "lippen": "lip", "balsem": "balm",
        "nagel": "nail", "nagels": "nail", "oog": "eye", "ogen": "eye", "wimper": "eyelash", "wimpers": "eyelash",
        "wenkbrauw": "eyebrow", "wenkbrauwen": "eyebrow", "tand": "tooth", "tanden": "teeth", "borstel": "brush",
        "borstels": "brush", "kam": "comb", "masker": "mask", "maskers": "mask", "olie": "oil", "zeep": "soap",
        "droger": "dryer", "reiniger": "cleanser", "reiniging": "cleansing", "verzorging": "care",
        "parfum": "perfume", "geur": "fragrance", "zon": "sun", "zonne": "sun", "lichaam": "body",
        "voet": "foot", "voeten": "foot", "scheer": "shaving", "make": "make", "spiegel": "mirror",
    },
    "lifestyle-sport": {
        "sport": "sport", "yoga": "yoga", "blok": "block", "blokken": "block", "legging": "leggings",
        "broek": "pants", "fles": "bottle", "flessen": "bottle", "tas": "bag", "tassen": "bag",
        "hardloop": "running", "gewicht": "weight", "gewichten": "weight", "touw": "rope", "spring": "jump",
        "bal": "ball", "ballen": "ball", "knie": "knee", "pols": "wrist", "fitness": "fitness", "wandel": "hiking",
        "kampeer": "camping", "tent": "tent", "slaapzak": "sleeping bag",
    },
}

# Eigenschappen zonder eigen categorie (kleur, maat, materiaal). Bepalen nooit de webshopcategorie.
GENERAL = {
    "rood": "red", "rode": "red", "blauw": "blue", "blauwe": "blue", "zwart": "black", "zwarte": "black",
    "wit": "white", "witte": "white", "groen": "green", "groene": "green", "grijs": "grey", "grijze": "grey",
    "roze": "pink", "geel": "yellow", "gele": "yellow", "paars": "purple", "paarse": "purple", "bruin": "brown",
    "bruine": "brown", "oranje": "orange", "goud": "gold", "gouden": "gold", "zilver": "silver",
    "zilveren": "silver", "groot": "large", "grote": "large", "klein": "small", "kleine": "small",
    "waterdicht": "waterproof", "waterdichte": "waterproof", "draagbaar": "portable", "draagbare": "portable",
    "biologisch": "organic", "biologische": "organic", "natuurlijk": "natural", "natuurlijke": "natural",
    "katoen": "cotton", "katoenen": "cotton", "leer": "leather", "leren": "leather", "glazen": "glass",
    "kinderen": "kids", "kinder": "kids", "baby": "baby", "dames": "women", "heren": "men",
}

# Engelse leenwoorden: tellen alleen mee in een samenstelling met minstens één Nederlands deel.
LOANS = {
    "organizer": "organizer", "organiser": "organizer", "laptop": "laptop", "tablet": "tablet", "box": "box",
    "set": "set", "mat": "mat", "kit": "kit", "spray": "spray", "led": "led", "usb": "usb", "speaker": "speaker",
}
UNIT_CATEGORY = {
    "kattenbak": "pets", "kattenbakken": "pets", "krabpaal": "pets", "hondenriem": "pets", "hondenriemen": "pets",
    "kattenriem": "pets", "voerbak": "pets", "voerbakken": "pets", "drinkbak": "pets", "drinkfontein": "pets",
    "poepzakjes": "pets", "poepzakje": "pets", "transportbox": "pets", "nagelknipper": "beauty-care",
    "zonnebril": "lifestyle-sport", "zonnebrillen": "lifestyle-sport", "zonnebrand": "beauty-care",
    "zonnebrandcreme": "beauty-care", "snijplank": "home-living", "snijplanken": "home-living",
    "prullenbak": "home-living", "afvalbak": "home-living", "kapstok": "home-living", "wasmand": "home-living",
    "wasmanden": "home-living", "wasknijpers": "home-living", "deurslot": "smart-home", "rookmelder": "smart-home",
    "stofzuiger": "smart-home", "luchtbevochtiger": "smart-home", "luchtreiniger": "smart-home",
    "stopcontact": "smart-home", "verlengsnoer": "gadgets", "afwasborstel": "home-living",
    "vaatwasborstel": "home-living", "haarborstel": "beauty-care", "tandpasta": "beauty-care",
    "wimperkruller": "beauty-care", "handschoenen": "lifestyle-sport", "handschoen": "lifestyle-sport",
    "spiegelkast": "home-living", "dekbed": "home-living",
}

# Losse woorden die ook een (ander) Engels woord zijn: alleen vertalen binnen een samenstelling.
COLLISIONS = frozenset({
    "deur", "slot", "kop", "auto", "mand", "bal", "tent", "lip", "make", "robot", "sensor", "lamp", "toilet",
    "sport", "yoga", "fitness", "gaming", "fles", "zon", "pomp", "pols", "wand", "baby", "kinder",
})

WORDS = {word: english for group in PARTS.values() for word, english in group.items()}
WORDS.update({w: e for w, e in GENERAL.items() if w not in WORDS})
KNOWN = {**LOANS, **WORDS}
CATEGORY_OF = {word: category for category, group in PARTS.items() for word in group}
CATEGORY_OF.update({"laptop": "gadgets", "tablet": "gadgets", "usb": "gadgets", "speaker": "gadgets",
                    "organizer": "home-living", "organiser": "home-living", "led": "smart-home"})
LINKERS = ("s", "e", "")
MIN_PART, MAX_PARTS, MIN_COMPOUND = 3, 3, 6


def _split(word, parts_left):
    """Alle splitsingen van word in bekende delen (met optionele tussen-s/-e). Langste eerste deel eerst."""
    if word in KNOWN or word in UNITS:
        yield (word,)
    if parts_left <= 1:
        return
    for end in range(len(word) - MIN_PART, MIN_PART - 1, -1):
        head = word[:end]
        if head not in KNOWN and head not in UNITS:
            continue
        rest = word[end:]
        for linker in LINKERS:
            if linker and not rest.startswith(linker):
                continue
            tail = rest[len(linker):]
            if len(tail) < MIN_PART:
                continue
            for split in _split(tail, parts_left - 1):
                yield (head, *split)


@lru_cache(maxsize=8192)
def translate_word(word):
    """Engelse vertaling van één genormaliseerd Nederlands woord, of '' als dat niet zeker kan."""
    if word in UNITS:
        return UNITS[word]
    if word in WORDS:
        return "" if word in COLLISIONS else WORDS[word]
    if len(word) < MIN_COMPOUND or not word.isalpha():
        return ""
    for split in _split(word, MAX_PARTS):
        if len(split) < 2 or all(part in LOANS for part in split):
            continue
        return " ".join(UNITS.get(part) or KNOWN[part] for part in split)
    return ""


def categories_for(word):
    """Webshopcategorieën bij de bekende woorddelen van één Nederlands woord (eerste deel eerst); leeg = onbekend."""
    if word in UNIT_CATEGORY:
        return (UNIT_CATEGORY[word],)
    if word in CATEGORY_OF and word not in COLLISIONS:
        return (CATEGORY_OF[word],)
    if not translate_word(word):
        return ()
    for split in _split(word, MAX_PARTS):
        if len(split) < 2 or all(part in LOANS for part in split):
            continue
        found = [UNIT_CATEGORY.get(p) or CATEGORY_OF.get(p) for p in split]
        return tuple(dict.fromkeys(c for c in found if c))
    return ()
