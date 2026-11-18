import re

import app as A
import nv_checkout as C


def _client():
    c = A.app.test_client()
    html = c.get("/winkelwagen").get_data(as_text=True)
    return c, re.search(r'name="_csrf_token" value="([^"]+)"', html) and None


def _token(c):
    c.get("/gadgets")
    with c.session_transaction() as s:
        return s["_tm_csrf"]


def _post(c, path, **data):
    data["_csrf_token"] = _token(c)
    return c.post(path, data=data, follow_redirects=True)


def _pid():
    return A.find_product("draadloze-oplader-3-in-1")["id"] if A.find_product("draadloze-oplader-3-in-1") else A.CATEGORIES[0]["products"][0]["id"]


def _any_ids():
    c = A.app.test_client()
    html = c.get("/gadgets").get_data(as_text=True)
    return re.findall(r'name="action" value="add"><input type="hidden" name="product_id" value="([^"]+)"', html)


def test_add_change_remove_and_totals():
    c = A.app.test_client()
    ids = _any_ids()
    assert len(ids) >= 2
    _post(c, "/winkelwagen", action="add", product_id=ids[0])
    _post(c, "/winkelwagen", action="add", product_id=ids[0])
    r = _post(c, "/winkelwagen", action="add", product_id=ids[1])
    assert r.status_code == 200
    with c.session_transaction() as s:
        cart = {i["id"]: i["qty"] for i in s["trendmix_cart"]}
    assert cart[ids[0]] == 2 and cart[ids[1]] == 1
    _post(c, "/winkelwagen", action="change", product_id=ids[0], delta="-1")
    _post(c, "/winkelwagen", action="change", product_id=ids[1], delta="-1")
    with c.session_transaction() as s:
        assert [i["id"] for i in s["trendmix_cart"]] == [ids[0]]
    _post(c, "/winkelwagen", action="remove", product_id=ids[0])
    html = c.get("/winkelwagen").get_data(as_text=True)
    assert "Verder winkelen" in html and 'href="/shop"' in html


def test_unavailable_product_gives_notice_and_is_not_added():
    c = A.app.test_client()
    html = _post(c, "/winkelwagen", action="add", product_id="bestaat-niet-999").get_data(as_text=True)
    assert "niet beschikbaar" in html
    with c.session_transaction() as s:
        assert not s.get("trendmix_cart")


def test_removed_product_in_session_is_dropped_with_notice():
    c = A.app.test_client()
    ids = _any_ids()
    _post(c, "/winkelwagen", action="add", product_id=ids[0])
    with c.session_transaction() as s:
        s["trendmix_cart"] = s["trendmix_cart"] + [{"id": "verdwenen-product", "qty": 1}]
    html = c.get("/winkelwagen").get_data(as_text=True)
    assert "niet meer beschikbaar" in html
    with c.session_transaction() as s:
        assert [i["id"] for i in s["trendmix_cart"]] == [ids[0]]


def test_cart_shows_no_invented_shipping_discount_or_vat_amounts():
    c = A.app.test_client()
    _post(c, "/winkelwagen", action="add", product_id=_any_ids()[0])
    html = c.get("/winkelwagen").get_data(as_text=True)
    assert "Verzendkosten en btw worden getoond zodra" in html
    assert "Verder naar afrekenen" in html or "checkoutProceed" in html


def test_validate_customer_rules():
    ok = {"first_name": "Jan", "last_name": "Jansen", "email": "jan@example.com", "address_1": "Teststraat 1",
          "postcode": "1234 AB", "city": "Teststad", "country": "Nederland"}
    assert C.validate_customer(ok) == {}
    bad = dict(ok, email="x", postcode="12", address_1="Teststraat")
    assert set(C.validate_customer(bad)) == {"email", "postcode", "address_1"}
    assert set(C.validate_customer({k: "" for k in ok})) == set(ok)
    assert C.validate_customer(dict(ok, country="Belgium", postcode="1000")) == {}


def test_checkout_test_mode_field_errors_and_no_real_order():
    c = A.app.test_client()
    _post(c, "/winkelwagen", action="add", product_id=_any_ids()[0])
    form = {"first_name": "A", "last_name": "B", "email": "bad", "address_1": "Straat 1", "postcode": "1234 AB",
            "city": "Stad", "country": "Nederland", "checkout_consent": "yes"}
    html = _post(c, "/afrekenen", **form).get_data(as_text=True)
    assert 'id="err-email"' in html and 'aria-invalid="true"' in html and 'role="alert"' in html
    form["email"] = "a@example.com"
    html = _post(c, "/afrekenen", **form).get_data(as_text=True)
    assert "Testbestelling gecontroleerd" in html


def test_payment_provider_placeholder_is_not_configured():
    st = C.PaymentProvider().status()
    assert st["configured"] is False and st["payment_methods"] == []
    assert C.order_summary([{"id": "x", "qty": 2, "price": 10}])["shipping"] is None


def test_english_dictionary_covers_ui_strings():
    js = open("static/trendmix-english-labels.js", encoding="utf-8").read()
    for s in ("Bewaar als favoriet", "Toevoegen", "Wat is NUVEMIXA?", "Besteloverzicht", "Controleer de gemarkeerde velden."):
        assert '"%s"' % s in js
    langs = open("static/languages.js", encoding="utf-8").read()
    for k in ("backToTrendmix", "faqTitle", "faqLead", "checkoutProceed"):
        assert langs.count(k + ":") >= 2
