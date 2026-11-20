#!/usr/bin/env bash
# NUVEMIXA 20-11-2026 (f): correctie op (e): FAQ/afrekenen/desktop volledig Engels, hero-afbeeldingen niet aangeraakt door vertaler,
# geen horizontale scroll op desktop, Home & Living krijgt een H1 (zelfde uiterlijk), HSTS (1 dag) + CSP in testmodus.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=${NV_RAW:-https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120f}
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-f-$(date -u +%Y%m%d-%H%M%S).tar.gz
cd "$APP"
grep -q "nv-fix-20261120e.js" templates/_bottomnav.html
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates nuvemixa/static/nv-fix-20261120e.js nuvemixa/app.py && echo "Back-up: $BACKUP"
TMP=$(mktemp -d); curl -fsSL "$RAW/nv-fix-20261120e.js" -o "$TMP/nv.js"; grep -q "__nvFix20261120e" "$TMP/nv.js"
curl -fsSL "$RAW/headers.py" -o "$TMP/headers.py"; grep -q "_nv_security_headers_20261120f" "$TMP/headers.py"
restore(){ echo "FOUT: terugzetten..."; tar -xzf "$BACKUP" -C /home/nuvemixa/www; echo "Teruggezet."; }
trap restore ERR
cp "$TMP/nv.js" static/nv-fix-20261120e.js
grep -q "_nv_security_headers_20261120f" app.py || cat "$TMP/headers.py" >> app.py
sed -i 's/nv-fix-20261120e\.js?v=20261120e"/nv-fix-20261120e.js?v=20261120f"/' templates/_bottomnav.html
grep -q 'nv-fix-20261120e.js?v=20261120f' templates/_bottomnav.html
.venv/bin/python - <<'PY'
import glob, re
n = 0
for p in glob.glob('templates/*.html'):
    s = open(p, encoding='utf-8').read()
    s2, k = re.subn(r'<h2 class="nv-hl-h"([^>]*)>(.*?)</h2>', r'<h1 class="nv-hl-h"\1>\2</h1>', s, flags=re.S)
    if k:
        open(p, 'w', encoding='utf-8').write(s2); n += k
print('Home & Living H1:', n, 'aangepast')
PY
.venv/bin/python - <<'PY'
from app import app as application
c = application.test_client()
for path in ("/", "/shop", "/faq", "/meer", "/contact", "/home-living", "/gadgets"):
    r = c.get(path)
    if r.status_code == 404: print("let op: bestaat niet:", path); continue
    assert r.status_code == 200 and b"v=20261120f" in r.data, path
r = c.get("/")
assert r.headers.get("Strict-Transport-Security") and r.headers.get("Content-Security-Policy-Report-Only"), "headers ontbreken"
print("Headers OK: HSTS + CSP (testmodus)")
h = c.get("/home-living").data
print("Home & Living H1 aanwezig:", h.count(b"<h1") >= 1)
r = c.get("/static/nv-fix-20261120e.js"); assert b"WhatsApp will be added later" in r.data
print("Pagina's OK")
PY
trap - ERR; rm -rf "$TMP"
echo "KLAAR (f). Herstart de site."
