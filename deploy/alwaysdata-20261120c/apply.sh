#!/usr/bin/env bash
# NUVEMIXA 20-11-2026 (c): taalknop toont NL/EN naast de vlag; laatste TrendMix-teksten -> NUVEMIXA;
# oude ?v=-versies van scripts verversen zodat browsers de nieuwe teksten laden. Kleine back-up; bij fout terug.
set -euo pipefail
APP=/home/nuvemixa/www/nuvemixa
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/home/nuvemixa/backups/nuvemixa-voor-fix-c-$STAMP.tar.gz
cd "$APP"
tar -czf "$BACKUP" -C /home/nuvemixa/www nuvemixa/templates nuvemixa/static/trendmix-english-labels.js nuvemixa/static/app.js nuvemixa/static/languages.js nuvemixa/static/trendmix-ui-2026.js
tar -tzf "$BACKUP" >/dev/null && echo "Back-up: $BACKUP"
restore(){ echo "FOUT: back-up wordt teruggezet..."; tar -xzf "$BACKUP" -C /home/nuvemixa/www; echo "Teruggezet."; }
trap restore ERR
# Alleen zichtbare tekst: niet de JS-naam window.TrendMixEnglishLabels
perl -pi -e 's/(?<![\w.\$])TrendMix(?![\w\$])/NUVEMIXA/g' static/trendmix-english-labels.js
grep -q "window.TrendMixEnglishLabels" static/trendmix-english-labels.js
# Taalknop: NL / EN in plaats van Taal / Language (vlag blijft)
LOC='class="tm-locale-title" data-tm-tr data-tm-nl="Taal" data-tm-en="Language">[^<]*<'
NEW='class="tm-locale-title" data-tm-tr data-tm-nl="NL" data-tm-en="EN">NL<'
N=0
for f in templates/*.html static/trendmix-ui-2026.js static/app.js static/languages.js; do
  if grep -q 'class="tm-locale-title" data-tm-tr data-tm-nl="Taal"' "$f"; then sed -i "s#$LOC#$NEW#g" "$f"; N=$((N+1)); echo "taalknop aangepast in $f"; fi
done
# Versies verversen (hard-gecodeerde ?v=)
for t in templates/*.html; do
  sed -i -E 's#(app|languages|trendmix-english-labels|trendmix-ui-2026)\.js\?v=[0-9A-Za-z._-]+#\1.js?v=20261120c#g' "$t"
done
echo "Taalknop-bestanden: $N"
.venv/bin/python - <<'PY'
import re
from app import app as application
c = application.test_client()
for path in ("/", "/gadgets", "/gadgets/bluetooth-speaker", "/winkelwagen", "/contact"):
    r = c.get(path); assert r.status_code == 200, (path, r.status_code)
    zichtbaar = re.sub(rb"<[^>]+>", b" ", re.sub(rb"(?s)<(script|style)[^>]*>.*?</\1>", b"", r.data))
    print(path, "TrendMix zichtbaar:", b"TrendMix" in zichtbaar, "| NL-knop:", b'data-tm-nl="NL"' in r.data)
print("Pagina's OK")
PY
trap - ERR
echo "KLAAR. Herstart de site. Terugzetten: tar -xzf $BACKUP -C /home/nuvemixa/www"
