#!/usr/bin/env bash
# NUVEMIXA live-patch 22-11-2026 — uitvoeren op de Alwaysdata-server (SSH).
#   bash apply.sh            -> back-up + droge run (wijzigt niets)
#   bash apply.sh --apply    -> back-up + toepassen + controle + herstart app
# Raakt geen database, geen .env, geen 2FA-bestanden, geen Render/Neon.
set -euo pipefail
APP="${NUVEMIXA_APP:-/home/nuvemixa/www/nuvemixa}"
KIT="$(cd "$(dirname "$0")" && pwd)"
PY="$APP/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

test -f "$APP/app.py" || { echo "STOP: $APP/app.py niet gevonden"; exit 1; }

BK="${NUVEMIXA_BACKUPS:-/home/nuvemixa/backups}"
mkdir -p "$BK"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP="$BK/nuvemixa-pre-polish-$STAMP.tar.gz"
tar -czf "$BACKUP" -C "$APP" app.py templates static/nv-polish-20261122.css static/nv-polish-20261122.js 2>/dev/null \
  || tar -czf "$BACKUP" -C "$APP" app.py templates
tar -tzf "$BACKUP" >/dev/null
echo "Back-up gecontroleerd: $BACKUP"
echo "$BACKUP" > "$KIT/LAATSTE_BACKUP.txt"

if [ "${1:-}" != "--apply" ]; then
  "$PY" "$KIT/nv_patch_live.py" --app "$APP"
  echo; echo "Droge run klaar. Niets gewijzigd. Uitvoeren: bash apply.sh --apply"
  exit 0
fi

"$PY" "$KIT/nv_patch_live.py" --app "$APP" --apply
cd "$APP"
if [ -f wsgi.py ]; then
  "$PY" -c 'from wsgi import application; assert application is not None; print("WSGI import OK")'
  touch wsgi.py
else
  "$PY" -c 'import app; print("app import OK")'
fi
echo "Toegepast. Terugdraaien: bash $KIT/rollback.sh $BACKUP"
