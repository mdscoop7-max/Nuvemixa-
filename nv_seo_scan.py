"""Local, reproducible checks of the shop's rendered SEO metadata."""
import json
import os
import sqlite3
from html.parser import HTMLParser
from urllib.parse import urlsplit

from flask import current_app, request
from nv_dashboard_manager import bp, connect, management_result, require_admin


class ProductMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.structured_data = []
        self.capture = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title" or (tag == "script" and attrs.get("type") == "application/ld+json"):
            self.capture = tag
            self.buffer = []
        elif tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content") or ""
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href") or ""

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if self.capture != tag:
            return
        value = "".join(self.buffer).strip()
        if tag == "title":
            self.title = value
        else:
            try:
                self.structured_data.append(json.loads(value))
            except ValueError:
                self.structured_data.append(None)
        self.capture = None


def canonical_matches(value, path, base_url):
    try:
        canonical = urlsplit(value)
        target = urlsplit(os.getenv("NUVEMIXA_CANONICAL_URL") or base_url)
        return (canonical.scheme in {"http", "https"} and canonical.scheme == target.scheme
                and canonical.hostname == target.hostname and canonical.hostname is not None
                and canonical.port == target.port and not canonical.username and not canonical.password
                and not canonical.query and not canonical.fragment and canonical.path == path)
    except ValueError:
        return False


def last_scan():
    with connect() as db:
        table = db.execute("SELECT 1 FROM sqlite_master WHERE name='seo_scans'").fetchone()
        if not table:
            return None
        row = db.execute("SELECT created_at,payload FROM seo_scans ORDER BY id DESC LIMIT 1").fetchone()
        return (row["created_at"], json.loads(row["payload"])) if row else None


@bp.post("/admin/nv/seo-scan")
@require_admin
def seo_scan():
    _, catalog_items, _ = current_app.extensions["nuvemixa_catalog_api"]
    path = request.form.get("product_url", "")
    if not any(item["product_url"] == path for item in catalog_items()):
        return management_result("seo", "Kies een product uit de catalogus.")
    try:
        response = current_app.test_client().get(path, base_url=request.host_url, environ_overrides={"nuvemixa.internal_check": True})
        if response.status_code != 200 or response.mimetype != "text/html":
            return management_result("seo", f"Scan mislukt. De productpagina gaf HTTP {response.status_code}.")
        metadata = ProductMetadata()
        metadata.feed(response.get_data(as_text=True))
        metadata.close()
        schema = next((item for item in metadata.structured_data
                       if isinstance(item, dict) and item.get("@type") == "Product"), None)
        checks = [
            ["Paginatitel", bool(metadata.title), metadata.title],
            ["Metabeschrijving", bool(metadata.description), metadata.description],
            ["Canonieke productlink", canonical_matches(metadata.canonical, path, request.host_url),
             metadata.canonical],
            ["Productgegevens (JSON-LD)", bool(schema), str(schema.get("name") or "") if schema else ""],
        ]
        report = {"path": path, "checks": checks}
        with connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS seo_scans(
                       id INTEGER PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                       payload TEXT NOT NULL)""")
            db.execute("INSERT INTO seo_scans(payload) VALUES(?)", (json.dumps(report, ensure_ascii=False),))
    except (sqlite3.Error, OSError, ValueError):
        current_app.logger.error("Lokale SEO-controle mislukt")
        return management_result("seo", "De scan kon niet worden uitgevoerd of opgeslagen.")
    return management_result("seo", "Lokale SEO-controle opgeslagen.", success=True)
