import re
from app import app, load_all_products


def test_demo_product_pages_are_not_indexable():
    product = load_all_products()[0]
    html = app.test_client().get(product["product_url"]).get_data(as_text=True)
    assert '<meta name="robots" content="noindex,follow">' in html
    assert '"aggregateRating"' not in html


def test_demo_products_not_in_sitemap():
    product = load_all_products()[0]
    sitemap = app.test_client().get("/sitemap.xml").get_data(as_text=True)
    assert product["product_url"] + "</loc>" not in sitemap
    assert "/shop</loc>" in sitemap


def test_cart_and_checkout_not_indexable():
    client = app.test_client()
    cart_html = client.get("/winkelwagen").get_data(as_text=True)
    assert '<meta name="robots" content="noindex,nofollow">' in cart_html
    assert "Productsubtotaal" in cart_html
    product = load_all_products()[0]
    client.get("/")
    with client.session_transaction() as state:
        token = state["_tm_csrf"]
    client.post("/winkelwagen", data={"action": "add", "product_id": product["id"], "_csrf_token": token})
    response = client.get("/afrekenen")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<meta name="robots" content="noindex,nofollow">' in html
    assert "verzendkosten en eventuele bijkomende kosten" in html.lower()
