"""Regression tests for TrendMix application boundary security."""
from html.parser import HTMLParser

from app import app, load_all_products


class PostFormAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.active = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "form":
            self.active = {"post": attrs.get("method", "get").lower() == "post", "csrf": False}
            self.forms.append(self.active)
        elif tag == "input" and self.active is not None and attrs.get("name") == "_csrf_token":
            self.active["csrf"] = bool(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = None


def test_csrf_rejects_missing_token_and_accepts_valid_form():
    client = app.test_client()
    product = load_all_products()[0]
    client.get("/")
    denied = client.post("/winkelwagen", data={"action": "add", "product_id": product["id"]})
    assert denied.status_code == 403
    with client.session_transaction() as saved:
        token = saved["_tm_csrf"]
    allowed = client.post("/winkelwagen", data={"action": "add", "product_id": product["id"], "_csrf_token": token})
    assert allowed.status_code == 302


def test_csrf_rejects_foreign_origin_even_with_token():
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as saved:
        token = saved["_tm_csrf"]
    blocked = client.post("/winkelwagen", data={"_csrf_token": token},
                          headers={"Origin": "https://malicious.example"})
    assert blocked.status_code == 403


def test_csrf_rejects_token_from_another_session():
    source = app.test_client()
    source.get("/")
    with source.session_transaction() as saved:
        foreign_token = saved["_tm_csrf"]
    recipient = app.test_client()
    recipient.get("/")
    blocked = recipient.post("/wishlist", data={"_csrf_token": foreign_token})
    assert blocked.status_code == 403


def test_checkout_does_not_store_personal_data_in_signed_cookie(monkeypatch):
    monkeypatch.delenv("TRENDMIX_LIVE_ORDERS", raising=False)
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as saved:
        token = saved["_tm_csrf"]
    product = load_all_products()[0]
    client.post("/winkelwagen", data={"_csrf_token": token, "action": "add", "product_id": product["id"]})
    result = client.post("/afrekenen", data={
        "_csrf_token": token,
        "first_name": "Test", "last_name": "Shopper", "email": "test@example.com",
        "address_1": "Example 1", "postcode": "1234 AB", "city": "Leiden",
        "country": "NL", "checkout_consent": "yes",
    })
    assert result.status_code == 200
    with client.session_transaction() as saved:
        assert "trendmix_test_checkout" not in saved


def test_security_headers_and_request_size_limit(monkeypatch):
    client = app.test_client()
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert app.config["MAX_CONTENT_LENGTH"] == 65536
    assert client.get("/winkelwagen").headers["Cache-Control"] == "no-store"
    monkeypatch.setenv("VERCEL_ENV", "production")
    assert "max-age=" in client.get("/", base_url="https://localhost").headers["Strict-Transport-Security"]
    oversized = client.post("/contact", data={"message": "A" * 70000})
    assert oversized.status_code == 413


def test_all_storefront_post_forms_include_csrf_tokens():
    client = app.test_client()
    for route in ("/", "/shop", "/gadgets", "/wishlist", "/winkelwagen",
                  "/contact", "/beauty-care/elektrische-gezichtsroller"):
        response = client.get(route)
        assert response.status_code == 200, route
        audit = PostFormAudit()
        audit.feed(response.get_data(as_text=True))
        assert all(not form["post"] or form["csrf"] for form in audit.forms), route


def test_dashboard_checks_primary_2fa_once_per_request(monkeypatch):
    from unittest.mock import Mock

    import nv_2fa_login

    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "fixture@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", "fixture-only")
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", False)
    check = Mock(side_effect=[True, RuntimeError("simulated database outage"), True])
    monkeypatch.setattr(nv_2fa_login, "is_2fa_actief", check)

    client = app.test_client()
    with client.session_transaction() as saved:
        saved["nv_admin"] = True

    first = client.get("/dashboard")
    assert first.status_code == 200
    assert b"Viral Product Finder" in first.data
    assert check.call_count == 1

    blocked = client.get("/dashboard")
    assert blocked.status_code == 302
    assert blocked.location == "/admin/login"
    assert check.call_count == 2

    assert client.get("/dashboard?section=viral").status_code == 200
    assert check.call_count == 3
