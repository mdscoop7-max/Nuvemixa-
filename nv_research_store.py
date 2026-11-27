"""Permanente zoekcache en taakstatus voor het onderzoeksproces (Neon PostgreSQL, lokaal SQLite).

Eén rij per zoekopdracht (sleutel = genormaliseerde invoer). De rij bevat de status ('running', 'done', 'failed'),
de voortgangsstappen en het resultaat als JSON. Omdat Render meerdere gunicorn-workers kan draaien, leest de
statusroute altijd uit deze tabel: de worker die de taak uitvoert en de worker die de status geeft hoeven niet dezelfde
te zijn. Er wordt nooit iets verwijderd (de applicatierol heeft alleen SELECT, INSERT en UPDATE).

Is de opslag tijdelijk niet bereikbaar, dan valt dit terug op het geheugen van het proces; dat staat in 'storage'.
"""
import json
import threading
import time

SQLITE_TABLE = ("CREATE TABLE IF NOT EXISTS research_cache (cache_key TEXT PRIMARY KEY, state TEXT NOT NULL, "
                "payload TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL)")
UPSERT = ("INSERT INTO research_cache(cache_key, state, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?) "
          "ON CONFLICT(cache_key) DO UPDATE SET state = excluded.state, payload = excluded.payload, "
          "created_at = excluded.created_at, updated_at = excluded.updated_at")
MAX_PAYLOAD = 900_000
_memory = {}
_lock = threading.Lock()


def connect():
    import nuvemixa_admin_store
    return nuvemixa_admin_store.connect()


def _sqlite(db):
    import nv_dashboard_postgres
    if not nv_dashboard_postgres.runtime_enabled():
        db.execute(SQLITE_TABLE)


def save(key, state, payload, created_at=None):
    """Bewaart status + gegevens. Geeft 'database' of 'geheugen' terug (waar het werkelijk staat)."""
    now = time.time()
    created_at = created_at or now
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) > MAX_PAYLOAD:
        text = json.dumps({**payload, "result": None, "error": "Resultaat te groot om op te slaan."})
    with _lock:
        _memory[key] = (state, text, created_at, now)
        if len(_memory) > 200:
            _memory.pop(min(_memory, key=lambda item: _memory[item][3]))
    try:
        with connect() as db:
            _sqlite(db)
            db.execute(UPSERT, (key, state, text, created_at, now))
        return "database"
    except Exception:  # noqa: BLE001 - opslag tijdelijk weg: taak loopt door in het geheugen
        return "geheugen"


def load(key):
    """Geeft {'state', 'payload', 'created_at', 'updated_at', 'storage'} of None."""
    try:
        with connect() as db:
            _sqlite(db)
            row = db.execute("SELECT state, payload, created_at, updated_at FROM research_cache WHERE cache_key = ?",
                             (key,)).fetchone()
        if row is not None:
            return {"state": row[0], "payload": json.loads(row[1]), "created_at": float(row[2]),
                    "updated_at": float(row[3]), "storage": "database"}
    except Exception:  # noqa: BLE001
        pass
    with _lock:
        hit = _memory.get(key)
    if hit is None:
        return None
    return {"state": hit[0], "payload": json.loads(hit[1]), "created_at": hit[2], "updated_at": hit[3],
            "storage": "geheugen"}
