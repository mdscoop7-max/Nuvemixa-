"""Private, local-only administrative drafts. No public catalog writes or outgoing mail."""
import os, sqlite3, time
from pathlib import Path

def database():
    path=Path(os.getenv("TRENDMIX_ADMIN_DB",str(Path(__file__).resolve().parent/"instance"/"admin_drafts.sqlite3")))
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(path),timeout=5)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("CREATE TABLE IF NOT EXISTS product_drafts (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price_cents INTEGER NOT NULL, description TEXT NOT NULL, image_url TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS support_drafts (id INTEGER PRIMARY KEY, customer_question TEXT NOT NULL, draft_answer TEXT NOT NULL, created_at INTEGER NOT NULL)")
    return db

def list_drafts():
    with database() as db:
        return [dict(r) for r in db.execute("SELECT * FROM product_drafts ORDER BY updated_at DESC,id DESC LIMIT 100").fetchall()]

def save_draft(name,category,price_cents,description,image_url="",draft_id=None):
    with database() as db:
        now=int(time.time())
        if draft_id is not None:
            cur=db.execute("UPDATE product_drafts SET name=?,category=?,price_cents=?,description=?,image_url=?,updated_at=? WHERE id=?", (name,category,price_cents,description,image_url,now,draft_id))
            return cur.rowcount>0
        db.execute("INSERT INTO product_drafts(name,category,price_cents,description,image_url,updated_at) VALUES(?,?,?,?,?,?)",(name,category,price_cents,description,image_url,now))
        return True

def remove_draft(draft_id):
    with database() as db:
        return db.execute("DELETE FROM product_drafts WHERE id=?",(draft_id,)).rowcount>0

def add_support_draft(question,answer):
    with database() as db:
        db.execute("INSERT INTO support_drafts(customer_question,draft_answer,created_at) VALUES(?,?,?)",(question,answer,int(time.time())))

def list_support_drafts():
    with database() as db:
        return [dict(r) for r in db.execute("SELECT * FROM support_drafts ORDER BY id DESC LIMIT 30").fetchall()]
