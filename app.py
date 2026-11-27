import json

import re

import os

import hmac

import secrets

import urllib.request

import urllib.error

from contextlib import closing, contextmanager
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from flask import g, has_request_context, Flask, Response, current_app, render_template, request, redirect, url_for, session, abort, jsonify

from werkzeug.security import check_password_hash
from werkzeug.local import LocalProxy
import nv_extra_pricing
from nv_catalog_manager import catalog_changes
from nuvemixa_integrations import mollie_readonly_check
from nv_storage_paths import CUSTOMER_DB
import nv_dashboard_postgres

from datetime import datetime, timezone

import time

from product_art import render_product_svg



app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32).hex()

app.config.update(

    SESSION_COOKIE_HTTPONLY=True,

    SESSION_COOKIE_SECURE=os.getenv("NUVEMIXA_COOKIE_SECURE", "true").lower() == "true",

    SESSION_COOKIE_SAMESITE="Lax",

    MAX_CONTENT_LENGTH=65536,

    MAX_FORM_MEMORY_SIZE=32768,

    MAX_FORM_PARTS=50,

)

BASE_DIR = Path(__file__).resolve().parent

PRODUCTS_DIR = BASE_DIR / "products"

with (BASE_DIR / "content" / "product-names-en.json").open(encoding="utf-8") as _product_translation_stream:

    PRODUCT_NAMES_EN = json.load(_product_translation_stream)

SITE_URL = os.getenv("SITE_URL", "").rstrip("/")



BASE_CATEGORIES = {

    "gadgets": {"name": "Gadgets", "icon": "▣", "eyebrow": "Slimme tech voor elke dag"},

    "smart-home": {"name": "Smart Home", "icon": "⌂", "eyebrow": "Comfort & connected living"},

    "beauty-care": {"name": "Beauty & Care", "icon": "♧", "eyebrow": "Self-care & beauty"},

    "home-living": {"name": "Home & Living", "icon": "▤", "eyebrow": "Wonen, organiseren & comfort"},

    "lifestyle-sport": {"name": "Lifestyle & Sport", "icon": "♢", "eyebrow": "Bewegen, herstellen & leven"},

}

# Backwards compatibility for existing catalog tests and integrations.
CATEGORY_DIRS = {
    meta["name"]: slug
    for slug, meta in BASE_CATEGORIES.items()
}










def clean_products(items):

    cleaned = []

    seen = set()

    for raw in items:

        name = str(raw.get("name", "")).strip()

        if not name:

            continue

        key = name.casefold()

        if key in seen:

            continue

        seen.add(key)

        product = dict(raw)

        product.setdefault("image", "")

        product.setdefault("icon", "🛍️")

        product.setdefault("price", 0)

        product.setdefault("cost_price", 0)

        product.setdefault("margin", 0)

        product.setdefault("orders", 0)

        cleaned.append(product)

    return cleaned





def load_catalog():

    catalog = {}

    global_seen = set()

    for slug in BASE_CATEGORIES:

        path = PRODUCTS_DIR / slug / "products.json"

        try:

            data = json.loads(path.read_text(encoding="utf-8-sig"))

            items = clean_products(data.get("products", []))

            unique_items = []

            for item in items:

                key = item["name"].casefold()

                if key in global_seen:

                    continue

                global_seen.add(key)

                unique_items.append(item)

            # NUVEMIXA testcatalogus: maximaal 20 artikelen per actieve hoofdcollectie.

            # Bij een leverancierskoppeling vervangen we deze selectie door de echte feed.

            catalog[slug] = unique_items[:20]

        except (FileNotFoundError, json.JSONDecodeError, OSError):

            catalog[slug] = []

    return catalog





base_products = load_catalog()


def catalog_snapshot():
    if has_request_context() and "nv_catalog" in g:
        return g.nv_catalog
    categories = {slug: dict(meta) for slug, meta in BASE_CATEGORIES.items()}
    items = {slug: list(rows) for slug, rows in base_products.items()}
    category_edits, product_edits = catalog_changes()
    for category, _, changes in category_edits:
        categories.setdefault(category, {"icon": "▦", "eyebrow": ""}).update(changes)
        items.setdefault(category, [])
    index = {(category, raw.get("slug") or slugify(raw["name"])): i
             for category, rows in items.items() for i, raw in enumerate(rows)}
    # Extra producten die nog als concept (verborgen) staan, zie je alleen in het dashboard, niet in de webshop.
    show_hidden = has_request_context() and request.path.startswith(("/dashboard", "/admin"))
    for category, slug, changes in product_edits:
        if category not in items:
            continue
        position = index.get((category, slug))
        if changes.get("hidden") and not show_hidden:
            if position is not None:
                items[category][position] = {**items[category][position], "hidden": True}
            continue
        if "offer_enabled" in changes and not show_hidden:
            changes = nv_extra_pricing.public_price(changes)
        position = index.get((category, slug))
        if position is None:
            if changes.get("id"):
                items[category].append(changes)
        else:
            items[category][position] = {**items[category][position], "slug": slug, **changes}
    if not show_hidden:
        items = {key: [p for p in rows if not p.get("hidden")] for key, rows in items.items()}
    snapshot = (categories, items)
    if has_request_context():
        g.nv_catalog = snapshot
    return snapshot


CATEGORIES = LocalProxy(lambda: catalog_snapshot()[0])
products = LocalProxy(lambda: catalog_snapshot()[1])





def catalog_items():

    for slug, items in products.items():

        for index, product in enumerate(items):

            yield enrich_product(product, slug, index)





def featured_mix():

    """Show the 20 curated gadget products on the homepage."""

    return [enrich_product(item, "gadgets", index) for index, item in enumerate(products.get("gadgets", [])[:20])]





def category_images():

    return {

        slug: next((item.get("image", "") for item in items if item.get("image")), "")

        for slug, items in products.items()

    }





def slugify(value):

    value = str(value or "").lower()

    value = value.replace("+", " plus ").replace("&", " en ")

    value = re.sub(r"[^a-z0-9\s-]", "", value).strip()

    return re.sub(r"[-\s]+", "-", value)





def product_url(product):

    category_slug = product["category_slug"]

    product_slug = product["slug"]

    try:

        return url_for("product_detail", category_slug=category_slug, product_slug=product_slug)

    except RuntimeError:

        return f"/{category_slug}/{product_slug}"





BROKEN_IMAGE_HOSTS = ("loremflickr.com", "placeimg.com", "source.unsplash.com")





def needs_generated_image(url):

    """Lege of onbetrouwbare placeholder-afbeeldingen vervangen we door eigen NUVEMIXA-art."""

    url = str(url or "").strip()

    return not url or any(host in url for host in BROKEN_IMAGE_HOSTS)





def product_art_url(category_slug, product_slug):

    try:

        return url_for("product_art", category_slug=category_slug, product_slug=product_slug)

    except RuntimeError:

        return f"/img/product/{category_slug}/{product_slug}.svg"





def enrich_product(product, category_slug, index):

    item = dict(product)

    item["category_slug"] = category_slug

    item["category_name"] = CATEGORIES[category_slug]["name"]

    item["index"] = index

    item.setdefault("id", f"tm-{category_slug}-{slugify(item.get('name'))}-{index}")

    item.setdefault("slug", slugify(item.get("name")) or f"product-{index + 1}")

    item["en_name"] = PRODUCT_NAMES_EN.get(category_slug, {}).get(item["slug"], item["name"])

    item["en_short_description"] = f"{item['en_name']} — a provisional selection from the NUVEMIXA test catalogue."

    item["en_description"] = (

        f"{item['en_name']} is a provisional product in the NUVEMIXA catalogue. "

        "The image is temporary and may differ from the final item. "

        "Specifications, pricing, supplier, availability and delivery times "

        "will be verified before commercial sales."

    )

    item.setdefault("brand", None)

    item.setdefault("old_price", None)

    item.setdefault("badge", None)

    item.setdefault("stock_status", "unknown")

    item.setdefault("stock_quantity", None)

    item.setdefault("delivery_time", "Wordt bevestigd bij leverancier")

    if needs_generated_image(item.get("image")):

        item["image"] = product_art_url(category_slug, item["slug"])

    item["images"] = [img for img in (item.get("images") or []) if not needs_generated_image(img)] or [item["image"]]

    item.setdefault("short_description", f"Bekijk {item['name']} binnen de {item['category_name']}-testcollectie.")

    item.setdefault("description", item.get("short_description") or f"{item['name']} is onderdeel van de NUVEMIXA-collectie.")

    item.setdefault("specifications", {})

    item.setdefault("usps", [])

    item.setdefault("seo_title", f"{item['name']} | NUVEMIXA")

    item.setdefault("seo_description", f"{item['name']} binnen {item['category_name']}. Bekijk prijs, productinformatie en alternatieven bij NUVEMIXA.")

    item.setdefault("faq", [])

    item.setdefault("related_product_ids", [])

    item["product_url"] = product_url(item)

    return item





def cart_items():

    """Read only valid catalog items from the signed session; never trust cached prices."""

    valid = []

    seen = set()

    for item in session.get("trendmix_cart", []):

        if not isinstance(item, dict):

            continue

        product_id = str(item.get("id", "")).strip()

        if not product_id or product_id in seen:

            continue

        product = find_product(product_id)

        if not product:

            continue

        try:

            qty = max(1, min(99, int(item.get("qty", 1))))

        except (TypeError, ValueError):

            qty = 1

        valid.append({

            "id": product["id"],

            "name": product["name"],

            "en_name": product["en_name"],

            "price": float(product.get("price", 0) or 0),

            "image": product.get("image", ""),

            "category_name": product["category_name"],

            "qty": qty,

        })

        seen.add(product_id)

        if len(valid) >= 40:

            break

    return valid





def cart_count():

    return sum(max(1, int(item.get("qty", 1))) for item in cart_items())





def cart_total():

    return sum(

        float(item.get("price", 0) or 0) * max(1, int(item.get("qty", 1)))

        for item in cart_items()

    )





def load_all_products():

    all_products = []

    for category_slug, items in products.items():

        for index, raw in enumerate(items):

            item = enrich_product(raw, category_slug, index)

            item["category"] = item.get("category_name", category_slug)

            all_products.append(item)

    # Keep legacy numeric URLs stable when products are added to earlier categories.
    all_products.sort(key=lambda product: str(product["id"]).startswith("tm-local-"))
    for index, product in enumerate(all_products, start=1):
        product["catalog_id"] = product["id"]
        product["id"] = index

    return all_products





def find_product(product_id):

    product_id = str(product_id or "").strip()

    for category_slug, items in products.items():

        for index, raw in enumerate(items):

            item = enrich_product(raw, category_slug, index)

            if item["id"] == product_id:

                return item

    match = re.fullmatch(r"([a-z0-9-]+)-(\d+)", product_id)

    if match and match.group(1) in products:

        index = int(match.group(2))

        items = products[match.group(1)]

        if 0 <= index < len(items):

            return enrich_product(items[index], match.group(1), index)



    try:

        numeric_id = int(product_id)

    except ValueError:

        numeric_id = None

    if numeric_id is not None:

        for product in load_all_products():

            if product.get("id") == numeric_id:

                return product

    return None





def filter_products(product_list, category=None, search=None):

    result = list(product_list)

    if category:

        result = [p for p in result if p.get("category") == category or p.get("category_name") == category]

    if search:

        needle = str(search).strip().lower()

        if needle:

            result = [

                p for p in result

                if needle in str(p.get("name", "")).lower()

                or needle in str(p.get("en_name", "")).lower()

                or needle in str(p.get("brand", "")).lower()

                or needle in str(p.get("description", "")).lower()

                or needle in str(p.get("category_name", "")).lower()

                or needle in str(p.get("short_description", "")).lower()

                or needle in " ".join(f"{key} {value}" for key, value in (p.get("specifications") or {}).items()).lower()

            ]

    return result





# WooCommerce is optional during development. Keep secrets in Vercel environment variables.

def woo_configured():

    return bool(os.getenv("WOOCOMMERCE_URL") and os.getenv("WOOCOMMERCE_CONSUMER_KEY") and os.getenv("WOOCOMMERCE_CONSUMER_SECRET"))





def live_orders_enabled():

    """Require an explicit go-live switch; connecting credentials is not permission to order."""

    return woo_configured() and os.getenv("TRENDMIX_LIVE_ORDERS", "").lower() == "true"





def woo_request(method, path, payload=None):

    base = os.getenv("WOOCOMMERCE_URL", "").rstrip("/")

    key = os.getenv("WOOCOMMERCE_CONSUMER_KEY", "")

    secret = os.getenv("WOOCOMMERCE_CONSUMER_SECRET", "")

    if not base or not key or not secret:

        return None

    url = f"{base}/wp-json/wc/v3/{path.lstrip('/')}"

    body = None

    headers = {"Accept": "application/json"}

    if payload is not None:

        body = json.dumps(payload).encode("utf-8")

        headers["Content-Type"] = "application/json"


    import base64

    token = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")

    headers["Authorization"] = f"Basic {token}"

    try:
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        request_obj = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        # Avoid forwarding WooCommerce credentials across redirects.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect)

        with opener.open(request_obj, timeout=12) as response:

            raw = response.read(500001)
            if len(raw) > 500000:
                return None

            return json.loads(raw) if raw else {}

    except (OSError, ValueError) as exc:

        app.logger.error("WooCommerce API request failed (%s)", type(exc).__name__)

        return None





def create_woo_order(cart, customer):

    line_items = []

    for item in cart:

        product = find_product(item.get("id"))

        woo_id = (product or {}).get("woocommerce_product_id")

        if not woo_id:

            return None, "Producten zijn nog niet aan WooCommerce gekoppeld."

        line_items.append({"product_id": int(woo_id), "quantity": max(1, int(item.get("qty", 1)))})

    payload = {

        "payment_method": "",

        "payment_method_title": "Nog te betalen",

        "set_paid": False,

        "billing": customer,

        "shipping": customer,

        "line_items": line_items,

    }

    result = woo_request("POST", "orders", payload)

    if not result or not result.get("id"):

        return None, "De WooCommerce-bestelling kon niet worden aangemaakt."

    return result, None





def format_eur(value):

    """Format a numeric price for visible Dutch storefront output only."""

    try:

        amount = float(value or 0)

    except (TypeError, ValueError):

        amount = 0.0

    return f"€{amount:.2f}".replace(".", ",")





def csrf_token():

    """Return a cryptographically random per-session token for POST forms."""

    token = session.get("_tm_csrf")

    if not isinstance(token, str) or len(token) < 32:

        token = secrets.token_urlsafe(32)

        session["_tm_csrf"] = token

    return token





@app.before_request
def retire_legacy_public_storefront():
    # Only the legacy Render dashboard host; never local development or the new shop.
    if request.host.split(":")[0].lower() != "trendmix.onrender.com":
        return
    endpoint = request.endpoint
    public_pages = {
        "home", "shop", "products_page", "aanbiedingen", "account",
        "wishlist", "cart", "product", "category_page", "subcategory_page",
        "legacy_product_detail", "product_detail", "legacy_product_url",
        "winkelwagen", "afrekenen", "faq", "meer", "contact_page",
        "over_nuvemixa", "over_trendmix", "bestellen", "privacy", "retouren",
        "voorwaarden", "cookies", "sitemap", "robots",
    }
    public_path = request.path.rstrip("/") or "/"
    if endpoint not in public_pages and public_path not in {
        "/aanbiedingen", "/account/register", "/account/login",
        "/account/logout", "/contact",
    }:
        return
    # Preserve explicitly requested, authorized dashboard previews.
    preview = request.args.get("dashboard_from")
    preview_sections = {"category_page": {"categorieen"},
                        "product_detail": {"producten", "afbeeldingen"}}
    if preview in preview_sections.get(endpoint, ()) and allowed(*SECTIONS.get(preview, ())):
        return
    if request.method not in ("GET", "HEAD"):
        abort(410)
    # Do not forward legacy checkout data, query parameters or incompatible slugs.
    return redirect("https://nuvemixa.onrender.com/", code=302)


@app.before_request
def verify_form_csrf():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    if request.endpoint in ("trendmix_assistant", "webshop_visits.webshop_visit"):
        return

    if request.endpoint in ("nv_manage.catalog", "nv_manage.extra_editor") and allowed("product_add", "product_edit", "image_manage"):
        # Alleen voor ingelogde beheerders: ruimte voor één productfoto (max. 5 MB) bij 'Extra producten'.
        request.max_content_length = (41 if request.path == "/admin/nv/extra-producten" else 6) * 1024 * 1024
        # Multipart parser reads chunks larger than the global 32 KiB limit.
        request.max_form_memory_size = 512 * 1024

    origin = request.headers.get("Origin")
    app.logger.warning(
        "CSRF REQUEST DIAG: host=%r origin=%r endpoint=%r",
        request.host,
        origin,
        request.endpoint
    )
    if origin:
        from urllib.parse import urlsplit
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or parsed.netloc != request.host:
            app.logger.warning(
                "CSRF DIAG: ORIGIN MISMATCH; host=%s origin=%s",
                request.host, origin
            )
            abort(403)

    expected = session.get("_tm_csrf")
    provided = request.form.get("_csrf_token", "")

    if (
        not isinstance(expected, str)
        or not isinstance(provided, str)
        or not expected
        or not hmac.compare_digest(expected, provided)
    ):
        app.logger.warning(
            "CSRF DIAG: TOKEN MISMATCH; session_token=%s form_token=%s",
            bool(expected), bool(provided)
        )
        abort(403)

@app.context_processor

def inject_helpers():

    return {"slugify": slugify, "cart_count": cart_count(), "format_eur": format_eur, "wishlist_ids": set(session.get("trendmix_wishlist", [])), "csrf_token": csrf_token}









@app.route("/")

def home():

    query = request.args.get("q", "").strip()

    all_items = list(catalog_items())

    search_results = []

    if query:

        needle = query.casefold()

        search_results = [item for item in all_items if needle in item["name"].casefold() or needle in item["category_name"].casefold() or needle in str(item.get("brand") or "").casefold() or needle in str(item.get("description") or "").casefold() or needle in " ".join(f"{key} {value}" for key, value in (item.get("specifications") or {}).items()).casefold()]

    counts = {slug: len(items) for slug, items in products.items()}

    return render_template("index.html", categories=CATEGORIES, featured_products=featured_mix(), category_images=category_images(), search_query=query, search_results=search_results, counts=counts, total_products=len(all_items))





@app.route("/shop")

def shop():

    category = request.args.get("category")

    search = request.args.get("q", "").strip()

    all_products = load_all_products()

    if category and category not in {meta["name"] for meta in CATEGORIES.values()}:

        category = None

    if category:

        category_name = category

        filtered = filter_products(all_products, category=category_name, search=search)

    else:

        filtered = filter_products(all_products, search=search)

    return render_template("shop.html", products=filtered, category=category, search=search, categories=CATEGORIES)





@app.route("/aanbiedingen")

def deals():

    deal_products = [item for item in load_all_products() if (item.get("offer_list") and nv_extra_pricing.active(item, nv_extra_pricing.today().isoformat())) or ("offer_enabled" not in item and not item.get("extra") and item.get("old_price") and float(item["old_price"]) > float(item["price"]))]

    return render_template("offers.html", products=deal_products, category="Aanbiedingen", search="", categories=CATEGORIES, deals_page=True)





@app.route("/products")

def products_page():

    return redirect(url_for("shop"), code=302)





# NUVEMIXA customer accounts: separate from admin login and checkout.

import sqlite3

from werkzeug.security import generate_password_hash



_CUSTOMER_DB = CUSTOMER_DB

_CUSTOMER_ATTEMPTS = {}



@contextmanager
def _customer_conn():
    if nv_dashboard_postgres.runtime_enabled():
        with nv_dashboard_postgres.application_db() as conn:
            yield conn
        return
    if not nv_freeze.frozen():
        _CUSTOMER_DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(nv_freeze.sqlite_connect(_CUSTOMER_DB, 10)) as conn, conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        yield conn



def _current_customer():

    customer_id = session.get("nv_customer_id")

    if not isinstance(customer_id, int):

        return None

    with _customer_conn() as conn:

        row = conn.execute("SELECT id, name, email FROM customers WHERE id=?", (customer_id,)).fetchone()

        return dict(row) if row else None



def _customer_error(message, status=400):

    return render_template("account.html", categories=CATEGORIES, customer=None, account_error=message), status



@app.route("/account")

def account():

    return render_template("account.html", categories=CATEGORIES, customer=_current_customer(), account_error=None)



@app.route("/account/register", methods=["POST"])

def customer_register():

    name = request.form.get("name", "").strip()

    email = request.form.get("email", "").strip().casefold()

    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    if password != password_confirm:
        return _customer_error("De wachtwoorden komen niet overeen.")

    if not (1 <= len(name) <= 100) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254 or not (12 <= len(password) <= 128):

        return _customer_error("Controleer naam, e-mailadres en wachtwoord (minimaal 12 tekens).")

    try:

        with _customer_conn() as conn:

            insert = "INSERT INTO customers (name,email,password_hash) VALUES (?,?,?)"
            postgres = nv_dashboard_postgres.runtime_enabled()
            cursor = conn.execute(insert + (" RETURNING id" if postgres else ""),
                                  (name, email, generate_password_hash(password, method="scrypt")))
            customer_id = cursor.fetchone()[0] if postgres else cursor.lastrowid

    except sqlite3.IntegrityError:

        return _customer_error("Dit e-mailadres is al geregistreerd.")

    session.clear()

    session["nv_customer_id"] = customer_id

    record_customer_activity(_CUSTOMER_DB, customer_id, "registered")

    return redirect(url_for("account"), code=303)



# Local admin-only customer account creation. Never creates an administrator account.
@app.route("/admin/customers/create", methods=["POST"])
def admin_create_customer():
    if not admin_is_authenticated():
        abort(403)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().casefold()
    password = request.form.get("password", "")
    if not (1 <= len(name) <= 100) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254 or not (12 <= len(password) <= 128):
        return redirect(url_for("control", section="klanten", result="ongeldig"), code=303)
    try:
        with _customer_conn() as conn:
            conn.execute("INSERT INTO customers (name,email,password_hash) VALUES (?,?,?)",
                         (name, email, generate_password_hash(password, method="scrypt")))
    except sqlite3.IntegrityError:
        return redirect(url_for("control", section="klanten", result="bestaat"), code=303)
    except (sqlite3.Error, OSError):
        app.logger.error("Klantaccount kon niet worden opgeslagen")
        return redirect(url_for("control", section="klanten", result="fout"), code=303)
    return redirect(url_for("control", section="klanten", result="toegevoegd"), code=303)


@app.route("/account/login", methods=["POST"])

def customer_login():

    email = request.form.get("email", "").strip().casefold()

    password = request.form.get("password", "")

    ip = request.remote_addr or "unknown"

    now = time.monotonic()

    recent = [t for t in _CUSTOMER_ATTEMPTS.get(ip,[]) if now-t < 900]

    if len(recent) >= 8:

        return _customer_error("Te veel pogingen. Probeer het later opnieuw.",429)

    if len(email)>254 or len(password)>128 or not email or not password:

        return _customer_error("Ongeldige inloggegevens.",401)

    with _customer_conn() as conn:

        row=conn.execute("SELECT id,password_hash FROM customers WHERE email=?",(email,)).fetchone()

    if not row or not check_password_hash(row["password_hash"],password):

        recent.append(now)

        _CUSTOMER_ATTEMPTS[ip]=recent

        return _customer_error("Ongeldige inloggegevens.",401)

    _CUSTOMER_ATTEMPTS.pop(ip,None)

    session.clear()

    session["nv_customer_id"]=row["id"]

    record_customer_activity(_CUSTOMER_DB, int(row["id"]), "logged_in")

    return redirect(url_for("account"),code=303)



@app.route("/account/logout", methods=["POST"])

def customer_logout():

    session.clear()

    return redirect(url_for("account"),code=303)





@app.route("/wishlist", methods=["GET", "POST"])

def wishlist():

    saved = session.get("trendmix_wishlist", [])

    if request.method == "POST":

        product_id = request.form.get("product_id", "").strip()

        action = request.form.get("action", "toggle")

        if action == "clear":

            saved = []

        elif product_id:

            if product_id in saved:

                saved.remove(product_id)

            else:

                saved.append(product_id)

        session["trendmix_wishlist"] = saved

        session.modified = True

        referrer = request.referrer or ""

        safe_referrer = referrer.startswith(request.host_url.rstrip("/") + "/")

        return redirect(referrer if safe_referrer else url_for("wishlist"))

    wishlist_products = [item for product_id in saved if (item := find_product(product_id))]

    return render_template("wishlist.html", categories=CATEGORIES, products=wishlist_products, wishlist_ids=set(saved))





@app.route("/cart")

def cart():

    return redirect(url_for("winkelwagen"), code=302)





@app.route("/product/<int:product_id>")

def product(product_id):

    product_item = find_product(product_id)

    if not product_item:

        return "Product niet gevonden", 404

    return redirect(product_item["product_url"], code=302)







# NUVEMIXA admin controls: deny access unless an administrator password hash is configured.

# Use a persistent SECRET_KEY; never store credentials in the repository.

import nv_2fa_postgres as postgres_2fa

_ADMIN_LOGIN_ATTEMPTS = {}

_ADMIN_MAX_ATTEMPTS = 6

_ADMIN_ATTEMPT_WINDOW = 900





def admin_is_authenticated():

    if not admin_configured():
        return False
    if session.get("nv_admin") is True:
        # Reuse the primary 2FA check across all permission checks in this request.
        cache_key = "nuvemixa.primary_2fa_active"
        if cache_key not in request.environ:
            try:
                from nv_2fa_login import is_2fa_actief
                request.environ[cache_key] = is_2fa_actief()
            except Exception:
                request.environ[cache_key] = False
        return request.environ[cache_key]
    # Medewerkers (ook met rol "admin") zijn nooit eigenaar: zij hebben geen 2FA en krijgen
    # alleen de rechten uit hun eigen rechtenlijst (zie nv_permissions.allowed).
    return False





def admin_configured():

    return all(bool(os.getenv(key)) for key in ("NUVEMIXA_ADMIN_EMAIL", "NUVEMIXA_ADMIN_PASSWORD_HASH", "SECRET_KEY"))







# NUVEMIXA Control - WooCommerce

from nv_woo_bridge import (
    CommerceConnectionError, connection_status as woo_connection_status, nuvemixa_woo_blueprint, read_configuration_present, read_recent_orders, record_test as woo_record_test,
)
import nv_supplier_sources
import nv_research_period
import nv_product_rows
import nv_stats_cache
import nv_partners
import nv_concepts
from nv_dashboard_manager import bp as management_blueprint, staff_auth, staff_current, team_rows, coupon_rows, test_checkout_discount

from nv_seo_scan import last_scan
from nv_permissions import RIGHTS, SECTIONS, account_rights, allowed
from nv_visits import record_visit, visit_summary
import nv_freeze
from nv_webshop_visits import bp as webshop_visits_bp, summary as webshop_visit_summary
from nv_system_check import check_customers, scan as run_system_scan
from nv_merchant_audit import audit as merchant_audit
from nv_international import dashboard_market
from nv_supplier_finder import directories as supplier_directories
import nv_supplier_ai
import nv_web_discovery_view
import nv_research_job  # noqa: F401  (routes: gecombineerd onderzoeksproces)
import nv_trends  # noqa: F401  (routes: Onderzoeksplatforms & trends)
import nv_search_history  # noqa: F401  (routes: zoekgeschiedenis per gebruiker)
from nv_viral_research import viral_dashboard
from nv_market_search import search_view as market_search_view

app.after_request(record_visit)
nv_freeze.init_app(app)
app.register_blueprint(webshop_visits_bp)
from nv_db_diagnostic import bp as db_diagnostic_bp
app.register_blueprint(db_diagnostic_bp)

app.register_blueprint(management_blueprint)
from nv_public_catalog import bp as public_catalog_bp
app.register_blueprint(public_catalog_bp)



app.extensions["nuvemixa_admin_checker"] = admin_is_authenticated
app.extensions["nuvemixa_admin_configured"] = admin_configured
app.extensions["nuvemixa_live_orders"] = live_orders_enabled
app.extensions["nuvemixa_catalog_api"] = (CATEGORIES, catalog_items, slugify)

app.register_blueprint(nuvemixa_woo_blueprint)









# NUVEMIXA CUSTOMER ACTIVITY INTEGRATION v1

from nv_customer_activity import record_customer_activity, read_customer_activity



import hashlib as _nv_hashlib

_NV_STATIC_VERSIONS = {}


def nv_static_version(filename):
    """Inhoudsversie voor statische bestanden: de server cachet ze 7 dagen ('immutable'), dus elke
    wijziging moet een nieuwe URL krijgen, anders blijft de browser het oude bestand gebruiken."""
    if filename not in _NV_STATIC_VERSIONS:
        try:
            data = (Path(app.static_folder) / filename).read_bytes()
            _NV_STATIC_VERSIONS[filename] = _nv_hashlib.sha256(data).hexdigest()[:10]
        except OSError:
            _NV_STATIC_VERSIONS[filename] = "0"
    return _NV_STATIC_VERSIONS[filename]


app.jinja_env.globals["nv_static_version"] = nv_static_version


@app.context_processor
def dashboard_return_link():
    endpoint = request.endpoint
    target = request.args.get("dashboard_from")
    if not admin_configured() or endpoint not in {"home", "product_detail", "category_page"}:
        return {}
    valid = {"category_page": {"categorieen"}, "product_detail": {"producten", "afbeeldingen"}}
    rights = SECTIONS.get(target, ())
    if target in valid.get(endpoint, ()) and allowed(*rights):
        return {"dashboard_back": url_for("control", section=target)}
    if endpoint == "home" and request.args.get("from_dashboard") == "1":
        if admin_is_authenticated() or staff_current():
            return {"dashboard_back": url_for("control")}
    return {}


@app.route("/admin/customer-activity", methods=["GET"])

def nv_admin_customer_activity():

    # NV_CONTROL_MODERN_2026_V1 — alleen één beheerderswerkplek

    if not allowed("customer_view"):
        if request.method == "GET" and not staff_current():
            return redirect(url_for("admin_login"))
        abort(403)

    return redirect("/dashboard?section=klanten", code=302)



@app.route("/admin/login", methods=["GET", "POST"])

def admin_login():

    if not admin_configured():

        return render_template("admin_login.html", config_missing=True, error=None), 503

    if admin_is_authenticated() or staff_current():

        return redirect("/dashboard")

    error = None

    if request.method == "POST":

        ip = request.remote_addr or "unknown"

        ticket = None
        if postgres_2fa.enabled():
            try:
                ticket = postgres_2fa.reserve_attempt(
                    "password", ip, _ADMIN_MAX_ATTEMPTS, _ADMIN_ATTEMPT_WINDOW
                )
            except postgres_2fa.StorageUnavailable:
                return "Beveiligde login tijdelijk niet beschikbaar", 503
            blocked = ticket is None
        else:
            now = time.monotonic()
            attempts = [t for t in _ADMIN_LOGIN_ATTEMPTS.get(ip, []) if now - t < _ADMIN_ATTEMPT_WINDOW]
            blocked = len(attempts) >= _ADMIN_MAX_ATTEMPTS

        if blocked:

            return render_template("admin_login.html", config_missing=False, error="Te veel pogingen. Probeer het later opnieuw."), 429

        password = request.form.get("password", "")
        email = request.form.get("email", "").strip().casefold()

        primary = False
        staff_login = None
        try:
            if email and 0 < len(password) <= 1024:
                if email == os.environ["NUVEMIXA_ADMIN_EMAIL"].strip().casefold():
                    primary = check_password_hash(os.environ["NUVEMIXA_ADMIN_PASSWORD_HASH"], password)
                elif len(email) <= 254 and len(password) <= 128:
                    staff_login = staff_auth(email, password)
        except (ValueError, TypeError):
            pass
        except (sqlite3.Error, OSError):
            app.logger.error("Dashboardaccountdatabase niet beschikbaar")
            return render_template("admin_login.html", config_missing=False,
                                   error="Accountdatabase tijdelijk niet beschikbaar."), 503

        if primary or staff_login:

            if ticket is not None:
                try:
                    postgres_2fa.finish_password_attempt(ip, ticket)
                except postgres_2fa.StorageUnavailable:
                    return "Beveiligde login tijdelijk niet beschikbaar", 503
            else:
                _ADMIN_LOGIN_ATTEMPTS.pop(ip, None)

            session.clear()

            if primary:
                from nv_2fa_login import is_2fa_actief

                try:
                    tweede_stap_nodig = is_2fa_actief()
                except Exception:
                    session.clear()
                    app.logger.exception("Verplichte 2FA-opslag niet beschikbaar")
                    return "Beveiligde login tijdelijk niet beschikbaar", 503

                if tweede_stap_nodig:
                    session["nv_2fa_pending"] = True
                    session["nv_2fa_started"] = time.time()
                    return redirect("/admin/2fa")

                # Geen toegang tot het dashboard vóór de eerste succesvolle 2FA-inschrijving.
                session["nv_2fa_enroll_pending"] = True
                session["nv_2fa_enroll_started"] = time.time()
                return redirect(url_for("admin_2fa_setup"))
            else:
                session["nv_staff_id"], session["nv_staff_version"] = staff_login

            return redirect("/dashboard")

        if ticket is not None:
            try:
                postgres_2fa.fail_password_attempt(ticket)
            except postgres_2fa.StorageUnavailable:
                return "Beveiligde login tijdelijk niet beschikbaar", 503
        else:
            attempts.append(now)
            _ADMIN_LOGIN_ATTEMPTS[ip] = attempts

        error = "Gebruikersnaam, e-mailadres of wachtwoord klopt niet."

    return render_template("admin_login.html", config_missing=False, error=error)






@app.route("/admin/reviews-beheren")
def admin_reviews_beheren():
    """Stuur de ingelogde (2FA-)beheerder met een eenmalige link naar het reviewbeheer op Alwaysdata."""
    if not admin_is_authenticated():
        return redirect(url_for("admin_login"))
    import nv_reviews_sso
    from urllib.parse import quote
    doel = "https://nuvemixa.alwaysdata.net/admin/reviews"
    if nv_reviews_sso.ingeschakeld():
        doel = "https://nuvemixa.alwaysdata.net/admin/reviews/sso?t=" + quote(nv_reviews_sso.maak_token(), safe="")
    response = redirect(doel)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.route("/admin/2fa", methods=["GET", "POST"])
def admin_2fa():
    from nv_2fa_login import is_2fa_actief, controleer_tweede_stap
    from nv_2fa_rate_limit import registreer_en_controleer

    if session.get("nv_2fa_pending") is not True:
        return redirect(url_for("admin_login"))

    begonnen = session.get("nv_2fa_started")
    if not isinstance(begonnen, (int, float)) or time.time() - begonnen > 300:
        session.clear()
        return redirect(url_for("admin_login"))

    try:
        if not is_2fa_actief():
            session.clear()
            return redirect(url_for("admin_login"))
    except Exception:
        app.logger.exception("2FA-opslag niet beschikbaar")
        return "2FA tijdelijk niet beschikbaar", 503

    sleutel = request.remote_addr or "unknown"
    error = None

    if request.method == "POST":
        try:
            toegestaan = registreer_en_controleer(sleutel)
        except Exception:
            app.logger.exception("2FA-poginglimiet niet beschikbaar")
            return "2FA tijdelijk niet beschikbaar", 503

        if not toegestaan:
            response = app.make_response(render_template(
                "admin_2fa.html",
                error="Te veel pogingen. Probeer het later opnieuw."
            ))
            response.status_code = 429
            response.headers["Cache-Control"] = "no-store"
            return response

        try:
            geldig = controleer_tweede_stap(request.form.get("code", ""))
        except Exception:
            app.logger.exception("2FA-controle mislukt")
            return "2FA tijdelijk niet beschikbaar", 503

        if geldig:
            session.clear()
            session["nv_admin"] = True
            response = app.make_response(redirect("/dashboard"))
            response.headers["Cache-Control"] = "no-store"
            return response
        error = "Ongeldige beveiligingscode."

    response = app.make_response(render_template("admin_2fa.html", error=error))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/admin/2fa/setup", methods=["GET", "POST"])
def admin_2fa_setup():
    """Eerste inschrijving: alleen de primaire beheerder, met recente wachtwoordcontrole."""
    from nv_2fa import maak_geheime_sleutel, controleer_code, maak_herstelcodes
    from nv_2fa_storage import bewaar_pending, laad_pending, wis_pending, activeer
    from nv_2fa_login import is_2fa_actief
    from nv_2fa_rate_limit import registreer_en_controleer

    enrollment = session.get("nv_2fa_enroll_pending") is True
    primary_session = session.get("nv_admin") is True
    if not (enrollment or primary_session):
        return redirect(url_for("admin_login"))

    started = session.get("nv_2fa_enroll_started")
    if enrollment and (
        not isinstance(started, (int, float)) or time.time() - started > 900
    ):
        session.clear()
        return redirect(url_for("admin_login"))

    try:
        if is_2fa_actief():
            if enrollment:
                session.clear()
                return redirect(url_for("admin_login"))
            return redirect("/dashboard")
    except FileNotFoundError:
        pass
    except Exception:
        app.logger.exception("2FA-status kon niet worden gecontroleerd")
        return "Beveiligde 2FA-opslag tijdelijk niet beschikbaar", 503

    token = session.get("nv_2fa_setup_token")
    try:
        pending = laad_pending(token, time.time()) if token else None
    except postgres_2fa.StorageUnavailable:
        return "Beveiligde 2FA-opslag tijdelijk niet beschikbaar", 503
    error = None
    qr_data_uri = None
    recovery_codes = None

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "start":
            try:
                wachtwoordpoging_toegestaan = registreer_en_controleer(
                    "setup-password:" + (request.remote_addr or "unknown")
                )
            except Exception:
                app.logger.exception("2FA-setup wachtwoordlimiet niet beschikbaar")
                return "2FA tijdelijk niet beschikbaar", 503
            password = request.form.get("password", "")
            if not wachtwoordpoging_toegestaan:
                correct = False
                error = "Te veel pogingen. Probeer het later opnieuw."
            else:
                try:
                    correct = (
                        0 < len(password) <= 1024
                        and check_password_hash(
                            os.environ["NUVEMIXA_ADMIN_PASSWORD_HASH"], password
                        )
                    )
                except (KeyError, ValueError, TypeError):
                    correct = False

            if wachtwoordpoging_toegestaan and not correct:
                error = "Het beheerderswachtwoord klopt niet."
            elif correct:
                try:
                    from secrets import token_urlsafe
                    token = token_urlsafe(32)
                    geheim = maak_geheime_sleutel()
                    bewaar_pending(token, geheim, time.time())
                    session["nv_2fa_setup_token"] = token
                    session["nv_2fa_setup_started"] = time.time()
                    return redirect(url_for("admin_2fa_setup"), code=303)
                except Exception:
                    app.logger.exception("2FA-inschrijving kon niet worden gestart")
                    return "2FA-inschrijving tijdelijk niet beschikbaar", 503

        elif action == "activate":
            sleutel = request.remote_addr or "unknown"
            try:
                toegestaan = registreer_en_controleer("setup:" + sleutel)
            except Exception:
                app.logger.exception("2FA-activatiepoginglimiet niet beschikbaar")
                return "2FA tijdelijk niet beschikbaar", 503

            if not toegestaan:
                error = "Te veel pogingen. Probeer het later opnieuw."
            elif not pending:
                error = "De tijdelijke QR-koppeling is verlopen. Begin opnieuw."
            else:
                code = request.form.get("code", "")
                if not controleer_code(pending["totp_secret"], code):
                    error = "De Authenticator-code is niet geldig. Controleer je telefoon."
                else:
                    try:
                        import pyotp
                        from nv_2fa_replay import registreer_eenmalig
                        totp = pyotp.TOTP(pending["totp_secret"])
                        code_step = int(time.time()) // totp.interval
                        normalized_code = str(code).strip()
                        matched_step = next(
                            (
                                step for step in (code_step - 1, code_step, code_step + 1)
                                if totp.at(step * totp.interval) == normalized_code
                            ),
                            None,
                        )
                        recovery_codes, recovery_hashes = maak_herstelcodes(10)
                        if postgres_2fa.enabled():
                            activated = matched_step is not None and postgres_2fa.activate_pending(
                                token, pending["totp_secret"], recovery_hashes, matched_step
                            )
                            if not activated:
                                error = "De inschrijving is verlopen of de code is al gebruikt."
                                raise ValueError("TOTP setup replay blocked")
                        else:
                            if matched_step is None or not registreer_eenmalig(matched_step):
                                error = "Deze Authenticator-code is al gebruikt. Wacht op een nieuwe code."
                                raise ValueError("TOTP setup replay blocked")
                            activeer(pending["totp_secret"], recovery_hashes)
                            try:
                                wis_pending()
                            except OSError:
                                app.logger.warning("Tijdelijke 2FA-inschrijving kon niet direct worden verwijderd")
                        session.clear()
                        session["nv_admin"] = True
                        response = app.make_response(render_template(
                            "admin_2fa_setup.html",
                            error=None,
                            qr_data_uri=None,
                            recovery_codes=recovery_codes,
                            activated=True,
                        ))
                        response.headers["Cache-Control"] = "no-store"
                        response.headers["Pragma"] = "no-cache"
                        response.headers["Referrer-Policy"] = "same-origin"
                        return response
                    except ValueError as exc:
                        if str(exc) == "TOTP setup replay blocked":
                            pass
                        else:
                            app.logger.exception("Definitieve 2FA-activatie mislukt")
                            return "2FA kon niet veilig worden geactiveerd. Probeer opnieuw.", 503
                    except Exception:
                        app.logger.exception("Definitieve 2FA-activatie mislukt")
                        return "2FA kon niet veilig worden geactiveerd. Probeer opnieuw.", 503
        else:
            error = "Ongeldige aanvraag."

    try:
        pending = laad_pending(session.get("nv_2fa_setup_token"), time.time()) if session.get("nv_2fa_setup_token") else None
    except postgres_2fa.StorageUnavailable:
        return "Beveiligde 2FA-opslag tijdelijk niet beschikbaar", 503
    if pending:
        try:
            import base64
            import io
            import pyotp
            import qrcode
            account_name = os.environ.get("NUVEMIXA_ADMIN_EMAIL", "beheerder")
            uri = pyotp.TOTP(pending["totp_secret"]).provisioning_uri(
                name=account_name, issuer_name="NUVEMIXA"
            )
            qr = qrcode.make(uri)
            output = io.BytesIO()
            qr.save(output, format="PNG")
            qr_data_uri = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
        except Exception:
            app.logger.exception("QR-code kon niet worden aangemaakt")
            return "QR-code tijdelijk niet beschikbaar. Controleer de installatie van qrcode[pil].", 503

    response = app.make_response(render_template(
        "admin_2fa_setup.html",
        error=error,
        qr_data_uri=qr_data_uri,
        recovery_codes=recovery_codes,
        activated=False,
    ))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.route("/admin/logout", methods=["POST"])

def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))





@app.route("/admin/merchant-preview")

def admin_merchant_preview():

    if not allowed("merchant_view"):
        if request.method == "GET" and not staff_current():
            return redirect(url_for("admin_login"))
        abort(403)

    response = jsonify(merchant_audit(catalog_items(), app.static_folder))
    response.headers["Cache-Control"] = "no-store"

    if request.args.get("download") == "1":
        response.headers["Content-Disposition"] = "attachment; filename=nuvemixa-merchant-productcontrole.json"

    return response





@app.route("/admin/research-preview")

def admin_research_preview():

    """Show verified catalogue completeness, not invented market demand."""

    if not allowed("research"):
        if request.method == "GET" and not staff_current():
            return redirect(url_for("admin_login"))
        abort(403)

    findings = []

    for item in catalog_items():

        confirmed_cost = bool(item.get("cost_verified"))

        confirmed_supplier = bool(item.get("supplier_verified"))

        findings.append({

            "id": str(item.get("id", "")),

            "name": item["name"],

            "category": item["category_name"],

            "supplier_verified": confirmed_supplier,

            "purchase_cost_verified": confirmed_cost,

            "stock_verified": item.get("stock_status") in ("in_stock", "out_of_stock"),

            "selling_price_verified": bool(item.get("price_verified")),

            "market_demand": None,

            "competition_score": None,

            "estimated_profit": None,

        })

    response = jsonify({

        "status": "internal_research_only",

        "market_data_connected": False,

        "products": findings,

        "total": len(findings),

    })

    response.headers["Cache-Control"] = "no-store"

    return response





def monitoring_integrations():
    woo = woo_connection_status()
    integrations = {
        "WooCommerce": (woo["state"] != "not_configured" or woo_configured(),
                        "" if woo["state"] != "not_configured" or woo_configured() else woo["detail"]),
        "Leverancierskoppeling": (False, "CSV-voorcontrole is lokaal. Er is geen externe voorraadbron gekoppeld."),
        "Gmail-inbox": (False, "De Gmail-inbox heeft nog geen geautoriseerde koppeling."),
        "Google Ads": (False, "Er is nog geen geautoriseerde campagnebron."),
        "RankFix": (bool(os.getenv("RANKFIX_API_URL", "").strip() and os.getenv("RANKFIX_API_TOKEN", "").strip()),
                    "Het dashboard heeft geen RankFix-API-verbindingstest. De bestaande link is afzonderlijk."),
        "Betalingen": (bool(os.getenv("MOLLIE_API_KEY", "").strip()), "Er is een Mollie-sleutel nodig."),
    }
    result = {name: ("unchecked", "Instellingen aanwezig. Verbinding niet getest.", follow_up)
              if configured else ("unconfigured", "Geen externe koppeling ingericht.", follow_up)
              for name, (configured, follow_up) in integrations.items()}
    if woo["state"] == "connected":
        result["WooCommerce"] = ("works", woo["label"] + ".", "")
    elif woo["state"] == "error":
        result["WooCommerce"] = ("failed", woo["detail"], "Controleer HTTPS, host en leesrechten.")
    elif woo["state"] == "configured_untested":
        result["WooCommerce"] = ("unchecked", woo["label"] + ".", woo["detail"])
    return result


def probe_monitoring_connection(name, current):
    if current[0] == "unconfigured":
        return current
    if name == "WooCommerce":
        if not read_configuration_present():
            return current
        try:
            if read_recent_orders() is not None:
                woo_record_test(True)
                return "works", "Alleen-lezen orderuitlezing bevestigd.", ""
        except CommerceConnectionError as exc:
            woo_record_test(False, exc)
            return "failed", "WooCommerce-orderuitlezing mislukt.", str(exc)
        return "failed", "WooCommerce-orderuitlezing mislukt.", "Controleer HTTPS, host en leesrechten."
    result = mollie_readonly_check()
    if result["state"] in ("connected_test", "connected_live_credentials"):
        return "works", result["message"], ""
    if result["state"] == "invalid_configuration":
        return "error", result["message"], "Controleer de bestaande Mollie-configuratie."
    return "failed", result["message"], "Controleer bereikbaarheid en de bestaande Mollie-configuratie."


def system_report(integrations=None):
    return run_system_scan(list(catalog_items()), CATEGORIES, _CUSTOMER_DB,
                           monitoring_integrations() if integrations is None else integrations)


@app.route("/admin/monitoring/check", methods=["GET", "POST"])
def admin_monitoring_check():
    if not allowed("monitoring"):
        if request.method == "GET" and not staff_current():
            return redirect(url_for("admin_login"))
        abort(403)
    integrations = monitoring_integrations()
    if request.method == "POST":
        if not admin_is_authenticated():
            abort(403)
        action = request.form.get("action")
        if action == "initialize_customers":
            try:
                status, _, _ = check_customers(_CUSTOMER_DB)
                if status == "attention":
                    with _customer_conn():
                        pass
                    status, _, _ = check_customers(_CUSTOMER_DB)
            except (OSError, sqlite3.Error, ValueError):
                status = "error"
            if status != "works":
                return jsonify(error="Klanttabel kan niet veilig worden geïnitialiseerd."), 409
            return redirect(url_for("control", section="monitoring", scan=1), code=303)
        if action not in ("WooCommerce", "Betalingen"):
            abort(400)
        integrations[action] = probe_monitoring_connection(action, integrations[action])
    response = jsonify(system_report(integrations))
    response.headers["Cache-Control"] = "no-store"
    if request.args.get("download") == "1":
        response.headers["Content-Disposition"] = "attachment; filename=nuvemixa-systeemcontrole.json"
    return response


@app.route("/admin/integrations")

def admin_integrations():

    if not admin_is_authenticated():

        return redirect(url_for("admin_login"))

    response = jsonify({

        "status": "configuration_presence_only",

        "orders_live_enabled": live_orders_enabled(),

        "woocommerce_configured": read_configuration_present() or woo_configured(),
        "woocommerce_readonly_configured": read_configuration_present(),

        "merchant_publishing_enabled": False,

        "rankfix_configured": bool(os.getenv("RANKFIX_API_URL") and os.getenv("RANKFIX_API_TOKEN")),

        "payment_key_present": bool(os.getenv("MOLLIE_API_KEY")),

        "contact_configured": bool(os.getenv("RESEND_API_KEY") and os.getenv("CONTACT_FROM_EMAIL")),
        "gmail_inbox_connected": False,
        "google_ads_connected": False,
        "secure_session_cookie": app.config["SESSION_COOKIE_SECURE"],

        "note": "Configuration presence does not confirm external connectivity.",

    })

    response.headers["Cache-Control"] = "no-store"

    return response







# Local administrative records are separate from the public test catalogue.

# All mutations require both administrator login and the existing CSRF middleware.

def admin_local_records(kind):


    try:

        from nuvemixa_admin_store import list_suppliers, list_research

        return (list_suppliers() if kind == "suppliers" else list_research()), None

    except (OSError, RuntimeError, sqlite3.Error):

        app.logger.error("NUVEMIXA admin storage unavailable")

        return None, "Admin database is tijdelijk niet beschikbaar."





@app.route("/admin/suppliers", methods=["POST"])

def admin_add_supplier():

    if not admin_is_authenticated():

        abort(403)


    from nuvemixa_admin_store import add_supplier

    try:

        add_supplier(

            request.form.get("name", ""), request.form.get("contact_email", ""),

            request.form.get("website", ""), request.form.get("notes", "")

        )

        result = "toegevoegd"

    except (ValueError, __import__("sqlite3").IntegrityError):

        result = "ongeldig"

    except (OSError, RuntimeError, sqlite3.Error):

        app.logger.error("Supplier record write failed")

        result = "fout"

    return redirect(url_for("control", section="leveranciers", result=result), code=303)





@app.route("/admin/research", methods=["POST"])

def admin_add_research_note():

    if not allowed("research"):
        if request.method == "GET" and not staff_current():
            return redirect(url_for("admin_login"))
        abort(403)


    from nuvemixa_admin_store import add_research

    try:

        add_research(

            request.form.get("category", ""), request.form.get("product_name", ""),

            request.form.get("source", ""), request.form.get("notes", "")

        )

        result = "toegevoegd"

    except ValueError:

        result = "ongeldig"

    except (OSError, RuntimeError, sqlite3.Error):

        app.logger.error("Research note write failed")

        result = "fout"

    return redirect(url_for("control", section="onderzoek", result=result), code=303)





def recent_woo_orders():
    """Toont alleen de momentopname van een bewuste klik op 'Gegevens vernieuwen'.

    Het openen van een pagina doet NOOIT een WooCommerce-aanroep. Er worden geen bestellingen verzonnen.
    """
    import nv_woo_bridge
    snapshot = nv_woo_bridge._SNAPSHOT
    if not snapshot["at"]:
        if nv_woo_bridge.connection_status()["state"] == "not_configured":
            return None, "WooCommerce niet gekoppeld."
        return None, "Nog niet opgehaald. Gebruik 'Gegevens vernieuwen' bij WooCommerce; deze pagina doet zelf geen aanroep."
    # Alleen operationele velden; geen adressen, telefoonnummers of klantgegevens.
    return [{"id": str(o.get("id", ""))[:40], "status": str(o.get("status", "onbekend"))[:45],
             "date": str(o.get("date", ""))[:25], "total": str(o.get("total", ""))[:40], "currency": "EUR"}
            for o in snapshot["orders"]], None


# Optional integrations are restricted to a logged-in administrator.

@app.route("/admin/rankfix/open")

def admin_rankfix_open():

    if not admin_is_authenticated():

        return redirect(url_for("admin_login"))

    from nuvemixa_integrations import rankfix_scan_url

    address = rankfix_scan_url()

    if not address:

        return "RankFix-adres niet veilig geconfigureerd.", 503

    response = redirect(address, code=302)

    response.headers["Referrer-Policy"] = "no-referrer"

    return response





@app.route("/admin/mollie/check")

def admin_mollie_check():

    if not admin_is_authenticated():

        return redirect(url_for("admin_login"))

    response = jsonify(mollie_readonly_check())

    response.headers["Cache-Control"] = "no-store"

    return response





@app.route("/admin/merchant-feed-preview.xml")

def admin_merchant_feed_preview():

    if not allowed("merchant_view"):
        if request.method == "GET" and not staff_current():
            return redirect(url_for("admin_login"))
        abort(403)

    from nuvemixa_integrations import merchant_feed_preview

    items = list(catalog_items())
    report = merchant_audit(items, app.static_folder)
    xml, count = merchant_feed_preview(item for item, row in zip(items, report["products"]) if not row["issues"])

    response = Response(xml, content_type="application/xml; charset=utf-8")

    response.headers["Cache-Control"] = "no-store"

    response.headers["X-NUVEMIXA-Preview-Only"] = "true"

    response.headers["X-NUVEMIXA-Eligible-Count"] = str(count)

    return response





@app.route("/admin/supplier-feed-preview", methods=["POST"])

def admin_supplier_feed_preview():

    if not admin_is_authenticated():

        abort(403)

    uploaded = request.files.get("feed")

    if not uploaded or not uploaded.filename.lower().endswith(".csv"):

        return jsonify({"error": "Upload een CSV-bestand."}), 400

    raw = uploaded.stream.read(60001)

    from nuvemixa_integrations import supplier_csv_preview

    try:

        result = supplier_csv_preview(raw)

    except ValueError as exc:

        return jsonify({"error": str(exc)}), 400

    response = jsonify(result)

    response.headers["Cache-Control"] = "no-store"

    return response





def margin_fx_context(args):
    """'Bereken marge' vanuit onderzoek: oorspronkelijke prijs + valuta -> euro met ECB-koers en datum (nooit geschat)."""
    amount, currency = args.get("margin_amount", ""), args.get("margin_currency", "")
    if not amount or not currency:
        return None
    import nv_fx
    try:
        conversion = nv_fx.to_eur(amount, currency)
    except ValueError:
        return {"error": "Ongeldig bedrag of valuta; vul de inkoopprijs zelf in."}
    except nv_fx.RateUnavailable:
        return {"error": f"Geen actuele ECB-koers voor {currency[:3].upper()} beschikbaar; vul de inkoopprijs zelf in "
                         "euro in. Er is niet omgerekend."}
    return {**conversion, "text": nv_fx.describe(conversion)}


@app.route("/control")

@app.route("/catalogus-overzicht")

@app.route("/dashboard")

def control():

    is_admin = admin_is_authenticated()
    staff = staff_current() if admin_configured() else None
    if not is_admin and not staff:

        return redirect(url_for("admin_login"))

    all_products = load_all_products()

    category_counts = {category["name"]: 0 for category in CATEGORIES.values()}

    for product in all_products:

        category_name = product.get("category") or product.get("category_name") or "Onbekend"

        category_counts[category_name] = category_counts.get(category_name, 0) + 1



    offer_count = sum(1 for product in all_products if product.get("old_price") or product.get("is_offer"))

    avg_price = round(sum(float(product.get("price", 0) or 0) for product in all_products) / len(all_products), 2) if all_products else 0

    top_category = max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else "N/A"

    featured_products = sorted(all_products, key=lambda p: (float(p.get("price", 0) or 0), p.get("name", "")), reverse=True)[:8]



    section_names = {
        "internationaal": "Internationaal marktonderzoek",
        "partners": "Partners zoeken",
        "concepten": "Kandidaten en concepten",
        "viral": "Viral Product Finder",
        "trends": "Onderzoeksplatforms & trends",

        "dashboard": "Dashboard", "woocommerce": "WooCommerce & Leveranciers", "producten": "Producten", "extra-producten": "Extra producten", "categorieen": "Categorieën",

        "bestellingen": "Bestellingen", "klanten": "Klanten", "accountbeheer": "Accountbeheer", "kortingen": "Kortingen & acties",

        "marketing": "Marketing", "seo": "SEO & GEO", "rankfix": "RankFix AI",

        "statistieken": "Statistieken", "leveranciers": "Leveranciers & dropshipping",

        "instellingen": "Instellingen",

        "onderzoek": "Productonderzoek & niches",

        "calculator": "Prijs & marge calculator",

        "afbeeldingen": "Productafbeeldingen",

        "google-ads": "Google Ads",

        "google-shopping": "Google Shopping & Merchant Center",

        "talen": "Talen",

        "klantenservice": "Klantenservice & berichten",

        "monitoring": "Monitoring",

        "administratie": "Administratie",

        "publicatie": "Productpublicatie",

    }

    section_descriptions = {
        "internationaal": "Vergelijk vraag, leveranciers en marge per verkoopmarkt.",
        "partners": "Zoek dropshipping-, reseller- en affiliatepartners. Niets wordt automatisch aangevraagd.",
        "concepten": "Bewaar gevonden producten, beoordeel ze en bereid conceptproducten voor. Er wordt niets gepubliceerd.",
        "viral": "Leg trendsignalen vast en beoordeel commerciële kansen per land.",
        "trends": "Zonder artikelnaam: AI ontdekt welke producten in een categorie en periode aandacht krijgen, met bron en datum.",

        "producten": "Zoek en bekijk producten, prijzen en voorraad in de testcatalogus.",

        "categorieen": "Bekijk de productgroepen en hun catalogusaantallen.",
        "extra-producten": "Voeg per hoofdcategorie extra producten toe. Nieuwe producten staan eerst als concept en zijn pas in de webshop te zien als jij ze zichtbaar zet.",

        "bestellingen": "Bestellingen zodra een echte orderbron is gekoppeld.",

        "klanten": "Beveiligd klantenoverzicht zodra klantbeheer beschikbaar is.",
        "accountbeheer": "Beheer toegang tot het NUVEMIXA-dashboard.",

        "kortingen": "Beheer kortingscodes en bereken hun effect op een testbedrag.",

        "marketing": "Google Ads, Merchant Center en marketing op één plek.",

        "seo": "Beheer SEO, GEO en productvindbaarheid.",

        "rankfix": "RankFix scans, auditrapporten en verbeterpunten na koppeling.",

        "statistieken": "Cataloguscijfers zonder fictieve omzet.",

        "leveranciers": "Europese dropshipleveranciers en productfeeds.",

        "instellingen": "Shopinstellingen, betalingen en integraties.",

        "onderzoek": "Vind kansen voor producten en niches met gecontroleerde bronnen.",

        "calculator": "Bereken verkoopprijzen, marge, btw en kosten.",

        "afbeeldingen": "Productafbeeldingen en contentbeheer.",

        "google-ads": "Google Ads-account en campagnegegevens.",

        "google-shopping": "Google Merchant Center en Shopping-productfeeds.",

        "talen": "Welke talen de webshop ondersteunt en welke taalfuncties nog niet gekoppeld zijn.",

        "klantenservice": "Klantvragen, contact en berichten.",

        "monitoring": "Koppelingen, beschikbaarheid en controles.",

        "publicatie": "Producten controleren, goedkeuren en voorbereiden voor WooCommerce. Er wordt niets verzonden zonder schrijfkoppeling.",

        "administratie": "Omzet, kosten, marges en overzichten voor de boekhouding.",

    }

    section = request.args.get("section", "dashboard").strip().lower()

    if section not in section_names:

        section = "dashboard"

    employee_sections = {"dashboard"} | {name for name, rights in SECTIONS.items() if allowed(*rights)}
    if not is_admin and (section not in employee_sections or request.path == "/catalogus-overzicht"):
        abort(403)
    search = request.args.get("q", "").strip()[:120]

    filtered_products = all_products
    if search and section in {"producten", "afbeeldingen"}:
        from nv_research_intent import matches, normalize, offer_match, subject_for

        subject = subject_for(normalize(search))
        if subject:
            filtered_products = [product for product in all_products if any(
                offer_match(search, title, product.get("description") or "")[0] == "exact"
                for title in (product.get("name"), product.get("en_name")) if title
            )]
        else:
            raw_matches = {id(product) for product in filter_products(all_products, search=search)}
            filtered_products = [product for product in all_products if id(product) in raw_matches or matches(
                search, " ".join(str(product.get(key) or "") for key in ("name", "en_name", "brand", "category_name", "sku"))
            )]



    livegang = None
    if section == "woocommerce" and is_admin:
        import nv_livegang
        livegang = nv_livegang.checklist()
    extra_groups = None
    if section in {"extra-producten", "producten"}:
        day = nv_extra_pricing.today().isoformat()
        for product in all_products:
            product["active_offer"] = nv_extra_pricing.active(product, day)
            product["scheduled_offer"] = bool(product.get("offer_start") and product["offer_start"] > day)
        week_candidates = sorted((p for p in all_products if p.get("active_offer") and p.get("offer_week") and not p.get("hidden")),
                                 key=lambda p: (p["category_slug"], str(p.get("sku") or p["slug"])))
        for product in all_products:
            product["homepage_offer"] = bool(week_candidates and product is week_candidates[0])
        extra_groups = [{"key": key, "name": meta.get("name", key),
                         "base": sum(1 for p in all_products if p["category_slug"] == key and not p.get("extra")),
                         "extra": [p for p in all_products if p["category_slug"] == key and p.get("extra")],
                         "items": [p for p in all_products if p["category_slug"] == key]}
                        for key, meta in CATEGORIES.items()]

    merchant_report = (merchant_audit(catalog_items(), app.static_folder)
                       if section in {"google-shopping", "monitoring"} else None)
    merchant_preview_rows = merchant_report["products"] if section == "google-shopping" else []
    integration_status = {

        "merchant": merchant_report or {"ready": 0, "total": len(all_products)},

        "rankfix": bool(os.getenv("RANKFIX_API_URL") and os.getenv("RANKFIX_API_TOKEN")),

        "payment": bool(os.getenv("MOLLIE_API_KEY")),

        "woo": read_configuration_present() or woo_configured(),

        "contact": bool(os.getenv("RESEND_API_KEY") and os.getenv("CONTACT_FROM_EMAIL")),

    }

    supplier_rows, supplier_error = (admin_local_records("suppliers") if section == "leveranciers" else (None, None))

    research_rows, research_error = (admin_local_records("research") if section == "onderzoek" else (None, None))
    product_margin = None
    margin_scenario = None
    product_margin_error = None
    margin_unified = None
    margin_unified_error = None
    # Oude links (margin_run zonder methode, of de vroegere automatische berekening) rekenen voortaan ook via de
    # gedeelde rekenmodule, zodat bladwijzers blijven werken en er maar één berekening bestaat.
    if (section in {"onderzoek", "calculator"} and request.args.get("margin_run") == "1"
            and request.args.get("margin_method") in {None, "", "unified", "automatic"}):
        # Gedeelde rekenmodule (zelfde regels als static/nv-margin-core.js); werkt ook zonder JavaScript.
        from nv_product_margin import unified_margin
        try:
            margin_unified = unified_margin(request.args)
        except ValueError as exc:
            margin_unified_error = str(exc)
    elif section == "onderzoek" and request.args.get("margin_run") == "1":
        from nv_product_margin import automatic_margin, calculate_margin
        try:
            if request.args.get("margin_method") == "scenario":
                margin_scenario = calculate_margin(request.args)
            else:
                product_margin = automatic_margin(request.args.get("purchase_cost", ""))
        except ValueError as exc:
            product_margin_error = str(exc)
    product_discovery = None
    source_coverage = None
    research_options = {}
    if section == "onderzoek":
        from nv_product_discovery import (
            ALL_PRODUCTS, COUNTRIES, EMPTY_RESULTS, FILTERS, MODES, PLATFORMS, RESEARCH_CATEGORIES, SUPPLIER_MODES, discover,
        )

        research_categories = {**{slug: meta["name"] for slug, meta in BASE_CATEGORIES.items()}, **RESEARCH_CATEGORIES}
        research_category = request.args.get("research_category", ALL_PRODUCTS)
        research_mode = request.args.get("research_mode", "products")
        research_country = request.args.get("research_country", "NL")
        source_coverage = nv_supplier_sources.coverage(research_country if research_country in COUNTRIES else "NL")
        research_platforms = [
            "Publicaties" if value == "Bing" else value for value in request.args.getlist("research_platform")
        ]
        research_filter = request.args.get("research_supplier_filter", "eu" if research_mode in SUPPLIER_MODES else "all")
        research_options = {
            "categories": {**research_categories, ALL_PRODUCTS: "All products"},
            "countries": COUNTRIES,
            "modes": MODES,
            "platforms": PLATFORMS,
            "selected_platforms": research_platforms if request.args.get("research_run") else PLATFORMS,
            "category": research_category,
            "country": research_country,
            "mode": research_mode,
            "empty_message": EMPTY_RESULTS,
            "supplier_filters": FILTERS,
            "supplier_filter": research_filter,
            "country_bases": __import__("nv_product_discovery").COUNTRY_BASES,
            "country_basis": (request.args.get("research_country_basis")
                              if request.args.get("research_country_basis") in __import__("nv_product_discovery").COUNTRY_BASES
                              else "either"),
            "periods": nv_research_period.CHOICES,
            "period": request.args.get("research_period", "slim"),
            # Schakelaar: verborgen '0' plus aangevinkte '1'. Zonder AI-configuratie toont ai_discover zelf 'uit'.
            "ai_enabled": (request.args.get("research_run") != "1" or "1" in request.args.getlist("research_ai")
                           or "research_ai" not in request.args or not __import__("nv_openai").configured()),
            "block": request.args.get("research_block", "product"),
            "platform_categories": {ALL_PRODUCTS: "Alle categorieën",
                                    **{slug: meta["name"] for slug, meta in BASE_CATEGORIES.items()},
                                    "overig": "Overig / Algemeen"},
        }
        if request.args.get("research_run") == "1":
            from nv_ai_search import ai_discover
            period_days, period_label = nv_research_period.resolve(research_options["period"], research_mode)
            general = research_category == "overig"  # Onderzoeksplatforms: 'Overig / Algemeen'
            search_args = dict(country=research_country, mode=research_mode, platforms=research_platforms,
                               category=ALL_PRODUCTS if general else research_category,
                               categories=research_categories, supplier_filter=research_filter,
                               country_basis=research_options["country_basis"])
            if general:
                search_args["infer"] = False
            if research_options["ai_enabled"]:
                product_discovery = ai_discover(request.args.get("research_term", ""), **search_args)
            else:
                product_discovery = discover(request.args.get("research_term", ""), **search_args)
                if isinstance(product_discovery, dict) and not product_discovery.get("error"):
                    product_discovery["ai"] = {"state": "off", "label": "AI uitgezet", "removed": 0,
                                               "message": "AI is voor deze zoekopdracht uitgezet; normaal zoeken.",
                                               "keywords_en": [], "keywords_nl": [], "category": "", "used_query": ""}
            if isinstance(product_discovery, dict) and not product_discovery.get("error"):
                product_discovery["rows"] = nv_product_rows.build(product_discovery.get("products") or [],
                                                                  product_discovery.get("suppliers") or [],
                                                                  research_options["categories"])
                if general:
                    product_discovery["category_name"] = "Overig / Algemeen"
                product_discovery["period"] = {**nv_research_period.apply(product_discovery, period_days),
                                               "label": period_label}


    order_rows, order_error = (recent_woo_orders() if section in ("bestellingen", "administratie") else (None, None))
    admin_overview = None
    publicatie = None
    if section == "publicatie" and is_admin:
        import nv_publicatie, json as _json
        try:
            own = nv_concepts.selected_candidates()
        except Exception:
            own = {}
        pool = {**nv_publicatie.TEST_CANDIDATES, **own}
        # Standaard alleen eigen concepten; testproducten alleen nog via een expliciete ?kandidaat=TEST-…-link.
        chosen = pool.get(request.args.get("kandidaat", ""), None) or next(iter(own.values()), None)
        existing, bron, fout = nv_publicatie.existing_products()
        if chosen is None:
            publicatie = {"leeg": True, "eigen": [], "bron": bron, "bron_fout": fout}
        else:
            rows = nv_publicatie.check(chosen, existing)
            if bron != "echt" and chosen.get("bron") == "concept":
                # Zonder leesverbinding is er niets echt gecontroleerd: niet vergelijken met voorbeeldproducten.
                rows = [({**r, "status": "let op", "tekst": "Niet gecontroleerd: er is nog geen leesverbinding met WooCommerce. "
                          "Controleer zelf in WooCommerce of dit product al bestaat."}
                         if r["stap"] == "Bestaat al in WooCommerce" else r) for r in rows]
            publicatie = {"leeg": False, "kandidaten": list(nv_publicatie.TEST_CANDIDATES.values()), "eigen": list(own.values()), "gekozen": chosen, "rijen": rows,
                      "fouten": bool(nv_publicatie.blocking(rows)), "marge": nv_publicatie.margin(chosen),
                      "voorbeeld": _json.dumps(nv_publicatie.payload(chosen), indent=2, ensure_ascii=False),
                      "bron": bron, "bron_fout": fout, "goedgekeurd": nv_publicatie.approval_valid(app.secret_key, chosen, session.get("nv_pub_goedkeuringen", {}).get(chosen["sku"], "")),
                      "schrijven_klaar": nv_publicatie.write_connection_ready() and __import__("nv_woo_writer").configured(), "ontbrekend": __import__("nv_woo_writer").missing_configuration(), "min_marge": nv_publicatie.MIN_MARGE}
    if section == "administratie" and is_admin:
        import nv_administratie
        admin_overview = {"test": nv_administratie.test_overview(),
                          "echt": nv_administratie.real_orders(order_rows), "echt_fout": order_error}

    admin_customer_rows = []
    admin_customer_error = None
    seo_report = None
    seo_error = None
    if section == "seo":
        try:
            seo_report = last_scan()
        except (sqlite3.Error, OSError, ValueError):
            seo_error = "Het laatste scanrapport kan tijdelijk niet worden geladen."
    coupons = []
    coupon_error = None
    if section == "kortingen":
        try:
            coupons = coupon_rows()
        except (sqlite3.Error, OSError):
            coupon_error = "Kortingen kunnen tijdelijk niet worden geladen."
    staff_rows = []
    staff_error = None
    if section == "accountbeheer":
        try:
            staff_rows = team_rows()
        except (sqlite3.Error, OSError):
            staff_error = "Dashboardaccounts kunnen tijdelijk niet worden geladen."
    if section == "klanten":
        try:
            with nv_dashboard_postgres.read_db(_CUSTOMER_DB) as conn:
                admin_customer_rows = [dict(row) for row in conn.execute(
                    "SELECT id,name,email,created_at FROM customers ORDER BY id DESC LIMIT 100").fetchall()]
        except (OSError, sqlite3.Error):
            admin_customer_error = "Klantdatabase kan niet worden gelezen. Bekijk de klantdatabasecontrole bij Monitoring."

    report = system_report() if section == "monitoring" and request.args.get("scan") == "1" else None
    view_template = "control.html" if request.path == "/catalogus-overzicht" else "dashboard.html"
    if report and view_template == "dashboard.html":
        view_template = "nv_monitoring_report.html"

    # NV_CONTROL_MODERN_2026_V1 — lees alleen lokale klantactiviteit als het nodig is

    nv_customer_count, nv_customer_events, nv_customer_error = (

        # Hoofdscherm: max. 60 s gecachet (alleen geslaagde reads); Klanten leest altijd live.
        nv_stats_cache.cached("home:customers", lambda: read_customer_activity(_CUSTOMER_DB),
                              ok=lambda value: value[2] is None)
        if (is_admin and section == "dashboard")
        else read_customer_activity(_CUSTOMER_DB) if section == "klanten"

        else (None, [], None)

    )

    return render_template(

        view_template,
        market_research=dashboard_market() if section == "internationaal" else None,
        viral=viral_dashboard() if section == "viral" else None,
        market_search=(market_search_view(
            "viral" if section == "viral" else "internationaal",
            {slug: meta["name"] for slug, meta in BASE_CATEGORIES.items()}, request.args,
        ) if section in {"viral", "internationaal"} else None),

        products=featured_products,

        filtered_products=filtered_products,
        extra_groups=extra_groups,
        livegang=livegang,

        section=section,

        search=search,

        section_names=section_names,

        section_descriptions=section_descriptions,

        stats={

            "total_products": len(all_products),

            "total_categories": len(category_counts),

            "offers": offer_count,

            "avg_price": avg_price,

            "top_category": top_category,

            "max_category_count": max(category_counts.values(), default=0),

        },

        category_counts=sorted(category_counts.items()),

        categories=CATEGORIES,

        integration_status=integration_status,

        merchant_preview_rows=merchant_preview_rows,

        supplier_rows=supplier_rows,
        supplier_directory=supplier_directories('NL') if section == 'leveranciers' else (),
        supplier_ai=nv_supplier_ai.view_context() if section == 'leveranciers' else None,
        web_discovery=nv_web_discovery_view.view_context(section),
        research_job={'can_save': bool(is_admin)} if section == 'onderzoek' else None,
        trends_view={**nv_trends.view_context(), 'can_save': bool(is_admin)} if section == 'trends' else None,
        margin_fx=margin_fx_context(request.args) if section in ('onderzoek', 'calculator') else None,
        ai_status=__import__('nv_ai_search').safe_status(),
        nv_supplier_rows=nv_product_rows.suppliers,
        nv_supplier_summary=nv_product_rows.summary,

        supplier_error=supplier_error,

        research_rows=research_rows,

        research_error=research_error,
        product_discovery=product_discovery,
        concept_view=nv_concepts.view(request.args.get("concept_q", "")) if section == 'concepten' and is_admin else None,
        partner_view=nv_partners.view(request.args) if section == 'partners' else None,
        source_coverage=source_coverage,
        source_test=nv_supplier_sources.test_state() if section == 'onderzoek' else None,
        product_margin=product_margin,
        margin_unified=margin_unified,
        margin_unified_error=margin_unified_error,
        margin_scenario=margin_scenario,
        product_margin_error=product_margin_error,
        research_options=research_options,

        order_rows=order_rows,
        admin_overview=admin_overview,
        publicatie=publicatie,
        staff_login_enabled=__import__('nv_dashboard_manager').staff_login_enabled(),
        talen=(__import__('nv_talen').winkel_talen() if section == 'talen' else []),
        talen_niet_gekoppeld=__import__('nv_talen').NIET_GEKOPPELD,
        euro=__import__('nv_administratie').euro,

        order_error=order_error,

        nv_customer_count=nv_customer_count,

        nv_customer_events=nv_customer_events,

        nv_customer_error=nv_customer_error,
        is_admin=is_admin,
        staff=staff,
        employee_sections=employee_sections,
        report=report,
        scan_labels={"works": "Werkt", "attention": "Aandacht nodig", "error": "Fout",
                     "unchecked": "Niet getest", "unconfigured": "Niet gekoppeld",
                     "failed": "Verbinding mislukt", "disabled": "Uitgeschakeld"},
        woo_connection=woo_connection_status(),
        monitoring_connections=monitoring_integrations() if section == "monitoring" else {},
        monitoring_probes=("WooCommerce", "Betalingen") if section == "monitoring" and read_configuration_present()
                          else ("Betalingen",),
        visitor_stats=visit_summary() if section in {"statistieken", "monitoring"} else None,
        webshop_stats=(nv_stats_cache.cached("home:webshop_visits", webshop_visit_summary,
                                             ok=lambda value: bool(value) and not (isinstance(value, dict) and value.get("error")))
                       if section == "dashboard"
                       else webshop_visit_summary() if section in {"statistieken", "monitoring"} else None),
        allowed=allowed,
        rights_labels=RIGHTS,
        account_rights=account_rights,
        stock_labels={"unknown": "Onbekend", "in_stock": "Op voorraad", "out_of_stock": "Uitverkocht"},
        staff_rows=staff_rows,
        seo_report=seo_report,
        seo_error=seo_error,
        coupons=coupons,
        coupon_error=coupon_error,
        staff_error=staff_error,
        admin_customer_rows=admin_customer_rows,
        admin_customer_error=admin_customer_error,

    )





INFO_PAGES = {

    "over-trendmix": {"title": "Over NUVEMIXA", "description": "Ontdek het verhaal achter NUVEMIXA, onze vijf productcollecties en hoe we bouwen aan een overzichtelijke webshop met betrouwbare informatie vóór de commerciële opening.", "content": """

        <p>NUVEMIXA wordt ontwikkeld als een moderne webshop waarin overzicht, duidelijke informatie en een prettige winkelervaring centraal staan. Het assortiment is verdeeld over vijf vaste categorieën: Gadgets, Smart Home, Beauty & Care, Home & Living en Lifestyle & Sport.</p>

        <h2>Waar we voor staan</h2><p>We willen klanten niet door een eindeloze catalogus laten zoeken. NUVEMIXA kiest voor een overzichtelijk assortiment en productpagina’s waarop prijs, belangrijkste kenmerken, voorraad- en leverinformatie zo duidelijk mogelijk worden weergegeven.</p>

        <h2>Van testfase naar echte webshop</h2><p>NUVEMIXA bevindt zich momenteel in ontwikkeling. Producten en prijzen in de testcatalogus kunnen nog wijzigen. Echte bestellingen worden pas geactiveerd nadat leverancier, betaling, verzending, retourproces en bedrijfsgegevens definitief zijn ingericht en gecontroleerd.</p>

        <h2>Transparantie</h2><p>Voor de commerciële livegang publiceren we de volledige identiteit en contactgegevens van de verkopende onderneming, de definitieve verkoopvoorwaarden en alle informatie die klanten nodig hebben vóór het sluiten van een overeenkomst.</p>

        <h2>Vragen of feedback</h2><p>Zie je onduidelijke productinformatie of heb je een vraag over NUVEMIXA? Gebruik dan de contactpagina. Feedback uit de testfase gebruiken we om de webshop verder te verbeteren.</p>

    """},

    "bestellen": {"title": "Bestellen & levering", "description": "Informatie over bestellen, prijzen, betalen, levering en orderbevestiging bij NUVEMIXA.", "content": """

        <p>Deze pagina beschrijft hoe het bestelproces van NUVEMIXA wordt ingericht. Zolang de webshop in testfase is, worden geen definitieve betaal- of leverbeloften gedaan.</p>

        <h2>Product en prijs</h2><p>Vóór een commerciële bestelling tonen we de belangrijkste productkenmerken, de totale verkoopprijs inclusief toepasselijke belastingen en eventuele bijkomende kosten. Verzendkosten en andere kosten worden uiterlijk vóór het definitief plaatsen van de bestelling duidelijk gemaakt.</p>

        <h2>Bestellen</h2><p>Je voegt producten toe aan de winkelwagen, controleert aantallen en gegevens en krijgt vóór de definitieve bestelhandeling een overzicht van de bestelling. De bestelknop zal bij livegang ondubbelzinnig duidelijk maken dat de bestelling een betalingsverplichting inhoudt.</p>

        <h2>Betalen</h2><p>De definitieve betaalmethoden worden vóór livegang gepubliceerd. NUVEMIXA brengt geen betaalmethode of toeslag in rekening die niet vooraf duidelijk is vermeld.</p>

        <h2>Levering</h2><p>De beschikbare bezorglanden, verzendkosten, verwachte levertijd en eventuele beperkingen worden vóór de bestelling getoond zodra de leverancier en logistieke inrichting definitief zijn. Na een echte bestelling ontvangt de klant een bevestiging met de relevante bestelgegevens.</p>

        <h2>Probleem met levering</h2><p>Is een bestelling na livegang niet of niet correct geleverd, dan kan de klant contact opnemen met NUVEMIXA. De definitieve contactgegevens en procedure worden vóór livegang op deze website gepubliceerd.</p>

    """},

    "retouren": {"title": "Retour & herroeping", "description": "Informatie over wettelijke bedenktijd, herroeping, retourneren en terugbetaling.", "content": """

        <p>Bij online consumentenkoop geldt in de EU in veel gevallen een wettelijk herroepingsrecht. Voor goederen is de gebruikelijke bedenktijd 14 dagen vanaf ontvangst. Er bestaan wettelijke uitzonderingen; daarom wordt per relevant product duidelijk gemaakt wanneer het herroepingsrecht niet geldt.</p>

        <h2>Een aankoop herroepen</h2><p>Wanneer NUVEMIXA commercieel live gaat, leggen we vóór de koop duidelijk uit hoe je binnen de wettelijke termijn laat weten dat je de overeenkomst wilt herroepen. We publiceren ook het vereiste modelformulier en de definitieve contact- en retourgegevens.</p>

        <h2>Product terugsturen</h2><p>Na een geldige herroeping moet het product binnen de wettelijke termijn worden teruggestuurd. Vóór de koop vermelden we wie de directe retourkosten draagt en, waar vereist, welke kosten daarbij te verwachten zijn.</p>

        <h2>Product beoordelen</h2><p>Tijdens de bedenktijd mag een consument een product beoordelen zoals dat redelijkerwijs in een winkel mogelijk is. Als verder gebruik tot waardevermindering leidt, kan daarvoor volgens de wettelijke regels een vergoeding gelden.</p>

        <h2>Terugbetaling</h2><p>Bij een geldige herroeping wordt de terugbetaling volgens de wettelijke regels uitgevoerd. Daarbij kan in bepaalde gevallen worden gewacht tot het product is ontvangen of bewijs van terugzending is geleverd.</p>

        <h2>Online herroepingsfunctie</h2><p>De commerciële versie van NUVEMIXA krijgt vóór livegang de vereiste online mogelijkheid om een daarvoor in aanmerking komende online aankoop eenvoudig te herroepen, inclusief ontvangstbevestiging.</p>

    """},

    "voorwaarden": {"title": "Algemene voorwaarden", "description": "Conceptuele opbouw van de verkoopvoorwaarden van NUVEMIXA voor de commerciële livegang.", "content": """

        <p>De definitieve algemene voorwaarden worden vóór de commerciële livegang juridisch gecontroleerd en gekoppeld aan de identiteit van de verkopende onderneming. Onderstaande onderdelen beschrijven alvast de structuur die klanten mogen verwachten; deze tekst is nog geen definitieve verkoopovereenkomst.</p>

        <h2>1. Toepasselijkheid en verkoper</h2><p>De voorwaarden zullen vermelden op welke overeenkomsten zij van toepassing zijn en wie de verkopende onderneming is, inclusief handelsnaam, vestigings- en contactgegevens en relevante registratienummers.</p>

        <h2>2. Aanbod en productinformatie</h2><p>NUVEMIXA beschrijft producten zo duidelijk mogelijk. Kennelijke fouten kunnen worden gecorrigeerd. Voor slimme en verbonden producten wordt waar relevant informatie toegevoegd over compatibiliteit, benodigde diensten en updates zodra die informatie door de leverancier is bevestigd.</p>

        <h2>3. Prijzen en kosten</h2><p>Consumentenprijzen worden duidelijk weergegeven inclusief toepasselijke belastingen. Eventuele verzend- of andere bijkomende kosten worden vóór de bestelling kenbaar gemaakt.</p>

        <h2>4. Totstandkoming van de overeenkomst</h2><p>De definitieve voorwaarden beschrijven wanneer een bestelling is geplaatst, wanneer een overeenkomst tot stand komt en hoe de klant daarvan een bevestiging ontvangt.</p>

        <h2>5. Betaling en levering</h2><p>Beschikbare betaalmethoden, levergebieden, verwachte levertijden en eventuele beperkingen worden vóór de koop duidelijk gemaakt.</p>

        <h2>6. Herroeping en retour</h2><p>Voor consumenten wordt het wettelijke herroepingsrecht uitgelegd, inclusief termijn, werkwijze, uitzonderingen, retourkosten en terugbetaling. Zie ook de aparte pagina Retour & herroeping.</p>

        <h2>7. Wettelijke rechten en conformiteit</h2><p>De voorwaarden beperken geen wettelijke consumentenrechten. Als een geleverd product niet aan de overeenkomst beantwoordt, gelden de toepasselijke wettelijke rechten.</p>

        <h2>8. Klachten</h2><p>Klachten kunnen na livegang via de gepubliceerde contactkanalen worden ingediend. De definitieve procedure vermeldt hoe klachten worden geregistreerd en beantwoord en welke geschillenroute van toepassing is.</p>

        <h2>9. Privacy</h2><p>Persoonsgegevens worden alleen verwerkt voor duidelijk omschreven doeleinden en volgens het privacybeleid. Voor externe betaal-, verzend- of technische dienstverleners wordt uitgelegd welke rol zij hebben.</p>

        <h2>10. Wijzigingen</h2><p>Nieuwe voorwaarden gelden niet met terugwerkende kracht ten nadele van reeds gesloten overeenkomsten. De versie die bij een bestelling hoort, moet door de klant kunnen worden bewaard of geraadpleegd.</p>

    """},

    "privacy": {"title": "Privacybeleid", "description": "Lees hoe NUVEMIXA persoonsgegevens verwerkt tijdens de ontwikkeling van de webshop, welke gegevens nodig kunnen zijn en hoe we privacy-informatie aanvullen vóór livegang.", "content": """

        <p>NUVEMIXA wil alleen persoonsgegevens verwerken die nodig zijn om de webshop te laten functioneren, vragen te beantwoorden en — na commerciële livegang — bestellingen uit te voeren. Vóór livegang wordt dit privacybeleid aangevuld met de definitieve identiteit en contactgegevens van de verwerkingsverantwoordelijke.</p>

        <h2>Welke gegevens</h2><p>Afhankelijk van de gebruikte functie kunnen naam, contactgegevens, aflever- en factuurgegevens, bestelgegevens en technische gegevens worden verwerkt. We vragen niet meer gegevens dan nodig is voor het betreffende doel.</p>

        <h2>Waarvoor</h2><p>Gegevens kunnen worden gebruikt voor klantenservice, uitvoering en administratie van bestellingen, fraudepreventie, wettelijke verplichtingen en het technisch functioneren van de webshop. De definitieve grondslagen en bewaartermijnen worden vóór livegang per doel beschreven.</p>

        <h2>Dienstverleners</h2><p>Voor onder meer hosting, betaling, e-mail en verzending kunnen externe dienstverleners nodig zijn. Zodra deze partijen definitief zijn gekozen, wordt relevante informatie hierover opgenomen in het privacybeleid.</p>

        <h2>Jouw privacyrechten</h2><p>De definitieve privacyverklaring legt uit hoe betrokkenen hun toepasselijke rechten kunnen uitoefenen, zoals inzage, correctie of verwijdering waar de wet dat toestaat.</p>

        <h2>Beveiliging en contact</h2><p>NUVEMIXA neemt passende technische en organisatorische maatregelen voor de functies die worden aangeboden. Het definitieve privacycontact wordt vóór commerciële livegang gepubliceerd.</p>

    """},

    "cookies": {"title": "Cookies & voorkeuren", "description": "Informatie over functionele opslag, cookies en toekomstige toestemming.", "content": """

        <p>NUVEMIXA gebruikt tijdens de ontwikkeling functionele browseropslag voor onderdelen zoals taalvoorkeur en winkelwagenfunctionaliteit. Deze functies zijn bedoeld om de website technisch te laten werken en voorkeuren te onthouden.</p>

        <h2>Functionele opslag</h2><p>Een taalkeuze of winkelwagen kan lokaal of via een sessie worden bewaard. Zonder deze technische functies kan een deel van de webshop minder goed werken.</p>

        <h2>Analyse en marketing</h2><p>Voordat niet-noodzakelijke analyse- of marketingtechnologie wordt geactiveerd, wordt gecontroleerd welke toestemming en informatie daarvoor nodig is. NUVEMIXA activeert zulke technologie niet als daarvoor eerst geldige toestemming vereist is.</p>

        <h2>Voorkeuren wijzigen</h2><p>Bij livegang komt er, indien nodig voor de gebruikte technologie, een duidelijke manier om cookie- en privacyvoorkeuren te bekijken en te wijzigen. Browsergegevens kunnen daarnaast via de instellingen van de browser worden verwijderd.</p>

    """},

}





def company_details_line():
    """Bedrijfsgegevens uit omgevingsvariabelen; alleen ingevulde velden worden getoond."""
    fields = [
        ("", os.getenv("NUVEMIXA_BEDRIJFSNAAM", "NUVEMIXA").strip()),
        ("", os.getenv("NUVEMIXA_ADRES", "").strip()),
        ("KvK-nummer: ", os.getenv("NUVEMIXA_KVK", "").strip()),
        ("btw-id: ", os.getenv("NUVEMIXA_BTW", "").strip()),
        ("e-mail: ", os.getenv("NUVEMIXA_EMAIL", "").strip()),
        ("telefoon: ", os.getenv("NUVEMIXA_TELEFOON", "").strip()),
    ]
    return ", ".join(label + value for label, value in fields if value)


def _fill_company_details(node):
    if isinstance(node, str):
        return node.replace("{bedrijfsgegevens}", company_details_line()) if "{bedrijfsgegevens}" in node else node
    if isinstance(node, list):
        return [_fill_company_details(item) for item in node]
    if isinstance(node, dict):
        return {key: _fill_company_details(value) for key, value in node.items()}
    return node


def render_info_page(info_slug):

    page = INFO_PAGES.get(info_slug)

    if not page:

        return "Pagina niet gevonden", 404



    # Professional bilingual information pages are stored locally, with the Dutch

    # text rendered on the server for accessibility and search indexing. No

    # supplier, delivery, payment or business details are invented.

    info_file = BASE_DIR / "content" / "information" / f"{info_slug}.json"

    info_doc = None

    if info_file.is_file():

        with info_file.open(encoding="utf-8") as stream:

            info_doc = json.load(stream)

        if info_doc.get("slug") != info_slug or not all(

            info_doc.get(language, {}).get("sections") for language in ("nl", "en")

        ):

            raise ValueError(f"Invalid bilingual information document: {info_slug}")

        info_doc = _fill_company_details(info_doc)



    source = info_doc["nl"] if info_doc else page

    return render_template(

        "info.html",

        title=source["title"],

        description=source["description"],

        info_slug=info_slug,

        path=f"/{info_slug}",

        content=page["content"],

        info_doc=info_doc,

        categories=CATEGORIES,

    )





@app.route("/<category_slug>")

def category_page(category_slug):

    if category_slug not in CATEGORIES:

        return "Pagina niet gevonden", 404

    category = CATEGORIES[category_slug]

    category_products = [

        enrich_product(item, category_slug, index)

        for index, item in enumerate(products[category_slug])

    ]

    return render_template(

        "category.html",

        category_name=category["name"],

        category_icon=category["icon"],

        category_eyebrow=category["eyebrow"],

        category_slug=category_slug,

        categories=CATEGORIES,

        products=category_products,

    )





@app.route("/<category_slug>/<subcategory_slug>/")

def subcategory_page(category_slug, subcategory_slug):

    """Keep old collection URLs working, but send them to the main collection."""

    if category_slug not in CATEGORIES:

        return "Pagina niet gevonden", 404

    return redirect(url_for("category_page", category_slug=category_slug), code=301)





@app.route("/product/<category_slug>/<int:product_index>")

def legacy_product_detail(category_slug, product_index):

    if category_slug not in products or product_index < 0 or product_index >= len(products[category_slug]):

        return "Product niet gevonden", 404

    product = enrich_product(products[category_slug][product_index], category_slug, product_index)

    return redirect(product["product_url"], code=301)





@app.route("/<category_slug>/<product_slug>")

def product_detail(category_slug, product_slug):

    if category_slug not in products:

        return "Product niet gevonden", 404

    match = None

    for index, raw in enumerate(products[category_slug]):

        item = enrich_product(raw, category_slug, index)

        if item["slug"] == product_slug:

            match = item

            break

    if not match:

        return "Product niet gevonden", 404

    related = [

        enrich_product(raw, category_slug, index)

        for index, raw in enumerate(products[category_slug])

        if enrich_product(raw, category_slug, index)["id"] != match["id"]

    ][:6]

    return render_template(

        "product.html",

        product=match,

        product_index=match["index"],

        category_slug=category_slug,

        category_name=CATEGORIES[category_slug]["name"],

        categories=CATEGORIES,

        related=related,

    )





@app.route("/<category_slug>/<subcategory_slug>/<product_slug>")

def legacy_product_url(category_slug, subcategory_slug, product_slug):

    if category_slug not in products:

        return "Product niet gevonden", 404

    for index, raw in enumerate(products[category_slug]):

        item = enrich_product(raw, category_slug, index)

        if item["slug"] == product_slug:

            return redirect(item["product_url"], code=301)

    return "Product niet gevonden", 404





@app.route("/winkelwagen", methods=["GET", "POST"])

def winkelwagen():

    cart = [dict(item) for item in cart_items()]



    if request.method == "POST":

        action = request.form.get("action", "").strip()



        if action == "add":

            product = find_product(request.form.get("product_id", "").strip())

            if product:

                found = next((item for item in cart if str(item["id"]) == str(product["id"])), None)

                if found:

                    found["qty"] = min(99, max(1, int(found.get("qty", 1))) + 1)

                elif len(cart) < 40:

                    cart.append({

                        "id": product["id"],

                        "name": product["name"],

                        "price": float(product.get("price", 0) or 0),

                        "image": product.get("image", ""),

                        "category_name": product["category_name"],

                        "qty": 1,

                    })



        elif action == "change":

            product_id = request.form.get("product_id", "").strip()

            try:

                delta = int(request.form.get("delta", "0"))

            except ValueError:

                delta = 0

            for item in cart:

                if str(item.get("id")) == product_id:

                    new_qty = int(item.get("qty", 1)) + delta

                    if new_qty <= 0:

                        cart = [cart_item for cart_item in cart if str(cart_item.get("id")) != product_id]

                    else:

                        item["qty"] = min(99, new_qty)

                    break



        elif action == "remove":

            product_id = request.form.get("product_id", "").strip()

            cart = [item for item in cart if str(item.get("id")) != product_id]



        elif action == "clear":

            cart = []



        session["trendmix_cart"] = [{"id": item["id"], "qty": item["qty"]} for item in cart]

        session.modified = True

        return redirect(url_for("winkelwagen"))



    total = sum(

        float(item.get("price", 0) or 0) * max(1, int(item.get("qty", 1)))

        for item in cart

    )

    return render_template(

        "cart.html",

        categories=CATEGORIES,

        cart=cart,

        cart_count=cart_count(),

        cart_total=total,

    )





@app.route("/afrekenen", methods=["GET", "POST"])

def afrekenen():

    cart = [dict(item) for item in cart_items()]

    if not cart:

        return redirect(url_for("winkelwagen"))

    total = sum(float(item.get("price", 0) or 0) * max(1, int(item.get("qty", 1))) for item in cart)

    test_mode = not live_orders_enabled()
    discount = None
    coupon_error = None
    coupon_code = request.form.get("coupon_code", "").strip()[:32] if test_mode else ""
    if coupon_code:
        subtotal = int(sum(Decimal(str(item["price"])) * item["qty"] for item in cart)
                       .quantize(Decimal(".01"), rounding=ROUND_HALF_UP) * 100)
        try:
            discount = test_checkout_discount(coupon_code, subtotal)
        except (sqlite3.Error, OSError):
            app.logger.error("Kortingsdatabase niet beschikbaar tijdens testafrekening")
            coupon_error = "Kortingscontrole is tijdelijk niet beschikbaar."
        else:
            if discount is None:
                coupon_error = "Deze kortingscode is ongeldig of verlopen."
            else:
                total = (subtotal - discount) / 100
    order = None

    error = None

    if request.method == "POST":

        customer = {

            "first_name": request.form.get("first_name", "").strip(),

            "last_name": request.form.get("last_name", "").strip(),

            "email": request.form.get("email", "").strip(),

            "address_1": request.form.get("address_1", "").strip(),

            "postcode": request.form.get("postcode", "").strip(),

            "city": request.form.get("city", "").strip(),

            "country": request.form.get("country", "").strip(),

        }

        consent = request.form.get("checkout_consent") == "yes"

        if request.form.get("checkout_action") == "coupon" and test_mode:
            pass
        elif coupon_error:
            error = coupon_error
        elif not all(customer.values()):

            error = "Vul alle verplichte gegevens in."

        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", customer["email"]):

            error = "Vul een geldig e-mailadres in."

        elif not consent:

            error = "Controleer en bevestig je gegevens voordat je doorgaat."

        elif len(customer["country"]) > 100 or len(customer["country"]) < 2 or any(ord(char) < 32 for char in customer["country"]):

            error = "Vul een geldige landnaam in."

        elif live_orders_enabled():

            # Free-text country is not a WooCommerce ISO-3166 code.
            # Require a verified name-to-code mapping AND an explicit shipping readiness switch.
            try:

                configured_countries = json.loads(os.getenv("NUVEMIXA_VERIFIED_SHIPPING_COUNTRIES_JSON", "{}"))

            except (ValueError, TypeError):

                configured_countries = {}

            if not isinstance(configured_countries, dict):

                configured_countries = {}

            country_code = configured_countries.get(customer["country"].casefold().strip())

            if (os.getenv("NUVEMIXA_SHIPPING_READY", "").lower() != "true"
                or not isinstance(country_code, str)
                or not re.fullmatch(r"[A-Z]{2}", country_code)):

                error = "Verzending naar dit land is nog niet bevestigd. Er is geen bestelling geplaatst."

            else:

                customer["country"] = country_code

                order, error = create_woo_order(cart, customer)

                if order:

                    session.pop("trendmix_cart", None)

                    return render_template("checkout.html", categories=CATEGORIES, cart=[], cart_count=0, cart_total=0, test_mode=False, order=order, error=None)

        else:

            # Flask session data is stored in a signed but readable browser cookie.

            # Never retain customer names, emails or addresses in that cookie.

            session.pop("trendmix_test_checkout", None)

            return render_template("checkout.html", categories=CATEGORIES, cart=cart, cart_count=cart_count(), cart_total=total, test_mode=True, order={"id": "TEST"}, error=None, discount=discount)

    return render_template("checkout.html", categories=CATEGORIES, cart=cart, cart_count=cart_count(), cart_total=total, test_mode=test_mode, order=order, error=error, discount=discount, coupon_code=coupon_code, coupon_error=coupon_error, customer=(customer if request.method == "POST" else {}))





@app.route("/faq")

def faq():

    return render_template("faq.html", categories=CATEGORIES)



@app.route("/meer")

def nuvemixa_more():

    return render_template("meer.html", categories=CATEGORIES)



@app.route("/contact", methods=["GET"])

def contact_page():

    return render_template("contact.html", categories=CATEGORIES, search_query="")



@app.route("/contact", methods=["POST"])

def contact():

    name = request.form.get("name", "").strip()

    email = request.form.get("email", "").strip()

    message = request.form.get("message", "").strip()

    subject = request.form.get("subject", "Overig").strip()

    if subject not in ("Productvraag", "Bestelling", "Levering en retour", "Overig"):

        subject = "Overig"



    if not name or not email or not message or len(name) > 120 or len(email) > 254 or len(message) > 5000:

        return redirect(url_for("contact_page") + "?status=error")



    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):

        return redirect(url_for("contact_page") + "?status=error")



    is_ajax = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    api_key = os.getenv("RESEND_API_KEY")

    from_email = os.getenv("CONTACT_FROM_EMAIL")



    # Never claim a customer message was delivered if outbound email is not configured.

    if not api_key or not from_email:

        if is_ajax:

            return Response(json.dumps({"ok": False, "test_mode": True, "error": "mail_not_configured"}), status=503, mimetype="application/json")

        return redirect(url_for("contact_page") + "?status=unavailable")



    payload = {

        "from": from_email,

        "to": [os.getenv("CONTACT_TO_EMAIL", from_email)],

        "reply_to": email,

        "subject": f"NUVEMIXA contactformulier: {subject}",

        "text": f"Naam: {name}\\nE-mail: {email}\\nOnderwerp: {subject}\\n\\nBericht:\\n{message}",

    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(

        "https://api.resend.com/emails",

        data=data,

        headers={

            "Authorization": f"Bearer {api_key}",

            "Content-Type": "application/json",

        },

        method="POST",

    )

    try:

        with urllib.request.urlopen(req, timeout=10) as response:

            if 200 <= response.status < 300:

                if is_ajax:

                    return Response(json.dumps({"ok": True}), mimetype="application/json")

                return redirect(url_for("contact_page") + "?status=sent")

    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:

        app.logger.error("Contact mail failed: %s", exc)



    if is_ajax:

        return Response(json.dumps({"ok": False}), status=502, mimetype="application/json")

    return redirect(url_for("contact_page") + "?status=error")



@app.route("/over-nuvemixa")
def over_nuvemixa():
    return render_info_page("over-trendmix")

@app.route("/over-trendmix")
def over_trendmix():
    return redirect(url_for("over_nuvemixa"), code=301)




@app.route("/bestellen")

def bestellen():

    return render_info_page("bestellen")





@app.route("/privacy")

def privacy():

    return render_info_page("privacy")





@app.route("/retouren")

def retouren():

    return render_info_page("retouren")





@app.route("/voorwaarden")

def voorwaarden():

    return render_info_page("voorwaarden")





@app.route("/cookies")

def cookies():

    return render_info_page("cookies")





@app.route("/img/product/<category_slug>/<product_slug>.svg")

def product_art(category_slug, product_slug):

    name = product_slug.replace("-", " ").capitalize()

    for raw in products.get(category_slug, []):

        if (raw.get("slug") or slugify(raw.get("name"))) == product_slug:

            name = raw.get("name") or name

            break

    response = Response(render_product_svg(name, category_slug), mimetype="image/svg+xml")

    response.headers["Cache-Control"] = "public, max-age=604800, immutable"

    return response





@app.route("/robots.txt")

def robots():

    site_url = SITE_URL or request.url_root.rstrip("/")

    return Response(f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n", mimetype="text/plain")





@app.route("/sitemap.xml")

def sitemap():

    site_url = SITE_URL or request.url_root.rstrip("/")

    urls = [f"{site_url}/"] + [f"{site_url}/{slug}" for slug in CATEGORIES] + [f"{site_url}/{chr(111)+"ver-nuvemixa" if path == "over-trendmix" else path}" for path in INFO_PAGES] + [f"{site_url}/faq"]

    for slug, items in products.items():

        for index, raw in enumerate(items):

            urls.append(f"{site_url}{enrich_product(raw, slug, index)['product_url']}")

    from xml.sax.saxutils import escape

    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" + "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">" + "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls) + "</urlset>"

    return Response(xml, mimetype="application/xml")





@app.after_request

def trendmix_security_headers(response):

    # Safe baseline headers; a strict CSP requires a separate audit of inline scripts.

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    commit = os.getenv("RENDER_GIT_COMMIT", "")
    if re.fullmatch(r"[0-9a-f]{40}", commit):
        response.headers["X-NUVEMIXA-Commit"] = commit

    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    if request.is_secure:

        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")

    if request.path in ("/winkelwagen", "/afrekenen", "/wishlist", "/contact", "/dashboard", "/dashboard/internationaal", "/dashboard/viral", "/control", "/catalogus-overzicht") or request.path.startswith(("/api/", "/admin/", "/dashboard/")):

        response.headers["Cache-Control"] = "no-store"

    if request.path in ("/dashboard", "/control", "/catalogus-overzicht") or request.path.startswith(("/admin/", "/dashboard/")):

        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"

    if "dashboard_from" in request.args or request.args.get("from_dashboard") == "1":
        response.headers["Cache-Control"] = "private, no-store"

    # Browser caching speeds up repeat page visits without caching private pages,

    # cart state, API replies or customer information.

    if request.path.startswith("/static/") and response.status_code == 200:

        if request.args.get("v"):

            response.headers["Cache-Control"] = "public, max-age=604800, immutable"

        elif response.mimetype.startswith("image/"):

            response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"

        else:

            response.headers["Cache-Control"] = "public, max-age=900, stale-while-revalidate=3600"

    return response





# Public read-only support endpoint; customer orders remain private.

from trendmix_assistant import register_trendmix_assistant

register_trendmix_assistant(app, products, CATEGORIES, live_orders_enabled)



if __name__ == "__main__":

    app.run(debug=False)
