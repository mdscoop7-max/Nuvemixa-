"""Verbreding en rangschikking van leveranciers: Syncee-aanbiedingsgegevens, sortering, samenvatting en weergave."""
from datetime import date

from flask import Flask, render_template_string

import nv_product_rows
from nv_product_discovery import relevance_for, unique_suppliers
from nv_research_assessment import Fact
from nv_research_sources import supplier, syncee_offer_facts

URL = "https://syncee.com/product/1_2_3/dog-leash"


def states(record, currency="USD"):
    return {"a": {"u": "https://entry.syncee.com/syncee-user-service/Supplier?userId=1", "b": [{**record, "paymentCurrency": currency}]}}


def product(prices=(9.6,), show=True):
    return {"USER_ID": 1, "SETTINGS": {"showPrices": show}, "VARIANTS": [{"PRICE": p} for p in prices]}


def test_offer_facts_use_only_published_data():
    record = {"website": "www.shop.example", "companyName": "Shop BV", "publicPhoneCode": "+31",
              "publicPhoneNumber": "201234567", "contactEmail": "info@shop.example", "mainWarehouseLocation": "Netherlands"}
    out = syncee_offer_facts(states(record), product((12.5, 9.6)), URL)
    assert out["purchase"].value == 9.6 and out["purchase"].unit == "USD"
    assert out["purchase_label"] == "USD 9,60 (vanaf)"
    assert out["own_website"] == "https://www.shop.example"
    assert out["phone"] == "+31 201234567" and out["email"] == "info@shop.example"


def test_offer_facts_never_guess():
    # Prijzen verborgen, geen valuta, gratis mailadres op ander domein, Syncee als 'website': niets overnemen.
    record = {"website": "syncee.com/shop", "contactEmail": "x@gmail.com", "publicPhoneCode": "31", "publicPhoneNumber": "abc"}
    assert "purchase" not in syncee_offer_facts(states(record), product(show=False), URL)
    assert "purchase" not in syncee_offer_facts(states(record, currency=None), product(), URL)
    out = syncee_offer_facts(states(record), product(), URL)
    assert not {"own_website", "email", "phone"} & out.keys()
    gmail = syncee_offer_facts(states({"website": "www.shop.example", "contactEmail": "shop@gmail.com"}), product(), URL)
    assert "email" not in gmail and gmail["own_website"] == "https://www.shop.example"


def _offer(name, origin, url, **extra):
    profile = supplier(name, origin, "Leverancier via Syncee", "https://syncee.com/supplier/" + name,
                       identity="syncee:" + name, identity_source="https://syncee.com/supplier/" + name, **extra)
    return profile, {"title": name + " dog leash", "url": url, "category": "pets"}


def test_confirmed_dropshipping_ranks_first_and_products_do_not_inflate_suppliers():
    plain = _offer("aaa", "NL", "https://syncee.com/product/1/a")
    drop = _offer("bbb", "CN", "https://syncee.com/product/2/b", dropshipping=True,
                  dropshipping_source="https://syncee.com/product/2/b")
    more = (plain[0], {"title": "aaa dog leash red", "url": "https://syncee.com/product/1/c", "category": "pets"})
    companies = unique_suppliers([plain, drop, more], "all")
    assert [c["name"] for c in companies][0].casefold().startswith("bbb")
    summary = nv_product_rows.summary(companies)
    assert summary["suppliers"] == 2 and summary["products"] == 3 and summary["dropship"] == 1


def test_known_purchase_price_shown_per_supplier():
    profile, item = _offer("ccc", "DE", "https://syncee.com/product/3/c")
    item["facts"] = {"purchase": Fact(7.5, "https://syncee.com/product/3/c", date.today().isoformat(), "EUR")}
    company = unique_suppliers([(profile, item)], "all")[0]
    assert company["purchase_price"] == "EUR 7,50 (via Syncee)"
    row = nv_product_rows.suppliers([company])[0]
    assert row["offers"][0]["price"] == "Inkoop € 7,50 (via Syncee)"
    assert nv_product_rows.summary([company])["priced"] == 1


def test_variants_grouped_and_max_two_products_visible():
    items = [{"title": t, "url": f"https://x.example/{i}"} for i, t in
             enumerate(["Dog leash black", "Dog leash white", "Cat bowl", "Pet brush", "Dog collar"])]
    groups = nv_product_rows.offer_groups(items)
    assert groups[0]["variants"] == 2 and len(groups) == 4
    app = Flask(__name__, template_folder="../templates")
    with app.test_request_context():
        html = render_template_string(
            "{% from '_product_rows.html' import supplier_rows %}{{ supplier_rows(rows, 'x') }}",
            rows=[{"name": "Shop", "role": "Leverancier", "offers": groups, "products": 5, "origin": "NL",
                   "dropship": "Niet bevestigd", "shipping_nl": "Niet bevestigd", "shop_notice": "Winkel of merk — geen bevestigde dropshipper"}])
    assert "Meer producten tonen (2)" in html and "(2 varianten)" in html
    assert "geen bevestigde dropshipper" in html


def test_sunglasses_are_lifestyle_results():
    assert relevance_for("Zonnebril")("lifestyle-sport", "Polarized Sunglasses UV400")
