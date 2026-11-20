#!/usr/bin/env bash
# NUVEMIXA 20-11-2026 (f): kleine correctie op (e): FAQ volledig Engels, hero-afbeeldingen niet meer aangeraakt door de vertaler.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=${NV_RAW:-https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120f}
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-f-$(date -u +%Y%m%d-%H%M%S).tar.gz
cd "$APP"
grep -q "nv-fix-20261120e.js" templates/_bottomnav.html
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates/_bottomnav.html nuvemixa/static/nv-fix-20261120e.js && echo "Back-up: $BACKUP"
TMP=$(mktemp -d); curl -fsSL "$RAW/nv-fix-20261120e.js" -o "$TMP/nv.js"; grep -q "__nvFix20261120e" "$TMP/nv.js"
restore(){ echo "FOUT: terugzetten..."; tar -xzf "$BACKUP" -C /home/nuvemixa/www; echo "Teruggezet."; }
trap restore ERR
cp "$TMP/nv.js" static/nv-fix-20261120e.js
sed -i 's/nv-fix-20261120e\.js?v=20261120e"/nv-fix-20261120e.js?v=20261120f"/' templates/_bottomnav.html
grep -q 'nv-fix-20261120e.js?v=20261120f' templates/_bottomnav.html
.venv/bin/python - <<'PY'
from app import app as application
c = application.test_client()
for path in ("/", "/shop", "/faq", "/meer", "/contact"):
    r = c.get(path); assert r.status_code == 200 and b"v=20261120f" in r.data, path
r = c.get("/static/nv-fix-20261120e.js"); assert b"WhatsApp will be added later" in r.data
print("Pagina's OK")
PY
trap - ERR; rm -rf "$TMP"
echo "KLAAR (f). Herstart de site."
