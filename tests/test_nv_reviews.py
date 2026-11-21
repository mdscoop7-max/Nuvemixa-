import importlib

import pytest


@pytest.fixture()
def reviews(tmp_path, monkeypatch):
    import nv_reviews
    monkeypatch.setattr(nv_reviews, "REVIEWS_DB", tmp_path / "reviews.sqlite3")
    return nv_reviews


VALID = {"name": "Sanne", "email": "sanne@example.com", "rating": "5",
         "title": "Top product", "body": "Snel geleverd en werkt perfect.", "product": "Oplader"}


def test_new_review_is_pending_and_not_public(reviews):
    assert reviews.submit_review(VALID, consent=True) == "ok"
    assert reviews.published_reviews() == []
    assert reviews.review_stats()["count"] == 0
    rows = reviews.all_reviews()
    assert len(rows) == 1 and rows[0]["status"] == "wachtend"


def test_publish_reply_and_stats(reviews):
    reviews.submit_review(VALID, consent=True)
    reviews.submit_review({**VALID, "email": "b@example.com", "rating": "3"}, consent=True)
    for row in reviews.all_reviews():
        reviews.update_review(row["id"], "publiceren")
    first = reviews.all_reviews()[0]
    reviews.update_review(first["id"], "opslaan", reply="Dank je!", verified=True)
    public = reviews.published_reviews()
    assert len(public) == 2
    assert "email" not in public[0]
    stats = reviews.review_stats()
    assert stats["count"] == 2 and stats["average"] == 4.0
    assert any(r["reply"] == "Dank je!" and r["verified"] == 1 for r in public)


def test_invalid_and_consent_required(reviews):
    assert reviews.submit_review(VALID, consent=False) == "ongeldig"
    assert reviews.submit_review({**VALID, "rating": "9"}, consent=True) == "ongeldig"
    assert reviews.submit_review({**VALID, "email": "geen-email"}, consent=True) == "ongeldig"
    assert reviews.submit_review({**VALID, "body": "kort"}, consent=True) == "ongeldig"


def test_rate_limit_per_email(reviews):
    for _ in range(reviews.MAX_PER_DAY_PER_EMAIL):
        assert reviews.submit_review(VALID, consent=True) == "ok"
    assert reviews.submit_review(VALID, consent=True) == "limiet"


def test_hide_and_delete(reviews):
    reviews.submit_review(VALID, consent=True)
    rid = reviews.all_reviews()[0]["id"]
    reviews.update_review(rid, "publiceren")
    reviews.update_review(rid, "verbergen")
    assert reviews.published_reviews() == []
    reviews.update_review(rid, "verwijderen")
    assert reviews.all_reviews() == []
    with pytest.raises(ValueError):
        reviews.update_review(rid, "hacken")


def test_homepage_form_flow(reviews):
    from app import app
    client = app.test_client()
    home = client.get("/")
    assert home.status_code == 200
    html = home.get_data(as_text=True)
    assert 'id="reviews"' in html and "Nog geen reviews" in html and 'data-tm-en="What customers say"' in html
    with client.session_transaction() as data:
        token = data["_tm_csrf"]
    # zonder CSRF-token geweigerd
    assert client.post("/reviews", data={**VALID, "consent": "1"}).status_code == 403
    resp = client.post("/reviews", data={**VALID, "consent": "1", "_csrf_token": token})
    assert resp.status_code == 303 and "review=bedankt" in resp.headers["Location"]
    assert len(reviews.all_reviews()) == 1
    # honeypot slaat niets op
    client.post("/reviews", data={**VALID, "email": "bot@example.com", "consent": "1", "website": "spam", "_csrf_token": token})
    assert len(reviews.all_reviews()) == 1
    # na publiceren zichtbaar, e-mailadres nooit
    reviews.update_review(reviews.all_reviews()[0]["id"], "publiceren")
    html = client.get("/").get_data(as_text=True)
    assert "Top product" in html and "sanne@example.com" not in html


def test_admin_review_update_requires_login():
    from app import app
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as data:
        token = data["_tm_csrf"]
    assert client.post("/admin/reviews/1", data={"action": "publiceren", "_csrf_token": token}).status_code == 403
