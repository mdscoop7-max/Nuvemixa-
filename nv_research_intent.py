"""Conservative Dutch/English search intent and offer matching."""
import re
import unicodedata

# First normalize vocabulary, then distinguish product identity from properties.
PHRASES = (
    (r"\b(?:wi[\s-]*fi|wlan)\b", "wifi"),
    (r"\bargan[\s-]+(?:huidolie|skin oil)\b", "argan oil skin"),
    (r"\b(?:arganolie|argan[\s-]+(?:huidolie|haarolie|skin oil|hair oil|olie))\b", "argan oil"),
    (r"\b(?:skin care|skincare|huidverzorging|cosmetisch(?:e)?|cosmetic|skin|huid)\b", "skin"),
    (r"\b(?:puur|pure|zuiver(?:e)?)\b", "pure"),
    (r"\b(?:koud[\s-]*geperst|cold[\s-]*press(?:ed)?)\b", "cold pressed"),
    (r"\b(?:gezichtsreinigingsborstel|gezichtsborstel|(?:facial|face) (?:cleansing|cleaning) brush)\b", "facial cleansing brush"),
    (r"\b(?:siliconen|silicone)\b", "silicone"),
    (r"\b(?:elektrisch(?:e)?|electric|sonic|sonisch(?:e)?)\b", "electric"),
    (r"\b(?:slimm?e? (?:wifi )?stekker|slim stopcontact|smart (?:socket|outlet|plug)|wifi (?:socket|outlet|stekker))\b", "smart plug"),
    (r"\b(?:energiemeter|energiemeting|energiebewaking|energiemonitor(?:ing)?|energy (?:meter|monitor(?:ing)?)|power (?:metering|monitoring)|stroomverbruik meten)\b", "energy monitoring"),
    (r"\b(?:weerstandsband(?:en)?|resistance band(?:s)?|exercise band(?:s)?|fitnessband(?:en)?)\b", "resistance band"),
    (r"\b(?:sets|kit|pakket)\b", "set"),
    (r"\b(?:oplaadbaar|oplaadbare|herlaadbaar|rechargeable|recharge(?:s|d)?|opladen)\b", "rechargeable"),
    (r"\b(?:draadloos|draadloze|wireless|cordless|kabellos(?:es)?)\b", "wireless"),
    (r"\b(?:tafellamp(?:en)?|table (?:light|lamp)|desk lamp|bureaulamp)\b", "table lamp"),
    (r"\b(?:hydraterend(?:e)?\s+creme|moisturi[sz]ing cream|moisturi[sz]er(?: cream)?|vochtinbrengend(?:e)?\s+creme)\b", "moisturizing cream"),
    (r"\b(?:creme|cream)\b", "cream"),
    (r"\b(?:kabel[\s-]*(?:organizers?|organiser|beheer|houders?|clips?|management)|cable[\s-]*(?:organi[sz]ers?|management|clips?|holders?))\b", "cable organizer"),
    (r"\b(?:yoga[\s-]*matten?|yoga mats?)\b", "yoga mat"),
    (r"\b(?:power[\s-]*banks?|powerbanks?|externe accu)\b", "power bank"),
    (r"\b(?:beveiligings|bewakings|security|surveillance)[\s-]*(?:camera'?s?|cams?)\b", "security camera"),
)
NORMALIZATIONS = tuple((re.compile(pattern), replacement) for pattern, replacement in PHRASES)

# Terms in this table deliberately expand candidate retrieval only.
PRODUCTS = {
    "argan oil": ("argan oil", "arganolie", "cosmetic argan oil", "argan olie"),
    "facial cleansing brush": ("facial cleansing brush", "gezichtsreinigingsborstel", "silicone face brush"),
    "smart plug": ("smart plug", "slimme stekker", "wifi energy monitoring plug"),
    "resistance band": ("resistance bands", "weerstandsbanden", "exercise bands"),
    "table lamp": ("table lamp", "tafellamp", "portable lamp", "rechargeable lamp"),
    "moisturizing cream": ("moisturizing cream", "hydraterende crème", "moisturiser"),
    "security camera": ("security camera", "beveiligingscamera", "surveillance camera"),
    "yoga mat": ("yoga mat", "yogamat", "exercise mat"),
    "cable organizer": ("cable organizer", "kabelorganizer", "cable management", "cable clips"),
    "face serum": ("face serum", "gezichtsserum", "facial serum"),
    "smart doorbell": ("smart doorbell", "slimme deurbel", "video doorbell"),
}

FACETS = {
    "argan oil": ("pure", "cold pressed", "skin"),
    "facial cleansing brush": ("electric", "silicone", "usbc"),
    "smart plug": ("wifi", "energy monitoring"),
    "resistance band": ("set",),
    "table lamp": ("wireless", "led", "rechargeable", "usbc"),
}
FACET_LABELS = {
    "pure": "zuiverheid", "cold pressed": "koudgeperst", "skin": "geschikt voor de huid",
    "electric": "elektrisch", "silicone": "siliconen", "usbc": "USB-C",
    "wifi": "wifi", "energy monitoring": "energiemeter", "set": "meerdelige set",
    "wireless": "draadloos", "led": "led", "rechargeable": "oplaadbaar",
}

ALIASES = {
    "magnetische": "magnetic", "magnetischen": "magnetic", "magnetisch": "magnetic",
    "oplader": "charger", "slimme": "smart", "slim": "smart",
    "gordijn": "curtain", "gordijnen": "curtain", "deurbel": "doorbell",
    "beveiligingscamera": "security camera", "vloerlamp": "floor lamp", "stoel": "chair", "kussen": "cushion", "tafel": "table",
    "vaas": "vase", "yogamat": "yoga mat", "yogamatten": "yoga mat",
    "rgbicww": "rgbicww smart", "eufycam": "eufycam camera", "bewakingscamera": "security camera",
    "surveillance": "security", "desklamp": "table lamp", "gezichtsserum": "face serum",
    "magsafe": "magsafe magnetic", "smartlife": "smartlife smart",
}

STOP_WORDS = frozenset("a de een en for het in is met of the van voor with and by via".split())
MEASURE = re.compile(r"\b(\d+)\s+(mah|ml|amp)\b")
CAPACITY = re.compile(r"\b([0-9]+) mah\b")
CONNECTOR = re.compile(r"\b(?:usb[\s‐‑–—-]*(?:type[\s‐‑–—-]*)?c|type[\s‐‑–—-]*c)\b")
ACCESSORIES = r"cable|kabel|spray|cover|case|houder|mount|bracket|strap|hoes|replacement head|opzetborstel"

def normalize(value):
    value = "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))
    value = re.sub(r"(?<=\d)[., ](?=\d{3}\b)", "", value)
    value = re.sub(r"\bpower[ -]?(?:banks?|packs?)\b", "power bank", value)
    value = CONNECTOR.sub("usbc", value)
    value = re.sub(r"\bqi[ -]?2\b", "qi2", value)
    value = re.sub(r"\bmagsafe[- ]+(?:compatible|compatibel)\b|\bcompatible with magsafe\b", "magsafe", value)
    if "power bank" in value:
        value = re.sub(r"\b([1-9][0-9]?)k\b", r"\g<1>000 mah", value)
    value = re.sub(r"\b(\d+)\s*(mah|ml|amp(?:ere)?s?|a)\b",
                   lambda m: f"{m[1]} {'amp' if m[2].startswith('a') else m[2]}", value)
    for pattern, replacement in NORMALIZATIONS:
        value = pattern.sub(replacement, value)
    return " ".join(ALIASES.get(word, word) for word in re.findall(r"[^\W_]+", value))

def words(value):
    return set(value.split()) - STOP_WORDS

def has_phrase(text, phrase):
    return f" {phrase} " in f" {text} "

def matches(search, evidence):
    required = words(normalize(search))
    return bool(required) and required.issubset(words(normalize(evidence)))

def power_bank_query(term):
    return {"power", "bank"}.issubset(words(normalize(term)))

def subject_for(normalized):
    return next((subject for subject in PRODUCTS if has_phrase(normalized, subject)), "")

def english_query(term):
    value = normalize(term)
    return re.sub(r"(?<=\d) (?=(?:mah|ml)\b)", "", value).replace("usbc", "USB-C").replace(" amp", "A")

def candidate_queries(term):
    if not term:
        return ()
    normalized = normalize(term)
    if power_bank_query(term) and "magnetic" in normalized.split():
        capacity = CAPACITY.search(normalized)
        suffix = f" {capacity[1]}mAh" if capacity else ""
        return (f"magnetic power bank{suffix}", f"MagSafe power bank{suffix}", "Qi2 magnetic charger")
    subject = subject_for(normalized)
    strategies = [term, english_query(term)]
    if subject:
        # Preserve identity tokens (including unknown brand/model tokens) in a
        # shorter index search. Offer verification always uses the original term.
        identity = identity_words(normalized, subject)
        prefix = " ".join(w for w in dict.fromkeys(normalized.split()) if w in identity)
        suffix = " set" if subject == "resistance band" and "set" in normalized.split() else ""
        if subject == "table lamp" and "rechargeable" in normalized.split():
            strategies.extend((" ".join(filter(None, (prefix, "rechargeable table lamp"))),
                               " ".join(filter(None, (prefix, "portable lamp")))))
        else:
            strategies.extend(" ".join(filter(None, (prefix, variant + suffix))) for variant in PRODUCTS[subject])
    else:
        short = [w for w in MEASURE.sub("", normalized).split() if w not in STOP_WORDS | {"usbc", "pure", "rechargeable", "wireless"}]
        if len(short) >= 2:
            strategies.append(" ".join(short))
    return tuple(dict.fromkeys(q for q in strategies if q))[:7]


def index_query(term):
    normalized = normalize(term)
    subject = subject_for(normalized)
    if subject and not identity_words(normalized, subject):
        return PRODUCTS[subject][0]
    variants = candidate_queries(term)
    return variants[0] if variants else ""


def identity_words(normalized, subject):
    base = MEASURE.sub("", normalized)
    if subject:
        for phrase in (subject, *FACETS.get(subject, ())):
            base = re.sub(r"\b" + re.escape(phrase) + r"\b", " ", base)
    if subject == "resistance band":
        base = re.sub(r"\b(?:fitness|training|workout|exercise|sport)\b", " ", base)
    return words(base)


def exact_identity(query, title, subject):
    identifiers = identity_words(query, subject)
    prefix = tuple(word for word in query.split(subject, 1)[0].split() if word in identifiers)
    return identifiers.issubset(words(title)) and (len(prefix) < 2 or has_phrase(title, " ".join(prefix)))

def offer_match(term, identity, description="", variant=""):
    """Return match level and unverified requirements. Reject unrelated models."""
    if not term:
        return "exact", ()
    query, title, body = normalize(term), normalize(identity), normalize(description)
    variant = normalize(variant)
    evidence = f"{title} {body} {variant}"
    subject = subject_for(query)
    core = "power bank" if power_bank_query(term) else subject
    if core and not re.search(r"\b(?:" + ACCESSORIES + r")\b", query):
        if (re.search(r"\b(?:" + ACCESSORIES + r") (?:for|voor|compatible with) " + core + r"\b", title)
                or re.search(r"\b" + core + r" (?:cleaning )?(?:" + ACCESSORIES + r")\b", title)):
            return "", ()
    if core == "power bank":
        if not power_bank_query(identity):
            return "", ()
        required = set(CAPACITY.findall(query))
        sizes = set(CAPACITY.findall(title))
        if required and sizes and not required.issubset(sizes):
            return "", ()
    if not subject:
        return ("exact", ()) if matches(term, f"{identity} {description} {variant}") else ("", ())

    subject_in_title = has_phrase(title, subject)
    if subject == "moisturizing cream":
        subject_in_title |= "cream" in title.split()
    if subject == "table lamp" and "lamp" in title.split() and "portable" in title.split():
        subject_in_title |= "table" in body.split() and "floor lamp" not in title
    if not subject_in_title or not exact_identity(query, title, subject):
        return "", ()
    if subject == "argan oil" and words(title) & {
        "soap", "zeep", "shampoo", "conditioner", "balm", "lotion", "blend", "gratis", "proefflesje",
    }:
        return "", ()
    if subject == "moisturizing cream" and words(title) & {"shower", "wash", "cleanser", "soap", "gel"}:
        return "", ()
    if subject == "smart plug" and "zigbee" in title.split() and "wifi" not in title.split() and "wifi" in query.split():
        return "", ()
    missing = []
    for facet in FACETS.get(subject, ()):
        if not has_phrase(query, facet):
            continue
        found = has_phrase(evidence, facet)
        if facet == "skin":
            found |= bool(words(evidence) & {"face", "gezicht", "huidverzorging", "lichaam"})
        if facet == "usbc":
            found &= not bool(re.search(r"\b(?:no|geen|without|zonder|not compatible with) usbc\b", evidence))
            found &= ("usbc" in title.split() or any(re.search(
                r"\b(?:rechargeable|charging|charges?|laadt|opgeladen) (?:\w+ ){0,4}usbc\b|"
                r"\busbc (?:charging |laad)?(?:port|poort)\b", normalize(sentence),
            ) for sentence in re.split(r"[.!?;\n]", description)))
        if facet == "set":
            found = has_phrase(title, "set") or bool(re.search(r"\b[2-9]\s+resistance band\b", title))
        if facet == "wifi" and "zigbee" in title.split():
            found = "wifi" in variant.split() and "zigbee" not in variant.split()
        if not found:
            missing.append(FACET_LABELS[facet])
    for amount, unit in MEASURE.findall(query):
        published_sizes = {size for size, u in MEASURE.findall(f"{title} {variant}") if u == unit}
        if ((published_sizes and amount not in published_sizes)
                or not has_phrase(evidence, f"{amount} {unit}")):
            label = {"amp": "A", "ml": "ml", "mah": "mAh"}[unit]
            missing.append(f"{amount} {label}")
    if subject == "moisturizing cream" and not re.search(r"\bspf\s*\d*", query) and re.search(r"\bspf\s*\d*", title):
        missing.append("gevraagde standaarduitvoering")
    return ("similar", tuple(missing)) if missing else ("exact", ())


# Automatische categorieherkenning (Nederlands en Engels). Deelstrings van samenstellingen tellen mee.
CATEGORY_TERMS = {
    "gadgets": ("powerbank", "power bank", "oplader", "charger", "lader", "kabel", "cable", "usb", "bluetooth",
                "koptelefoon", "headphone", "oordopje", "earbud", "speaker", "telefoon", "phone", "laptop",
                "magsafe", "adapter", "toetsenbord", "keyboard", "muis", "mouse", "organizer"),
    "smart-home": ("smart", "slim", "wifi", "zigbee", "matter", "camera", "deurbel", "doorbell", "beveilig",
                   "security", "bewaking", "sensor", "stekker", "plug", "thermostaat", "gordijn", "robotstof", "robot vacuum"),
    "beauty-care": ("olie", "oil", "serum", "creme", "cream", "huid", "skin", "haar", "hair", "shampoo", "zeep", "soap",
                    "parfum", "make-up", "makeup", "gezicht", "face", "facial", "lotion", "scheer", "tandenborstel"),
    "home-living": ("lamp", "licht", "light", "kussen", "cushion", "vaas", "vase", "tafel", "table", "stoel", "chair",
                    "kast", "rek", "shelf", "organizer", "opberg", "storage", "decor", "kaars", "candle", "tapijt", "rug", "kabelbeheer"),
    "lifestyle-sport": ("yoga", "mat", "fitness", "halter", "dumbbell", "weerstand", "resistance", "sport", "hardloop",
                        "running", "drinkfles", "bottle", "rugzak", "backpack", "training", "gym", "wandel", "hiking"),
}


def infer_categories(term):
    """Geeft de categorieën terug waarin een zoekterm waarschijnlijk valt. Leeg = onbekend (dan alles doorzoeken)."""
    text = normalize(term or "")
    flat = text.replace(" ", "")
    found = []
    for category, hints in CATEGORY_TERMS.items():
        for hint in hints:
            plain = hint.replace(" ", "")
            if (len(plain) >= 4 and (plain in flat)) or has_phrase(text, hint):
                found.append(category)
                break
    return tuple(found)
