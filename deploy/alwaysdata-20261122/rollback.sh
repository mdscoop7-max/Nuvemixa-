#!/usr/bin/env bash
# Zet app.py en templates terug uit de back-up die apply.sh maakte en verwijdert de correctielaag.
#   bash rollback.sh /home/nuvemixa/backups/nuvemixa-pre-polish-YYYYMMDD-HHMMSS.tar.gz
set -euo pipefail
APP="${NUVEMIXA_APP:-/home/nuvemixa/www/nuvemixa}"
KIT="$(cd "$(dirname "$0")" && pwd)"
BACKUP="${1:-$(cat "$KIT/LAATSTE_BACKUP.txt" 2>/dev/null || true)}"
test -f "$BACKUP" || { echo "STOP: back-up niet gevonden: $BACKUP"; exit 1; }
tar -tzf "$BACKUP" >/dev/null
rm -f "$APP/static/nv-polish-20261122.css" "$APP/static/nv-polish-20261122.js"
tar -xzf "$BACKUP" -C "$APP"
PY="$APP/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
cd "$APP"; if [ -f wsgi.py ]; then "$PY" -c 'from wsgi import application; print("WSGI import OK")'; touch wsgi.py; fi
echo "Teruggezet uit $BACKUP"
