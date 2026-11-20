"""Livegang-checklist: per stap of de benodigde instellingen op Render aanwezig zijn.

Alleen de NAMEN van omgevingsvariabelen en of ze gevuld zijn; nooit de waarden. Niets wordt geactiveerd of gewijzigd.
"""
import json
import os


def _filled(name):
    return bool(os.environ.get(name, "").strip())


def _step(key, title, who, names, note, *, optional=(), extra_ok=True, switch=None):
    present = [{"name": n, "ok": _filled(n)} for n in names]
    present += [{"name": n, "ok": _filled(n), "optional": True} for n in optional]
    ok = all(item["ok"] for item in present if not item.get("optional")) and extra_ok
    if switch:
        ok = ok and os.environ.get(switch[0], "").strip().lower() == switch[1]
        present.append({"name": f"{switch[0]}={switch[1]}", "ok": os.environ.get(switch[0], "").strip().lower() == switch[1]})
    return {"key": key, "title": title, "who": who, "vars": present, "note": note, "ok": ok}


def checklist(merchant_ready=None, product_total=None):
    try:
        countries = json.loads(os.environ.get("NUVEMIXA_VERIFIED_SHIPPING_COUNTRIES_JSON", "") or "{}")
        countries_ok = isinstance(countries, dict) and bool(countries)
    except ValueError:
        countries_ok = False
    steps = [
        _step("bedrijf", "Bedrijfsgegevens op voorwaarden, privacy en contact", "Jij: invullen op Render (Environment)",
              ("NUVEMIXA_BEDRIJFSNAAM", "NUVEMIXA_ADRES", "NUVEMIXA_KVK", "NUVEMIXA_BTW", "NUVEMIXA_EMAIL"),
              "Wettelijk verplicht voor een webshop: handelsnaam, vestigingsadres, KvK-nummer, btw-id en e-mailadres. "
              "Ze verschijnen automatisch in artikel 2 van de voorwaarden.", optional=("NUVEMIXA_TELEFOON",)),
        _step("contact", "Contactformulier verstuurt e-mail", "Jij: Resend-account + Render",
              ("RESEND_API_KEY", "CONTACT_FROM_EMAIL"), "Zonder deze twee worden vragen via het contactformulier niet gemaild.",
              optional=("CONTACT_TO_EMAIL",)),
        _step("lezen", "Dashboard leest WooCommerce (alleen-lezen)", "Jij: sleutel maken in WooCommerce, waarden op Render",
              ("NUVEMIXA_WOO_URL", "NUVEMIXA_WOO_HOST", "NUVEMIXA_WOO_KEY", "NUVEMIXA_WOO_SECRET"),
              "WooCommerce → Instellingen → Geavanceerd → REST API → sleutel met rechten 'Lezen'. Daarna zie je echte "
              "producten, bestellingen en administratie in het dashboard en werkt de dubbelcontrole bij publicatie."),
        _step("concept", "Producten als concept naar WooCommerce sturen", "Jij: aparte sleutel + bewuste aanzetknop",
              ("NUVEMIXA_WOO_WRITE_KEY", "NUVEMIXA_WOO_WRITE_SECRET"),
              "Tweede sleutel met 'Lezen/Schrijven'. Het dashboard maakt alleen concepten (draft); publiceren doe je zelf in "
              "WooCommerce.", switch=("NUVEMIXA_WOO_WRITE", "on")),
        _step("bestellen", "Webshopbestellingen komen in WooCommerce", "Jij: sleutel + verzendlanden + laatste schakelaar",
              ("WOOCOMMERCE_URL", "WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET",
               "NUVEMIXA_VERIFIED_SHIPPING_COUNTRIES_JSON"),
              "Pas als laatste stap: NUVEMIXA_SHIPPING_READY=true en TRENDMIX_LIVE_ORDERS=true. Tot die tijd plaatst "
              "niemand een echte bestelling. Verzendlanden als JSON, bijv. {\"nederland\": \"NL\"}.",
              extra_ok=countries_ok and os.environ.get("NUVEMIXA_SHIPPING_READY", "").lower() == "true",
              switch=("TRENDMIX_LIVE_ORDERS", "true")),
        _step("betalen", "Betalen", "Jij: betaalprovider in WooCommerce (bijv. Mollie-plugin)", (),
              "Klanten betalen in WooCommerce. Controleer daar dat de betaalmethoden in live-modus staan en doe één "
              "proefbestelling met een klein bedrag.", optional=("MOLLIE_API_KEY",), extra_ok=False),
    ]
    if merchant_ready is not None and product_total:
        steps.append({"key": "producten", "title": "Producten gecontroleerd (prijs, foto, tekst)", "who": "Jij: in het dashboard",
                      "vars": [], "ok": merchant_ready >= product_total,
                      "note": f"{merchant_ready} van {product_total} producten intern goedgekeurd (zie Google Shopping → Merchant-preview)."})
    return steps
