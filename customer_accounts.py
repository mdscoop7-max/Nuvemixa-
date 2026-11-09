"""Local development customer accounts. This SQLite store is NOT a production identity service."""
import os
import sqlite3
import time
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

_DUMMY_HASH = generate_password_hash("unusable-login-sentinel", method="scrypt")

def _path():
    return Path(os.getenv("TRENDMIX_ACCOUNTS_DB", str(Path(__file__).resolve().parent / "instance" / "customer_accounts.sqlite3")))

def _db():
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS login_attempts (key TEXT PRIMARY KEY, failures INTEGER NOT NULL, last_failure INTEGER NOT NULL)")
    return db

def normalize_email(value):
    return value.strip().casefold()

def create_account(name, email, password):
    email = normalize_email(email)
    name = name.strip()
    if not (1 <= len(name) <= 80 and 3 <= len(email) <= 254 and "@" in email and email.index("@") > 0 and "." in email.rsplit("@", 1)[-1] and 12 <= len(password) <= 1024):
        return None
    hashed = generate_password_hash(password, method="scrypt")
    with _db() as db:
        try:
            cur = db.execute("INSERT INTO accounts(email,name,password_hash,created_at) VALUES(?,?,?,?)", (email,name,hashed,int(time.time())))
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

def authenticate(email, password, ip):
    email = normalize_email(email)
    key = email + "|" + ip[:48]
    now = int(time.time())
    with _db() as db:
        row = db.execute("SELECT failures,last_failure FROM login_attempts WHERE key=?", (key,)).fetchone()
        if row and row["failures"] >= 5 and now - row["last_failure"] < 900:
            return None, True
        account = db.execute("SELECT id,email,name,password_hash FROM accounts WHERE email=?", (email,)).fetchone()
        # Always perform a password-hash verification to reduce account enumeration.
        dummy = _DUMMY_HASH
        ok = check_password_hash(account["password_hash"] if account else dummy, password)
        if ok and account:
            db.execute("DELETE FROM login_attempts WHERE key=?", (key,))
            return dict(account), False
        failures = (row["failures"] if row and now - row["last_failure"] < 900 else 0) + 1
        db.execute("INSERT INTO login_attempts(key,failures,last_failure) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET failures=excluded.failures,last_failure=excluded.last_failure", (key,failures,now))
        return None, failures >= 5

def account_by_id(account_id):
    with _db() as db:
        account = db.execute("SELECT id,email,name,created_at FROM accounts WHERE id=?", (account_id,)).fetchone()
        return dict(account) if account else None
