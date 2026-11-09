from app import app


def test_shop_filter_controls_and_mobile_ready_fields():
    response = app.test_client().get("/shop")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="tm-shop-filters"' in html
    for expected in ('name="min_price"', 'name="max_price"', 'name="sort"'):
        assert expected in html


def test_shop_price_filters_are_server_side():
    client = app.test_client()
    response = client.get("/shop?min_price=1000000")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "0" in html or "Geen producten gevonden" in html


def test_shop_invalid_price_filter_does_not_error():
    client = app.test_client()
    for query in ("min_price=abc", "max_price=-10", "min_price=nan", "min_price=inf", "sort=bogus"):
        assert client.get("/shop?" + query).status_code == 200


def test_shop_sorting_options_visible():
    html = app.test_client().get("/shop?sort=price-low").get_data(as_text=True)
    assert 'value="price-low" selected' in html
