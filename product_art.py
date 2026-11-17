"""NUVEMIXA productillustraties.

Genereert per product een strakke, merkvaste SVG-afbeelding (geen externe
afbeeldingsdienst nodig). Elke categorie heeft een eigen kleurenpalet en elk
product krijgt een passend icoon op basis van trefwoorden in de productnaam.
"""
import hashlib
from xml.sax.saxutils import escape

# Kleurpaletten per categorie: (achtergrond licht, achtergrond donker, accent, accent2)
PALETTES = {
    "gadgets": ("#eaf3ff", "#cfe2ff", "#0866f5", "#5aa2ff"),
    "smart-home": ("#e9fbf3", "#c9f0de", "#10a36b", "#4fd39d"),
    "beauty-care": ("#fff0f6", "#ffd5e6", "#e2407f", "#ff8bb5"),
    "home-living": ("#fff6ea", "#ffe3bf", "#e07b12", "#ffb35c"),
    "lifestyle-sport": ("#f1edff", "#ddd3ff", "#6a3df5", "#a68bff"),
    "pc-componenten": ("#eef0ff", "#d6dbff", "#3046d8", "#7d8cff"),
    "aanbiedingen": ("#fff0f0", "#ffd2d6", "#f32647", "#ff7a8c"),
}

# Lijn-iconen (viewBox 0 0 24 24, stroke). Volgorde in KEYWORDS bepaalt prioriteit.
ICONS = {
    "earbuds": '<path d="M7 4a3 3 0 0 0-3 3v3a3 3 0 0 0 3 3h1V4z"/><path d="M8 13v5a2 2 0 0 0 2 2"/><path d="M17 4a3 3 0 0 1 3 3v3a3 3 0 0 1-3 3h-1V4z"/><path d="M16 13v5a2 2 0 0 1-2 2"/>',
    "headphones": '<path d="M3 15v-3a9 9 0 0 1 18 0v3"/><rect x="2" y="14" width="5" height="7" rx="2"/><rect x="17" y="14" width="5" height="7" rx="2"/>',
    "projector": '<rect x="2" y="8" width="20" height="10" rx="3"/><circle cx="16" cy="13" r="3"/><path d="M6 12h4M6 15h3M5 18v2M19 18v2"/>',
    "charger": '<rect x="4" y="13" width="16" height="6" rx="3"/><rect x="8" y="3" width="8" height="9" rx="2"/><path d="M12 6l-1 2h2l-1 2"/>',
    "watch": '<rect x="6" y="6" width="12" height="12" rx="3"/><path d="M9 6l1-4h4l1 4M9 18l1 4h4l1-4M12 9v3l2 1"/>',
    "led": '<path d="M2 16c3-6 6 2 10-4s7 2 10-4"/><circle cx="5" cy="13.5" r="1"/><circle cx="9.5" cy="13" r="1"/><circle cx="14.5" cy="10.5" r="1"/><circle cx="19" cy="9" r="1"/>',
    "speaker": '<rect x="5" y="2" width="14" height="20" rx="3"/><circle cx="12" cy="14" r="4"/><circle cx="12" cy="6.5" r="1.3"/>',
    "battery": '<rect x="5" y="3" width="14" height="18" rx="3"/><path d="M13 7l-3 5h4l-3 5"/>',
    "tracker": '<rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3"/><path d="M12 4V2"/>',
    "gimbal": '<rect x="7" y="2" width="10" height="6" rx="1.5"/><path d="M12 8v3M9 11h6v3H9zM12 14v8"/>',
    "ringlight": '<circle cx="12" cy="9" r="6"/><circle cx="12" cy="9" r="3"/><path d="M12 15v7M8 22h8"/>',
    "plug": '<path d="M9 2v5M15 2v5"/><rect x="6" y="7" width="12" height="7" rx="2"/><path d="M12 14v3a3 3 0 0 0 3 3h2"/>',
    "fan": '<circle cx="12" cy="10" r="1.6"/><path d="M12 8.4C12 4 16 3 16 6s-2.5 3-4 4M13.6 10c4.4 0 5.4 4 2.4 4s-3-2.5-4-4M10.4 10C6 10 5 6 8 6s3 2.5 4 4"/><path d="M12 12v8M8 21h8"/>',
    "phone": '<rect x="7" y="2" width="10" height="16" rx="2"/><path d="M11 15h2M5 22h14l-2-4H7z"/>',
    "mouse": '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v6"/>',
    "hub": '<rect x="3" y="9" width="18" height="6" rx="3"/><path d="M7 12h1M11 12h1M15 12h1M21 12h2"/>',
    "keyboard": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h0M10 10h0M14 10h0M18 10h0M6 14h12"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "printer": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "ssd": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h6M7 12h4"/><circle cx="17" cy="15" r="1"/>',
    "camera": '<path d="M3 8h4l2-3h6l2 3h4v11H3z"/><circle cx="12" cy="13" r="4"/>',
    "bulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>',
    "doorbell": '<rect x="7" y="2" width="10" height="20" rx="4"/><circle cx="12" cy="8" r="2"/><circle cx="12" cy="15" r="2.5"/>',
    "thermostat": '<circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><circle cx="12" cy="14" r="2"/>',
    "sensor": '<path d="M5 12a7 7 0 0 1 14 0M8 12a4 4 0 0 1 8 0"/><circle cx="12" cy="12" r="1.5"/><path d="M12 14v7"/>',
    "smoke": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 9v1M12 14v1M9 12h1M14 12h1"/>',
    "air": '<path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h8"/>',
    "curtain": '<path d="M3 3h18M5 3v18c3-4 3-9 0-18M19 3v18c-3-4-3-9 0-18"/>',
    "switch": '<rect x="6" y="2" width="12" height="20" rx="3"/><rect x="9" y="6" width="6" height="8" rx="1.5"/>',
    "drop": '<path d="M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z"/>',
    "remote": '<rect x="7" y="2" width="10" height="20" rx="3"/><circle cx="12" cy="7" r="1.5"/><path d="M10 12h4M10 15h4M10 18h4"/>',
    "robot": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M5 9h3M16 9h3"/>',
    "energy": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "hairdryer": '<path d="M3 8a5 5 0 0 1 5-5h9v10H8a5 5 0 0 1-5-5z"/><path d="M20 5v6M10 13l-1 8h4l1-8"/>',
    "face": '<circle cx="12" cy="12" r="9"/><path d="M9 10h0M15 10h0M9 15c2 1.5 4 1.5 6 0"/>',
    "straightener": '<path d="M7 2l3 14M17 2l-3 14M10 16l-1 6M14 16l1 6"/>',
    "nail": '<path d="M8 22V10a4 4 0 0 1 8 0v12z"/><path d="M10 10a2 2 0 0 1 4 0v3h-4z"/>',
    "mirror": '<circle cx="12" cy="9" r="7"/><path d="M12 16v4M8 22h8"/>',
    "toothbrush": '<path d="M10 22V10h4v12z"/><path d="M10 6h4M10 3h4M9 8h6"/>',
    "trimmer": '<rect x="8" y="6" width="8" height="16" rx="3"/><path d="M8 4h8M9 2h6"/>',
    "massage": '<path d="M4 10h10l4-4v12l-4-4H4z"/><path d="M14 14v6h-4"/>',
    "brush": '<rect x="9" y="12" width="6" height="10" rx="2"/><path d="M7 2v10h10V2M10 2v6M14 2v6"/>',
    "diffuser": '<path d="M8 22h8l1-9H7z"/><path d="M10 9c-1-2 1-3 0-5M14 9c-1-2 1-3 0-5"/>',
    "lamp": '<path d="M8 3h8l3 8H5z"/><path d="M12 11v9M8 21h8"/>',
    "organizer": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M3 12h18M9 7v13M15 12v8M8 3h8l1 4H7z"/>',
    "sunset": '<path d="M5 18a7 7 0 0 1 14 0M2 18h20M12 4v3M4.9 8.9l2.1 2.1M19.1 8.9 17 11"/>',
    "scale": '<rect x="3" y="12" width="18" height="8" rx="2"/><path d="M8 12V8h8v4M12 8V4"/>',
    "cup": '<path d="M5 8h11v7a5 5 0 0 1-10 0z"/><path d="M16 10h2a2 2 0 0 1 0 4h-2M8 3v2M11 3v2"/>',
    "vacuum": '<path d="M4 20h16M6 20V9a3 3 0 0 1 3-3h6l3 3v11"/><circle cx="12" cy="13" r="3"/>',
    "basket": '<path d="M3 9h18l-2 12H5zM7 9l3-6M17 9l-3-6"/>',
    "plant": '<path d="M7 22h10l1-8H6z"/><path d="M12 14V8M12 8c0-3 3-5 6-5 0 3-3 5-6 5zM12 10c0-3-3-4-5-4 0 2 2 4 5 4"/>',
    "thermometer": '<path d="M14 14V4a2 2 0 0 0-4 0v10a4 4 0 1 0 4 0z"/><path d="M12 9v7"/>',
    "laptop": '<rect x="4" y="5" width="16" height="11" rx="1"/><path d="M2 19h20"/>',
    "dumbbell": '<path d="M6 7v10M3 9v6M18 7v10M21 9v6M6 12h12"/>',
    "bottle": '<path d="M9 2h6v3H9zM8 5h8l1 3v13H7V8z"/><path d="M7 12h10"/>',
    "band": '<path d="M4 16c4-10 12-10 16 0"/><path d="M3 16h3M18 16h3"/>',
    "yoga": '<rect x="4" y="5" width="4" height="14" rx="2"/><path d="M8 7h12v10H8"/>',
    "rope": '<path d="M5 3v5M19 3v5M5 8c0 14 14 14 14 0"/>',
    "roller": '<rect x="2" y="8" width="20" height="8" rx="4"/><path d="M6 8v8M10 8v8M14 8v8M18 8v8"/>',
    "bag": '<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M8 8V5a4 4 0 0 1 8 0v3M3 13h18"/>',
    "stepper": '<path d="M4 18h16M6 18l2-8h4l2 8M12 10l4-4h3"/>',
    "grip": '<path d="M7 3v8a5 5 0 0 0 10 0V3M7 21l3-6M17 21l-3-6"/>',
    "glove": '<path d="M7 21v-9l-2-3V5h3v4V3h3v6V2h3v7V3h3v9l-2 9z"/>',
    "bike": '<circle cx="6" cy="16" r="4"/><circle cx="18" cy="16" r="4"/><path d="M6 16l4-8h5l3 8M10 8l2 8"/>',
    "pump": '<rect x="10" y="10" width="4" height="12" rx="1"/><path d="M8 4h8M12 4v6M14 16h4a2 2 0 0 0 2-2v-3"/>',
    "ram": '<rect x="2" y="7" width="20" height="9" rx="1"/><path d="M5 16v3M9 16v3M13 16v3M17 16v3M6 10h3M11 10h3M16 10h2"/>',
    "psu": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="14" cy="12" r="4"/><path d="M6 8h2M6 11h2"/>',
    "cooler": '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    "case": '<rect x="6" y="2" width="12" height="20" rx="2"/><circle cx="12" cy="9" r="3"/><path d="M9 17h6"/>',
    "motherboard": '<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="8" y="8" width="8" height="8" rx="1"/><path d="M3 6h2M3 10h2M19 14h2M19 18h2M6 19v2M18 3v2"/>',
    "wifi": '<path d="M2 9a15 15 0 0 1 20 0M5 13a10 10 0 0 1 14 0M8.5 16.5a5 5 0 0 1 7 0"/><circle cx="12" cy="20" r="1"/>',
    "controller": '<path d="M6 9h12a4 4 0 0 1 4 4v1a3 3 0 0 1-5 2l-2-2H9l-2 2a3 3 0 0 1-5-2v-1a4 4 0 0 1 4-4z"/><path d="M7 11v3M5.5 12.5h3M16 12h0M18 13h0"/>',
    "webcam": '<circle cx="12" cy="10" r="7"/><circle cx="12" cy="10" r="3"/><path d="M8 19h8l-1-2"/>',
    "monitor": '<rect x="3" y="3" width="18" height="12" rx="1"/><path d="M12 15v3l-4 3M12 18h6"/>',
    "gift": '<rect x="3" y="9" width="18" height="12" rx="1"/><path d="M3 13h18M12 9v12M12 9c-2-5-6-4-6-2s3 2 6 2c2-5 6-4 6-2s-3 2-6 2"/>',
    "spark": '<path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z"/>',
}

# (trefwoord in naam, icoon) — eerste match wint.
KEYWORDS = [
    ("sportoordop", "earbuds"), ("oordop", "earbuds"), ("headset", "headphones"), ("koptelefoon", "headphones"),
    ("projectielamp", "sunset"), ("sunset", "sunset"), ("projector", "projector"),
    ("wekker", "clock"), ("draadloos laden", "charger"), ("oplader", "charger"), ("snellader", "plug"), ("smartstekker", "plug"),
    ("fitnessarmband", "watch"), ("smartwatch", "watch"), ("wearable", "watch"),
    ("lichtstrip", "led"), ("led-strip", "led"), ("strip", "led"), ("rgb", "led"),
    ("speaker", "speaker"), ("powerbank", "battery"), ("tracker", "tracker"), ("gimbal", "gimbal"),
    ("ringlamp", "ringlight"), ("ventilator", "fan"), ("telefoonhouder", "phone"), ("hardlooptelefoon", "phone"),
    ("muis", "mouse"), ("mouse", "mouse"), ("hub", "hub"), ("toetsenbord", "keyboard"), ("keyboard", "keyboard"), ("macro", "keyboard"),
    ("fotoprinter", "printer"), ("ssd", "ssd"), ("nvme", "ssd"),
    ("webcam", "webcam"), ("camera", "camera"), ("videodeurbel", "doorbell"),
    ("nachtla", "bulb"), ("led-lamp", "bulb"), ("buitenverlichting", "bulb"), ("kastverlichting", "bulb"), ("fietslamp", "bike"),
    ("thermostaat", "thermostat"), ("bewegingssensor", "sensor"), ("deursensor", "sensor"), ("sensor", "sensor"),
    ("rookmelder", "smoke"), ("luchtreiniger", "air"), ("luchtbevochtiger", "drop"), ("watersensor", "drop"), ("waterflosser", "drop"),
    ("gordijn", "curtain"), ("lichtschakelaar", "switch"), ("afstandsbediening", "remote"), ("robotstofzuiger", "robot"),
    ("energiemeter", "energy"), ("temperatuurmeter", "thermometer"), ("thermometer", "thermometer"),
    ("föhn", "hairdryer"), ("fohn", "hairdryer"), ("gezichtsmasker", "face"), ("gezichtsreiniger", "face"), ("gezichtsroller", "face"),
    ("gezichtsstomer", "face"), ("gezichtsmassage", "face"), ("huidreiniger", "face"), ("beauty", "face"),
    ("stijltang", "straightener"), ("krultang", "straightener"), ("nagel", "nail"), ("voetvijl", "nail"),
    ("spiegel", "mirror"), ("tandenborstel", "toothbrush"), ("trimmer", "trimmer"), ("hoofdhuid", "massage"),
    ("warmteborstel", "brush"), ("massagegun", "massage"), ("spiermassager", "massage"), ("massage", "massage"),
    ("diffuser", "diffuser"), ("tafellamp", "lamp"), ("organizer", "organizer"), ("keukenweegschaal", "scale"),
    ("bagageweegschaal", "scale"), ("zeepdispenser", "drop"), ("melkopschuimer", "cup"), ("kruimeldief", "vacuum"),
    ("vacuüm", "vacuum"), ("ontpluizer", "brush"), ("wasmand", "basket"), ("plant", "plant"), ("laptoptafel", "laptop"),
    ("drinkfles", "bottle"), ("waterfles", "bottle"), ("weerstandsband", "band"), ("yogamat", "yoga"), ("springtouw", "rope"),
    ("foamroller", "roller"), ("sporttas", "bag"), ("heuptas", "bag"), ("reisorganizer", "bag"), ("travel", "bag"),
    ("stepper", "stepper"), ("handtrainer", "grip"), ("handschoen", "glove"), ("bandenpomp", "pump"),
    ("ddr5", "ram"), ("ram kit", "ram"), ("psu", "psu"), ("aio", "cooler"), ("cooler", "cooler"), ("airflow", "case"), ("case", "case"),
    ("motherboard", "motherboard"), ("wifi 7", "wifi"), ("controller", "controller"), ("monitor", "monitor"),
    ("gaming", "controller"), ("fitness", "dumbbell"), ("smart lock", "sensor"), ("smart home", "bulb"),
    ("bundle", "gift"), ("kit", "gift"), ("pack", "gift"), ("set", "gift"),
]


def icon_for(name):
    lowered = str(name or "").casefold()
    for keyword, icon in KEYWORDS:
        if keyword in lowered:
            return icon
    return "spark"


def render_product_svg(name, category_slug):
    bg1, bg2, accent, accent2 = PALETTES.get(category_slug, PALETTES["gadgets"])
    icon = ICONS[icon_for(name)]
    seed = int(hashlib.md5(f"{category_slug}:{name}".encode("utf-8")).hexdigest()[:8], 16)
    # Kleine variatie per product zodat de grid niet identiek oogt.
    bx = 470 + seed % 90
    by = 90 + (seed >> 8) % 80
    rot = (seed >> 16) % 30 - 15
    uid = f"p{seed:x}"
    title = escape(str(name or "NUVEMIXA product"))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" role="img" aria-label="{title}">
<title>{title}</title>
<defs>
<linearGradient id="{uid}bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient>
<linearGradient id="{uid}ac" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent2}"/><stop offset="1" stop-color="{accent}"/></linearGradient>
<filter id="{uid}sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="22" stdDeviation="22" flood-color="{accent}" flood-opacity=".28"/></filter>
</defs>
<rect width="640" height="640" fill="url(#{uid}bg)"/>
<circle cx="{bx}" cy="{by}" r="150" fill="{accent2}" opacity=".18"/>
<circle cx="{640 - bx + 40}" cy="{560 - by // 3}" r="110" fill="{accent}" opacity=".10"/>
<g transform="rotate({rot} 320 320)" opacity=".5"><rect x="150" y="150" width="340" height="340" rx="90" fill="none" stroke="{accent}" stroke-opacity=".18" stroke-width="2" stroke-dasharray="6 12"/></g>
<rect x="190" y="190" width="260" height="260" rx="72" fill="url(#{uid}ac)" filter="url(#{uid}sh)"/>
<rect x="190" y="190" width="260" height="130" rx="72" fill="#fff" opacity=".12"/>
<g transform="translate(236 236) scale(7)" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{icon}</g>
<g fill="{accent}" opacity=".55"><circle cx="128" cy="150" r="7"/><circle cx="520" cy="470" r="5"/><circle cx="150" cy="500" r="4"/></g>
</svg>"""
