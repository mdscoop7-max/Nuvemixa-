"""Readiness checks for verified supplier products before paid advertising.

This module does not change the visible demo catalogue, checkout or payment flow.
Only explicitly verified supplier data may qualify for a launch shortlist.
"""
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

REQUIRED = (
    "supplier_id", "supplier_name", "sku", "name", "description",
    "image_url", "currency", "selling_price", "purchase_price",
    "shipping_cost", "stock_status", "delivery_days_min",
    "delivery_days_max", "returns_policy_url", "product_url",
)

ALLOWED_STOCK = {"in_stock", "out_of_stock"}
ALLOWED_CURRENCY = {"EUR"}


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _https_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value.strip())
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username


def review_product(product):
    """Return a non-invasive readiness report; never invent absent facts."""
    if not isinstance(product, dict):
        return {"ready": False, "issues": ["invalid_product_record"], "contribution_before_ads": None}
    issues = [f"missing:{key}" for key in REQUIRED if product.get(key) is None or product.get(key) == ""]
    for key in ("image_url", "returns_policy_url", "product_url"):
        if product.get(key) and not _https_url(product[key]):
            issues.append(f"invalid_https_url:{key}")
    if product.get("currency") and product["currency"] not in ALLOWED_CURRENCY:
        issues.append("unsupported_currency")
    if product.get("stock_status") and product["stock_status"] not in ALLOWED_STOCK:
        issues.append("unverified_stock")
    if product.get("stock_status") == "out_of_stock":
        issues.append("not_in_stock")
    for key in ("selling_price", "purchase_price", "shipping_cost"):
        if product.get(key) is not None and _amount(product[key]) is None:
            issues.append(f"invalid_amount:{key}")
    if product.get("delivery_days_min") is not None and product.get("delivery_days_max") is not None:
        try:
            start, end = int(product["delivery_days_min"]), int(product["delivery_days_max"])
            if start < 0 or end < start:
                issues.append("invalid_delivery_window")
        except (TypeError, ValueError):
            issues.append("invalid_delivery_window")
    contribution = None
    prices = [_amount(product.get(key)) for key in ("selling_price", "purchase_price", "shipping_cost")]
    if all(p is not None for p in prices):
        # Indicative only: do not infer VAT, processing fees, expected returns or advertising spend.
        contribution = str(prices[0] - prices[1] - prices[2])
    for flag in ("supplier_approved", "image_rights_confirmed", "claims_verified", "tax_and_fees_reviewed"):
        if product.get(flag) is not True:
            issues.append(f"not_verified:{flag}")
    return {"ready": not issues, "issues": issues, "contribution_before_ads": contribution}
