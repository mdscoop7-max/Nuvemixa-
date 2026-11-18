"""Source-backed trend observations and transparent candidate assessment."""
from datetime import date, timedelta
import json
import re
import sqlite3
from urllib.parse import urlsplit

from flask import abort, current_app, flash, redirect, request, url_for
from nuvemixa_admin_store import connect
from nv_dashboard_manager import bp
from nv_international import AMOUNTS, MARKETS, assessment as cost_result, record_from_form
from nv_permissions import allowed
import nv_dashboard_postgres
from nv_product_dossier import dossier_view
from nv_supplier_finder import comparison_view
from nv_research_assistant import research_enabled

PLATFORMS = {
    "tiktok": ("TikTok", ("tiktok.com",)), "tiktok-shop": ("TikTok Shop", ("tiktok.com", "tiktokshop.com")),
    "instagram": ("Instagram / Reels", ("instagram.com",)), "instagram-shop": ("Instagram Shopping", ("instagram.com",)),
    "pinterest": ("Pinterest", ("pinterest.com",)), "google-trends": ("Google Trends", ("trends.google.com",)),
    "google-shopping": ("Google Shopping", ("google.com", "shopping.google.com")),
}
COUNTRIES = {code: row[0] for code, row in MARKETS.items()} | {"AU": "Australië", "ES": "Spanje", "SE": "Zweden", "JP": "Japan"}
NICHES = (
    "Beauty en persoonlijke verzorging", "Gadgets en elektronica", "Huis en wonen", "Bureau en werkplek",
    "Keuken en huishouden", "Fitness en sport", "Huisdieren", "Reisaccessoires", "Modeaccessoires",
    "Telefoon en computer", "Creatief en DIY", "Smart home", "Tuin en buiten",
    "Dagelijkse hulpmiddelen", "Opkomende niche",
)
FACTORS = {
    "growth": ("Groei van belangstelling", 15, "social"),
    "tiktok": ("TikTok-interactie", 10, "social"),
    "instagram": ("Instagram-interactie", 10, "social"),
    "search": ("Google-zoekinteresse", 10, "social"),
    "creators": ("Onafhankelijke creators", 5, "social"),
    "intent": ("Koopintentie", 15, "commercial"),
    "competition": ("Ruimte tussen concurrenten", 10, "commercial"),
    "supplier": ("Dropshippingbeschikbaarheid", 5, "commercial"),
    "delivery": ("Verzendmogelijkheden", 5, "commercial"),
    "profit": ("Verwachte bijdrage", 15, "commercial"),
}
CHECKS = {
    "supplier": "Leverancier gecontroleerd",
    "shipping": "Dropshipping en levering naar dit land bevestigd",
    "quality": "Productkwaliteit gecontroleerd",
    "returns": "Retourvoorwaarden gecontroleerd",
    "margin": "Minimummarge goedgekeurd",
}


def tables(db):
    if nv_dashboard_postgres.runtime_enabled():
        return
    db.execute("""CREATE TABLE IF NOT EXISTS viral_candidates (
        id INTEGER PRIMARY KEY, title TEXT NOT NULL COLLATE NOCASE, country TEXT NOT NULL,
        niche TEXT NOT NULL, notes TEXT NOT NULL, assessment TEXT NOT NULL,
        UNIQUE(title,country))""")
    db.execute("""CREATE TABLE IF NOT EXISTS viral_observations (
        candidate INTEGER NOT NULL REFERENCES viral_candidates(id), platform TEXT NOT NULL,
        source TEXT NOT NULL, observed TEXT NOT NULL, window INTEGER NOT NULL,
        metric TEXT NOT NULL, value INTEGER NOT NULL, estimate INTEGER NOT NULL,
        PRIMARY KEY(candidate,platform,source,observed,window,metric))""")


def clean(field, size, required=True):
    value = request.form.get(field, "").strip()
    if (required and not value) or len(value) > size:
        raise ValueError
    return value


def integer(field, maximum):
    value = clean(field, 12)
    if not value.isascii() or not value.isdecimal() or int(value) > maximum:
        raise ValueError
    return int(value)


def save_observation(db, candidate):
    platform, source = clean("platform", 40), clean("source", 450)
    if platform not in PLATFORMS:
        raise ValueError
    uri = urlsplit(source)
    if ("\\" in source or uri.scheme != "https" or uri.username or uri.password or uri.port not in (None,443)
            or not uri.hostname or any(c.isspace() for c in source)
            or not any(uri.hostname == h or uri.hostname.endswith("." + h) for h in PLATFORMS[platform][1])):
        raise ValueError
    observed = date.fromisoformat(clean("observed", 10))
    window = integer("window", 90)
    if observed > date.today() or window not in (7,30,90):
        raise ValueError
    metric = clean("metric", 20)
    if metric not in ("views", "likes", "comments", "shares", "saves", "interest", "creators", "orders"):
        raise ValueError
    value = integer("value", 999_999_999)
    if metric == "interest" and (platform not in ("google-trends", "pinterest") or value > 100):
        raise ValueError
    db.execute("""INSERT INTO viral_observations
        (candidate,platform,source,observed,"window",metric,value,estimate) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(candidate,platform,source,observed,"window",metric)
        DO UPDATE SET value=excluded.value, estimate=excluded.estimate""",
        (candidate, platform, source, observed.isoformat(), window, metric, value, int(request.form.get("estimate")=="1")))


@bp.post("/dashboard/viral")
def save_viral():
    if not allowed("research"):
        abort(403)
    candidate = request.form.get("candidate", type=int)
    if "candidate" in request.form and candidate is None:
        abort(400)
    try:
        with connect() as db:
            tables(db)
            if candidate is None:
                country, niche = clean("country", 2), clean("niche", 100)
                if country not in COUNTRIES or niche not in NICHES:
                    raise ValueError
                db.execute("""INSERT INTO viral_candidates(title,country,niche,notes,assessment)
                    VALUES (?,?,?,?,?)""", (clean("title",120), country, niche, clean("new_niche",120,False), "{}"))
            else:
                row = db.execute("SELECT country FROM viral_candidates WHERE id=?", (candidate,)).fetchone()
                if not row:
                    abort(404)
                if request.form.get("action") == "observation":
                    save_observation(db,candidate)
                elif request.form.get("action") == "assessment":
                    costs = record_from_form(request.form)
                    scores = {f: integer(f,10) for f in FACTORS if request.form.get(f, "").strip()}
                    assessment = {"scores": scores, "costs": costs,
                                  "checks": [key for key in CHECKS if request.form.get("check_" + key) == "1"],
                                  "rationale": clean("rationale",1600,False),
                                  "supplier_name": clean("supplier_name",160,False)}
                    if scores and not assessment["rationale"]:
                        raise ValueError
                    db.execute("UPDATE viral_candidates SET assessment=? WHERE id=?",
                               (json.dumps(assessment,ensure_ascii=False), candidate))
                else:
                    abort(400)
    except ValueError:
        flash("Controleer bron, datum, bedragen en score-onderbouwing.", "error")
    except sqlite3.IntegrityError:
        flash("Deze productkandidaat bestaat al voor dit land.", "error")
    except (sqlite3.Error, OSError, RuntimeError):
        current_app.logger.error("Trendonderzoek kon niet worden opgeslagen")
        flash("Opslaan is niet gelukt.", "error")
    else:
        flash("Trendonderzoek opgeslagen.", "success")
    return redirect(url_for("control",section="viral",detail=candidate),code=303)


def growth_for(observations):
    groups = {}
    for row in observations:  # newest first
        if row["estimate"] or row["metric"] not in ("interest", "views", "likes", "shares", "saves", "orders"):
            continue
        key = (row["platform"], row["source"], row["window"], row["metric"])
        groups.setdefault(key, []).append(row)
    growth = []
    for (platform, source, window, metric), points in groups.items():
        latest = points[0]
        end = date.fromisoformat(latest["observed"])
        if (date.today()-end).days >= window:
            continue
        previous = next((row for row in points[1:] if date.fromisoformat(row["observed"]) == end-timedelta(days=window)),None)
        if previous and previous["value"]:
            growth.append(dict(platform=platform, source=source, window=window, metric=metric,
                               end=latest["observed"], percent=round(100*(latest["value"]/previous["value"]-1),1)))
    return growth


def viral_dashboard():
    from nv_research_intent import matches

    filters = {field: request.args.get(field,"") for field in ("country","niche","platform","period","score")}
    filters["candidate_q"] = request.args.get("candidate_q", "").strip()[:100]
    if (filters["country"] not in COUNTRIES and filters["country"]
            or filters["niche"] not in NICHES and filters["niche"]
            or filters["platform"] not in PLATFORMS and filters["platform"]
            or filters["period"] not in ("", "7", "30", "90")
            or not re.fullmatch(r"(?:[0-9]{1,2}|100)?",filters["score"])):
        abort(400)
    records = []
    detail = request.args.get("detail",type=int)
    error = None
    try:
        with connect() as db:
            tables(db)
            candidates = db.execute("SELECT * FROM viral_candidates ORDER BY id DESC").fetchall()
            observations = {}
            for row in db.execute("SELECT * FROM viral_observations ORDER BY observed DESC"):
                observations.setdefault(row["candidate"],[]).append(dict(row))
    except (sqlite3.Error,OSError,RuntimeError):
        current_app.logger.error("Trendonderzoekdatabase kon niet worden gelezen")
        candidates = []
        error = "Trendonderzoek is tijdelijk niet beschikbaar."
    for row in candidates:
        if filters["candidate_q"] and not matches(
            filters["candidate_q"], " ".join((row["title"], row["niche"], row["notes"])),
        ):
            continue
        if any(filters[key] and row[key] != filters[key] for key in ("country", "niche")):
            continue
        evidence = observations.get(row["id"],[])
        if filters["platform"] and not any(e["platform"]==filters["platform"] for e in evidence):
            continue
        if filters["period"] and not any(e["window"]==int(filters["period"]) and
                (date.today()-date.fromisoformat(e["observed"])).days<int(filters["period"]) and
                (not filters["platform"] or e["platform"]==filters["platform"]) for e in evidence):
            continue
        saved = json.loads(row["assessment"])
        scores = saved.get("scores",{})
        score = sum(scores[f]*weight for f,(_,weight,_) in FACTORS.items())/10 if scores.keys()==FACTORS.keys() else None
        if filters["score"] and (score is None or score < int(filters["score"])):
            continue
        costs = saved.get("costs",{})
        result = cost_result(costs)
        qualified = bool(result and result[0]>0 and len(saved.get("checks",[]))==len(CHECKS)
                         and saved.get("supplier_name") and saved.get("rationale"))
        growth = growth_for(evidence)
        contribution = {group: sum(scores[f]*w for f,(_,w,g) in FACTORS.items() if g==group)/10
                        for group in ("social","commercial")} if score is not None else {}
        records.append(dict(row)|dict(evidence=evidence, saved=saved, score=score, result=result,
                     growth=growth, qualified=qualified, components=contribution,
                     alert=qualified and any(g["metric"] in ("interest", "views", "likes", "shares", "saves", "orders")
                         and g["percent"]>=50 and g["window"] in (7,30) for g in growth)))
    selected = next((row for row in records if row["id"] == detail), None)
    dossier = dossier_view(selected) if selected else None
    if dossier and not dossier.get("error"):
        comparison = comparison_view(selected["id"], dossier["market"], dossier["record"])
        dossier["comparison"] = comparison
        offers = comparison.get("offers", [])
        supplier = dossier["record"].get("supplier_name", "").casefold()
        if offers and dossier["stage"] >= 2 and not any(
                row["ready"] and row["name"].casefold() == supplier for row in offers):
            dossier["stage"] = 1
            dossier["supplier_gate"] = True
    return dict(records=records, filters=filters, dossier=dossier, research_ai=research_enabled(), countries=COUNTRIES, niches=NICHES, platforms=PLATFORMS,
                factors=FACTORS, checks=CHECKS, amounts=AMOUNTS, detail=detail, error=error,
                currencies={code:row[1] for code,row in MARKETS.items()}|{"AU":"AUD","ES":"EUR","SE":"SEK","JP":"JPY"},
                today=date.today().isoformat())
