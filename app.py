import json
import re
import os
import hmac
import secrets
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from flask import make_response, Flask, Response, current_app, render_template, request, redirect, url_for, session, abort, send_from_directory
from integration_readiness import status_rows
from monitor_snapshots import save_report, latest_reports, METRICS
from supplier_pricing import quote
from product_research import review_candidate
from admin_drafts import list_drafts, save_draft, remove_draft, add_support_draft, list_support_drafts
from support_email_drafts import draft_reply
from decimal import Decimal, InvalidOperation
from customer_accounts import create_account, authenticate, account_by_id
from admin_accounts import account as verify_admin_account, list_users as admin_list_users, add_user as admin_add_user, update_password as admin_update_password, remove_user as admin_remove_user
from product_art import render_product_svg
from catalog_readiness import review_product
from visitor_metrics import record_page_view, summary as visitor_metrics_summary

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32).hex()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=bool(os.getenv("VERCEL_ENV")),
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

CATEGORIES = {
    "gadgets": {"name": "Gadgets", "icon": "▣", "eyebrow": "Slimme tech voor elke dag"},
    "smart-home": {"name": "Smart Home", "icon": "⌂", "eyebrow": "Comfort & connected living"},
    "beauty-care": {"name": "Beauty & Care", "icon": "♧", "eyebrow": "Self-care & beauty"},
    "home-living": {"name": "Home & Living", "icon": "▤", "eyebrow": "Wonen, organiseren & comfort"},
    "lifestyle-sport": {"name": "Lifestyle & Sport", "icon": "♢", "eyebrow": "Bewegen, herstellen & leven"},
}

CATEGORY_DIRS = {meta["name"]: slug for slug, meta in CATEGORIES.items()}


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
    for slug in CATEGORIES:
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
            # TrendMix testcatalogus: maximaal 20 artikelen per actieve hoofdcollectie.
            # Bij een leverancierskoppeling vervangen we deze selectie door de echte feed.
            catalog[slug] = unique_items[:20]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            catalog[slug] = []
    return catalog


products = load_catalog()


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
    """Lege of onbetrouwbare placeholder-afbeeldingen vervangen we door eigen TrendMix-art."""
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
    item["en_short_description"] = f"{item['en_name']} — a provisional selection from the TrendMix test catalogue."
    item["en_description"] = (
        f"{item['en_name']} is a provisional product in the TrendMix catalogue. "
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
    item.setdefault("description", item.get("short_description") or f"{item['name']} is onderdeel van de TrendMix-collectie.")
    item.setdefault("specifications", {})
    item.setdefault("usps", [])
    item.setdefault("seo_title", f"{item['name']} | TrendMix")
    item.setdefault("seo_description", f"{item['name']} in de categorie {item['category_name']} bij TrendMix. Bekijk de beschikbare productinformatie en controleer specificaties en levering vóór bestelling.")
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
    for index, product in enumerate(all_products, start=1):
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
    request_obj = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    import base64
    token = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
    request_obj.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request_obj, timeout=12) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        app.logger.error("WooCommerce API request failed: %s", exc)
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


@app.after_request
def count_anonymous_page_views(response):
    """Count public HTML GET responses only; exclude bots, administration and assets."""
    if (request.method == "GET" and response.status_code == 200
            and response.mimetype == "text/html"
            and request.endpoint not in ("admin_preview",)
            and not request.path.startswith(("/beheer", "/static/", "/api/"))
            and not any(word in request.headers.get("User-Agent", "").lower()
                        for word in ("bot", "crawler", "spider", "preview", "headless", "pytest"))):
        record_page_view()
    return response


@app.before_request
def verify_form_csrf():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    if request.endpoint == "admin_upload_photo":
        request.max_content_length = 3 * 1024 * 1024
    # Read-only JSON assistant handles Origin separately.
    if request.endpoint == "trendmix_assistant":
        return
    origin = request.headers.get("Origin")
    if origin:
        from urllib.parse import urlsplit
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or parsed.netloc != request.host:
            abort(403)
    expected = session.get("_tm_csrf")
    provided = request.form.get("_csrf_token", "")
    if not isinstance(expected, str) or not isinstance(provided, str) or not expected or not hmac.compare_digest(expected, provided):
        abort(403)


@app.context_processor
def inject_helpers():
    return {"slugify": slugify, "cart_count": cart_count(), "format_eur": format_eur, "wishlist_ids": set(session.get("trendmix_wishlist", [])), "csrf_token": csrf_token, "site_url": SITE_URL or request.url_root.rstrip("/")}




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
    if category and category not in CATEGORY_DIRS:
        category = None
    if category:
        filtered = filter_products(all_products, category=category, search=search)
    else:
        filtered = filter_products(all_products, search=search)
    # Filters operate on the currently loaded test catalogue; no supplier claims.
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort = request.args.get("sort", "relevance")
    if sort not in ("relevance", "price-low", "price-high", "name"):
        sort = "relevance"
    def valid_nonnegative_price(value):
        try:
            parsed = float(value)
            return parsed if parsed >= 0 and parsed < float("inf") else None
        except (ValueError, TypeError):
            return None
    minimum = valid_nonnegative_price(min_price) if min_price else None
    maximum = valid_nonnegative_price(max_price) if max_price else None
    if minimum is not None:
        filtered = [p for p in filtered if float(p.get("price") or 0) >= minimum]
    if maximum is not None:
        filtered = [p for p in filtered if float(p.get("price") or 0) <= maximum]
    if sort == "price-low":
        filtered.sort(key=lambda p: float(p.get("price") or 0))
    elif sort == "price-high":
        filtered.sort(key=lambda p: float(p.get("price") or 0), reverse=True)
    elif sort == "name":
        filtered.sort(key=lambda p: str(p.get("name") or "").casefold())
    return render_template("shop.html", products=filtered, category=category, search=search,
                           min_price=min_price if minimum is not None else "",
                           max_price=max_price if maximum is not None else "", sort=sort, categories=CATEGORIES)


@app.route("/aanbiedingen")
def deals():
    deal_products = [item for item in load_all_products() if item.get("old_price") and float(item.get("old_price") or 0) > float(item.get("price") or 0)]
    return render_template("offers.html", products=deal_products, category="Aanbiedingen", search="", categories=CATEGORIES, deals_page=True)


@app.route("/products")
def products_page():
    return redirect(url_for("shop"), code=302)


def _current_admin():
    auth = request.authorization
    if not auth or auth.type != "basic":
        return None
    return verify_admin_account(auth.username or "", auth.password or "")


def _admin_authorized():
    return _current_admin() is not None


def _admin_csrf_token():
    if "admin_csrf" not in session:
        session["admin_csrf"] = secrets.token_urlsafe(32)
    return session["admin_csrf"]


@app.route("/beheer")
def admin_preview():
    if not os.getenv("TRENDMIX_ADMIN_USER") or len(os.getenv("TRENDMIX_ADMIN_PASSWORD", "")) < 16:
        abort(404)
    if not _admin_authorized():
        return Response("Beheer: aanmelden vereist", 401,
                        {"WWW-Authenticate": 'Basic realm="TrendMix beheer"'})
    overview = [
        {"name": data["name"], "count": len(products.get(slug, []))}
        for slug, data in CATEGORIES.items()
    ]
    # Do not infer successful sales from test checkouts or unpaid WooCommerce orders.
    # A verified read-only order integration will supply actual paid totals later.
    order_stats = {
        "orders": "—",
        "order_label": "Nog geen gekoppelde orderbron",
        "sold_items": "—",
        "revenue_display": "Niet beschikbaar",
        "live_connected": False,
    }
    # No durable visitor analytics store exists yet. Never invent session counts.
    metrics = visitor_metrics_summary()
    visitor_stats = {
        "visits_display": metrics["total"] if metrics else "—",
        "today_display": metrics["today"] if metrics else "—",
        "note": "Anonieme paginaweergaven (geen unieke bezoekers)" if metrics else "Meting niet beschikbaar",
    }
    response = Response(render_template("admin_preview.html",
                                        overview=overview,
                                        order_stats=order_stats,
                                        visitor_stats=visitor_stats,
                                        total_products=sum(row["count"] for row in overview), current_admin=_current_admin()))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response



@app.route("/beheer/lancering")
def admin_launch_readiness():
    """Read-only launch gate: no secrets, no payments or supplier actions."""
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    checks = [
        {"title": "EU-leveranciers", "ready": False, "detail": "Getekend contract, goedgekeurde leverancier en echte productfeed zijn nog niet bevestigd."},
        {"title": "Producten en voorraad", "ready": False, "detail": "Live prijzen, afbeeldingsrechten, voorraad en levertijden moeten uit de leveranciersbron komen."},
        {"title": "Betalingen", "ready": False, "detail": "Een geverifieerde betaalprovider, webhook en terugbetalingsproces zijn nog niet bevestigd."},
        {"title": "Bestellingen en verzending", "ready": False, "detail": "Echte betaalde orders, fulfilment, verzendkosten en retouren zijn nog niet end-to-end getest."},
        {"title": "Live productbeheer", "ready": False, "detail": "Concepten zijn beschikbaar; gecontroleerde publicatie met back-up en auditlog ontbreekt."},
        {"title": "Volledige vertalingen", "ready": False, "detail": "NL/EN taalkeuze bestaat, maar de volledige site en voorwaarden zijn nog niet vertaald."},
        {"title": "Bedrijfsgegevens en support", "ready": False, "detail": "Zakelijke contactgegevens, e-mailaflevering en juridische teksten vergen definitieve verificatie."},
        {"title": "Laptop- en RankFix-test", "ready": False, "detail": "Mobiel, desktop, beveiliging en de volledige bestelstroom moeten nog samen getest worden."},
    ]
    response = make_response(render_template("admin_launch_readiness.html", checks=checks))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/beheer/accounts", methods=["GET", "POST"])
def admin_accounts_page():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    actor = _current_admin()
    if actor["role"] != "owner":
        abort(403)
    error = None
    info = None
    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("csrf", ""), session.get("admin_csrf", "")):
            abort(403)
        action = request.form.get("action", "")
        try:
            if action == "create":
                admin_add_user(request.form.get("username", "").strip(),
                               request.form.get("password", ""),
                               request.form.get("role", ""))
                info = "Gebruiker toegevoegd."
            elif action == "password":
                new_password = request.form.get("new_password", "")
                if not verify_admin_account(actor["username"], request.form.get("current_password", "")):
                    raise ValueError("Huidig wachtwoord klopt niet.")
                admin_update_password(actor["username"], new_password)
                info = "Wachtwoord gewijzigd. Gebruik bij de volgende aanmelding het nieuwe wachtwoord."
            elif action == "delete":
                target = request.form.get("username", "")
                if not target or target == actor["username"]:
                    raise ValueError("Eigenaar kan niet worden verwijderd.")
                admin_remove_user(target)
                info = "Gebruiker verwijderd."
            else:
                raise ValueError("Onbekende actie.")
        except (ValueError, __import__("sqlite3").IntegrityError) as exc:
            error = str(exc) if isinstance(exc, ValueError) else "Deze gebruikersnaam bestaat al."
    response = make_response(render_template("admin_accounts.html",
        current_admin=actor, users=admin_list_users(), csrf=_admin_csrf_token(), error=error, info=info),
        400 if error else 200)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _admin_draft_guard():
    if os.getenv("VERCEL_ENV") or not os.getenv("TRENDMIX_ADMIN_USER") or len(os.getenv("TRENDMIX_ADMIN_PASSWORD", "")) < 16:
        abort(404)
    actor = _current_admin()
    if actor is None:
        return Response("Beheer: aanmelden vereist", 401, {"WWW-Authenticate": 'Basic realm="TrendMix beheer"'})
    if actor["role"] not in ("owner", "manager"):
        abort(403)
    return None


@app.route("/beheer/monitoring", methods=["GET", "POST"])
def admin_integrations_monitor():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    error = None
    if request.method == "POST":
        try:
            source = request.form.get("source", "")
            subject = request.form.get("subject", "")
            metric = request.form.get("metric", "")
            value = request.form.get("value", "")
            if source not in METRICS or metric not in METRICS[source]:
                raise ValueError("Ongeldige meting")
            number = float(value)
            save_report(source, subject, {metric: number})
            return redirect(url_for("admin_integrations_monitor"), code=303)
        except (ValueError, OverflowError):
            error = "Niet opgeslagen: controleer bron, onderwerp, meting en getal."
    response = make_response(render_template("admin_integrations.html",
        integrations=status_rows(), reports=latest_reports(), metrics=METRICS, error=error),
        400 if error else 200)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/beheer/productonderzoek", methods=["GET", "POST"])
def admin_product_research():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    result, error = None, None
    fields = {}
    if request.method == "POST":
        fields = {k: request.form.get(k, "") for k in (
            "name", "category", "supplier", "price", "shipping", "selling",
            "stock", "competition", "demand")}
        try:
            result = review_candidate(**fields)
        except ValueError as exc:
            error = str(exc)
    response = make_response(render_template(
        "admin_product_research.html", fields=fields, result=result, error=error, categories=CATEGORIES),
        400 if error else 200)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/beheer/prijsberekening", methods=["GET", "POST"])
def admin_supplier_pricing():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    result = None
    error = None
    fields = {}
    if request.method == "POST":
        fields = {key: request.form.get(key, "") for key in (
            "purchase", "shipping", "packaging", "fees_fixed",
            "fees_percent", "vat_percent", "margin_percent")}
        try:
            result = quote(**fields)
        except ValueError as exc:
            error = str(exc)
    response = make_response(render_template(
        "admin_supplier_pricing.html", result=result, error=error, fields=fields), 400 if error else 200)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/beheer/productconcepten", methods=["GET", "POST"])
def manage_product_drafts():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    error = None
    if request.method == "POST":
        action = request.form.get("action")
        try:
            draft_id = int(request.form.get("draft_id", "0"))
            if action == "remove":
                if draft_id <= 0:
                    raise ValueError("Ongeldig concept")
                remove_draft(draft_id)
                return redirect(url_for("manage_product_drafts"), code=303)
            if action != "save":
                raise ValueError("Ongeldige bewerking")
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "")
            desc = request.form.get("description", "").strip()
            image_url = request.form.get("image_url", "").strip()
            price = Decimal(request.form.get("price", "").strip())
            if not (2 <= len(name) <= 120 and category in CATEGORIES and len(desc) <= 2000 and price.is_finite() and Decimal("0") <= price <= Decimal("999999.99")):
                raise ValueError("Controleer productnaam, categorie, prijs en omschrijving")
            if image_url and (len(image_url)>500 or not (image_url.startswith("https://") or re.fullmatch(r"/beheer/foto/[a-f0-9]{32}\\.(?:png|jpg|webp)", image_url))):
                raise ValueError("Afbeeldingslink moet HTTPS gebruiken")
            cents = int(price.quantize(Decimal(".01")) * 100)
            if not save_draft(name, category, cents, desc, image_url, draft_id if draft_id>0 else None):
                raise ValueError("Concept niet gevonden")
            return redirect(url_for("manage_product_drafts"), code=303)
        except (ValueError, InvalidOperation, OverflowError):
            error = "Niet opgeslagen. Controleer de velden en probeer opnieuw."
    response = make_response(render_template("admin_product_drafts.html", drafts=list_drafts(), categories=CATEGORIES, error=error, uploaded_photo=request.args.get("photo", "")), 400 if error else 200)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/beheer/foto/upload", methods=["POST"])
def admin_upload_photo():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    image = request.files.get("image")
    if not image:
        abort(400)
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    try:
        data = image.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            abort(413)
        picture = Image.open(BytesIO(data))
        picture.verify()
        picture = Image.open(BytesIO(data))
        if picture.width * picture.height > 12_000_000:
            abort(413)
        picture.thumbnail((1600, 1600))
        picture = picture.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        abort(400)
    folder = BASE_DIR / "instance" / "admin_uploads"
    folder.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + ".jpg"
    picture.save(folder / filename, format="JPEG", quality=86)
    return redirect(url_for("manage_product_drafts", photo=url_for("admin_photo", filename=filename)), code=303)


@app.route("/beheer/foto/<filename>")
def admin_photo(filename):
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    if not re.fullmatch(r"[a-f0-9]{32}\\.jpg", filename):
        abort(404)
    response = make_response(send_from_directory(BASE_DIR / "instance" / "admin_uploads", filename))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@app.route("/beheer/klantenservice", methods=["GET", "POST"])
def admin_support_drafts():
    denied = _admin_draft_guard()
    if denied is not None:
        return denied
    error = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        try:
            answer, used_ai = draft_reply(question)
            add_support_draft(question, answer)
            return redirect(url_for("admin_support_drafts"), code=303)
        except ValueError:
            error = "Vul een klantvraag van 5 tot 3000 tekens in."
    response = make_response(render_template("admin_support_drafts.html", drafts=list_support_drafts(), error=error), 400 if error else 200)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/account")
def account():
    customer = account_by_id(session["customer_id"]) if isinstance(session.get("customer_id"), int) else None
    response = make_response(render_template("account.html", categories=CATEGORIES, customer=customer))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/registreren", methods=["GET", "POST"])
def register_customer():
    if os.getenv("VERCEL_ENV") or os.getenv("TRENDMIX_ACCOUNTS_ENABLED") == "false":
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if len(name.strip()) > 80 or len(email) > 254 or not (12 <= len(password) <= 1024):
            error = "Controleer je naam, e-mailadres en wachtwoord (minimaal 12 tekens)."
        else:
            customer_id = create_account(name, email, password)
            if customer_id:
                session.clear()
                session["customer_id"] = customer_id
                return redirect(url_for("account"), code=303)
            error = "Registratie is niet gelukt. Controleer je gegevens of gebruik Inloggen."
        response = make_response(render_template("customer_auth.html", mode="register", error=error, categories=CATEGORIES), 400)
    else:
        response = make_response(render_template("customer_auth.html", mode="register", error=None, categories=CATEGORIES))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/inloggen", methods=["GET", "POST"])
def login_customer():
    if os.getenv("VERCEL_ENV") or os.getenv("TRENDMIX_ACCOUNTS_ENABLED") == "false":
        abort(404)
    if request.method == "POST":
        email, password = request.form.get("email", ""), request.form.get("password", "")
        customer, limited = authenticate(email[:254], password[:1025], request.remote_addr or "")
        if customer:
            session.clear()
            session["customer_id"] = customer["id"]
            return redirect(url_for("account"), code=303)
        error = "Te veel pogingen. Probeer over 15 minuten opnieuw." if limited else "E-mailadres of wachtwoord niet correct."
        response = make_response(render_template("customer_auth.html", mode="login", error=error, categories=CATEGORIES), 400 if not limited else 429)
    else:
        response = make_response(render_template("customer_auth.html", mode="login", error=None, categories=CATEGORIES))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/uitloggen", methods=["POST"])
def logout_customer():
    session.clear()
    return redirect(url_for("account"), code=303)


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


@app.route("/control")
def control():
    all_products = load_all_products()
    category_counts = {}
    for product in all_products:
        category_name = product.get("category") or product.get("category_name") or "Onbekend"
        category_counts[category_name] = category_counts.get(category_name, 0) + 1

    offer_count = sum(1 for product in all_products if product.get("old_price") or product.get("is_offer"))
    avg_price = round(sum(float(product.get("price", 0) or 0) for product in all_products) / len(all_products), 2) if all_products else 0
    top_category = max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else "N/A"
    featured_products = sorted(all_products, key=lambda p: (float(p.get("price", 0) or 0), p.get("name", "")), reverse=True)[:8]

    return render_template(
        "control.html",
        products=featured_products,
        stats={
            "total_products": len(all_products),
            "total_categories": len(category_counts),
            "offers": offer_count,
            "avg_price": avg_price,
            "top_category": top_category,
        },
        category_counts=sorted(category_counts.items()),
        categories=CATEGORIES,
    )


INFO_PAGES = {
    "over-trendmix": {"title": "Over TrendMix", "description": "Ontdek het verhaal achter TrendMix, onze vijf productcollecties en hoe we bouwen aan een overzichtelijke webshop met betrouwbare informatie vóór de commerciële opening.", "content": """
        <p>TrendMix wordt ontwikkeld als een moderne webshop waarin overzicht, duidelijke informatie en een prettige winkelervaring centraal staan. Het assortiment is verdeeld over vijf vaste categorieën: Gadgets, Smart Home, Beauty & Care, Home & Living en Lifestyle & Sport.</p>
        <h2>Waar we voor staan</h2><p>We willen klanten niet door een eindeloze catalogus laten zoeken. TrendMix kiest voor een overzichtelijk assortiment en productpagina’s waarop prijs, belangrijkste kenmerken, voorraad- en leverinformatie zo duidelijk mogelijk worden weergegeven.</p>
        <h2>Van testfase naar echte webshop</h2><p>TrendMix bevindt zich momenteel in ontwikkeling. Producten en prijzen in de testcatalogus kunnen nog wijzigen. Echte bestellingen worden pas geactiveerd nadat leverancier, betaling, verzending, retourproces en bedrijfsgegevens definitief zijn ingericht en gecontroleerd.</p>
        <h2>Transparantie</h2><p>Voor de commerciële livegang publiceren we de volledige identiteit en contactgegevens van de verkopende onderneming, de definitieve verkoopvoorwaarden en alle informatie die klanten nodig hebben vóór het sluiten van een overeenkomst.</p>
        <h2>Vragen of feedback</h2><p>Zie je onduidelijke productinformatie of heb je een vraag over TrendMix? Gebruik dan de contactpagina. Feedback uit de testfase gebruiken we om de webshop verder te verbeteren.</p>
    """},
    "bestellen": {"title": "Bestellen & levering", "description": "Informatie over bestellen, prijzen, betalen, levering en orderbevestiging bij TrendMix.", "content": """
        <p>Deze pagina beschrijft hoe het bestelproces van TrendMix wordt ingericht. Zolang de webshop in testfase is, worden geen definitieve betaal- of leverbeloften gedaan.</p>
        <h2>Product en prijs</h2><p>Vóór een commerciële bestelling tonen we de belangrijkste productkenmerken, de totale verkoopprijs inclusief toepasselijke belastingen en eventuele bijkomende kosten. Verzendkosten en andere kosten worden uiterlijk vóór het definitief plaatsen van de bestelling duidelijk gemaakt.</p>
        <h2>Bestellen</h2><p>Je voegt producten toe aan de winkelwagen, controleert aantallen en gegevens en krijgt vóór de definitieve bestelhandeling een overzicht van de bestelling. De bestelknop zal bij livegang ondubbelzinnig duidelijk maken dat de bestelling een betalingsverplichting inhoudt.</p>
        <h2>Betalen</h2><p>De definitieve betaalmethoden worden vóór livegang gepubliceerd. TrendMix brengt geen betaalmethode of toeslag in rekening die niet vooraf duidelijk is vermeld.</p>
        <h2>Levering</h2><p>De beschikbare bezorglanden, verzendkosten, verwachte levertijd en eventuele beperkingen worden vóór de bestelling getoond zodra de leverancier en logistieke inrichting definitief zijn. Na een echte bestelling ontvangt de klant een bevestiging met de relevante bestelgegevens.</p>
        <h2>Probleem met levering</h2><p>Is een bestelling na livegang niet of niet correct geleverd, dan kan de klant contact opnemen met TrendMix. De definitieve contactgegevens en procedure worden vóór livegang op deze website gepubliceerd.</p>
    """},
    "retouren": {"title": "Retour & herroeping", "description": "Informatie over wettelijke bedenktijd, herroeping, retourneren en terugbetaling.", "content": """
        <p>Bij online consumentenkoop geldt in de EU in veel gevallen een wettelijk herroepingsrecht. Voor goederen is de gebruikelijke bedenktijd 14 dagen vanaf ontvangst. Er bestaan wettelijke uitzonderingen; daarom wordt per relevant product duidelijk gemaakt wanneer het herroepingsrecht niet geldt.</p>
        <h2>Een aankoop herroepen</h2><p>Wanneer TrendMix commercieel live gaat, leggen we vóór de koop duidelijk uit hoe je binnen de wettelijke termijn laat weten dat je de overeenkomst wilt herroepen. We publiceren ook het vereiste modelformulier en de definitieve contact- en retourgegevens.</p>
        <h2>Product terugsturen</h2><p>Na een geldige herroeping moet het product binnen de wettelijke termijn worden teruggestuurd. Vóór de koop vermelden we wie de directe retourkosten draagt en, waar vereist, welke kosten daarbij te verwachten zijn.</p>
        <h2>Product beoordelen</h2><p>Tijdens de bedenktijd mag een consument een product beoordelen zoals dat redelijkerwijs in een winkel mogelijk is. Als verder gebruik tot waardevermindering leidt, kan daarvoor volgens de wettelijke regels een vergoeding gelden.</p>
        <h2>Terugbetaling</h2><p>Bij een geldige herroeping wordt de terugbetaling volgens de wettelijke regels uitgevoerd. Daarbij kan in bepaalde gevallen worden gewacht tot het product is ontvangen of bewijs van terugzending is geleverd.</p>
        <h2>Online herroepingsfunctie</h2><p>De commerciële versie van TrendMix krijgt vóór livegang de vereiste online mogelijkheid om een daarvoor in aanmerking komende online aankoop eenvoudig te herroepen, inclusief ontvangstbevestiging.</p>
    """},
    "voorwaarden": {"title": "Algemene voorwaarden", "description": "Conceptuele opbouw van de verkoopvoorwaarden van TrendMix voor de commerciële livegang.", "content": """
        <p>De definitieve algemene voorwaarden worden vóór de commerciële livegang juridisch gecontroleerd en gekoppeld aan de identiteit van de verkopende onderneming. Onderstaande onderdelen beschrijven alvast de structuur die klanten mogen verwachten; deze tekst is nog geen definitieve verkoopovereenkomst.</p>
        <h2>1. Toepasselijkheid en verkoper</h2><p>De voorwaarden zullen vermelden op welke overeenkomsten zij van toepassing zijn en wie de verkopende onderneming is, inclusief handelsnaam, vestigings- en contactgegevens en relevante registratienummers.</p>
        <h2>2. Aanbod en productinformatie</h2><p>TrendMix beschrijft producten zo duidelijk mogelijk. Kennelijke fouten kunnen worden gecorrigeerd. Voor slimme en verbonden producten wordt waar relevant informatie toegevoegd over compatibiliteit, benodigde diensten en updates zodra die informatie door de leverancier is bevestigd.</p>
        <h2>3. Prijzen en kosten</h2><p>Consumentenprijzen worden duidelijk weergegeven inclusief toepasselijke belastingen. Eventuele verzend- of andere bijkomende kosten worden vóór de bestelling kenbaar gemaakt.</p>
        <h2>4. Totstandkoming van de overeenkomst</h2><p>De definitieve voorwaarden beschrijven wanneer een bestelling is geplaatst, wanneer een overeenkomst tot stand komt en hoe de klant daarvan een bevestiging ontvangt.</p>
        <h2>5. Betaling en levering</h2><p>Beschikbare betaalmethoden, levergebieden, verwachte levertijden en eventuele beperkingen worden vóór de koop duidelijk gemaakt.</p>
        <h2>6. Herroeping en retour</h2><p>Voor consumenten wordt het wettelijke herroepingsrecht uitgelegd, inclusief termijn, werkwijze, uitzonderingen, retourkosten en terugbetaling. Zie ook de aparte pagina Retour & herroeping.</p>
        <h2>7. Wettelijke rechten en conformiteit</h2><p>De voorwaarden beperken geen wettelijke consumentenrechten. Als een geleverd product niet aan de overeenkomst beantwoordt, gelden de toepasselijke wettelijke rechten.</p>
        <h2>8. Klachten</h2><p>Klachten kunnen na livegang via de gepubliceerde contactkanalen worden ingediend. De definitieve procedure vermeldt hoe klachten worden geregistreerd en beantwoord en welke geschillenroute van toepassing is.</p>
        <h2>9. Privacy</h2><p>Persoonsgegevens worden alleen verwerkt voor duidelijk omschreven doeleinden en volgens het privacybeleid. Voor externe betaal-, verzend- of technische dienstverleners wordt uitgelegd welke rol zij hebben.</p>
        <h2>10. Wijzigingen</h2><p>Nieuwe voorwaarden gelden niet met terugwerkende kracht ten nadele van reeds gesloten overeenkomsten. De versie die bij een bestelling hoort, moet door de klant kunnen worden bewaard of geraadpleegd.</p>
    """},
    "privacy": {"title": "Privacybeleid", "description": "Lees hoe TrendMix persoonsgegevens verwerkt tijdens de ontwikkeling van de webshop, welke gegevens nodig kunnen zijn en hoe we privacy-informatie aanvullen vóór livegang.", "content": """
        <p>TrendMix wil alleen persoonsgegevens verwerken die nodig zijn om de webshop te laten functioneren, vragen te beantwoorden en — na commerciële livegang — bestellingen uit te voeren. Vóór livegang wordt dit privacybeleid aangevuld met de definitieve identiteit en contactgegevens van de verwerkingsverantwoordelijke.</p>
        <h2>Welke gegevens</h2><p>Afhankelijk van de gebruikte functie kunnen naam, contactgegevens, aflever- en factuurgegevens, bestelgegevens en technische gegevens worden verwerkt. We vragen niet meer gegevens dan nodig is voor het betreffende doel.</p>
        <h2>Waarvoor</h2><p>Gegevens kunnen worden gebruikt voor klantenservice, uitvoering en administratie van bestellingen, fraudepreventie, wettelijke verplichtingen en het technisch functioneren van de webshop. De definitieve grondslagen en bewaartermijnen worden vóór livegang per doel beschreven.</p>
        <h2>Dienstverleners</h2><p>Voor onder meer hosting, betaling, e-mail en verzending kunnen externe dienstverleners nodig zijn. Zodra deze partijen definitief zijn gekozen, wordt relevante informatie hierover opgenomen in het privacybeleid.</p>
        <h2>Jouw privacyrechten</h2><p>De definitieve privacyverklaring legt uit hoe betrokkenen hun toepasselijke rechten kunnen uitoefenen, zoals inzage, correctie of verwijdering waar de wet dat toestaat.</p>
        <h2>Beveiliging en contact</h2><p>TrendMix neemt passende technische en organisatorische maatregelen voor de functies die worden aangeboden. Het definitieve privacycontact wordt vóór commerciële livegang gepubliceerd.</p>
    """},
    "cookies": {"title": "Cookies & voorkeuren", "description": "Informatie over functionele opslag, cookies en toekomstige toestemming.", "content": """
        <p>TrendMix gebruikt tijdens de ontwikkeling functionele browseropslag voor onderdelen zoals taalvoorkeur en winkelwagenfunctionaliteit. Deze functies zijn bedoeld om de website technisch te laten werken en voorkeuren te onthouden.</p>
        <h2>Functionele opslag</h2><p>Een taalkeuze of winkelwagen kan lokaal of via een sessie worden bewaard. Zonder deze technische functies kan een deel van de webshop minder goed werken.</p>
        <h2>Analyse en marketing</h2><p>Voordat niet-noodzakelijke analyse- of marketingtechnologie wordt geactiveerd, wordt gecontroleerd welke toestemming en informatie daarvoor nodig is. TrendMix activeert zulke technologie niet als daarvoor eerst geldige toestemming vereist is.</p>
        <h2>Voorkeuren wijzigen</h2><p>Bij livegang komt er, indien nodig voor de gebruikte technologie, een duidelijke manier om cookie- en privacyvoorkeuren te bekijken en te wijzigen. Browsergegevens kunnen daarnaast via de instellingen van de browser worden verwijderd.</p>
    """},
}


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
    # JSON-LD image links must be absolute; do not change rendered gallery URLs.
    base_url = SITE_URL or request.url_root.rstrip("/")
    match["seo_images"] = [
        image if image.startswith(("https://", "http://")) else base_url + "/" + image.lstrip("/")
        for image in match.get("images", [])
    ]
    match["seo_verified"] = review_product(raw)["ready"]
    related = [
        enrich_product(raw, category_slug, index)
        for index, raw in enumerate(products[category_slug])
        if enrich_product(raw, category_slug, index)["id"] != match["id"]
    ][:6]
    return render_template(
        "product.html",
        product=match,
        show_demo_review=(not os.getenv("VERCEL_ENV") and os.getenv("TRENDMIX_SHOW_DEMO_REVIEWS") == "1"),
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
            "country": request.form.get("country", "").strip().upper(),
        }
        consent = request.form.get("checkout_consent") == "yes"
        if not all(customer.values()):
            error = "Vul alle verplichte gegevens in."
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", customer["email"]):
            error = "Vul een geldig e-mailadres in."
        elif not consent:
            error = "Controleer en bevestig je gegevens voordat je doorgaat."
        elif live_orders_enabled():
            order, error = create_woo_order(cart, customer)
            if order:
                session.pop("trendmix_cart", None)
                return render_template("checkout.html", categories=CATEGORIES, cart=[], cart_count=0, cart_total=0, test_mode=False, order=order, error=None)
        else:
            # Flask session data is stored in a signed but readable browser cookie.
            # Never retain customer names, emails or addresses in that cookie.
            session.pop("trendmix_test_checkout", None)
            return render_template("checkout.html", categories=CATEGORIES, cart=cart, cart_count=cart_count(), cart_total=total, test_mode=True, order={"id": "TEST"}, error=None)
    return render_template("checkout.html", categories=CATEGORIES, cart=cart, cart_count=cart_count(), cart_total=total, test_mode=not live_orders_enabled(), order=order, error=error, customer=(customer if request.method == "POST" else {}))


@app.route("/faq")
def faq():
    return render_template("faq.html", categories=CATEGORIES)

@app.route("/contact", methods=["GET"])
def contact_page():
    return render_template("contact.html", categories=CATEGORIES, search_query="")

@app.route("/contact", methods=["POST"])
def contact():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

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
        "subject": f"TrendMix contactformulier: {name}",
        "text": f"Naam: {name}\\nE-mail: {email}\\n\\nBericht:\\n{message}",
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

@app.route("/over-trendmix")
def over_trendmix():
    return render_info_page("over-trendmix")


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
    urls = [f"{site_url}/", f"{site_url}/shop"] + [f"{site_url}/{slug}" for slug in CATEGORIES] + [f"{site_url}/{path}" for path in INFO_PAGES] + [f"{site_url}/faq"]
    for slug, items in products.items():
        for index, raw in enumerate(items):
            # Do not submit unverified test products as indexable listings.
            if review_product(raw)["ready"]:
                urls.append(f"{site_url}{enrich_product(raw, slug, index)['product_url']}")
    from xml.sax.saxutils import escape
    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" + "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">" + "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls) + "</urlset>"
    return Response(xml, mimetype="application/xml")


@app.after_request
def trendmix_security_headers(response):
    # Safe baseline headers; a strict CSP requires a separate audit of inline scripts.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if os.getenv("VERCEL_ENV"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.path in ("/winkelwagen", "/afrekenen", "/wishlist", "/contact") or request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
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
