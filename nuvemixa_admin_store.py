"""Persistent NUVEMIXA administration records.

Only manually entered supplier contacts and research notes are stored here.
This module never creates customer orders, charges payments or publishes products.
Production configuration should keep SQLite files outside the git checkout.
"""
import sqlite3
from contextlib import contextmanager

from nv_storage_paths import ADMIN_DB
import nv_dashboard_postgres


def database_path():
    return ADMIN_DB


@contextmanager
def connect():
    if nv_dashboard_postgres.runtime_enabled():
        with nv_dashboard_postgres.application_db() as db:
            yield db
        return
    path = database_path()
    if not path.parent.is_dir():
        raise RuntimeError("Admin database parent directory does not exist")
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                contact_email TEXT NOT NULL DEFAULT '',
                website TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'onderzoek'
                   CHECK (status IN ('onderzoek','goedgekeurd','afgekeurd')),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                product_name TEXT NOT NULL,
                supplier_id INTEGER,
                purchase_cost_cents INTEGER,
                shipping_cost_cents INTEGER,
                selling_price_cents INTEGER,
                source TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
            )
        """)
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_suppliers():
    with connect() as db:
        rows = db.execute(
            "SELECT id,name,contact_email,website,notes,status,updated_at "
            "FROM suppliers ORDER BY lower(name) LIMIT 250"
        ).fetchall()
        return [dict(row) for row in rows]


def add_supplier(name, contact_email="", website="", notes=""):
    name = str(name).strip()
    contact_email = str(contact_email).strip()
    website = str(website).strip()
    notes = str(notes).strip()
    if not 2 <= len(name) <= 120:
        raise ValueError("Naam moet 2 tot 120 tekens bevatten.")
    if len(contact_email) > 254 or len(website) > 500 or len(notes) > 1500:
        raise ValueError("Een van de velden is te lang.")
    if contact_email and ("@" not in contact_email or any(c.isspace() for c in contact_email)):
        raise ValueError("Ongeldig e-mailadres.")
    if website and not website.startswith(("https://", "http://")):
        raise ValueError("Website moet beginnen met https:// of http://.")
    with connect() as db:
        db.execute(
            "INSERT INTO suppliers(name,contact_email,website,notes) VALUES (?,?,?,?)",
            (name, contact_email, website, notes)
        )


def list_research():
    with connect() as db:
        rows = db.execute("""
            SELECT r.id,r.category,r.product_name,r.purchase_cost_cents,
                   r.shipping_cost_cents,r.selling_price_cents,r.source,
                   r.notes,r.updated_at,s.name AS supplier_name
            FROM research_notes r LEFT JOIN suppliers s ON r.supplier_id=s.id
            ORDER BY r.id DESC LIMIT 250
        """).fetchall()
        return [dict(row) for row in rows]


def add_research(category, product_name, source="", notes=""):
    category = str(category).strip()
    product_name = str(product_name).strip()
    source = str(source).strip()
    notes = str(notes).strip()
    if not (2 <= len(category) <= 80 and 2 <= len(product_name) <= 160):
        raise ValueError("Vul een categorie en productnaam in.")
    if len(source) > 500 or len(notes) > 1500:
        raise ValueError("Bron of notities te lang.")
    with connect() as db:
        db.execute(
            "INSERT INTO research_notes(category,product_name,source,notes) VALUES (?,?,?,?)",
            (category, product_name, source, notes)
        )
