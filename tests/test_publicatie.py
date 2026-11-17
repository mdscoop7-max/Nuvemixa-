import pytest
from decimal import Decimal

import app as dashboard
import nv_publicatie as pub
from test_system_check import administrator, CSRF_TOKEN
from test_staff_access import staffdb, staff_client, login  # noqa: F401
import nv_dashboard_manager as manager

P1, P2, P3 = (pub.TEST_CANDIDATES[k] for k in ("TEST-P1", "TEST-P2", "TEST-P3"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    def refuse(*a, **k):
        raise AssertionError("netwerkaanroep tijdens test")
    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)
    monkeypatch.setattr(requests, "put", refuse)
    monkeypatch.delenv(pub.WRITE_SWITCH, raising=False)
    for key in ("NUVEMIXA_WOO_URL", "NUVEMIXA_WOO_KEY", "NUVEMIXA_WOO_SECRET", "NUVEMIXA_WOO_HOST"):
        monkeypatch.delenv(key, raising=False)


def failing(rows):
    return {r["stap"] for r in pub.blocking(rows)}


def test_margin_calculation():
    m = pub.margin(P1)
    assert m["netto_verkoop"] == 2475 and m["procent"] == Decimal("39.3")
    assert pub.margin(P3)["procent"] < 0 and pub.margin({"verkoop": 0}) is None


def test_checks_pass_fail_and_duplicates():
    assert failing(pub.check(P1, pub.TEST_EXISTING)) == set()
    assert failing(pub.check(P2, pub.TEST_EXISTING)) == {"Bestaat al in WooCommerce"}
    assert failing(pub.check(P3, [])) == {"Winstmarge", "Producttitel", "Beschrijving", "Afbeeldingen"}
    assert pub.find_duplicates(dict(P1, sku="x-1", titel="  testproduct SLIMME plug "), pub.TEST_EXISTING)[0]["reden"] == "zelfde titel"


def test_low_margin_is_a_warning_not_an_error():
    low = dict(P1, verkoop=1990)
    status = {r["stap"]: r["status"] for r in pub.check(low, [])}
    assert status["Winstmarge"] == "let op" and pub.margin(low)["procent"] < pub.MIN_MARGE


def test_image_urls_must_be_https_images_and_are_never_fetched():
    for bad in ("http://x.example.invalid/a.jpg", "https://user:pw@x.example.invalid/a.jpg", "https://x.example.invalid/a.exe", "javascript:alert(1)"):
        assert not pub._https_image(bad)
    assert pub._https_image("https://x.example.invalid/a.WEBP")


def test_payload_is_always_a_draft():
    payload = pub.payload(P1)
    assert payload["status"] == "draft" and payload["regular_price"] == "29.95" and payload["sku"] == "TEST-P1"


def test_approval_is_bound_to_content_and_expires():
    token = pub.sign_approval("geheim", P1, now=1000)
    assert pub.approval_valid("geheim", P1, token, now=1100)
    assert not pub.approval_valid("geheim", dict(P1, verkoop=3000), token, now=1100)
    assert not pub.approval_valid("ander", P1, token, now=1100)
    assert not pub.approval_valid("geheim", P1, token, now=1000 + pub.APPROVAL_VALID_SECONDS + 1)
    assert not pub.approval_valid("geheim", P1, "kapot", now=1100) and not pub.approval_valid("geheim", P1, None)


def test_publish_is_refused_without_approval_connection_or_sender(monkeypatch):
    sent = []
    sender = lambda payload: sent.append(payload) or {"id": 1}
    token = pub.sign_approval("geheim", P1)
    with pytest.raises(pub.PublishRefused, match="goedkeuring"):
        pub.publish(P1, [], "geheim", "", sender=sender)
    with pytest.raises(pub.PublishRefused, match="schrijfkoppeling"):
        pub.publish(P1, [], "geheim", token, sender=sender)          # schakelaar uit
    monkeypatch.setenv(pub.WRITE_SWITCH, "on")
    with pytest.raises(pub.PublishRefused, match="schrijfkoppeling"):
        pub.publish(P1, [], "geheim", token, sender=None)            # geen zender
    with pytest.raises(pub.PublishRefused, match="fouten"):
        pub.publish(P2, pub.TEST_EXISTING, "geheim", pub.sign_approval("geheim", P2), sender=sender)
    assert sent == []
    assert pub.publish(P1, [], "geheim", token, sender=sender) == {"id": 1} and sent[0]["status"] == "draft"


def test_publication_page_labels_testdata_and_sends_nothing(administrator):
    text = administrator.get("/dashboard?section=publicatie").get_data(as_text=True)
    assert "TESTDATA" in text and "nog niet gekoppeld" in text and "niets naar de echte webshop" in text
    assert "TEST-P2" in administrator.get("/dashboard?section=publicatie&kandidaat=TEST-P2").get_data(as_text=True)


def test_approve_then_publish_flow_in_routes(administrator):
    data = {"_csrf_token": CSRF_TOKEN, "sku": "TEST-P1"}
    assert administrator.post("/admin/nv/publicatie/publiceren", data=data).status_code == 303
    page = administrator.get("/dashboard?section=publicatie&kandidaat=TEST-P1").get_data(as_text=True)
    assert "Nog niet goedgekeurd" in page
    assert administrator.post("/admin/nv/publicatie/goedkeuren", data=data).status_code == 303
    page = administrator.get("/dashboard?section=publicatie&kandidaat=TEST-P1").get_data(as_text=True)
    assert "Goedgekeurd door jou" in page
    publish = administrator.post("/admin/nv/publicatie/publiceren", data=data)   # geen schakelaar, geen zender
    assert publish.status_code == 303
    assert "niet verzonden" in administrator.get("/dashboard?section=publicatie&kandidaat=TEST-P1").get_data(as_text=True).lower()


def test_cannot_approve_product_with_errors(administrator):
    administrator.post("/admin/nv/publicatie/goedkeuren", data={"_csrf_token": CSRF_TOKEN, "sku": "TEST-P2"})
    assert "Nog niet goedgekeurd" in administrator.get("/dashboard?section=publicatie&kandidaat=TEST-P2").get_data(as_text=True)
    assert administrator.post("/admin/nv/publicatie/goedkeuren", data={"_csrf_token": CSRF_TOKEN, "sku": "ONBEKEND"}).status_code == 404


def test_publication_routes_are_owner_only(staffdb, monkeypatch):
    monkeypatch.setenv(manager.STAFF_SWITCH, "on")
    for client in (dashboard.app.test_client(), staff_client(staffdb, "beheerder"), staff_client(staffdb, "medewerker")):
        for route in ("/admin/nv/publicatie/goedkeuren", "/admin/nv/publicatie/publiceren"):
            assert client.post(route, data={"_csrf_token": CSRF_TOKEN, "sku": "TEST-P1"}).status_code in (302, 303, 403)
        assert client.get("/dashboard?section=publicatie").status_code in (302, 303, 403)
