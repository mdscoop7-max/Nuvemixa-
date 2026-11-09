from app import app


def test_shop_loads_filter_polish_styles_and_language_code():
    html = app.test_client().get("/shop").get_data(as_text=True)
    assert "trendmix-forms-polish.css" in html
    assert "app.js" in html
    assert 'class="tm-shop-filters"' in html
    assert 'name="min_price"' in html


def test_home_and_category_load_language_menu_code():
    for path in ("/", "/gadgets"):
        html = app.test_client().get(path).get_data(as_text=True)
        assert "trendmix-forms-polish.css" in html
        assert "app.js" in html
        assert 'data-language="en"' in html
        assert 'data-language="nl"' in html


def test_filter_styles_are_served():
    response = app.test_client().get("/static/trendmix-forms-polish.css")
    assert response.status_code == 200
    styles = response.get_data(as_text=True)
    assert "grid-template-columns" in styles
    assert ".tm-language-options button[data-language]" in styles
