from concurrent.futures import ThreadPoolExecutor
import re
from threading import Barrier, local

import pytest

from app import app
import nv_2fa_login
import nv_dashboard_manager as discounts


ROUTE = "/admin/nv/coupons"
CSRF_TOKEN = "coupon-test-token-" + "x" * 32


@pytest.fixture
def administrator(monkeypatch, tmp_path):
    monkeypatch.setattr(discounts, "DB", tmp_path / "dashboard.sqlite3")
    monkeypatch.setenv("SECRET_KEY", "fixture-only")
    monkeypatch.setenv("NUVEMIXA_ADMIN_EMAIL", "admin@example.invalid")
    monkeypatch.setenv("NUVEMIXA_ADMIN_PASSWORD_HASH", "fixture-only")
    monkeypatch.setattr(nv_2fa_login, "is_2fa_actief", lambda: True)
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", False)
    client = app.test_client()
    with client.session_transaction() as saved:
        saved["nv_admin"] = True
        saved["_tm_csrf"] = CSRF_TOKEN
    return client


def test_create_coupon_shows_code_and_keeps_legacy_rows(administrator, monkeypatch):
    with discounts.connect() as db:
        db.executemany("""INSERT INTO coupons(code,kind,amount,ends,usage_limit,used)
                          VALUES(?,?,?,?,?,?)""", [
            ("nv-AAAA-aaaa", "fixed", 3.5, None, 8, 2),
            ("LEGACY", "percent", 17.5, "2000-01-01", None, 0),
        ])
    choices = iter("AAAAAAAABBBBBBBB")
    monkeypatch.setattr(discounts.secrets, "choice", lambda alphabet: next(choices))

    page = administrator.get("/dashboard?section=kortingen")
    assert re.findall(rb'<option value="(\d+)">\d+%</option>', page.data) == [
        str(value).encode() for value in range(2, 21)
    ]
    response = administrator.post(ROUTE, data={
        "_csrf_token": CSRF_TOKEN, "op": "create", "percentage": "20",
        "code": "OVERRIDE", "kind": "fixed", "amount": "200",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'<code id="nv-created-coupon">NV-BBBB-BBBB</code>' in response.data
    assert "Kopiëren".encode() in response.data
    assert b"20%" in response.data and b"17.5%" in response.data and b"Verlopen" in response.data
    assert b"nv-AAAA-aaaa" in response.data

    rows = {row["code"]: row for row in discounts.coupon_rows()}
    assert set(rows) == {"nv-AAAA-aaaa", "LEGACY", "NV-BBBB-BBBB"}
    assert rows["nv-AAAA-aaaa"]["used"] == 2 and rows["nv-AAAA-aaaa"]["usage_limit"] == 8
    new = rows["NV-BBBB-BBBB"]
    assert (new["kind"], new["amount"], new["starts"], new["status"]) == ("percent", 20, None, "Actief")
    assert discounts.test_checkout_discount("nv-bbbb-bbbb", 1234) == 247
    assert discounts.test_checkout_discount("LEGACY", 1234) is None


def test_coupon_creation_rejects_invalid_amounts_and_checks_csrf_and_roles(administrator, monkeypatch):
    for percentage in ("", "1", "21", "19.5", "2.0", "2e0", "２０"):
        response = administrator.post(ROUTE, data={
            "_csrf_token": CSRF_TOKEN, "percentage": percentage,
        }, follow_redirects=True)
        assert b"Kies een heel percentage van 2% tot en met 20%" in response.data
    assert administrator.post(ROUTE, data={"percentage": "2"}).status_code == 403
    staff = app.test_client()
    with staff.session_transaction() as saved:
        saved["_tm_csrf"] = CSRF_TOKEN
    monkeypatch.setattr(discounts, "staff_current", lambda: {"role": "viewer", "permissions": "discount_view"})
    assert staff.post(ROUTE, data={"_csrf_token": CSRF_TOKEN, "percentage": "2"}).status_code == 403
    assert discounts.coupon_rows() == []
    assert administrator.post(ROUTE, data={"_csrf_token": CSRF_TOKEN, "percentage": "2"}).status_code == 303
    coupon = discounts.coupon_rows()[0]
    assert coupon["amount"] == 2
    for operation, status in (("disable", "Uitgeschakeld"), ("enable", "Actief")):
        assert administrator.post(ROUTE, data={
            "_csrf_token": CSRF_TOKEN, "id": coupon["id"], "op": operation,
        }).status_code == 303
        assert discounts.coupon_rows()[0]["status"] == status


def test_concurrent_creation_retries_a_colliding_code(administrator, monkeypatch):
    discounts.coupon_rows()
    barrier = Barrier(2)

    state = local()

    def use_candidates(letter):
        # Both threads first try the same code, then have separate retry candidates.
        state.letters = iter("AAAAAAAA" + letter * 8)
        with discounts.connect() as db:
            barrier.wait(timeout=5)
            return discounts.create_percentage_coupon(db, 10)

    monkeypatch.setattr(discounts.secrets, "choice", lambda alphabet: next(state.letters))
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = set(executor.map(use_candidates, ("B", "C")))
    assert "NV-AAAA-AAAA" in codes and len(codes) == 2
    assert {row["code"] for row in discounts.coupon_rows()} == codes
