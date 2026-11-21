import time

import pytest

import nv_reviews_sso as sso

SLEUTEL = "x" * 40


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("NUVEMIXA_REVIEWS_SSO_SECRET", SLEUTEL)
    return tmp_path / "sso.sqlite3"


def test_geldige_link_werkt_eenmalig(db):
    token = sso.maak_token()
    assert sso.controleer_token(token, db) is True
    assert sso.controleer_token(token, db) is False


def test_verlopen_link_geweigerd(db):
    token = sso.maak_token(nu=time.time() - 120)
    assert sso.controleer_token(token, db) is False


def test_vervalste_handtekening_geweigerd(db):
    exp, nonce, sig = sso.maak_token().split(".")
    assert sso.controleer_token(f"{exp}.{nonce}.{'0' * len(sig)}", db) is False
    assert sso.controleer_token(f"{int(exp) + 30}.{nonce}.{sig}", db) is False


def test_andere_sleutel_geweigerd(db, monkeypatch):
    token = sso.maak_token()
    monkeypatch.setenv("NUVEMIXA_REVIEWS_SSO_SECRET", "y" * 40)
    assert sso.controleer_token(token, db) is False


def test_zonder_sleutel_uitgeschakeld(tmp_path, monkeypatch):
    monkeypatch.delenv("NUVEMIXA_REVIEWS_SSO_SECRET", raising=False)
    assert sso.ingeschakeld() is False
    assert sso.controleer_token("1.2.3", tmp_path / "x.sqlite3") is False
    monkeypatch.setenv("NUVEMIXA_REVIEWS_SSO_SECRET", "kort")
    assert sso.ingeschakeld() is False


def test_ontvanger_route(db):
    from flask import Flask, session
    app = Flask(__name__)
    app.secret_key = "t"
    sso.registreer_ontvanger(app, db)
    c = app.test_client()
    assert c.get("/admin/reviews/sso?t=fout").status_code == 403
    r = c.get("/admin/reviews/sso?t=" + sso.maak_token())
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/reviews")
    with c.session_transaction() as s:
        assert s.get("nv_admin") is True


def test_render_route_vereist_login(monkeypatch):
    monkeypatch.setenv("NUVEMIXA_REVIEWS_SSO_SECRET", SLEUTEL)
    from app import app
    r = app.test_client().get("/admin/reviews-beheren")
    assert r.status_code == 302 and "alwaysdata" not in r.headers["Location"]


def test_sleutel_uit_bestand(tmp_path, monkeypatch):
    monkeypatch.delenv("NUVEMIXA_REVIEWS_SSO_SECRET", raising=False)
    bestand = tmp_path / ".nv_reviews_sso_secret"
    bestand.write_text("k" * 40)
    monkeypatch.setattr(sso, "SLEUTELBESTAND", bestand)
    assert sso.ingeschakeld() is True
    assert sso.controleer_token(sso.maak_token(), tmp_path / "db.sqlite3") is True
