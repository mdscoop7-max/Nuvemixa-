from app import app


def test_account_page_shows_real_registration_without_claiming_live_orders():
    response = app.test_client().get("/account")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Account aanmaken" in html
    assert 'href="/registreren"' in html
    assert 'href="/inloggen"' in html
    assert "betaling" in html.lower()
    assert 'type="password"' not in html
    assert response.headers.get("Cache-Control") == "no-store"


def test_customer_orders_are_not_exposed_on_account():
    html = app.test_client().get("/account").get_data(as_text=True)
    assert "testfunctionaliteiten" in html.lower()
    assert "betaling" in html.lower()
