import re
from app import app


def test_primary_navigation_highlights_only_current_category():
    client = app.test_client()
    categories = ("gadgets", "smart-home", "beauty-care", "home-living", "lifestyle-sport")
    for current in categories:
        response = client.get("/" + current)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for category in categories:
            matches = re.findall(r'<a\s+href="/' + re.escape(category) + r'"[^>]*>', html)
            assert matches, (current, category)
            selected = any('aria-current="page"' in item for item in matches)
            assert selected == (category == current), (current, category)


def test_homepage_does_not_preselect_gadgets():
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'href="/gadgets" class="nav-link is-active"' not in html
    assert 'href="/gadgets" class="selected"' not in html
