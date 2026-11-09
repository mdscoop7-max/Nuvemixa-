"""Locally stored, verified-source monitoring snapshots; no live external API calls."""
import json
import math
import os
import sqlite3
import time
from pathlib import Path

ALLOWED = ("rankfix", "search_console", "google_ads")
METRICS = {
    "rankfix": ("overall_score", "seo_score", "geo_score", "coverage_percent"),
    "search_console": ("clicks", "impressions", "ctr_percent", "position"),
    "google_ads": ("spend_eur", "clicks", "conversions", "cost_per_conversion_eur"),
}

def connect():
    path = Path(os.getenv("TRENDMIX_MONITORING_DB", str(Path(__file__).resolve().parent / "instance" / "monitoring.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, source TEXT NOT NULL, subject TEXT NOT NULL, data TEXT NOT NULL, captured_at INTEGER NOT NULL)")
    return db

def save_report(source, subject, metrics):
    if source not in ALLOWED or not (2 <= len(subject.strip()) <= 150):
        raise ValueError("Ongeldige bron of onderwerp")
    if not isinstance(metrics, dict) or not metrics or len(metrics) > 8:
        raise ValueError("Ongeldige metingen")
    cleaned = {}
    for key, value in metrics.items():
        if key not in METRICS[source]:
            raise ValueError("Onbekende meting")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not (-10000000 <= value <= 10000000):
            raise ValueError("Meting buiten veilige grenzen")
        if not math.isfinite(value):
            raise ValueError("NaN niet toegestaan")
        cleaned[key] = float(value)
    with connect() as db:
        db.execute("INSERT INTO reports(source,subject,data,captured_at) VALUES(?,?,?,?)",
                   (source,subject.strip(),json.dumps(cleaned),int(time.time())))

def latest_reports():
    with connect() as db:
        rows = db.execute("SELECT source,subject,data,captured_at FROM reports ORDER BY captured_at DESC,id DESC LIMIT 60").fetchall()
    return [{"source":r["source"],"subject":r["subject"],"metrics":json.loads(r["data"]),
             "captured_at":r["captured_at"]} for r in rows]
