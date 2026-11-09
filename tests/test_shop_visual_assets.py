"""Guard the previously missing shop CSS and language controls."""
from app import app


def test_storefront_pages_load_visual_polish_and_language_script():
    client = app.test_client()
    for path in ("/", "/shop", "/gadgets"):
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "trendmix-forms-polish.css" in html
        assert "storefront-language.js" in html


def test_filter_stylesheet_and_language_script_are_served():
    client = app.test_client()
    styles = client.get("/static/trendmix-forms-polish.css")
    language = client.get("/static/storefront-language.js")
    assert styles.status_code == 200
    assert language.status_code == 200
    assert b"tm-shop-filters" in styles.data
    assert b"data-language" in language.data
    assert b"aria-pressed" in language.data


def test_shop_filters_preserve_actual_get_form_and_labels():
    html = app.test_client().get("/shop").get_data(as_text=True)
    assert 'method="get"' in html
    for key in ('for="tmMinPrice"', 'for="tmMaxPrice"', 'for="tmSort"'):
        assert key in html
    assert 'class="tm-filter-submit"' in html
    assert 'Toepassen' in html


def test_hero_template_remains_independent_of_control_scripts():
    html = app.test_client().get("/").get_data(as_text=True)
    assert "storefront-language.js" in html
    assert "tm-global-language" in html
