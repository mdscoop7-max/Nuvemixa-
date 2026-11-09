"""Fail-closed TrendMix support triage based only on approved, static information.

This module never sends email, handles orders, accesses secrets, or decides refunds.
Questions about individual orders or unavailable facts require human review.
"""
import re

def classify_question(question):
    text = re.sub(r"\s+", " ", str(question or "").casefold()).strip()
    if not text or len(text) > 3000:
        return "human", "Ongeldige of te lange klantvraag"
    personal = ("bestelling", "bestelnummer", "pakket", "tracking", "track & trace",
                "bezorgdatum", "leverdatum", "waar blijft", "mijn order",
                "terugbetaling", "refund", "geld terug", "annuleren", "account",
                "wachtwoord", "factuur", "betaling", "klacht", "beschadigd",
                "adres wijzigen", "voorraad", "op voorraad")
    if any(word in text for word in personal):
        return "human", "Persoonlijke gegevens of onbevestigde bestel-/betaalinformatie vereist"
    if any(word in text for word in ("hoe kan ik contact", "contact opnemen", "klantenservice bereiken")):
        return "approved", "Verwijs naar de contactpagina op de webshop; vermeld geen onbevestigde contactgegevens."
    if any(word in text for word in ("welke categorie", "welke producten", "assortiment", "collecties")):
        return "approved", "TrendMix heeft categorieen Gadgets, Smart Home, Beauty & Care, Home & Living en Lifestyle & Sport. De catalogus is in test."
    return "human", "Geen bevestigd antwoord beschikbaar"

def customer_acknowledgment():
    return ("Bedankt voor je bericht aan TrendMix. We hebben je vraag ontvangen. "
            "Onze klantenservice bekijkt deze persoonlijk en reageert zodra er "
            "betrouwbare informatie beschikbaar is.\n\nMet vriendelijke groet,\nKlantenservice TrendMix")
