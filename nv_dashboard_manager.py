"""NUVEMIXA local dashboard accounts and discounts."""
import os, sqlite3, re, secrets
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from contextlib import closing, contextmanager
from flask import Blueprint, request, session, redirect, abort, current_app, g, flash, url_for
from nv_permissions import RIGHTS, DEFAULT_RIGHTS, allowed
from nv_storage_paths import DASHBOARD_DB
import nv_dashboard_postgres
import nv_freeze
from werkzeug.security import generate_password_hash, check_password_hash

bp=Blueprint('nv_manage',__name__)
DB=DASHBOARD_DB
@contextmanager
def connect():
    if nv_dashboard_postgres.runtime_enabled():
        with nv_dashboard_postgres.application_db() as db:
            yield db
        return
    if not nv_freeze.frozen():
        DB.parent.mkdir(parents=True, exist_ok=True)
    db = nv_freeze.sqlite_connect(DB, 8)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.executescript("""CREATE TABLE IF NOT EXISTS staff(
                id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'viewer',
                active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS coupons(id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, amount REAL NOT NULL, starts TEXT, ends TEXT, usage_limit INTEGER, used INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS visits(day TEXT NOT NULL, visitor TEXT NOT NULL, views INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(day,visitor));""")
            _migrate_staff(db)
            yield db
    finally:
        db.close()


def _migrate_staff(db):
    columns = {column["name"] for column in db.execute("PRAGMA table_info(staff)")}
    if {"username", "session_version", "permissions"} <= columns:
        return
    db.execute("BEGIN IMMEDIATE")
    columns = {column["name"] for column in db.execute("PRAGMA table_info(staff)")}
    if "username" not in columns:
        db.execute("ALTER TABLE staff ADD COLUMN username TEXT COLLATE NOCASE")
    if "session_version" not in columns:
        db.execute("ALTER TABLE staff ADD COLUMN session_version TEXT NOT NULL DEFAULT ''")
    if "permissions" not in columns:
        db.execute("ALTER TABLE staff ADD COLUMN permissions TEXT")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS staff_username ON staff(username)")
    db.commit()


STAFF_SWITCH = "NUVEMIXA_STAFF_LOGIN"


def staff_login_enabled():
    """Medewerkerstoegang staat standaard UIT en gaat alleen aan bij de expliciete waarde "on".

    Een ontbrekende of verkeerd geschreven variabele laat de toegang dus dicht (fail-closed).
    """
    return os.getenv(STAFF_SWITCH, "").strip().lower() == "on"


def admin():
    return current_app.extensions["nuvemixa_admin_checker"]()


def require_admin(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def staff_auth(identity, password):
    if not staff_login_enabled():
        return None
    with connect() as db:
        row = db.execute(
            """SELECT id,password_hash,session_version FROM staff
               WHERE (lower(email) = lower(?) OR lower(username) = lower(?)) AND active = 1
               ORDER BY id LIMIT 1""",
            (identity, identity),
        ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return row["id"], row["session_version"]
    return None


def staff_current():
    if "nv_staff" not in g:
        g.nv_staff = None
        if not staff_login_enabled():
            return None
        ident = session.get("nv_staff_id")
        version = session.get("nv_staff_version")
        if type(ident) is int and isinstance(version, str):
            try:
                with nv_dashboard_postgres.read_db(DB, timeout=0.3) as db:
                    row = db.execute(
                        """SELECT id,email,name,username,role,permissions FROM staff
                           WHERE id=? AND session_version=? AND active=1""",
                        (ident, version),
                    ).fetchone()
                g.nv_staff = dict(row) if row else None
            except (sqlite3.Error, OSError):
                current_app.logger.error("Dashboardaccountdatabase niet beschikbaar")
    return g.nv_staff


def team_rows():
    with connect() as db:
        return db.execute(
            "SELECT id,email,name,username,role,active,permissions FROM staff ORDER BY lower(name),id"
        ).fetchall()


def management_result(section, message, success=False):
    flash(message, "success" if success else "error")
    return redirect(url_for("control", section=section), code=303)


@bp.post("/admin/nv/team")
@require_admin
def team():
    operation = request.form.get("op", "create")
    if operation not in {"create", "edit", "disable", "enable", "reset"}:
        abort(400)
    account_id = request.form.get("id", type=int)
    password = request.form.get("password", "")
    if operation != "disable" and not staff_login_enabled():
        return management_result("accountbeheer", "Medewerkerstoegang staat uit. Alleen het uitschakelen van accounts is mogelijk.")
    if operation in {"create", "reset"} and not 12 <= len(password) <= 128:
        return management_result("accountbeheer", "Gebruik een wachtwoord van 12 tot 128 tekens.")
    if operation in {"create", "edit"}:
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().casefold()
        name = request.form.get("name", "").strip()
        role = request.form.get("role")
        status = request.form.get("active", "1" if operation == "create" else None)
        if status not in {"0", "1", None}:
            abort(400)
        active = int(status) if status is not None else None
        rights = (set(request.form.getlist("permission")) if request.form.get("permissions_present") == "1"
                  else DEFAULT_RIGHTS if operation == "create" else None)
        if rights is not None and rights - RIGHTS.keys():
            abort(400)
        permissions = ",".join(sorted(rights)) if rights is not None else None
        if (not re.fullmatch(r"[a-z0-9._-]{3,64}", username)
                or not 1 <= len(name) <= 80 or not 3 <= len(email) <= 254
                or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
                or role not in {"admin", "employee"}):
            return management_result("accountbeheer", "Controleer naam, gebruikersnaam, e-mailadres en rol.")
        if email == os.environ["NUVEMIXA_ADMIN_EMAIL"].strip().casefold():
            return management_result("accountbeheer", "Dit e-mailadres hoort bij de vaste beheerder.")

    password_hash = generate_password_hash(password) if operation in {"create", "reset"} else None
    version = secrets.token_urlsafe(24)
    try:
        with connect() as db:
            nv_dashboard_postgres.lock_staff(db)
            # Recheck authorization in the same transaction as the change.
            if session.get("nv_admin") is not True and not db.execute(
                """SELECT 1 FROM staff WHERE id=? AND session_version=?
                   AND active=1 AND role='admin'""",
                (session.get("nv_staff_id"), session.get("nv_staff_version")),
            ).fetchone():
                abort(403)
            if operation != "create" and not db.execute(
                "SELECT 1 FROM staff WHERE id=?", (account_id,)
            ).fetchone():
                abort(404)
            # The configured administrator has no mutable row and is always retained.
            if operation in {"create", "edit"} and db.execute(
                "SELECT 1 FROM staff WHERE lower(email)=lower(?) AND id<>?",
                (email, account_id if operation == "edit" else -1),
            ).fetchone():
                raise sqlite3.IntegrityError
            if operation == "create":
                db.execute(
                    """INSERT INTO staff(username,email,name,role,password_hash,session_version,active,permissions)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (username, email, name, role, password_hash, version, active, permissions),
                )
            elif operation == "edit":
                db.execute(
                    """UPDATE staff SET username=?,email=?,name=?,role=?,
                       active=COALESCE(?,active),permissions=COALESCE(?,permissions),session_version=? WHERE id=?""",
                    (username, email, name, role, active, permissions, version, account_id),
                )
            elif operation == "reset":
                db.execute(
                    "UPDATE staff SET password_hash=?,session_version=? WHERE id=?",
                    (password_hash, version, account_id),
                )
            else:
                db.execute(
                    "UPDATE staff SET active=?,session_version=? WHERE id=?",
                    (int(operation == "enable"), version, account_id),
                )
    except sqlite3.IntegrityError:
        return management_result("accountbeheer", "Gebruikersnaam of e-mailadres is al in gebruik.")
    except (sqlite3.Error, OSError):
        current_app.logger.error("Dashboardaccount kon niet worden opgeslagen")
        return management_result("accountbeheer", "Opslaan mislukt. Probeer het opnieuw.")
    return management_result("accountbeheer", "Dashboardaccount opgeslagen.", success=True)


@bp.post("/admin/nv/my-password")
def password():
    staff = staff_current()
    if not staff:
        abort(403)
    old = request.form.get("old", "")
    new = request.form.get("new", "")
    if len(old) > 128 or not 12 <= len(new) <= 128:
        abort(400, "Gebruik een wachtwoord van 12 tot 128 tekens.")
    try:
        with connect() as db:
            row = db.execute(
                "SELECT password_hash FROM staff WHERE id=? AND active=1 AND session_version=?",
                (staff["id"], session["nv_staff_version"]),
            ).fetchone()
            if not row or not check_password_hash(row["password_hash"], old):
                abort(403, "Huidig wachtwoord onjuist.")
            changed = db.execute(
                """UPDATE staff SET password_hash=?,session_version=?
                   WHERE id=? AND active=1 AND session_version=?""",
                (generate_password_hash(new), secrets.token_urlsafe(24),
                 staff["id"], session["nv_staff_version"]),
            ).rowcount
            if not changed:
                abort(409, "De accountstatus is gewijzigd. Log opnieuw in.")
    except (sqlite3.Error, OSError):
        current_app.logger.error("Dashboardwachtwoord kon niet worden opgeslagen")
        abort(503, "Accountdatabase tijdelijk niet beschikbaar.")
    session.clear()
    return redirect(url_for("admin_login"), code=303)


def _publicatie_kandidaat(sku):
    import nv_publicatie
    candidate = nv_publicatie.TEST_CANDIDATES.get(str(sku))
    if candidate is None:
        try:
            import nv_concepts  # alleen door de eigenaar geselecteerde concepten
            candidate = nv_concepts.candidate_by_sku(sku)
        except Exception:
            candidate = None
    if candidate is None:
        abort(404)
    return nv_publicatie, candidate


@bp.post("/admin/nv/publicatie/goedkeuren")
@require_admin
def publicatie_goedkeuren():
    pub, candidate = _publicatie_kandidaat(request.form.get("sku", ""))
    existing, _bron, _fout = pub.existing_products(live=True)
    rows = pub.check(candidate, existing)
    if pub.blocking(rows):
        flash("Goedkeuren kan pas als alle controles op fouten zijn opgelost.", "error")
    else:
        approvals = dict(session.get("nv_pub_goedkeuringen", {}))
        approvals[candidate["sku"]] = pub.sign_approval(current_app.secret_key, candidate)
        session["nv_pub_goedkeuringen"] = approvals
        flash("Goedkeuring vastgelegd voor precies deze productgegevens. Er is niets verzonden.", "success")
    return redirect(url_for("control", section="publicatie", kandidaat=candidate["sku"]), code=303)


@bp.post("/admin/nv/publicatie/publiceren")
@require_admin
def publicatie_publiceren():
    pub, candidate = _publicatie_kandidaat(request.form.get("sku", ""))
    existing, _bron, _fout = pub.existing_products(live=True)
    token = session.get("nv_pub_goedkeuringen", {}).get(candidate["sku"], "")
    try:
        if candidate.get("bron") != "concept":
            raise pub.PublishRefused("Testproducten worden nooit naar WooCommerce gestuurd.")
        import nv_concepts, nv_woo_writer
        concept = nv_concepts.get_concept(int(candidate["sku"].split("-")[1]))
        if concept is None or concept["status"] != "geselecteerd" or len(concept["checks"]) < len(nv_concepts.CHECKS):
            raise pub.PublishRefused("Vink eerst alle beoordelingscontroles af bij het concept.")
        if request.form.get("bevestig") != "1":
            raise pub.PublishRefused("Bevestig eerst dat er een concept (draft) in WooCommerce wordt aangemaakt.")
        try:
            sender = nv_woo_writer.build_sender()
            result = pub.publish(candidate, existing, current_app.secret_key, token, sender=sender)
        except nv_woo_writer.WriteError as exc:
            raise pub.PublishRefused(str(exc)) from None
        flash(f"Aangemaakt als concept (draft) in WooCommerce, id {result.get('id')}. Er is niets gepubliceerd; controleer en publiceer zelf in WooCommerce.", "success")
    except pub.PublishRefused as exc:
        flash(str(exc), "error")
    return redirect(url_for("control", section="publicatie", kandidaat=candidate["sku"]), code=303)


def coupon_today():
    return datetime.now(ZoneInfo("Europe/Amsterdam")).date().isoformat()


def coupon_rows():
    today = coupon_today()
    with connect() as db:
        return [dict(row, status=coupon_status(row, today))
                for row in db.execute("SELECT * FROM coupons ORDER BY id DESC")]


def amount_in_cents(value):
    if not re.fullmatch(r"\d{1,7}(?:[.,]\d{1,2})?", value):
        raise ValueError("Vul een geldig bedrag in met maximaal twee decimalen.")
    return int(Decimal(value.replace(",", ".")) * 100)


def test_checkout_discount(code, subtotal):
    with connect() as db:
        row = db.execute("SELECT * FROM coupons WHERE code=?", (code.strip().upper(),)).fetchone()
        return coupon_amount(row, subtotal, coupon_today())


def coupon_status(row, today):
    if not row["active"]:
        return "Uitgeschakeld"
    if row["starts"] and row["starts"] > today:
        return "Gepland"
    if row["ends"] and row["ends"] < today:
        return "Verlopen"
    if row["usage_limit"] is not None and row["used"] >= row["usage_limit"]:
        return "Gebruikslimiet bereikt"
    return "Actief"


def coupon_amount(row, subtotal, today):
    if not row or coupon_status(row, today) != "Actief":
        return None
    amount = Decimal(str(row["amount"]))
    if not amount.is_finite() or amount <= 0 or row['kind'] not in {'percent', 'fixed'}:
        return None
    discount = Decimal(subtotal) * amount / 100 if row["kind"] == "percent" else amount * 100
    return min(subtotal, int(discount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def create_percentage_coupon(db, percent, starts=None, ends=None):
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    for _ in range(12):
        suffix = "".join(secrets.choice(alphabet) for _ in range(8))
        code = f"NV-{suffix[:4]}-{suffix[4:]}"
        # Check legacy spelling and reserve the canonical code in one SQLite write.
        inserted = db.execute("""
            INSERT INTO coupons(code, kind, amount, starts, ends)
            SELECT ?, 'percent', ?, ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM coupons WHERE lower(code) = lower(?))
            ON CONFLICT(code) DO NOTHING
        """, (code, percent, starts, ends, code))
        if inserted.rowcount == 1:
            return code
    return None


@bp.post("/admin/nv/coupons")
def coupons():
    operation = request.form.get("op", "create")
    if operation == "delete" and not admin():
        abort(403)
    if not (allowed("discount_view", "discount_manage") if operation == "preview" else allowed("discount_manage")):
        abort(403)
    if operation == "create":
        percentage = request.form.get("percentage", "")
        if not re.fullmatch(r"[2-9]|1[0-9]|20", percentage):
            return management_result("kortingen", "Kies een heel percentage van 2% tot en met 20%.")
        dates = [request.form.get(field, "") for field in ("starts", "ends")]
        try:
            starts, ends = [date.fromisoformat(value).isoformat()
                            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)
                            else None for value in dates]
        except ValueError:
            return management_result("kortingen", "Kies geldige kalenderdatums.")
        if any(value and not parsed for value, parsed in zip(dates, (starts, ends))):
            return management_result("kortingen", "Kies geldige kalenderdatums.")
        if starts and ends and ends < starts:
            return management_result("kortingen", "De einddatum moet op of na de begindatum vallen.")
    try:
        with connect() as db:
            if operation == "create":
                code = create_percentage_coupon(db, int(percentage), starts, ends)
            elif operation == "delete":
                coupon_id = request.form.get("id", type=int)
                if coupon_id is None:
                    abort(400)
                deleted = db.execute("DELETE FROM coupons WHERE id=?", (coupon_id,))
                if deleted.rowcount != 1:
                    abort(404)
            elif operation in {"disable", "enable"}:
                updated = db.execute("UPDATE coupons SET active=? WHERE id=?",
                                     (int(operation == "enable"), request.form.get("id", type=int)))
                if not updated.rowcount:
                    abort(404)
            elif operation == "preview":
                code = request.form.get("code", "").strip().upper()
                subtotal = amount_in_cents(request.form.get("subtotal", "").strip())
                row = db.execute("SELECT * FROM coupons WHERE code=?", (code,)).fetchone()
                discount = coupon_amount(row, subtotal, coupon_today())
                if discount is None:
                    return management_result("kortingen", "Deze code is niet geldig voor de testdatum.")
                return management_result(
                    "kortingen", f"Korting EUR {discount / 100:.2f} · Testtotaal EUR {(subtotal - discount) / 100:.2f}.",
                    success=True,
                )
            else:
                abort(400)
    except ValueError:
        return management_result("kortingen", "Controleer het subtotaal.")
    except (sqlite3.Error, OSError):
        current_app.logger.error("Kortingsdatabase niet beschikbaar")
        return management_result("kortingen", "Kortingen zijn tijdelijk niet beschikbaar.")
    if operation == "create":
        if code is None:
            return management_result("kortingen", "Geen unieke code beschikbaar. Probeer opnieuw.")
        flash(code, "coupon_created")
        return redirect(url_for("control", section="kortingen"), code=303)
    return management_result("kortingen", "Kortingscode verwijderd." if operation == "delete" else "Kortingsactie opgeslagen.", success=True)
