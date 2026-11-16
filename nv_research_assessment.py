"""Evidence-based assessment of a specific product offer for NUVEMIXA."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from nv_product_margin import automatic_margin, calculate_margin


SAFETY_GATE = "https://ec.europa.eu/safety-gate-alerts/screen/webReport"


@dataclass(frozen=True)
class Fact:
    value: object
    source: str
    observed: str
    unit: str = ""

    def __post_init__(self):
        url = urlsplit(self.source)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Bewijs vereist een geldige HTTPS-bron.")
        date.fromisoformat(self.observed)


CHECKS = {
    "identity": "Identiteit leverancier",
    "business": "Zakelijke samenwerking",
    "dropshipping": "Dropshipping voor dit aanbod",
    "direct_delivery": "Rechtstreekse levering aan klant",
    "purchase": "Zakelijke inkoopprijs",
    "market_price": "Vergelijkbare verkoopprijs",
    "shipping": "Verzendkosten",
    "advertising": "Advertentiekosten",
    "transactions": "Transactiekosten",
    "returns": "Retourkosten",
    "other": "Overige kosten inclusief eventuele invoerkosten",
    "vat": "Btw-aanname voor het doelland",
    "market_signal": "Marktsignaal voor dit model",
    "compliance": "Veiligheids- en conformiteitsdocumentatie",
}
FINANCE = {
    "market_price": "selling_price", "purchase": "purchase_cost", "shipping": "shipping_cost",
    "advertising": "advertising_cost", "transactions": "platform_fee", "returns": "returns_reserve",
    "other": "other_cost", "vat": "vat_rate",
}


def assess_offer(item, company, country, publications, alert=None, safety_weeks=0):
    """Missing or expired SKU evidence cannot make an offer suitable."""
    recorded = item.get("facts", {})
    today = date.today()
    facts = {
        name: fact for name, fact in recorded.items()
        if name in CHECKS and isinstance(fact, Fact)
        and today - timedelta(days=90) <= date.fromisoformat(fact.observed) <= today
    }
    if company and company.get("identity") and company.get("identity_source"):
        facts.setdefault("identity", Fact(True, company["identity_source"], company["checked"]))
    if company and company.get("business") is True:
        facts.setdefault("business", Fact(True, company["website"], company["checked"]))
    if company and company.get("dropshipping") is False:
        source = company.get("dropshipping_source")
        if source:
            facts["dropshipping"] = Fact(False, source, company["checked"])

    if alert and alert["batch_limited"]:
        assessment = ("Nader onderzoeken", "Safety Gate meldt dit product. Controleer eerst partij- of productiegegevens.")
    elif alert:
        assessment = ("Ongeschikt", "Safety Gate meldt een risico voor de exacte productidentificatie.")
    elif "dropshipping" in facts and facts["dropshipping"].value is False:
        assessment = ("Ongeschikt", "Deze aanbieder vermeldt dat dropshipping niet beschikbaar is.")
    elif "direct_delivery" in facts and facts["direct_delivery"].value is False:
        assessment = ("Ongeschikt", "De bron sluit rechtstreekse levering aan het gekozen doelland uit.")
    elif "compliance" in facts and facts["compliance"].value is False:
        assessment = ("Ongeschikt", "De gecontroleerde bron vermeldt ontbrekende of afgekeurde conformiteit voor dit aanbod.")
    else:
        assessment = None

    scenario = None
    if FINANCE.keys() <= facts.keys() and all(facts[key].unit == "EUR" for key in FINANCE if key != "vat"):
        try:
            scenario = calculate_margin({target: facts[key].value for key, target in FINANCE.items()})
        except ValueError:
            pass
    indicative = None
    if scenario is None and "purchase" in facts and facts["purchase"].unit == "EUR" and country == "NL":
        try:
            indicative = automatic_margin(facts["purchase"].value)
        except ValueError:
            pass

    missing = [label for key, label in CHECKS.items() if key not in facts]
    pending = [CHECKS[key] for key in ("identity", "business", "dropshipping", "direct_delivery", "market_signal", "compliance")
               if key in facts and facts[key].value is not True]
    missing.extend(label for label in pending if label not in missing)
    if FINANCE.keys() <= facts.keys() and scenario is None:
        missing.append("Bruikbare bedragen voor het kostenscenario")
    if assessment is None:
        if scenario and Decimal(scenario["profit"]) <= 0:
            assessment = ("Ongeschikt", "Het kostenscenario op basis van de beschikbare vergelijkingsprijs houdt geen positieve winst over.")
        elif not missing and scenario:
            assessment = ("Geschikt", "Zakelijke levering en veiligheidsdocumentatie zijn onderbouwd. Het kostenscenario is positief.")
        else:
            assessment = ("Nader onderzoeken", "Controleer eerst: " + ", ".join(missing[:3]).lower() + ".")

    evidence = [(CHECKS[key], fact) for key, fact in facts.items()]
    related = [article for article in publications if article["date"] >= (today - timedelta(days=365)).isoformat()][:2]
    return {
        "status": assessment[0], "reason": assessment[1], "facts": evidence, "missing": missing,
        "scenario": scenario, "indicative": indicative, "market_context": related,
        "safety_portal": SAFETY_GATE, "alert": alert, "safety_weeks": safety_weeks,
    }
