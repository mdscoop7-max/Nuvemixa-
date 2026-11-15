"""Per-market research, separate from storefront prices and stock."""
import json
import re
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from flask import abort, current_app, flash, redirect, request, url_for
from nuvemixa_admin_store import connect
from nv_dashboard_manager import bp
from nv_permissions import allowed

MARKETS = {
    "NL": ("Nederland", "EUR", "nl-NL", 1), "BE": ("België", "EUR", "nl-BE / fr-BE", 1),
    "DE": ("Duitsland", "EUR", "de-DE", 2), "FR": ("Frankrijk", "EUR", "fr-FR", 2),
    "GB": ("Verenigd Koninkrijk", "GBP", "en-GB", 3), "US": ("Verenigde Staten", "USD", "en-US", 3),
    "CA": ("Canada", "CAD", "en-CA / fr-CA", 3),
}
PRODUCTS = {
    "bureau": ("Bureau-organizer", "Home & Living", "29.95"),
    "kabels": ("Kabelorganizer", "Home & Living", "29.95"),
    "reis": ("Reisorganizerset", "Lifestyle & Sport", "34.95"),
}
COSTS = {
    "buy": "Inkoop", "shipping": "Transport", "duty": "Invoerrechten",
    "tax_cost": "Niet-aftrekbare belastingen", "payment": "Betaalkosten",
    "packaging": "Verpakking", "returns": "Verwachte retourkosten",
    "marketing": "Klantwerving", "fx": "Wisselkoersbuffer",
}
AMOUNTS = {"sales": "Opbrengst per order excl. af te dragen belasting", **COSTS}
TEXT = {
    "demand": ("Vraag en bron, inclusief meetperiode", 1200),
    "competition": ("Concurrentie, marktprijzen en onderscheid", 1200),
    "supplier": ("Leverancier, SKU en offerte", 1200),
    "logistics": ("Verzendlocatie, voorraad, levertijd en retouren", 1200),
    "quality": ("Proefexemplaar, veiligheid en documentatie", 1200),
    "potential": ("Marktpotentieel en besluit", 1200),
}


def record_from_form(form):
    record = {}
    for field, label in AMOUNTS.items():
        value = form.get(field, "").strip().replace(",", ".")
        if value and not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", value):
            raise ValueError(f"Controleer het bedrag voor {label.lower()}.")
        record[field] = str(Decimal(value)) if value else ""
    for field, (label, maximum) in TEXT.items():
        value = form.get(field, "").strip()
        if len(value) > maximum:
            raise ValueError(f"Het veld {label.lower()} is te lang.")
        record[field] = value
    checks = ("demand", "competition", "supplier", "logistics", "quality")
    record["confirmed"] = [key for key in checks if record[key] and form.get("confirmed_" + key) == "1"]
    return record


def assessment(record):
    if any(record.get(field, "") == "" for field in AMOUNTS):
        return None
    sales = Decimal(record["sales"])
    contribution = sales - sum(Decimal(record[key]) for key in COSTS)
    margin = (contribution * 100 / sales).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if sales else None
    return contribution, margin


def market_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS market_research (
        market TEXT NOT NULL, product TEXT NOT NULL, data TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (market, product))""")


def dashboard_market():
    market = request.args.get("market", "NL")
    product = request.args.get("product", "kabels")
    if market not in MARKETS or product not in PRODUCTS:
        abort(404)
    references = json.loads((Path(__file__).parent / "content" / "international-pilot.json").read_text(encoding="utf-8"))
    record, error = {}, None
    try:
        with connect() as db:
            market_table(db)
            row = db.execute("SELECT data FROM market_research WHERE market=? AND product=?", (market, product)).fetchone()
            if row:
                record = json.loads(row["data"])
    except (OSError, sqlite3.Error, RuntimeError):
        current_app.logger.error("Marktonderzoekdatabase kon niet worden gelezen")
        error = "De onderzoeksgegevens zijn tijdelijk niet beschikbaar."
    return dict(markets=MARKETS, candidates=PRODUCTS, market=market, candidate=product, data=record,
                amounts=AMOUNTS, text_fields=TEXT, result=assessment(record), storage_error=error,
                evidence=references["benchmarks"].get(market, {}).get(product, []),
                search_terms=references["keywords"][market][product], suppliers=references["suppliers"][product],
                observations=references["observed_on"])


@bp.post("/dashboard/internationaal")
def save_market():
    if not allowed("research"):
        abort(403)
    market = request.form.get("market")
    product = request.form.get("product")
    if market not in MARKETS or product not in PRODUCTS:
        abort(400)
    failed = False
    try:
        record = record_from_form(request.form)
        with connect() as db:
            market_table(db)
            db.execute("""INSERT INTO market_research(market, product, data) VALUES(?, ?, ?)
                ON CONFLICT(market, product) DO UPDATE SET data=excluded.data, updated_at=CURRENT_TIMESTAMP""",
                (market, product, json.dumps(record, ensure_ascii=False)))
    except ValueError as exc:
        abort(400, str(exc))
    except (OSError, sqlite3.Error, RuntimeError):
        current_app.logger.error("Marktonderzoek kon niet worden opgeslagen")
        failed = True
    flash("Opslaan is niet gelukt." if failed else "Marktonderzoek opgeslagen.", "error" if failed else "success")
    return redirect(url_for("control", section="internationaal", market=market, product=product), code=303)
