#!/usr/bin/env bash
# NUVEMIXA herstel 2 — back-up + droge run (standaard) of uitvoeren (--apply).
set -euo pipefail
APP="${NUVEMIXA_APP:-/home/nuvemixa/www/nuvemixa}"
KIT="$(cd "$(dirname "$0")" && pwd)"
BK="${NUVEMIXA_BACKUPS:-$HOME/backups}"
PY="$APP/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p "$BK"
BACKUP="$BK/nuvemixa-pre-fix2-$(date -u +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$BACKUP" -C "$APP" app.py templates static/languages.js
tar -tzf "$BACKUP" >/dev/null
echo "Back-up gecontroleerd: $BACKUP"
echo "$BACKUP" > "$KIT/LAATSTE_BACKUP_FIX2.txt"
"$PY" "$KIT/nv_fix2.py" --app "$APP" ${1:-}
echo "Terugdraaien indien nodig: tar -xzf $BACKUP -C $APP  (daarna site herstarten)"
