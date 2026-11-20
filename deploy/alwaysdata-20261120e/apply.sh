#!/usr/bin/env bash
# NUVEMIXA 20-11-2026 (e): infoblok onder de producten op elke pagina, winkelwagen gelijk aan account,
# volledige NL/EN-vertaling, land vrij invullen, nieuw ontwerp pagina Meer, geen witte flits bij navigeren, sneller laden.
# Kleine back-up vooraf; bij een fout wordt alles automatisch teruggezet.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=${NV_RAW:-https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120e}
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-e-$(date -u +%Y%m%d-%H%M%S).tar.gz
cd "$APP"
test -f templates/_bottomnav.html && test -x .venv/bin/python
mkdir -p /home/nuvemixa/backups
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates && tar -tzf "$BACKUP" >/dev/null && echo "Back-up: $BACKUP"
TMP=$(mktemp -d)
for f in block.html head.html edit_templates.py nv-fix-20261120e.js meer.html; do curl -fsSL "$RAW/$f" -o "$TMP/$f"; done
grep -q "nv-ready-20261120e" "$TMP/block.html" && grep -q "__nvFix20261120e" "$TMP/nv-fix-20261120e.js"
restore(){ echo "FOUT: back-up wordt teruggezet..."; tar -xzf "$BACKUP" -C /home/nuvemixa/www; rm -f "$APP/static/nv-fix-20261120e.js"; echo "Teruggezet; de webshop is weer zoals voor deze update."; }
trap restore ERR
cp "$TMP/nv-fix-20261120e.js" static/nv-fix-20261120e.js
grep -q "NUVEMIXA 2026-11-20e:" templates/_bottomnav.html || cat "$TMP/block.html" >> templates/_bottomnav.html
.venv/bin/python "$TMP/edit_templates.py" "$TMP/head.html"
if [ -f templates/meer.html ]; then cp "$TMP/meer.html" templates/meer.html; echo "Pagina Meer: nieuw ontwerp geplaatst"; else echo "Pagina Meer: niet gevonden - overgeslagen"; fi
.venv/bin/python - <<'PY'
from app import app as application
application.jinja_env.get_template('checkout.html')
c = application.test_client()
ok = 0
for path in ("/", "/shop", "/gadgets", "/smart-home", "/beauty-care", "/home-living", "/lifestyle-sport", "/aanbiedingen", "/winkelwagen", "/contact", "/faq", "/gadgets/bluetooth-speaker", "/meer"):
    r = c.get(path)
    if r.status_code == 404:
        print("let op: bestaat niet:", path); continue
    assert r.status_code == 200, (path, r.status_code)
    assert b"nv-fix-20261120e.js" in r.data and b"nv-services-e" in r.data, ("blok ontbreekt", path)
    ok += 1
r = c.get("/"); assert b"NUVEMIXA 2026-11-20e head" in r.data, "kop ontbreekt op home"
r = c.get("/afrekenen"); assert r.status_code in (200, 302, 303), ("afrekenen", r.status_code)
r = c.get("/static/nv-fix-20261120e.js"); assert r.status_code == 200 and b"__nvFix20261120e" in r.data
print("Pagina's OK:", ok)
PY
trap - ERR
rm -rf "$TMP"
touch wsgi.py 2>/dev/null || true
echo "KLAAR. Herstart de site in Alwaysdata (Websites > herstarten). Terugzetten: tar -xzf $BACKUP -C /home/nuvemixa/www && rm -f $APP/static/nv-fix-20261120e.js"
