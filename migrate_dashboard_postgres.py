"""Verify three independent SQLite snapshots and import into an empty dashboard schema."""
import argparse
from contextlib import closing
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from psycopg import Error, sql

import nv_dashboard_postgres

FILES = {
    "nuvemixa_dashboard.sqlite3": {
        "staff": ("id email name password_hash role active username session_version permissions", "id"),
        "coupons": ("id code kind amount starts ends usage_limit used active", "id"),
        "visits": ("day visitor views", "day visitor"),
        "seo_scans": ("id created_at payload", "id"),
        "catalog_edits": ("kind category slug payload", "kind category slug"),
        "storefront_visits": ("traffic day marker measured_at", "traffic day marker"),
    },
    "nuvemixa_customers.sqlite3": {
        "customers": ("id name email password_hash created_at", "id"),
        "nv_customer_activity": ("id customer_id event_type occurred_at", "id"),
    },
    "nuvemixa_admin.sqlite3": {
        "suppliers": ("id name contact_email website notes status updated_at", "id"),
        "research_notes": ("id category product_name supplier_id purchase_cost_cents shipping_cost_cents selling_price_cents source notes updated_at", "id"),
        "market_research": ("market product data updated_at", "market product"),
        "viral_candidates": ("id title country niche notes assessment", "id"),
        "viral_observations": ("candidate platform source observed window metric value estimate", "candidate platform source observed window metric"),
        "product_dossier_offers": ("candidate_id market payload", "candidate_id market"),
    },
}
REQUIRED = {"staff", "coupons", "customers", "suppliers", "research_notes"}


def source_rows(bundle, checksums):
    if set(checksums) != FILES.keys():
        raise ValueError("Verwacht precies drie onafhankelijk gecontroleerde SQLite-snapshots.")
    result = {}
    for filename, tables in FILES.items():
        source = bundle / filename
        if source.is_symlink() or any(Path(str(source) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise ValueError("Gebruik zelfstandige SQLite-snapshots zonder symlinks of journalbestanden.")
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != checksums[filename]:
            raise ValueError(f"Snapshotchecksum wijkt af voor {filename}.")
        with closing(sqlite3.connect(":memory:")) as db:
            if payload[18:20] == bytes((2, 2)):
                payload = payload[:18] + bytes((1, 1)) + payload[20:]
            db.deserialize(payload)
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError(f"Integriteitscontrole mislukt voor {filename}.")
            discovered = {row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")
                          if not row[0].startswith("sqlite_")}
            if discovered - tables.keys() or (REQUIRED & tables.keys()) - discovered:
                raise ValueError(f"Onverwacht of onvolledig bronschema in {filename}.")
            for table, (column_text, keys) in tables.items():
                columns = column_text.split()
                if table not in discovered:
                    result[table] = (columns, keys.split(), [])
                    continue
                actual = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
                if actual != set(columns):
                    raise ValueError(f"Pas de kolomtoewijzing bewust aan voor {table}.")
                selection = ",".join(f'"{col}"' for col in columns)
                rows = db.execute(f'SELECT {selection} FROM "{table}"').fetchall()
                if table == "coupons":
                    rows = [row[:3] + (Decimal(str(row[3])),) + row[4:] for row in rows]
                result[table] = (columns, keys.split(), rows)
    return result


def import_rows(db, tables):
    relations = {key: sql.Identifier("nuvemixa_dashboard", key) for key in tables}
    db.execute(sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE")
               .format(sql.SQL(", ").join(relations.values())))
    for key, relation in relations.items():
        if db.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM {})").format(relation)).fetchone()[0]:
            raise ValueError(f"Import gestopt. Doeltabel {key} bevat gegevens.")
    for table, (columns, keys, rows) in tables.items():
        relation = relations[table]
        fields = sql.SQL(", ").join(map(sql.Identifier, columns))
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
        if rows:
            with db.cursor() as cursor:
                cursor.executemany(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    relation, fields, placeholders), rows)
            if columns[0] == "id":
                next_id = max(0, max(row[0] for row in rows)) + 1
                db.execute(sql.SQL("ALTER TABLE {} ALTER COLUMN id RESTART WITH {}")
                           .format(relation, sql.Literal(next_id)))
        imported = db.execute(sql.SQL("SELECT {} FROM {}").format(fields, relation)).fetchall()
        positions = [columns.index(key) for key in keys]
        def identity(row):
            return tuple(row[index] for index in positions)
        if {identity(row): row for row in imported} != {identity(row): row for row in rows} or len(imported) != len(rows):
            raise ValueError(f"Controle na import mislukt voor {table}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True,
                        help="Apart bewaard JSON-bestand met bestandsnamen en SHA-256-hashes.")
    parser.add_argument("--apply", action="store_true", help="Schrijf alleen naar het expliciet ingestelde, lege doel.")
    args = parser.parse_args()
    try:
        tables = source_rows(args.bundle, json.loads(args.checksums.read_text(encoding="utf-8")))
        if args.apply:
            with nv_dashboard_postgres.connect() as db:
                import_rows(db, tables)
        print(json.dumps({name: len(data[2]) for name, data in tables.items()}, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, Error, KeyError):
        # Driver errors can include connection and data values.
        print("Migratie gestopt. Controleer de snapshots, kolomtoewijzing en het lege dashboarddoel.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
