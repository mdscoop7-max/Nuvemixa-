"""Local-only admin accounts. Never expose this store in serverless deployments."""
import os
import re
import sqlite3
import hmac
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

DB = Path(os.environ.get("TRENDMIX_ADMIN_DB", str(Path(__file__).resolve().parent / "instance" / "admin_users.sqlite3")))
ROLES = ("owner", "manager", "staff")

def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS admin_users (username TEXT PRIMARY KEY COLLATE NOCASE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','manager','staff')), active INTEGER NOT NULL DEFAULT 1)")
    return conn

def account(username, password):
    if not username or not password:
        return None
    with connection() as db:
        row=db.execute("SELECT username,password_hash,role,active FROM admin_users WHERE username=?",(username,)).fetchone()
        if row:
            return {"username":row[0],"role":row[2]} if row[3] and check_password_hash(row[1],password) else None
    original=os.getenv("TRENDMIX_ADMIN_USER","")
    secret=os.getenv("TRENDMIX_ADMIN_PASSWORD","")
    if len(secret)>=16 and hmac.compare_digest(username,original) and hmac.compare_digest(password,secret):
        return {"username":original,"role":"owner"}
    return None

def list_users():
    with connection() as db:
        return [{"username":x[0],"role":x[1],"active":bool(x[2])} for x in db.execute("SELECT username,role,active FROM admin_users ORDER BY username").fetchall()]

def add_user(username,password,role):
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,40}",username or "") or role not in ("manager","staff") or len(password or "")<16 or len(password)>256:
        raise ValueError("Gebruik 3-40 tekens voor de naam en een uniek wachtwoord van minimaal 16 tekens.")
    if username.casefold()==os.getenv("TRENDMIX_ADMIN_USER","").casefold():
        raise ValueError("Deze gebruikersnaam is gereserveerd.")
    with connection() as db:
        db.execute("INSERT INTO admin_users(username,password_hash,role) VALUES(?,?,?)",(username,generate_password_hash(password),role))

def update_password(username,new_password):
    if not 16<=len(new_password or "")<=256:
        raise ValueError("Het nieuwe wachtwoord moet minimaal 16 tekens bevatten.")
    with connection() as db:
        db.execute("INSERT INTO admin_users(username,password_hash,role,active) VALUES(?,?,?,1) ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash",(username,generate_password_hash(new_password),"owner" if username==os.getenv("TRENDMIX_ADMIN_USER") else "staff"))

def remove_user(username):
    with connection() as db:
        db.execute("DELETE FROM admin_users WHERE username=? AND role!='owner'",(username,))
