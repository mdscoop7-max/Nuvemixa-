"""Bounded local checks for the NUVEMIXA dashboard. No external requests."""
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from time import perf_counter
import os
import re
import sqlite3

from flask import current_app, g, request
from jinja2 import meta

from nuvemixa_admin_store import database_path
from nv_merchant_audit import audit as merchant_audit
from nv_dashboard_manager import DB, coupon_amount
import nv_dashboard_postgres
from nv_permissions import RIGHTS, SECTIONS
from nv_seo_scan import ProductMetadata, canonical_matches
from nv_visits import visit_summary


def database_check(path, tables, columns=None):
    if not nv_dashboard_postgres.runtime_enabled() and not path.is_file():
        return "attention", "Databasebestand ontbreekt.", "Open de bijbehorende functie om de lokale database in te richten."
    with nv_dashboard_postgres.read_db(path, timeout=0.25) as db:
        for table in tables:
            db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        if columns:
            actual = nv_dashboard_postgres.columns_for(db, "staff")
            if not set(columns) <= actual:
                return "attention", "Het accountschema wacht op migratie.", "Open Accountbeheer als beheerder."
    return "works", "De vereiste tabellen zijn leesbaar.", ""


def check_customers(path):
    if not nv_dashboard_postgres.runtime_enabled() and not path.is_file():
        if path.exists() or path.is_symlink():
            return "error", "Het ingestelde klantdatabasepad is geen bestand.", "Controleer het ingestelde pad."
        if not path.parent.is_dir():
            return "error", "De ingestelde opslagmap voor klanten ontbreekt.", "Controleer het databasepad en de opslagmap."
        return ("attention", "Geen databasebestand op het ingestelde klantdatabasepad.",
                "Controleer of de bestaande klantdatabase elders staat. Initialiseer alleen als dit een lege installatie is.")
    with nv_dashboard_postgres.read_db(path, timeout=0.25) as db:
        if not nv_dashboard_postgres.table_exists(db, "customers"):
            return ("attention", "Het databasebestand bestaat, maar de klanttabel ontbreekt.",
                    "Initialiseer de klanttabel alleen als dit het bedoelde bestand is.")
        columns = {name.lower() for name in nv_dashboard_postgres.columns_for(db, "customers")}
        missing = {"id", "name", "email", "password_hash", "created_at"} - columns
        if missing:
            return ("error", "Ontbrekende klantkolommen: " + ", ".join(sorted(missing)) + ".",
                    "Controleer de bestaande schema-versie voordat je iets wijzigt.")
        has_customers = db.execute("SELECT 1 FROM customers LIMIT 1").fetchone() is not None
    return "works", "Klanttabel is leesbaar." if has_customers else "Klanttabel is leesbaar en leeg.", ""


def inspect_files():
    environment = current_app.jinja_env
    pending = ["dashboard.html", "control.html", "admin_login.html", "nv_commerce.html",
               "product.html", "category.html", "nv_monitoring_report.html"]
    visited = set()
    missing = []
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        source, _, _ = environment.loader.get_source(environment, name)
        environment.get_template(name)
        pending.extend(ref for ref in meta.find_referenced_templates(environment.parse(source)) if ref)
        filenames = re.findall(r"""url_for\(\s*['"](?:static|nuvemixa_woo\.static)['"]\s*,\s*filename\s*=\s*['"]([^'"]+)""", source)
        missing.extend(filename for filename in filenames if not (Path(current_app.static_folder) / filename).is_file())
    if missing:
        return "error", "Ontbrekend: " + ", ".join(sorted(set(missing))), "Herstel de bestanden uit de testbundel."
    return "works", f"{len(visited)} templates gecompileerd en hun statische verwijzingen gecontroleerd.", ""


def scan(items, categories, customer_db, integrations):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    started = perf_counter()

    def add(name, check, status, result, solution=""):
        results.append(dict(name=name, check=check, status=status, result=result, solution=solution, checked_at=timestamp))

    def run(name, check, operation, recovery):
        check_started = perf_counter()
        try:
            add(name, check, *operation())
        except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
            add(name, check, "error", f"Controle mislukt ({type(exc).__name__}).", recovery)
        except Exception as exc:
            current_app.logger.error("Systeemcontrole %s mislukt (%s)", name, type(exc).__name__)
            add(name, check, "error", f"Controle mislukt ({type(exc).__name__}).", recovery)
        results[-1]["duration_ms"] = round((perf_counter() - check_started) * 1000)

    def routes():
        required = {
            "control": "GET", "admin_login": "POST", "admin_logout": "POST",
            "nv_manage.team": "POST", "nv_manage.password": "POST", "nv_manage.catalog": "POST",
            "nv_manage.coupons": "POST", "admin_add_research_note": "POST",
            "nv_manage.seo_scan": "POST", "admin_merchant_preview": "GET",
            "admin_merchant_feed_preview": "GET", "admin_monitoring_check": "GET",
            "admin_integrations": "GET", "nuvemixa_woo.commerce_console": "GET",
            "admin_supplier_feed_preview": "POST", "admin_add_supplier": "POST",
        }
        adapter = current_app.url_map.bind("localhost")
        for endpoint, method in required.items():
            path = adapter.build(endpoint)
            if adapter.match(path, method=method)[0] != endpoint:
                raise ValueError("Route mismatch")
        for section in SECTIONS:
            if not set(SECTIONS[section]) <= RIGHTS.keys():
                raise ValueError("Invalid permission map")
        source, _, _ = current_app.jinja_env.loader.get_source(current_app.jinja_env, "_dashboard_menu.html")
        if any(f"'{section}'" not in source for section in SECTIONS):
            raise ValueError("Navigation missing")
        return "works", f"{len(required)} beheerrouteverwijzingen en {len(SECTIONS)} menurechten gevonden.", ""

    def catalogue():
        if g.get("nv_catalog_read_failed"):
            return "error", "Lokale cataloguswijzigingen zijn onleesbaar.", "Controleer de dashboarddatabase."
        ids = {item["id"] for item in items}
        counts = Counter(item["category_slug"] for item in items)
        if not items or len(ids) != len(items) or counts.keys() - categories.keys():
            return "error", "Lege catalogus, dubbele product-ID of ongeldige categorie.", "Herstel de catalogusgegevens."
        return "works", (f"{len(items)} producten in {len(categories)} categorieën. " +
            ", ".join(f"{meta['name']}: {counts[key]}" for key, meta in categories.items())), ""

    def images():
        missing = set()
        external = set()
        static = Path(current_app.static_folder).resolve()
        for item in items:
            for image in set([item["image"], *item["images"]]):
                url = urlsplit(image)
                if url.scheme or url.netloc:
                    external.add(image)
                elif url.path.startswith("/static/"):
                    path = (static / url.path.removeprefix("/static/")).resolve()
                    if not path.is_relative_to(static) or not path.is_file():
                        missing.add(url.path)
                elif not url.path.startswith("/img/product/"):
                    missing.add(url.path or "(lege link)")
        if missing:
            return "error", f"{len(missing)} ontbrekende lokale beelden: " + ", ".join(sorted(missing)[:8]), "Controleer de afbeeldingkoppelingen."
        return "works", f"Lokale beeldpaden gecontroleerd. {len(external)} externe links niet opgevraagd.", ""

    def coupons():
        if not nv_dashboard_postgres.runtime_enabled() and not DB.is_file():
            return "attention", "Kortingsdatabase wacht op initialisatie.", "Open Kortingen."
        today = timestamp[:10]
        invalid = 0
        with nv_dashboard_postgres.read_db(DB, timeout=0.25) as db:
            rows = db.execute("SELECT * FROM coupons LIMIT 1001").fetchall()
        if len(rows) > 1000:
            return "attention", "Meer dan 1000 codes; controle begrensd.", "Controleer het kortingsregister."
        for row in rows:
            try:
                starts = date.fromisoformat(row["starts"]) if row["starts"] else date.min
                ends = date.fromisoformat(row["ends"]) if row["ends"] else date.max
            except ValueError:
                invalid += 1
                continue
            if starts > ends:
                invalid += 1
                continue
            valid_amount = coupon_amount({**dict(row), "active": 1, "starts": None, "ends": None,
                                         "usage_limit": None}, 10000, today)
            invalid += valid_amount is None or (row["kind"] == "percent" and row["amount"] > 100)
        if invalid:
            return "error", f"{invalid} kortingscodes met ongeldige waarde.", "Controleer type en kortingsbedrag."
        return "works", f"{len(rows)} opgeslagen kortingscodes met leesbare waarden en datums.", ""

    def seo():
        if not items:
            return "attention", "Geen productpagina beschikbaar voor de steekproef.", "Controleer de catalogus."
        path = items[0]["product_url"]
        response = current_app.test_client().get(path, base_url=request.host_url,
                                                environ_overrides={"nuvemixa.internal_check": True})
        parser = ProductMetadata()
        parser.feed(response.get_data(as_text=True))
        schema = any(isinstance(row, dict) and row.get("@type") == "Product" for row in parser.structured_data)
        if (response.status_code != 200 or not all((parser.title, parser.description, schema))
                or not canonical_matches(parser.canonical, path, request.host_url)):
            return "error", "Steekproef op productmetadata mislukt.", "Controleer producttemplate en metadata."
        if not nv_dashboard_postgres.runtime_enabled() and not DB.is_file():
            return "attention", "Metadata aanwezig; rapportopslag nog niet ingericht.", "Voer een lokale SEO-controle uit."
        with nv_dashboard_postgres.read_db(DB, timeout=0.25) as db:
            table = nv_dashboard_postgres.table_exists(db, "seo_scans")
            stored = table and db.execute("SELECT 1 FROM seo_scans LIMIT 1").fetchone()
        return ("works", "Metadata en opgeslagen rapport leesbaar.", "") if stored else (
            "attention", "Metadata aanwezig; er is nog geen rapport opgeslagen.", "Voer een lokale SEO-controle uit.")

    def calculator():
        source, _, _ = current_app.jinja_env.loader.get_source(current_app.jinja_env, "dashboard.html")
        fields = ("buy", "shipping", "other", "fee", "vat", "manual", "margin")
        if not all(f'id="calc-{field}"' in source for field in fields):
            return "error", "Verwachte calculatorvelden ontbreken.", "Herstel het dashboardtemplate."
        return "works", "Alle zeven invoervelden gevonden. Browserberekening valt buiten deze scan.", ""

    run("Routes en navigatie", "Flask-router en menudefinities", routes, "Controleer route- en menuregistratie.")
    run("Templates en statische bestanden", "Jinja-templates en vaste lokale assetpaden", inspect_files, "Herstel het betreffende bestand.")
    run("Accountbeheer", "Leesbare accounts en kolommen voor rol, rechten en sessie",
        lambda: database_check(DB, ["staff"], ["role", "active", "permissions", "session_version"]),
        "Controleer het pad en het dashboarddatabaseschema.")
    run("Productcatalogus", "Product-ID's en aantallen per categorie", catalogue, "Controleer de catalogusbestanden.")
    run("Productafbeeldingen", "Lokale bestanden en verwijzingen naar gegenereerde beelden", images, "Controleer de afbeeldingspaden.")
    run("Kortingen", "Opgeslagen kortingswaarden", coupons, "Controleer de kortingsdatabase.")
    run("Klantdatabase", "Geconfigureerd pad en vereiste klantkolommen",
        lambda: check_customers(customer_db), "Controleer het pad, de leesrechten en de database-integriteit.")
    run("Onderzoek en leveranciers", "Leesbare tabellen voor notities en leveranciers",
        lambda: database_check(database_path(), ["research_notes", "suppliers"]),
        "Controleer ADMIN_DB (of NUVEMIXA_ADMIN_DB).")
    run("Calculator", "Vereiste invoervelden in het dashboard", calculator, "Controleer het dashboardtemplate.")
    run("SEO en rapportopslag", "Metadata van één productpagina en aanwezigheid van een opgeslagen rapport", seo, "Controleer het SEO-scherm.")
    def merchant():
        report = merchant_audit(items, current_app.static_folder)
        ready, total = report["ready"], report["total"]
        return ("works" if total and ready == total else "attention",
                f"{ready} van {total} doorstaan de interne controle.", "Bekijk de redenen per product bij Merchant.")
    run("Merchant-preview", "Interne validatie van catalogusproducten", merchant, "Controleer productgegevens en export.")
    def visitors():
        visits = visit_summary()
        if visits["error"]:
            return "error", "De opgeslagen bezoekcijfers zijn onleesbaar.", "Controleer de lokale dashboarddatabase."
        if not visits["enabled"]:
            stored = " Bestaande meetgegevens zijn leesbaar." if visits["groups"] else ""
            return "disabled", "Bezoekersregistratie staat uit." + stored, ""
        kind = visits["traffic"]
        if any(group[0] == kind and group[4] for group in visits["groups"]):
            return "works", f"Registratie ({kind}) staat aan en opgeslagen metingen zijn leesbaar.", ""
        return "unchecked", f"Registratie ({kind}) staat aan. Voor deze bron ontbreken meetgegevens.", ""

    run("Bezoekersteller", "Registratie-instelling en leesbaarheid van de meetbron", visitors, "Controleer Statistieken.")
    for name, (status, result, solution) in integrations.items():
        add(name, "Configuratie en resultaat van eventuele alleen-lezen verbindingstest", status, result, solution)
    live_orders = current_app.extensions["nuvemixa_live_orders"]()
    add("Applicatie-instellingen", "Vaste beheerconfiguratie en schakelaar voor live orders",
        "attention" if live_orders else "works",
        "Live orderverwerking is ingeschakeld." if live_orders else "De vaste beheerconfiguratie is aanwezig; live orders staan uit.",
        "Schakel live orders uit voor een lokale test." if live_orders else "")
    counts = Counter(row["status"] for row in results)
    return {"checked_at": timestamp, "duration_ms": round((perf_counter() - started) * 1000),
            "summary": {status: counts[status] for status in ("works", "attention", "error", "unchecked", "unconfigured", "failed", "disabled")},
            "checks": results}
