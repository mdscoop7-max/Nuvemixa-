import json
import re
from app import app, load_all_products


def test_shop_in_sitemap():
    response = app.test_client().get("/sitemap.xml")
    assert response.status_code == 200
    assert "/shop</loc>" in response.get_data(as_text=True)


def test_product_json_ld_has_absolute_urls():
    client = app.test_client()
    product = load_all_products()[0]
    response = client.get(product["product_url"])
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S)
    payloads = [json.loads(block) for block in blocks]
    product_schemas = [obj for obj in payloads if obj.get("@type") == "Product"]
    assert product_schemas
    schema = product_schemas[0]
    assert schema["url"].startswith("http")
    assert all(url.startswith("http") for url in schema["image"])
    assert "aggregateRating" not in schema
