"""Fast startup safeguards for static assets and above-the-fold banners."""
from app import app


def secure_post(client, *args, **kwargs):
    """Submit a real storefront CSRF token rather than bypassing protection."""
    client.get("/")
    with client.session_transaction() as data:
        csrf_token = data["_tm_csrf"]
    form = kwargs.pop("data", {}) or {}
    kwargs["data"] = {**form, "_csrf_token": csrf_token}
    return client.post(*args, **kwargs)


def test_static_browser_cache_and_private_pages():
    client = app.test_client()
    versioned = client.get("/static/storefront-v2.css?v=20261017-footer1")
    assert versioned.status_code == 200
    assert "immutable" in versioned.headers["Cache-Control"]
    assert "max-age=604800" in versioned.headers["Cache-Control"]

    unversioned = client.get("/static/trendmix-hero-fix.css")
    assert unversioned.status_code == 200
    assert "max-age=900" in unversioned.headers["Cache-Control"]

    hero = client.get("/static/images/hero/beauty-care.png")
    assert hero.status_code == 200
    assert "max-age=3600" in hero.headers["Cache-Control"]

    # Do not share cart state, customer pages or assistant answers via public caching.
    for path in ("/", "/winkelwagen", "/api/trendmix-assistant"):
        response = client.get(path)
        assert "public" not in response.headers.get("Cache-Control", "")


def test_visible_heroes_are_prioritized_without_changing_images():
    client = app.test_client()
    for path in ("/", "/gadgets", "/smart-home", "/beauty-care",
                 "/lifestyle-sport", "/shop", "/aanbiedingen"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'fetchpriority="high"' in response.get_data(as_text=True), path

    shop = client.get("/shop").get_data(as_text=True)
    offers = client.get("/aanbiedingen").get_data(as_text=True)
    assert 'rel="preload" as="image"' in shop
    assert 'rel="preload" as="image"' in offers


def test_shared_cart_footer_and_ai_trendmix_remain_everywhere():
    from app import load_all_products

    client = app.test_client()
    for path in ("/", "/gadgets", "/shop", "/aanbiedingen", "/winkelwagen",
                 "/contact", "/faq", "/privacy", "/wishlist"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert html.count('class="site-footer tm-footer tm-footer-v2"') == 1, path
        assert 'NUVEMIXA AI' in html, path

    # Checkout correctly redirects when the cart is empty. Populate a test
    # cart first so the actual checkout page is inspected, not the redirect.
    product = load_all_products()[0]
    secure_post(client, "/winkelwagen", data={"action": "add", "product_id": str(product["id"])})
    response = client.get("/afrekenen")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('class="site-footer tm-footer tm-footer-v2"') == 1
    assert 'NUVEMIXA AI' in html
