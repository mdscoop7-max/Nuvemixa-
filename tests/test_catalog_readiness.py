from catalog_readiness import review_product


def complete_product():
    return {
        "supplier_id": "supplier-01",
        "supplier_name": "Verified Supplier",
        "sku": "ABC-01",
        "name": "Demo Example",
        "description": "Confirmed specifications from supplier",
        "image_url": "https://example.com/product.jpg",
        "currency": "EUR",
        "selling_price": "39.95",
        "purchase_price": "18.00",
        "shipping_cost": "4.50",
        "stock_status": "in_stock",
        "delivery_days_min": 2,
        "delivery_days_max": 5,
        "returns_policy_url": "https://example.com/returns",
        "product_url": "https://example.com/product",
        "supplier_approved": True,
        "image_rights_confirmed": True,
        "claims_verified": True,
        "tax_and_fees_reviewed": True,
    }


def test_complete_verified_product_is_ready():
    result = review_product(complete_product())
    assert result["ready"] is True
    assert result["issues"] == []
    assert result["contribution_before_ads"] == "17.45"


def test_missing_supplier_facts_block_ads():
    result = review_product({"name": "Unknown"})
    assert not result["ready"]
    assert "missing:supplier_id" in result["issues"]
    assert "not_verified:claims_verified" in result["issues"]


def test_unverified_stock_and_images_block_ads():
    product = complete_product()
    product["stock_status"] = "unknown"
    product["image_url"] = "http://example.com/temporary.jpg"
    product["image_rights_confirmed"] = False
    result = review_product(product)
    assert not result["ready"]
    assert "unverified_stock" in result["issues"]
    assert "invalid_https_url:image_url" in result["issues"]
    assert "not_verified:image_rights_confirmed" in result["issues"]


def test_negative_cost_and_invalid_delivery_window_block_ads():
    product = complete_product()
    product["purchase_price"] = "-3"
    product["delivery_days_min"] = 8
    product["delivery_days_max"] = 2
    result = review_product(product)
    assert not result["ready"]
    assert "invalid_amount:purchase_price" in result["issues"]
    assert "invalid_delivery_window" in result["issues"]
    assert result["contribution_before_ads"] is None
