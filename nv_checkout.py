"""Checkout-validatie en betaalprovider-voorbereiding voor NUVEMIXA.

Bevat bewust GEEN bedrijfsgegevens, tarieven of betaalsleutels. Verzendkosten, btw en
betaalmethoden blijven "nog niet bevestigd" totdat de eigenaar echte gegevens aanlevert.
"""
import re

REQUIRED = ("first_name", "last_name", "email", "address_1", "postcode", "city", "country")

LABELS = {
    "first_name": ("Voornaam", "First name"),
    "last_name": ("Achternaam", "Last name"),
    "email": ("E-mailadres", "Email address"),
    "address_1": ("Adres", "Address"),
    "postcode": ("Postcode", "Postal code"),
    "city": ("Woonplaats", "City"),
    "country": ("Land", "Country"),
}

_NL_NAMES = {"nl", "nederland", "the netherlands", "netherlands", "holland"}


def is_netherlands(country):
    return (country or "").strip().casefold() in _NL_NAMES


def validate_customer(customer):
    """Geef {veld: (nl, en)} met foutmeldingen terug; leeg dict betekent geldig."""
    errors = {}
    for key in REQUIRED:
        if not (customer.get(key) or "").strip():
            nl, en = LABELS[key]
            errors[key] = (f"{nl} is verplicht.", f"{en} is required.")
    for key in ("first_name", "last_name", "city"):
        value = (customer.get(key) or "").strip()
        if value and (len(value) > 80 or value.isdigit()):
            errors[key] = ("Vul een geldige waarde in.", "Please enter a valid value.")
    email = (customer.get("email") or "").strip()
    if email and (len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
        errors["email"] = ("Vul een geldig e-mailadres in, bijvoorbeeld naam@voorbeeld.nl.",
                           "Enter a valid email address, for example name@example.com.")
    country = (customer.get("country") or "").strip()
    if country and (len(country) < 2 or len(country) > 100 or any(ord(c) < 32 for c in country)):
        errors["country"] = ("Vul een geldige landnaam in.", "Enter a valid country name.")
    address = (customer.get("address_1") or "").strip()
    if address and (len(address) < 5 or len(address) > 200):
        errors["address_1"] = ("Vul straat en huisnummer in.", "Enter street and house number.")
    elif address and is_netherlands(country) and not re.search(r"\d", address):
        errors["address_1"] = ("Vul ook een huisnummer in.", "Please add a house number.")
    postcode = (customer.get("postcode") or "").strip()
    if postcode and "postcode" not in errors:
        if is_netherlands(country):
            if not re.fullmatch(r"[1-9]\d{3}\s?[A-Za-z]{2}", postcode):
                errors["postcode"] = ("Vul een geldige Nederlandse postcode in, bijvoorbeeld 1234 AB.",
                                      "Enter a valid Dutch postal code, for example 1234 AB.")
        elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{1,9}", postcode):
            errors["postcode"] = ("Vul een geldige postcode in.", "Enter a valid postal code.")
    return errors


class PaymentProvider:
    """Aansluitpunt voor een latere betaalprovider. Doet bewust niets en rekent niets af."""

    name = "niet-gekoppeld"
    configured = False

    def create_payment(self, order_lines, customer):  # pragma: no cover - interface
        raise NotImplementedError("Er is nog geen betaalprovider gekoppeld.")

    def status(self):
        return {"provider": self.name, "configured": False,
                "shipping_costs": "nog niet bevestigd", "vat": "nog niet bevestigd",
                "payment_methods": []}


def order_summary(cart):
    """Regels en bedragen uit de server-side winkelwagen; geen verzonnen toeslagen."""
    lines = [{"id": i["id"], "qty": i["qty"], "unit": float(i["price"]),
              "line": round(float(i["price"]) * i["qty"], 2)} for i in cart]
    return {"lines": lines, "subtotal": round(sum(l["line"] for l in lines), 2),
            "shipping": None, "vat": None}
