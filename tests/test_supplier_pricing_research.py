"""Supplier price calculator and conservative product research regression checks."""
import base64
import pytest
from supplier_pricing import quote
from product_research import review_candidate
from app import app

def test_vat_and_margin_calculation_is_explicit():
    x=quote("10","3","1","0.30","2","21","30")
    assert x["price_inc_vat"] > x["price_ex_vat"]
    assert x["estimated_profit"] > 0
    assert x["vat_percent"] == 21

@pytest.mark.parametrize("value",["-1","NaN","Infinity","abc"])
def test_reject_unsafe_amounts(value):
    with pytest.raises(ValueError):
        quote(value,"3","1","0.3","2","21","30")

def test_market_probability_is_not_invented():
    x=review_candidate("Smart sensor","smart-home","","12","3","29","unknown","unknown","unknown")
    assert "Niet meetbaar" in x["sales_probability"]
    assert "Geen live" in x["supplier_comparison"]
    assert x["signals"]

def test_management_requires_authentication(monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER","tester")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD","a-strong-admin-password")
    monkeypatch.delenv("VERCEL_ENV",raising=False)
    client=app.test_client()
    for path in ("/beheer/productonderzoek","/beheer/prijsberekening"):
        assert client.get(path).status_code == 401
        hdr={"Authorization":"Basic "+base64.b64encode(b"tester:a-strong-admin-password").decode()}
        assert client.get(path,headers=hdr).status_code == 200
        assert client.post(path,headers=hdr,data={"name":"test"}).status_code == 403
