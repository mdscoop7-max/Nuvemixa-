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


_writer = __import__("concurrent.futures").futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="nv-store")


def _write(key, state, text, created_at, now):
    try:
        with connect() as db:
            _sqlite(db)
            db.execute(UPSERT, (key, state, text, created_at, now))
        with _lock:
            hit = _memory.get(key)
            if hit and hit[3] == now:
                _memory[key] = (*hit[:4], True)
        return "database"
    except Exception:  # noqa: BLE001 - opslag tijdelijk weg: taak loopt door in het geheugen
        return "geheugen"


def save(key, state, payload, created_at=None, wait=True):
    """Bewaart status + gegevens: altijd direct in het geheugen van dit proces, en in de database.

    wait=False (tussenstappen): de database-schrijfactie loopt op de achtergrond in volgorde, zodat geen verzoek wacht
    op een verbinding Render (Oregon) -> Neon (Frankfurt). Live 27-11: het starten van een onderzoek duurde 28 s.
    Eindresultaten worden met wait=True geschreven: pas daarna is 'permanent opgeslagen' waar."""
    now = time.time()
    created_at = created_at or now
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) > MAX_PAYLOAD:
        text = json.dumps({**payload, "result": None, "error": "Resultaat te groot om op te slaan."})
    with _lock:
        _memory[key] = (state, text, created_at, now, False)
        if len(_memory) > 300:
            _memory.pop(min(_memory, key=lambda item: _memory[item][3]))
    if not wait:
        _writer.submit(_write, key, state, text, created_at, now)
        return "database (op de achtergrond)"
    return _writer.submit(_write, key, state, text, created_at, now).result()


def load(key):
    """Geeft {'state', 'payload', 'created_at', 'updated_at', 'storage'} of None.

    Eerst het geheugen van dit proces (de taak draait meestal hier); anders de database (andere worker of herstart)."""
    with _lock:
        hit = _memory.get(key)
    if hit is not None:
        return {"state": hit[0], "payload": json.loads(hit[1]), "created_at": hit[2], "updated_at": hit[3],
                "storage": "database" if hit[4] else "geheugen"}
    try:
        with connect() as db:
            _sqlite(db)
            row = db.execute("SELECT state, payload, created_at, updated_at FROM research_cache WHERE cache_key = ?",
                             (key,)).fetchone()
        if row is not None:
            result = {"state": row[0], "payload": json.loads(row[1]), "created_at": float(row[2]),
                      "updated_at": float(row[3]), "storage": "database"}
            if row[0] == "done":
                with _lock:
                    _memory[key] = (row[0], row[1], float(row[2]), float(row[3]), True)
            return result
    except Exception:  # noqa: BLE001
        pass
    return None
