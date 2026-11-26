"""NUVEMIXA klantreviews.

Klanten sturen via de homepage een review in; die staat eerst op 'wachtend'
en wordt pas zichtbaar nadat de beheerder hem in het dashboard goedkeurt.
E-mailadressen worden nooit op de website getoond.
"""
import hashlib
import re
import sqlite3
from contextlib import contextmanager

from nv_storage_paths import database_path as _database_path

REVIEWS_DB = _database_path("NUVEMIXA_REVIEWS_DB", "nuvemixa_reviews.sqlite3")

STATUSES = ("wachtend", "gepubliceerd", "verborgen")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
MAX_PER_DAY_PER_EMAIL = 3
MAX_PER_DAY_PER_CLIENT = 5


def database_path():
    return REVIEWS_DB


@contextmanager
def connect():
    path = database_path()
    if not path.parent.is_dir():
        raise RuntimeError("Reviews database parent directory does not exist")
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                product TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'nl',
                verified INTEGER NOT NULL DEFAULT 0,
                reply TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'wachtend'
                    CHECK (status IN ('wachtend','gepubliceerd','verborgen')),
                client_hash TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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


def _clean(value, limit):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _clean_body(value, limit):
    text = str(value or "").replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:limit]


def client_hash(remote_addr, secret):
    raw = f"{secret}|{remote_addr or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def submit_review(form, language="nl", client="", consent=False):
    """Valideer en bewaar een nieuwe review. Geeft 'ok', 'ongeldig' of 'limiet' terug."""
    name = _clean(form.get("name"), 60)
    email = _clean(form.get("email"), 254).lower()
    title = _clean(form.get("title"), 80)
    body = _clean_body(form.get("body"), 1500)
    product = _clean(form.get("product"), 80)
    try:
        rating = int(form.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if (len(name) < 2 or not EMAIL_RE.match(email) or not 1 <= rating <= 5
            or len(title) < 2 or len(body) < 10 or not consent):
        return "ongeldig"
    language = "en" if language == "en" else "nl"
    with connect() as conn:
        recent_email = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE email = ? AND created_at >= datetime('now','-1 day')",
            (email,)).fetchone()[0]
        recent_client = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE client_hash = ? AND client_hash != '' "
            "AND created_at >= datetime('now','-1 day')", (client,)).fetchone()[0]
        if recent_email >= MAX_PER_DAY_PER_EMAIL or recent_client >= MAX_PER_DAY_PER_CLIENT:
            return "limiet"
        conn.execute(
            "INSERT INTO reviews (name, email, rating, title, body, product, language, client_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, email, rating, title, body, product, language, client))
    return "ok"


def published_reviews(limit=6):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, rating, title, body, product, verified, reply, created_at "
            "FROM reviews WHERE status = 'gepubliceerd' ORDER BY created_at DESC, id DESC LIMIT ?",
            (int(limit),)).fetchall()
    return [dict(row) for row in rows]


def review_stats():
    with connect() as conn:
        rows = conn.execute(
            "SELECT rating, COUNT(*) AS n FROM reviews WHERE status = 'gepubliceerd' GROUP BY rating"
        ).fetchall()
    dist = {star: 0 for star in (5, 4, 3, 2, 1)}
    for row in rows:
        dist[int(row["rating"])] = int(row["n"])
    count = sum(dist.values())
    average = (sum(star * n for star, n in dist.items()) / count) if count else 0.0
    bars = [{"star": star, "count": n, "percent": round(n * 100 / count) if count else 0}
            for star, n in dist.items()]
    return {"count": count, "average": round(average, 1), "bars": bars}


def all_reviews():
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY CASE status WHEN 'wachtend' THEN 0 ELSE 1 END, "
            "created_at DESC, id DESC LIMIT 500").fetchall()
    return [dict(row) for row in rows]


def update_review(review_id, action, reply="", verified=False):
    """Beheeractie: publiceren, verbergen, verwijderen of opslaan (reactie/geverifieerd)."""
    review_id = int(review_id)
    with connect() as conn:
        if action == "publiceren":
            conn.execute("UPDATE reviews SET status = 'gepubliceerd' WHERE id = ?", (review_id,))
        elif action == "verbergen":
            conn.execute("UPDATE reviews SET status = 'verborgen' WHERE id = ?", (review_id,))
        elif action == "verwijderen":
            conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        elif action == "opslaan":
            conn.execute("UPDATE reviews SET reply = ?, verified = ? WHERE id = ?",
                         (_clean_body(reply, 600), 1 if verified else 0, review_id))
        else:
            raise ValueError("Onbekende actie")
