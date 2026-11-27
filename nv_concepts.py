"""Conceptproducten: de brug tussen productonderzoek, beoordeling en de publicatievoorbereiding.

Een concept is een product dat de eigenaar zelf uit onderzoeksresultaten (of handmatig) bewaart. Gegevens die niet bekend
zijn blijven leeg: er worden nooit prijzen, titels, beschrijvingen of afbeeldingen verzonnen of overgenomen zonder dat
de eigenaar ze invult of bevestigt. Opslag: de bestaande tabel `research_notes` (geen schemawijziging, werkt in SQLite
en in de dashboard-Postgres). Er is geen verwijderfunctie: afgewezen concepten blijven bewaard.

Een concept publiceert niets. De publicatievoorbereiding (controles, goedkeuring, WooCommerce-voorbeeld als 'draft')
staat in nv_publicatie; de schrijfkoppeling in nv_woo_writer is standaard uit.
"""
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import nv_dashboard_postgres
from flask import abort, flash, redirect, request, url_for

from nv_dashboard_manager import admin, bp

PREFIX = "[Concept] "
CATEGORY_NAMES = {"gadgets": "Gadgets", "beauty-care": "Beauty & Care", "lifestyle-sport": "Lifestyle & Sport",
                  "pets": "Huisdieren",
                  "home-living": "Home & Living", "smart-home": "Smart Home"}
STATUSES = {"nieuw": "Nieuw", "beoordelen": "In beoordeling", "geselecteerd": "Geselecteerd voor publicatievoorbereiding",
            "afgewezen": "Afgewezen"}
CHECKS = {
    "supplier": "Leverancier gecontroleerd",
    "dropshipping": "Dropshipping zonder eigen voorraad bevestigd",
    "shipping": "Levering naar Nederland/EU, kosten en levertijd bevestigd",
    "quality": "Productkwaliteit en veiligheid gecontroleerd",
    "returns": "Retour- en zakelijke voorwaarden gecontroleerd",
    "rights": "Merk- en afbeeldingsrechten gecontroleerd",
    "margin": "Marge zelf berekend en goedgekeurd",
    # Europese productveiligheid (GPSR, Verordening (EU) 2023/988) en CE: altijd vóór publicatie zelf vaststellen.
    "gpsr": "GPSR: fabrikant of EU-verantwoordelijke, productidentificatie en veiligheidsinformatie bekend",
    "ce": "CE-markering en conformiteitsverklaring gecontroleerd waar verplicht (o.a. elektronica, speelgoed)",
    "docs": "Handleiding en waarschuwingen in het Nederlands aanwezig",
}
IMAGE = re.compile(r"\.(jpe?g|png|webp)$", re.I)


class Invalid(ValueError):
    """Foutmelding die veilig aan de eigenaar getoond mag worden."""


def euro_to_cents(value, name):
    value = (value or "").strip()
    if not value:
        return None
    if not re.fullmatch(r"\d{1,6}(?:[.,]\d{1,2})?", value):
        raise Invalid(f"{name}: vul een bedrag in met maximaal twee decimalen, of laat leeg als het onbekend is.")
    try:
        return int((Decimal(value.replace(",", ".")) * 100).to_integral_value())
    except InvalidOperation:
        raise Invalid(f"{name}: ongeldig bedrag.") from None


def web_url(value, name, *, https_only=False, image=False, required=False):
    value = (value or "").strip()
    if not value:
        if required:
            raise Invalid(f"{name} is verplicht.")
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        raise Invalid(f"{name}: ongeldige link.") from None
    allowed = ("https",) if https_only else ("https", "http")
    if (parts.scheme not in allowed or not parts.hostname or parts.username or parts.password or len(value) > 300
            or any(ord(c) < 33 for c in value)):
        raise Invalid(f"{name}: gebruik een volledige https-link zonder inloggegevens.")
    if image and not IMAGE.search(parts.path):
        raise Invalid(f"{name}: een afbeelding moet eindigen op .jpg, .png of .webp.")
    return value


def text(value, name, low, high):
    value = " ".join((value or "").split())
    if not low <= len(value) <= high:
        raise Invalid(f"{name}: {low} tot {high} tekens." if low else f"{name}: maximaal {high} tekens.")
    return value


def read_form(form, *, partial=False):
    """Valideert het formulier; geeft kolommen en JSON-velden terug. Wat niet is ingevuld blijft leeg."""
    images = []
    for line in (form.get("afbeeldingen") or "").replace(",", "\n").splitlines()[:3]:
        if line.strip():
            images.append(web_url(line, "Afbeelding", https_only=True, image=True))
    category = form.get("categorie", "")
    return {
        "product_name": text(form.get("titel"), "Titel", 3, 120),
        "purchase_cost_cents": euro_to_cents(form.get("inkoop"), "Inkoopprijs"),
        "shipping_cost_cents": euro_to_cents(form.get("verzend"), "Verzendkosten"),
        "selling_price_cents": euro_to_cents(form.get("verkoop"), "Verkoopprijs (incl. btw)"),
        "source": web_url(form.get("bron_url"), "Bronlink"),
        "category": CATEGORY_NAMES.get(category, category if category in CATEGORY_NAMES.values() else "Gadgets"),
        "data": {
            "beschrijving": text(form.get("beschrijving"), "Beschrijving", 0, 500),
            "afbeeldingen": images,
            "leverancier": text(form.get("leverancier"), "Leverancier", 0, 120),
            "bron_naam": text(form.get("bron_naam"), "Bronnaam", 0, 80),
            "notities": text(form.get("notities"), "Notities", 0, 300),
        },
    }


def blank_data():
    return {"beschrijving": "", "afbeeldingen": [], "leverancier": "", "bron_naam": "", "notities": "",
            "status": "nieuw", "checks": {}}


def sku_for(concept_id):
    return f"NV-{int(concept_id):05d}"


def concept_from_row(row):
    notes = str(row["notes"])
    if not notes.startswith(PREFIX):
        return None
    try:
        data = {**blank_data(), **json.loads(notes[len(PREFIX):])}
    except ValueError:
        return None
    return {"id": row["id"], "sku": sku_for(row["id"]), "titel": row["product_name"], "categorie": row["category"],
            "inkoop": row["purchase_cost_cents"], "verzend": row["shipping_cost_cents"],
            "verkoop": row["selling_price_cents"], "bron_url": row["source"], **data}


def list_concepts():
    from nuvemixa_admin_store import connect
    with connect() as db:
        rows = db.execute(
            "SELECT id,category,product_name,purchase_cost_cents,shipping_cost_cents,selling_price_cents,source,notes "
            "FROM research_notes WHERE notes LIKE ? ORDER BY id DESC LIMIT 200", (PREFIX + "%",)).fetchall()
    return [c for c in (concept_from_row(r) for r in rows) if c]


def get_concept(concept_id):
    return next((c for c in list_concepts() if c["id"] == concept_id), None)


def create(fields):
    from nuvemixa_admin_store import connect
    data = {**blank_data(), **fields["data"]}
    with connect() as db:
        db.execute(
            "INSERT INTO research_notes(category,product_name,purchase_cost_cents,shipping_cost_cents,selling_price_cents,"
            "source,notes) VALUES (?,?,?,?,?,?,?)",
            (fields["category"], fields["product_name"], fields["purchase_cost_cents"], fields["shipping_cost_cents"],
             fields["selling_price_cents"], fields["source"], PREFIX + json.dumps(data, ensure_ascii=False)))
        row = db.execute("SELECT id FROM research_notes WHERE product_name=? AND notes LIKE ? ORDER BY id DESC LIMIT 1",
                         (fields["product_name"], PREFIX + "%")).fetchone()
    return row["id"] if row else None


def update(concept_id, fields, status=None, checks=None):
    from nuvemixa_admin_store import connect
    current = get_concept(concept_id)
    if current is None:
        raise Invalid("Concept niet gevonden.")
    data = {**blank_data(), **{k: current[k] for k in blank_data()}, **fields["data"]}
    if status and current["status"] == "nieuw":  # bewerken zet nooit een geselecteerd/afgewezen concept terug
        data["status"] = status
    if checks is not None:
        data["checks"] = {k: True for k in CHECKS if checks.get(k)}
    with connect() as db:
        db.execute(
            "UPDATE research_notes SET category=?,product_name=?,purchase_cost_cents=?,shipping_cost_cents=?,"
            "selling_price_cents=?,source=?,notes=? WHERE id=? AND notes LIKE ?",
            (fields["category"], fields["product_name"], fields["purchase_cost_cents"], fields["shipping_cost_cents"],
             fields["selling_price_cents"], fields["source"], PREFIX + json.dumps(data, ensure_ascii=False),
             concept_id, PREFIX + "%"))


def set_status(concept_id, status):
    from nuvemixa_admin_store import connect
    current = get_concept(concept_id)
    if current is None or status not in STATUSES:
        raise Invalid("Concept niet gevonden.")
    data = {k: current[k] for k in blank_data()}
    data["status"] = status
    with connect() as db:
        db.execute("UPDATE research_notes SET notes=? WHERE id=? AND notes LIKE ?",
                   (PREFIX + json.dumps(data, ensure_ascii=False), concept_id, PREFIX + "%"))


def to_candidate(concept):
    """Behoud bij verzendkosten het onderscheid tussen onbekend en gratis."""
    return {"sku": concept["sku"], "titel": concept["titel"], "beschrijving": concept["beschrijving"],
            "afbeeldingen": list(concept["afbeeldingen"]), "inkoop": concept["inkoop"] or 0,
            "verzend": concept["verzend"], "verkoop": concept["verkoop"] or 0,
            "leverancier": concept["leverancier"], "categorie": concept["categorie"], "bron": "concept"}


def selected_candidates():
    return {c["sku"]: to_candidate(c) for c in list_concepts() if c["status"] == "geselecteerd"}


def candidate_by_sku(sku):
    """Alleen geselecteerde concepten komen in de publicatievoorbereiding."""
    return selected_candidates().get(str(sku))


def view(query=""):
    import nv_publicatie
    from nv_research_intent import matches

    query = query.strip()[:100]
    existing, bron, _fout = nv_publicatie.existing_products()
    rows = []
    for concept in list_concepts():
        if query and not matches(query, " ".join(
            str(concept.get(key) or "") for key in ("titel", "categorie", "leverancier", "sku")
        )):
            continue
        candidate = to_candidate(concept)
        steps = nv_publicatie.check(candidate, existing)
        rows.append({**concept, "marge": nv_publicatie.margin(candidate) if candidate["verkoop"] and candidate["inkoop"] else None,
                     "controle": steps, "fouten": [s["stap"] for s in nv_publicatie.blocking(steps)],
                     "checks_klaar": sum(1 for k in CHECKS if concept["checks"].get(k))})
    return {"concepten": rows, "query": query, "statuses": STATUSES, "checks": CHECKS, "categories": CATEGORY_NAMES,
            "bron": bron, "min_marge": nv_publicatie.MIN_MARGE,
            "permanent": nv_dashboard_postgres.runtime_enabled()}


def _go(**extra):
    return redirect(url_for("control", section="concepten", **extra), code=303)


def _guard():
    if not admin():  # alleen de eigenaar
        abort(403)


@bp.post("/dashboard/concepten/nieuw")
def concept_new():
    """Bewaart een product als concept. Publiceert niets en stuurt niets naar leveranciers of WooCommerce."""
    _guard()
    try:
        concept_id = create(read_form(request.form))
        flash("Conceptproduct bewaard. Vul ontbrekende gegevens aan en beoordeel het.", "success")
    except Invalid as error:
        flash(str(error), "error")
        return _go()
    except Exception:
        flash("Opslaan is nu niet gelukt; probeer het later opnieuw.", "error")
        return _go()
    return _go(open=concept_id)


@bp.post("/dashboard/concepten/bijwerken")
def concept_update():
    _guard()
    concept_id = request.form.get("concept_id", type=int)
    if not concept_id:
        abort(400)
    action = request.form.get("actie", "opslaan")
    try:
        if action in ("selecteren", "afwijzen", "terug"):
            target = {"selecteren": "geselecteerd", "afwijzen": "afgewezen", "terug": "beoordelen"}[action]
            if target == "geselecteerd":
                concept = get_concept(concept_id)
                if concept is None:
                    raise Invalid("Concept niet gevonden.")
            set_status(concept_id, target)
            flash({"geselecteerd": "Geselecteerd: het concept staat nu in Productpublicatie (alleen voorbereiding).",
                   "afgewezen": "Concept afgewezen en bewaard.", "beoordelen": "Concept staat weer in beoordeling."}[target], "success")
        else:
            update(concept_id, read_form(request.form), status="beoordelen" if action == "opslaan" else None,
                   checks={k: request.form.get("check_" + k) for k in CHECKS})
            flash("Concept opgeslagen. Er is niets gepubliceerd.", "success")
    except Invalid as error:
        flash(str(error), "error")
    except Exception:
        flash("Opslaan is nu niet gelukt; probeer het later opnieuw.", "error")
    return _go(open=concept_id)
