#!/usr/bin/env bash
# NUVEMIXA 20-11-2026 (d): hero-teksten vertaalbaar (NL/EN) over donker vlak. Kleine back-up; bij fout terug.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120d
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-dd-$(date -u +%Y%m%d-%H%M%S).tar.gz
cd "$APP"
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates && tar -tzf "$BACKUP" >/dev/null && echo "Back-up: $BACKUP"
TMP=$(mktemp -d); curl -fsSL "$RAW/hero-block.html" -o "$TMP/b.html"; curl -fsSL "$RAW/edit_templates.py" -o "$TMP/e.py"
grep -q 2026-11-20d "$TMP/b.html"
restore(){ echo "FOUT: back-up wordt teruggezet..."; tar -xzf "$BACKUP" -C /home/nuvemixa/www; echo "Teruggezet."; }
trap restore ERR
grep -q "NUVEMIXA 2026-11-20d" templates/_bottomnav.html || cat "$TMP/b.html" >> templates/_bottomnav.html
.venv/bin/python "$TMP/e.py"
.venv/bin/python - <<'PY'
from app import app as application
c = application.test_client()
for path in ("/", "/gadgets", "/smart-home", "/beauty-care", "/lifestyle-sport", "/shop", "/aanbiedingen", "/winkelwagen", "/gadgets/bluetooth-speaker"):
    r = c.get(path); assert r.status_code == 200, (path, r.status_code)
    assert b"2026-11-20d" in r.data, path
r = c.get("/smart-home"); assert b'data-tm-en="A smarter home, every day"' in r.data
print("Pagina's OK, hero vertaalbaar")
PY
trap - ERR
rm -rf "$TMP"
echo "KLAAR. Herstart de site. Terugzetten: tar -xzf $BACKUP -C /home/nuvemixa/www"
