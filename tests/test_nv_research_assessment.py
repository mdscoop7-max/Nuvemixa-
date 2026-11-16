"""Regression tests for sourced identity, safety, and decision outcomes."""
from datetime import date, timedelta

from nv_product_discovery import unique_suppliers
from nv_research_assessment import CHECKS, FINANCE, Fact, assess_offer
from nv_research_identity import approved_catalogue_identity, company_key
from nv_research_safety import REPORTS, gtin, recent_alerts
from nv_research_sources import supplier

SOURCE = "https://partner.example/products/offer"
TODAY = date.today().isoformat()


def complete_facts():
    amounts = {"market_price": "50.00", "purchase": "14.00", "shipping": "4.00", "advertising": "3.00",
               "transactions": "1.50", "returns": "1.50", "other": "0.50", "vat": "21"}
    return {key: Fact(amounts[key], SOURCE, TODAY, "" if key == "vat" else "EUR")
            if key in FINANCE else Fact(True, SOURCE, TODAY) for key in CHECKS}


def test_evidence_complete_incomplete_and_unsuitable():
    item = {"facts": complete_facts()}
    result = assess_offer(item, None, "NL", [])
    assert result["status"] == "Geschikt" and result["scenario"]["profit"] == "16.82"

    facts = dict(item["facts"])
    facts.pop("purchase")
    result = assess_offer({"facts": facts}, None, "NL", [])
    assert result["status"] == "Nader onderzoeken" and result["scenario"] is None and result["indicative"] is None
    assert "Zakelijke inkoopprijs" in result["missing"]

    for blocker in ("direct_delivery", "dropshipping", "compliance"):
        result = assess_offer({"facts": {**item["facts"], blocker: Fact(False, SOURCE, TODAY)}}, None, "NL", [])
        assert result["status"] == "Ongeschikt"

    costly = assess_offer({"facts": {**item["facts"], "purchase": Fact("75.00", SOURCE, TODAY, "EUR")}}, None, "NL", [])
    assert costly["status"] == "Ongeschikt" and costly["scenario"]["profit"].startswith("-")


def test_purchase_scenario_and_stale_or_foreign_currency_values_never_certify_offer():
    euro = Fact("14.00", SOURCE, TODAY, "EUR")
    result = assess_offer({"facts": {"purchase": euro}}, None, "NL", [])
    assert result["status"] == "Nader onderzoeken"
    assert result["indicative"] and result["scenario"] is None

    usd = assess_offer({"facts": {**complete_facts(), "purchase": Fact("14.00", SOURCE, TODAY, "USD")}}, None, "NL", [])
    assert usd["status"] == "Nader onderzoeken" and usd["indicative"] is None and usd["scenario"] is None

    old = (date.today() - timedelta(days=91)).isoformat()
    stale = assess_offer({"facts": {**complete_facts(), "purchase": Fact("14.00", SOURCE, old, "EUR")}}, None, "NL", [])
    assert stale["status"] == "Nader onderzoeken" and "Zakelijke inkoopprijs" in stale["missing"]


def test_identity_aliases_group_offers_without_merging_distinct_companies():
    main = supplier("UGREEN", "CN", "Fabrikant", "https://www.ugreen.com/pages/wholesale-program",
                    identity=approved_catalogue_identity("UGREEN"))
    alias = supplier("UGREEN EU", "CN", "Fabrikant", "https://eu.ugreen.com/pages/wholesale-program",
                     identity=approved_catalogue_identity("UGREEN EU"))
    dealer = supplier("UGREEN", "NL", "Distributeur", "https://dealer.example/products",
                      registration=("NL", "12345678"))
    another = supplier("UGREEN", "NL", "Distributeur", "https://dealer.example/products",
                       registration=("NL", "87654321"))
    shared = gtin("6977196683871")
    first = {"url": "https://www.ugreen.com/products/a", "gtin": shared}
    regional = {"url": "https://eu.ugreen.com/products/a", "gtin": shared}
    other = {"url": "https://eu.ugreen.com/products/b"}
    companies = unique_suppliers([(main, first), (alias, regional), (alias, other), (dealer, first), (another, first)], "all")
    assert [c["product_count"] for c in companies] == [2, 1, 1]
    assert company_key(dealer) != company_key(another)
    assert company_key(main) == company_key(alias)
    a = supplier("Same name Ltd", None, "Marketplace", "https://syncee.com/supplier/17/alias")
    b = supplier("Same name Ltd", None, "Marketplace", "https://syncee.com/supplier/18/alias")
    assert company_key(a) != company_key(b)


def test_safety_gate_exact_barcode_and_batch_limited_alert():
    raw = "6977196683871"
    code = gtin(raw)
    assert code and gtin(raw[:-1] + "2") is None
    alert_url = "https://ec.europa.eu/safety-gate-alerts/screen/webReport/alertDetail/42"
    stamp = date.today().strftime("%d-%m-%Y")
    report = f"""<Safety-Gate><notifications><caseNumber>SR/00001/26</caseNumber>
    <publicationDate>{stamp}</publicationDate><reference>{alert_url}</reference>
    <barcode>{raw}</barcode><riskType>Fires</riskType><batchNumber>123</batchNumber>
    </notifications></Safety-Gate>""".encode()
    index = b"""<Safety-Gate><weeklyReport><URL>https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/detail/xml/42</URL></weeklyReport>
    <weeklyReport><URL>https://evil.example/safety-gate-alerts/api/download/weeklyReport/detail/xml/42</URL></weeklyReport></Safety-Gate>"""

    def read(fetch, url, params, **kwargs):
        if url == REPORTS:
            return index
        assert url == "https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/detail/xml/42"
        return report

    alerts, weeks = recent_alerts(None, read, {code, gtin("5054298241091")})
    assert weeks == 1 and set(alerts) == {code}
    assert assess_offer({"facts": complete_facts()}, None, "NL", [], alerts[code])["status"] == "Nader onderzoeken"
    generic = {**alerts[code], "batch_limited": False}
    assert assess_offer({"facts": complete_facts()}, None, "NL", [], generic)["status"] == "Ongeschikt"
