#!/usr/bin/env bash
# NUVEMIXA 20-11-2026 (b): AI-knop eigen kleur + footer "TrendMix" -> NUVEMIXA. Kleine back-up; bij fout automatisch terug.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120b
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-b-$STAMP.tar.gz
cd "$APP"
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates nuvemixa/static/app.js nuvemixa/static/languages.js nuvemixa/product_art.py
tar -tzf "$BACKUP" >/dev/null && echo "Back-up: $BACKUP"
BLOCK=$(mktemp); curl -fsSL "$RAW/ai-kleur-block.html" -o "$BLOCK"; grep -q "2026-11-20b" "$BLOCK"
restore(){ echo "FOUT: back-up wordt teruggezet..."; tar -xzf "$BACKUP" -C /home/nuvemixa/www; echo "Teruggezet."; }
trap restore ERR
grep -q "NUVEMIXA 2026-11-20b" templates/_bottomnav.html || cat "$BLOCK" >> templates/_bottomnav.html
sed -i -e 's/TrendMix/NUVEMIXA/g' -e 's/Webshop in ontwikkeling/Slimme gadgets en meer/g' static/app.js static/languages.js
sed -i 's/"TrendMix product"/"NUVEMIXA product"/' product_art.py
for t in templates/*.html; do sed -i -e "s#filename='app.js')#filename='app.js', v='20261120b')#g" -e "s#filename='languages.js')#filename='languages.js', v='20261120b')#g" "$t"; done
echo "TrendMix over in js: $(cat static/app.js static/languages.js | grep -c TrendMix || true)"
echo "TrendMix in productdata (ter info): $(grep -rl TrendMix products content 2>/dev/null | wc -l) bestanden"
.venv/bin/python - <<'PY'
from app import app as application
c = application.test_client()
for path in ("/", "/gadgets", "/gadgets/bluetooth-speaker", "/winkelwagen", "/contact"):
    r = c.get(path); assert r.status_code == 200, (path, r.status_code)
    assert b"2026-11-20b" in r.data, ("AI-kleur ontbreekt", path)
    import re
    zichtbaar = re.sub(rb"<[^>]+>", b" ", re.sub(rb"(?s)<(script|style)[^>]*>.*?</\1>", b"", r.data))
    if b"TrendMix" in zichtbaar or b"TRENDMIX" in zichtbaar: print("Let op: TrendMix nog zichtbaar op", path)
print("Pagina's OK, AI-kleur overal aanwezig")
PY
trap - ERR
rm -f "$BLOCK"
echo "KLAAR. Herstart de site. Terugzetten: tar -xzf $BACKUP -C /home/nuvemixa/www"
