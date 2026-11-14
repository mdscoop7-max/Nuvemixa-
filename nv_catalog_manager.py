"""Local edits layered over the supplied test catalogue."""
import json
import re
import sqlite3
import uuid
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, current_app, g, has_request_context, request
from nv_dashboard_manager import DB, bp, connect, management_result
from nv_permissions import allowed


def catalog_changes():
    if not DB.is_file():
        return [], []
    try:
        with closing(sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='catalog_edits'").fetchone()
            if not exists:
                return [], []
            rows = db.execute("SELECT kind, category, slug, payload FROM catalog_edits ORDER BY rowid")
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
    if section not in {"producten", "categorieen", "afbeeldingen"}:
        abort(400)
    category = request.form.get("category", "")
    slug = request.form.get("slug", "")
    permission = {"categorieen": "category_manage", "afbeeldingen": "image_manage",
                  "producten": "product_edit" if slug else "product_add"}[section]
    if not allowed(permission):
        abort(403)
    try:
        with connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS catalog_edits(
                kind TEXT NOT NULL, category TEXT NOT NULL, slug TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(kind,category,slug))""")
            db.execute("BEGIN IMMEDIATE")
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
                if section == "afbeeldingen":
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
                else:
                    updated = validated_product(request.form, changes)
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
    return management_result(section, "Cataloguswijziging opgeslagen.", success=True)
