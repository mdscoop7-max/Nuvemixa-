"""Dashboard authorization shared by pages, forms and read endpoints."""
from flask import current_app

RIGHTS = {
    "product_view": "Producten bekijken",
    "product_add": "Producten toevoegen",
    "product_edit": "Producten bewerken",
    "image_manage": "Productafbeeldingen beheren",
    "category_manage": "Categorieën beheren",
    "discount_view": "Kortingen bekijken",
    "discount_manage": "Kortingen beheren",
    "order_view": "Bestellingen bekijken",
    "customer_view": "Klantgegevens bekijken",
    "research": "Productonderzoek gebruiken",
    "calculator": "Calculator gebruiken",
    "stats": "Statistieken bekijken",
    "seo_view": "SEO-rapporten bekijken",
    "merchant_view": "Merchant-preview bekijken",
    "monitoring": "Monitoring bekijken",
}
DEFAULT_RIGHTS = frozenset({"product_view", "calculator", "stats"})
SECTIONS = {
    "producten": ("product_view", "product_add", "product_edit"),
    "categorieen": ("product_view", "category_manage"),
    "extra-producten": ("product_add",),
    "afbeeldingen": ("product_view", "image_manage"),
    "kortingen": ("discount_view", "discount_manage"),
    "bestellingen": ("order_view",),
    "klanten": ("customer_view",),
    "onderzoek": ("research",),
    "internationaal": ("research",),
    "partners": ("research",),
    "viral": ("research",),
    "calculator": ("calculator",),
    "statistieken": ("stats",),
    "seo": ("seo_view",),
    "google-shopping": ("merchant_view",),
    "monitoring": ("monitoring",),
}


def account_rights(stored):
    if stored is None:
        return DEFAULT_RIGHTS
    return frozenset(stored.split(",")) & RIGHTS.keys()


def allowed(*rights):
    from nv_dashboard_manager import admin, staff_current
    if admin():
        return True
    if not current_app.extensions["nuvemixa_admin_configured"]():
        return False
    staff = staff_current()
    return bool(staff and account_rights(staff["permissions"]).intersection(rights))
