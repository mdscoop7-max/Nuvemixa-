"""TESTDATA: nagebootste leveranciersantwoorden (Shopify suggest.json) voor offline tests. Niets hiervan is echt."""
import json
from urllib.parse import urlsplit

# host -> lijst (id, titel, type, handle, tekst)
PRODUCTEN = {
    "pureoil.nl": [(1, "NIVEA Soft Hydraterende Crème 200 ml", "Gezichtscrème", "nivea-soft-hydraterende-creme-200-ml", "Hydraterende crème, 200 ml")],
    "cocunat.com": [(2, "The Ordinary Niacinamide 10% + Zinc 1% Serum", "Serum", "the-ordinary-niacinamide-serum", "Niacinamide serum 30 ml")],
    "www.cocunat.com": [(2, "The Ordinary Niacinamide 10% + Zinc 1% Serum", "Serum", "the-ordinary-niacinamide-serum", "Niacinamide serum 30 ml")],
    "aytira.nl": [(3, "Philips OneBlade Scheerapparaat", "Shaver", "philips-oneblade-scheerapparaat", "Scheerapparaat voor gezicht en lichaam")],
    "eu.manduka.com": [(4, "Decathlon Yogamat 8 mm antislip", "Yoga mat", "decathlon-yogamat-8-mm-antislip", "Yogamat 8 mm dik")],
    "www.gornation.com": [(5, "Bidon 750 ml roestvrij staal", "Bottle", "bidon-750-ml-roestvrij-staal", "Drinkfles 750 ml")],
    "atletica.de": [(6, "Nike Dri-FIT hardloopshirt heren", "Running shirt", "nike-dri-fit-hardloopshirt-heren", "Hardloopshirt training")],
    "fermliving.com": [(7, "Velvet sierkussen 45x45", "Cushion", "velvet-sierkussen-45x45", "Sierkussen velvet"),
                       (8, "Bamboe opbergbox met deksel", "Storage box", "bamboe-opbergbox-met-deksel", "Opbergbox van bamboe met deksel"),
                       (9, "Philips Hue woonkamer tafellamp", "Table lamp", "philips-hue-woonkamer-tafellamp", "Tafellamp woonkamer")],
    "nedis-shop.nl": [(10, "Slimme camera WiFi 1080p", "Camera", "slimme-camera-wifi-1080p", "Slimme WiFi camera"),
                      (11, "Sony WH-1000XM5 koptelefoon", "Headphones", "sony-wh-1000xm5-koptelefoon", "Draadloze koptelefoon bluetooth"),
                      (12, "Bluetooth speaker Soundcore", "Speaker", "bluetooth-speaker-soundcore", "Anker Soundcore Bluetooth speaker")],
    "eu.switch-bot.com": [(13, "Ring Video Doorbell", "Doorbell", "ring-video-doorbell", "Slimme deurbel met camera")],
    "eu.eufy.com": [(14, "TP-Link Tapo C200 camera", "Camera", "tp-link-tapo-c200-camera", "WiFi camera")],
}


class Antwoord:
    status_code = 200

    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=16384):
        yield self.body


def maak_fetch(log=None):
    def fetch(url, params=None, **kwargs):
        parts = urlsplit(url)
        if log is not None:
            log.append((parts.netloc, (params or {}).get("q")))
        rows = PRODUCTEN.get(parts.netloc, [])
        if parts.path.endswith("/search/suggest.json"):
            q = " ".join((params or {}).get("q", "").lower().split())
            woorden = [w for w in q.split() if len(w) > 2]
            hits = []
            loc = "/en" if parts.netloc == "atletica.de" else ""
            for pid, title, kind, handle, body in rows:
                hay = f"{title} {kind} {body}".lower()
                if woorden and sum(w in hay for w in woorden) >= max(1, len(woorden) // 2):
                    hits.append({"id": pid, "title": title, "type": kind, "handle": handle,
                                 "url": f"{loc}/products/{handle}", "body": body, "image": "", "variants": []})
            return Antwoord({"resources": {"results": {"products": hits}}})
        raise OSError("niet nagebootst: " + url)
    return fetch
