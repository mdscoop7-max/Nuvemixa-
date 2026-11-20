"""Local edits layered over the supplied test catalogue."""
import json
import re
import sqlite3
import uuid
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import nv_dashboard_postgres
from urllib.parse import urlsplit

from flask import abort, current_app, g, has_request_context, request
from nv_dashboard_manager import DB, bp, connect, management_result, require_admin
from nv_permissions import allowed


# Snelheid: elke pagina (dashboard en webshop) las de cataloguswijzigingen opnieuw uit de database; elke
# verbinding Render (Oregon) -> Neon (Frankfurt) kost seconden. Kort bewaren in het geheugen; save() leegt dit.
CACHE_SECONDS = 30
_changes_cache = {"at": 0.0, "value": None}


def invalidate_changes():
    _changes_cache.update(at=0.0, value=None)


def catalog_changes():
    import time
    cached = _changes_cache["value"]
    if cached is not None and time.monotonic() - _changes_cache["at"] < CACHE_SECONDS:
        return list(cached[0]), list(cached[1])
    value = _read_catalog_changes()
    if not (has_request_context() and g.get("nv_catalog_read_failed")):
        _changes_cache.update(at=time.monotonic(), value=(tuple(value[0]), tuple(value[1])))
    return value


def _read_catalog_changes():
    if not nv_dashboard_postgres.runtime_enabled() and not DB.is_file():
        return [], []
    try:
        with nv_dashboard_postgres.read_db(DB, timeout=2) as db:
            exists = nv_dashboard_postgres.table_exists(db, "catalog_edits")
            if not exists:
                return [], []
            order = "position" if nv_dashboard_postgres.runtime_enabled() else "rowid"
            rows = db.execute(f"SELECT kind, category, slug, payload FROM catalog_edits "
                             f"WHERE kind IN ('category','product') ORDER BY {order}")
            categories, products = [], []
            for row in rows:
                target = categories if row["kind"] == "category" else products
                target.append((row["category"], row["slug"], json.loads(row["payload"])))
            return categories, products
    except (sqlite3.Error, OSError, ValueError):
        if has_request_context():
            g.nv_catalog_read_failed = True
        current_app.logger.error("Lokale cataloguswijzigingen kunnen niet worden gelezen")
        return [], []


def save(db, kind, category, slug, payload):
    invalidate_changes()
    db.execute(
        """INSERT INTO catalog_edits(kind,category,slug,payload) VALUES(?,?,?,?)
           ON CONFLICT(kind,category,slug) DO UPDATE SET payload=excluded.payload""",
        (kind, category, slug, json.dumps(payload, ensure_ascii=False)),
    )


def validated_product(form, existing):
    name = form.get("name", "").strip()
    price = form.get("price", "").strip()
    quantity = form.get("stock_quantity", "").strip()
    status = form.get("stock_status")
    description = form.get("description", "").strip()
    if (not 1 <= len(name) <= 160 or len(description) > 4000
            or not re.fullmatch(r"\d{1,7}([.,]\d{1,2})?", price)
            or not re.fullmatch(r"\d{0,8}", quantity)
            or status not in {"unknown", "in_stock", "out_of_stock"}):
        raise ValueError("Controleer productnaam, prijs en voorraad.")
    units = int(quantity) if quantity else None
    if (status == "in_stock" and units == 0) or (status == "out_of_stock" and units):
        raise ValueError("De voorraadstatus en het aantal spreken elkaar tegen.")
    return {
        **existing, "name": name, "price": float(Decimal(price.replace(",", "."))),
        "stock_status": status, "stock_quantity": units, "description": description,
    }


IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MAX_SIDE = 1200


def processed_upload(upload):
    """Productfoto van je computer: alleen echte JPG/PNG/WebP/GIF, verkleind tot max. 1200 px en opgeslagen als WebP.
    Geeft (sleutel, base64-data) terug of None als er geen bestand is gekozen."""
    if upload is None or not upload.filename:
        return None
    data = upload.read(IMAGE_MAX_BYTES + 1)
    if not data:
        return None
    if len(data) > IMAGE_MAX_BYTES:
        raise ValueError("De foto is groter dan 5 MB. Kies een kleinere foto.")
    import base64
    import hashlib
    import io
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP", "GIF", "MPO"}:
                raise ValueError("Gebruik een JPG-, PNG- of WebP-foto.")
            if source.width * source.height > 40_000_000:
                raise ValueError("De foto is te groot (te veel pixels).")
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
            out = io.BytesIO()
            image.save(out, "WEBP", quality=82, method=4)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("Dit bestand is geen bruikbare foto.") from None
    webp = out.getvalue()
    return hashlib.sha256(webp).hexdigest()[:24], base64.b64encode(webp).decode("ascii")


def stored_image(key):
    """WebP-bytes van een geüploade productfoto, of None."""
    import base64
    if not re.fullmatch(r"[0-9a-f]{24}", key or ""):
        return None
    try:
        with nv_dashboard_postgres.read_db(DB, timeout=3) as db:
            if not nv_dashboard_postgres.table_exists(db, "catalog_edits"):
                return None
            row = db.execute("SELECT payload FROM catalog_edits WHERE kind='image' AND category='upload' AND slug=?",
                             (key,)).fetchone()
    except (sqlite3.Error, OSError):
        return None
    if not row:
        return None
    return base64.b64decode(json.loads(row[0])["data"])


@bp.get("/img/extra/<key>.webp")
def extra_image(key):
    from flask import Response
    data = stored_image(key)
    if data is None:
        abort(404)
    response = Response(data, mimetype="image/webp")
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def validated_extra(form, existing):
    """Extra product: dezelfde basiscontroles plus inkoopprijs, afbeelding, korte tekst en zichtbaarheid.
    Alleen wat jij invult wordt opgeslagen; er wordt niets aangevuld of verzonnen."""
    product = validated_product(form, existing)
    cost = form.get("cost_price", "").strip()
    if cost and not re.fullmatch(r"\d{1,7}([.,]\d{1,2})?", cost):
        raise ValueError("Controleer de inkoopprijs.")
    image = form.get("image", "").strip()
    if image and not (valid_image(image) or re.fullmatch(r"/img/extra/[0-9a-f]{24}\.webp", image)):
        raise ValueError("Gebruik een geldige HTTPS-afbeeldingslink of een bestaand lokaal afbeeldingsbestand.")
    short = form.get("short_description", "").strip()
    if len(short) > 300:
        raise ValueError("De korte omschrijving mag maximaal 300 tekens zijn.")
    product["cost_price"] = float(Decimal(cost.replace(",", "."))) if cost else 0
    product["short_description"] = short
    if image:
        images = [image] + [url for url in existing.get("images") or [] if url != image]
        product.update(image=image, images=images, image_verified=False)
    product["hidden"] = form.get("visible") != "1"
    product["extra"] = True
    return product


def valid_image(url):
    if not 1 <= len(url) <= 1500 or re.search(r"[\s\\]", url):
        return False
    parsed = urlsplit(url)
    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment:
        return not any(host in parsed.hostname for host in ("loremflickr.com", "placeimg.com", "source.unsplash.com"))
    return bool(re.fullmatch(r"/static/[a-zA-Z0-9_./-]+\.(?:png|jpe?g|webp|gif|avif)", url, re.I)
                and ".." not in parsed.path.split("/")
                and Path(current_app.root_path, parsed.path.lstrip("/")).is_file())


@bp.post("/admin/nv/catalog")
def catalog():
    CATEGORIES, catalog_items, slugify = current_app.extensions["nuvemixa_catalog_api"]
    section = request.form.get("section")
    if section not in {"producten", "categorieen", "afbeeldingen", "extra-producten"}:
        abort(400)
    category = request.form.get("category", "")
    slug = request.form.get("slug", "")
    deleting_extra = section == "extra-producten" and request.form.get("op") == "delete"
    if deleting_extra and not (slug and category):
        abort(400)
    if deleting_extra and not current_app.extensions["nuvemixa_admin_checker"]():
        abort(403)
    permission = {"categorieen": "category_manage", "afbeeldingen": "image_manage",
                  "producten": "product_edit" if slug else "product_add",
                  "extra-producten": "product_edit" if slug else "product_add"}[section]
    if not allowed(permission):
        abort(403)
    try:
        with connect() as db:
            if not nv_dashboard_postgres.runtime_enabled():
                db.execute("""CREATE TABLE IF NOT EXISTS catalog_edits(
                    kind TEXT NOT NULL, category TEXT NOT NULL, slug TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(kind,category,slug))""")
            nv_dashboard_postgres.lock_catalog(db)
            # Read the current committed snapshot while holding the write lock.
            if section == "categorieen":
                name = request.form.get("name", "").strip()
                category = category or slugify(name)
                if (not 2 <= len(name) <= 80 or not re.fullmatch(r"[a-z0-9-]{2,80}", category)
                        or category in {"admin", "api", "static", "shop", "products", "account", "cart", "dashboard", "control"}
                        or any(key != category and value["name"].casefold() == name.casefold()
                               for key, value in CATEGORIES.items())):
                    raise ValueError("Gebruik een unieke categorienaam van 2 tot 80 tekens.")
                if not request.form.get("category") and category in CATEGORIES:
                    raise ValueError("Deze categorie bestaat al.")
                if request.form.get("category") and category not in CATEGORIES:
                    abort(404)
                if category not in CATEGORIES and current_app.url_map.bind("localhost").match("/" + category)[0] != "category_page":
                    raise ValueError("Deze naam is gereserveerd voor een bestaande pagina.")
                save(db, "category", category, "", {"name": name})
            else:
                if category not in CATEGORIES:
                    raise ValueError("Kies een bestaande categorie.")
                existing = next((item for item in catalog_items()
                                 if item["category_slug"] == category and item["slug"] == slug), None)
                if slug and existing is None:
                    abort(404)
                row = db.execute(
                    "SELECT payload FROM catalog_edits WHERE kind='product' AND category=? AND slug=?",
                    (category, slug),
                ).fetchone()
                changes = json.loads(row[0]) if row else {}
                if deleting_extra:
                    # Only locally added products; never delete a built-in catalogue product.
                    if (existing is None or not changes.get("extra")
                            or not str(changes.get("id", "")).startswith("tm-local-")):
                        abort(404)
                    deleted = db.execute(
                        "DELETE FROM catalog_edits WHERE kind='product' AND category=? AND slug=?",
                        (category, slug),
                    )
                    if deleted.rowcount != 1:
                        abort(404)
                elif section == "afbeeldingen":
                    if existing is None:
                        abort(404)
                    url = request.form.get("image", "").strip()
                    if not valid_image(url):
                        raise ValueError("Gebruik een geldige HTTPS-afbeeldingslink of een bestaand lokaal afbeeldingsbestand.")
                    images = list(existing["images"])
                    if url in images:
                        images.remove(url)
                    if request.form.get("primary") == "1":
                        images.insert(0, url)
                        changes["image"] = url
                    else:
                        images.append(url)
                    changes["images"] = images
                    changes["image_verified"] = False
                elif section == "extra-producten" and request.form.get("op") == "visibility":
                    if existing is None or not changes.get("extra"):
                        abort(404)
                    changes["hidden"] = request.form.get("visible") != "1"
                else:
                    if section == "extra-producten" and slug and not changes.get("extra"):
                        abort(404)  # alleen zelf toegevoegde producten zijn hier te bewerken
                    updated = (validated_extra if section == "extra-producten" else validated_product)(request.form, changes)
                    if section == "extra-producten":
                        upload = processed_upload(request.files.get("image_file"))
                        if upload:
                            key, data = upload
                            save(db, "image", "upload", key, {"mime": "image/webp", "data": data})
                            url = f"/img/extra/{key}.webp"
                            updated.update(image=url, images=[url] + [u for u in updated.get("images") or [] if u != url],
                                           image_verified=False)
                    if not slug:
                        slug = slugify(updated["name"])[:100]
                        if not slug or any(item["category_slug"] == category and item["slug"] == slug
                                           for item in catalog_items()):
                            raise ValueError("Deze productnaam bestaat al in de categorie.")
                        updated.update(id="tm-local-" + uuid.uuid4().hex, slug=slug)
                    if not existing or existing["price"] != updated["price"]:
                        updated["price_verified"] = False
                    if not existing or existing["name"] != updated["name"] or existing["description"] != updated["description"]:
                        updated["product_data_verified"] = False
                    changes = updated
                save(db, "product", category, slug, changes)
    except ValueError as exc:
        return management_result(section, str(exc))
    except (sqlite3.Error, OSError):
        current_app.logger.error("Lokale cataloguswijziging kon niet worden opgeslagen")
        return management_result(section, "De cataloguswijziging kon niet worden opgeslagen.")
    invalidate_changes()  # na de commit: volgende pagina leest de nieuwe stand
    if deleting_extra:
        return management_result(section, "Extra product verwijderd.", success=True)
    if section == "extra-producten":
        state = "zichtbaar in de webshop" if not changes.get("hidden") else "opgeslagen als concept (niet zichtbaar in de webshop)"
        return management_result(section, f"Product {state}.", success=True)
    return management_result(section, "Cataloguswijziging opgeslagen.", success=True)
