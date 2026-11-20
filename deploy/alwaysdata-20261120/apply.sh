#!/usr/bin/env bash
# NUVEMIXA webshop op Alwaysdata bijwerken (20-11-2026): compacte AI-knop, gelijk ondermenu,
# slimmere assistent, NUVEMIXA-banner, testteksten weg. Eerst back-up; bij een fout automatisch terug.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-klein-$STAMP.tar.gz
TMP=$(mktemp -d)
cd "$APP"
test -f wsgi.py && test -x .venv/bin/python && test -f templates/_bottomnav.html && test -f trendmix_assistant.py
grep -q "register_trendmix_assistant(app, *products, *CATEGORIES, *live_orders_enabled)" app.py \
  || { echo "STOP: app.py roept de assistent anders aan; niets gewijzigd."; exit 1; }

mkdir -p /home/nuvemixa/backups
# Volledige back-up staat al klaar (nuvemixa-voor-fix-20261120-160829.tar.gz); hier alleen de bestanden die veranderen.
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates nuvemixa/trendmix_assistant.py nuvemixa/static/images/hero/gadgets.jpg
tar -tzf "$BACKUP" >/dev/null
echo "Back-up gemaakt en gecontroleerd: $BACKUP"

for f in bottomnav-block.html trendmix_assistant.py nv_openai.py gadgets.jpg; do
  curl -fsSL "$RAW/$f" -o "$TMP/$f"
done
test -s "$TMP/trendmix_assistant.py" && grep -q "def clean_answer" "$TMP/trendmix_assistant.py"

restore() {
  echo "FOUT: back-up wordt teruggezet..."
  tar -xzf "$BACKUP" -C /home/nuvemixa/www
  rm -f "$APP/nv_openai.py"
  touch "$APP/wsgi.py" 2>/dev/null || true
  echo "Back-up teruggezet; de webshop is weer zoals voor deze update."
}
trap restore ERR

grep -q "NUVEMIXA 2026-11-20" templates/_bottomnav.html || cat "$TMP/bottomnav-block.html" >> templates/_bottomnav.html
cp "$TMP/trendmix_assistant.py" trendmix_assistant.py
cp "$TMP/nv_openai.py" nv_openai.py
cp "$TMP/gadgets.jpg" static/images/hero/gadgets.jpg
sed -i 's#lifestyle-sport.jpg{% endif %}"#lifestyle-sport.jpg{% endif %}?v=20261120"#' templates/category.html
for t in templates/*.html; do
  sed -i -e 's#NUVEMIXA · Webshop in ontwikkeling#NUVEMIXA · Slimme gadgets en meer#g' \
         -e 's#Webshop in ontwikkeling#Slimme gadgets en meer#g' \
         -e 's#Checkout in testfase#Bestellen binnenkort mogelijk#g' \
         -e 's#Webshop in testfase#Bestellen binnenkort mogelijk#g' \
         -e '/class="detail-test-note"/d' "$t"
done

.venv/bin/python -m compileall -q app.py trendmix_assistant.py nv_openai.py
.venv/bin/python -c 'from app import app as application; assert application is not None; print("App import OK")'
.venv/bin/python - <<'PY'
from app import app as application
c = application.test_client()
for path in ("/", "/gadgets", "/gadgets/bluetooth-speaker", "/winkelwagen", "/contact"):
    r = c.get(path)
    assert r.status_code == 200, (path, r.status_code)
r = c.post("/api/trendmix-assistant", json={"question": "Hebben jullie cadeau-ideeen onder 30 euro?", "language": "nl"})
assert r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200]
print("Pagina's en assistent OK")
PY
trap - ERR
touch wsgi.py 2>/dev/null || echo "Let op: herstart de site in het Alwaysdata-beheer om de update te laden."
rm -rf "$TMP"
echo "KLAAR: webshop bijgewerkt. Terugzetten kan met: tar -xzf $BACKUP -C /home/nuvemixa/www en herstart de site"
