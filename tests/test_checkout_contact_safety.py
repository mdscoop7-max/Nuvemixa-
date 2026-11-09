from app import app, load_all_products


def secure_post(client, path, data):
    client.get("/")
    with client.session_transaction() as state:
        token = state["_tm_csrf"]
    return client.post(path, data={**data, "_csrf_token": token})


def test_cart_ignores_tampered_price_and_clamps_quantities():
    client = app.test_client()
    product = load_all_products()[0]
    with client.session_transaction() as state:
        state["trendmix_cart"] = [{"id": product["id"], "qty": 99999, "price": -99.0},
                                  {"id": "does-not-exist", "qty": 99}]
    response = client.get("/winkelwagen")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert product["name"] in html
    assert "99999" not in html
    assert "Productsubtotaal" in html
    assert "Betalen is nog niet mogelijk" in html


def test_cart_add_change_and_remove_with_csrf():
    client = app.test_client()
    product = load_all_products()[0]
    assert secure_post(client, "/winkelwagen", {"action": "add", "product_id": product["id"]}).status_code == 302
    assert secure_post(client, "/winkelwagen", {"action": "change", "product_id": product["id"], "delta": "1000"}).status_code == 302
    with client.session_transaction() as state:
        assert state["trendmix_cart"][0]["qty"] == 99
    assert secure_post(client, "/winkelwagen", {"action": "remove", "product_id": product["id"]}).status_code == 302
    with client.session_transaction() as state:
        assert state["trendmix_cart"] == []


def test_checkout_is_explicitly_test_only(monkeypatch):
    monkeypatch.delenv("TRENDMIX_LIVE_ORDERS", raising=False)
    client = app.test_client()
    product = load_all_products()[0]
    secure_post(client, "/winkelwagen", {"action": "add", "product_id": product["id"]})
    html = client.get("/afrekenen").get_data(as_text=True)
    assert "Testcheckout controleren" in html
    assert "gebruik uitsluitend fictieve" in html
    assert "Productsubtotaal" in html
    assert "Verzending" in html
    assert "Wordt later bepaald" in html


def test_contact_does_not_claim_message_sent_without_email_setup(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("CONTACT_FROM_EMAIL", raising=False)
    client = app.test_client()
    response = secure_post(client, "/contact", {"name": "Voorbeeld", "email": "test@example.test", "message": "Test bericht"})
    assert response.status_code == 302
    assert "status=unavailable" in response.location
