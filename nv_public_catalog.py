from flask import Blueprint, jsonify
from nv_catalog_manager import catalog_changes, invalidate_changes
from nv_extra_pricing import public_price, active, today

bp = Blueprint("nv_public_catalog", __name__)

PUBLIC_FIELDS = (
    "id", "name", "sku", "slug", "brand", "ean",
    "description", "short_description",
    "image", "images", "price", "old_price", "badge",
    "stock_quantity", "stock_status", "delivery_time",
    "weight", "length", "width", "height",
)


@bp.get("/api/public/catalog")
def public_catalog():
    invalidate_changes()
    _, edits = catalog_changes()
    day = today().isoformat()
    products = []

    for category, slug, product in edits:
        if product.get("hidden") or product.get("extra") and product.get("hidden") is not False or product.get("deleted"):
            if not product.get("extra") and product.get("hidden"):
                products.append(dict(category_slug=category, slug=slug, hidden=True, extra=False))
            continue

        priced = public_price(product)
        item = {
            key: priced[key]
            for key in PUBLIC_FIELDS
            if key in priced
        }

        item["id"] = str(product.get("id") or (category + ":" + slug))
        item["category_slug"] = category
        item["slug"] = slug
        item["extra"] = bool(product.get("extra"))

        offer_active = bool(active(product, day))
        item["offer_list"] = (
            offer_active and bool(product.get("offer_list"))
        )
        item["offer_week"] = (
            offer_active and bool(product.get("offer_week"))
        )
        item["offer_end"] = (
            product.get("offer_end") if offer_active else None
        )

        products.append(item)

    response = jsonify({"version": 1, "products": products})
    response.headers["Cache-Control"] = "no-store"
    return response
