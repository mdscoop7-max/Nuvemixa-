#!/usr/bin/env bash
# NUVEMIXA webshop op Alwaysdata bijwerken (20-11-2026): compacte AI-knop, gelijk ondermenu,
# slimmere assistent, NUVEMIXA-banner, testteksten weg. Eerst back-up; bij een fout automatisch terug.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
RAW=https://raw.githubusercontent.com/mdscoop7-max/Nuvemixa-/nv/webshop-fix-20261120/deploy/alwaysdata-20261120
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-$STAMP.tar.gz
TMP=$(mktemp -d)
cd "$APP"
test -f wsgi.py && test -x .venv/bin/python && test -f templates/_bottomnav.html && test -f trendmix_assistant.py
grep -q "register_trendmix_assistant(app, *products, *CATEGORIES, *live_orders_enabled)" app.py \
  || { echo "STOP: app.py roept de assistent anders aan; niets gewijzigd."; exit 1; }

mkdir -p /home/nuvemixa/backups
tar -czf "$BACKUP" --exclude=nuvemixa/.venv --exclude=nuvemixa/__pycache__ -C /home/nuvemixa/www nuvemixa
tar -tzf "$BACKUP" >/dev/null
echo "Back-up gemaakt en gecontroleerd: $BACKUP"

for f in bottomnav-block.html trendmix_assistant.py nv_openai.py gadgets.jpg; do
  curl -fsSL "$RAW/$f" -o "$TMP/$f"
done
test -s "$TMP/trendmix_assistant.py" && grep -q "def clean_answer" "$TMP/trendmix_assistant.py"

restore() {
  echo "FOUT: back-up wordt teruggezet..."
  tar -xzf "$BACKUP" -C /home/nuvemixa/www
  touch "$APP/wsgi.py"
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
.venv/bin/python -c 'from wsgi import application; assert application is not None; print("WSGI import OK")'
.venv/bin/python - <<'PY'
from wsgi import application
c = application.test_client()
for path in ("/", "/gadgets", "/gadgets/bluetooth-speaker", "/winkelwagen", "/contact"):
    r = c.get(path)
    assert r.status_code == 200, (path, r.status_code)
r = c.post("/api/trendmix-assistant", json={"question": "Hebben jullie cadeau-ideeen onder 30 euro?", "language": "nl"})
assert r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200]
print("Pagina's en assistent OK")
PY
trap - ERR
touch wsgi.py
rm -rf "$TMP"
echo "KLAAR: webshop bijgewerkt. Terugzetten kan met: tar -xzf $BACKUP -C /home/nuvemixa/www && touch $APP/wsgi.py"
