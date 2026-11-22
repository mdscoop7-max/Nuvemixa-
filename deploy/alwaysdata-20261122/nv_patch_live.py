#!/usr/bin/env python3
"""NUVEMIXA live-patch 22-11-2026 voor Alwaysdata.

Past ALLEEN gerichte, controleerbare wijzigingen toe op de live app-map.
Standaard is dit een droge run: er wordt niets gewijzigd.

  python3 nv_patch_live.py --app /home/nuvemixa/www/nuvemixa            # droge run
  python3 nv_patch_live.py --app /home/nuvemixa/www/nuvemixa --apply    # uitvoeren

Wat het doet (elke stap wordt overgeslagen en gemeld als het patroon niet exact gevonden wordt):
  1. static/nv-polish-20261122.css en .js plaatsen (correctielaag header/hero/zoekbalk/reviews)
  2. In elke publieke template: <link> vóór </head> en <script> vóór </body>
  3. Home & Living: <h2> -> <h1> in templates/category.html (RankFix: ontbrekende H1)
  4. Product-JSON-LD: geen "offers": null / "brand": null meer (templates/product.html)
  5. Alleen RAPPORT (geen wijziging): /over-trendmix-canonical in app.py

Elke gewijzigde template wordt vóór het wegschrijven met Jinja2 geparsed. Faalt dat, dan
wordt er niets geschreven. Maak altijd eerst de back-up met apply.sh (doet dat automatisch).
"""
import argparse
import os
import re
import shutil
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
CSS = "nv-polish-20261122.css"
JS = "nv-polish-20261122.js"
VER = "20261122a"
LINK = f'<link rel="stylesheet" href="/static/{CSS}?v={VER}">'
SCRIPT = f'<script defer src="/static/{JS}?v={VER}"></script>'
PRE_STEP3 = {}
SKIP = re.compile(r"^(_|admin|dashboard|control|nv_|order_success)")

NEW_PRODUCT_LD = '''  {% set nv_offer = {
      "@type":"Offer",
      "url":request.url_root.rstrip("/") ~ product.product_url,
      "price":"%.2f"|format(product.price),
      "priceCurrency":"EUR",
      "itemCondition":"https://schema.org/NewCondition"
  } %}
  {% if product.stock_status == "in_stock" %}{% set nv_tmp = nv_offer.update({"availability":"https://schema.org/InStock"}) %}
  {% elif product.stock_status == "out_of_stock" %}{% set nv_tmp = nv_offer.update({"availability":"https://schema.org/OutOfStock"}) %}{% endif %}
  {% set nv_images = [] %}{% for nv_im in (product.images or []) %}{% set nv_tmp = nv_images.append((request.url_root.rstrip("/") ~ nv_im) if nv_im.startswith("/") else nv_im) %}{% endfor %}
  {% set nv_schema = {
    "@context":"https://schema.org",
    "@type":"Product",
    "name":product.name,
    "description":product.description,
    "category":category_name,
    "image":nv_images,
    "sku":product.id
  } %}
  {% if product.brand %}{% set nv_tmp = nv_schema.update({"brand":{"@type":"Brand","name":product.brand}}) %}{% endif %}
  {% if product.price and product.price > 0 %}{% set nv_tmp = nv_schema.update({"offers":nv_offer}) %}{% endif %}
  <script type="application/ld+json">
  {{ nv_schema|tojson }}
  </script>'''

PRODUCT_LD_RE = re.compile(
    r'[ \t]*<script type="application/ld\+json">\s*\{\{\s*\{\s*"@context"\s*:\s*"https://schema\.org"\s*,\s*"@type"\s*:\s*"Product".*?</script>',
    re.S,
)
HL_H2_RE = re.compile(
    r"\{%\s*if category_slug == 'home-living'\s*%\}<h2>(\{\{ products\|length \}\} producten in \{\{ category_name \}\})</h2>\{%\s*else\s*%\}<h1>\1</h1>\{%\s*endif\s*%\}"
)


def jinja_ok(text, name):
    try:
        import jinja2
    except ImportError:
        print(f"  ! jinja2 niet beschikbaar; kan {name} niet valideren -> overgeslagen")
        return False
    try:
        jinja2.Environment(extensions=["jinja2.ext.do"]).parse(text)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Jinja-fout in {name}: {exc} -> NIET geschreven")
        return False


CHECK = r'''
import json, re, sys
from app import app, load_all_products
c = app.test_client()
out = {}
for path in ("/", "/gadgets", "/home-living", "/shop", "/winkelwagen"):
    r = c.get(path, follow_redirects=True)
    h = r.get_data(as_text=True)
    out[path] = {"status": r.status_code, "h1": h.lower().count("<h1"), "polish": "nv-polish-20261122" in h}
p = load_all_products()[0]
h = c.get(p["product_url"]).get_data(as_text=True)
out["product"] = {"offers_null": bool(re.search(r'"offers":\s*null', h)), "polish": "nv-polish-20261122" in h}
print(json.dumps(out))
'''


def verify(app, cpath, originals):
    """Render de belangrijkste pagina's lokaal (Flask test client, geen netwerk)."""
    import json
    import subprocess

    def run():
        res = subprocess.run([sys.executable, "-c", CHECK], cwd=app, capture_output=True, text=True, timeout=180)
        if res.returncode != 0:
            print("  ! Controle kon niet draaien:\n" + res.stderr[-1500:])
            return None
        return json.loads(res.stdout.strip().splitlines()[-1])

    out = run()
    if out is None:
        return
    if cpath in PRE_STEP3 and out["/home-living"]["h1"] != 1:
        with open(cpath, "w", encoding="utf-8") as fh:
            fh.write(PRE_STEP3[cpath])
        print(f"  ! /home-living had {out['/home-living']['h1']} H1's na stap 3 -> category.html teruggezet")
        out = run() or out
    print("Controle na toepassen:", json.dumps(out, ensure_ascii=False))
    bad = [k for k, v in out.items() if v.get("status", 200) != 200 or v.get("offers_null")]
    print("RESULTAAT:", "OK" if not bad else f"AANDACHT: {bad}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    app = os.path.abspath(a.app)
    tdir = os.path.join(app, "templates")
    sdir = os.path.join(app, "static")
    if not (os.path.isfile(os.path.join(app, "app.py")) and os.path.isdir(tdir) and os.path.isdir(sdir)):
        sys.exit(f"STOP: {app} lijkt geen NUVEMIXA-app-map (app.py/templates/static ontbreekt)")
    mode = "UITVOEREN" if a.apply else "DROGE RUN (niets wordt gewijzigd)"
    print(f"NUVEMIXA live-patch 20261122 — {mode}\nApp-map: {app}\n")
    changes = {}

    # 1) statische bestanden
    for fn in (CSS, JS):
        src = os.path.join(KIT, "static", fn)
        dst = os.path.join(sdir, fn)
        same = os.path.exists(dst) and open(src, "rb").read() == open(dst, "rb").read()
        print(f"[1] static/{fn}: {'al aanwezig' if same else 'plaatsen'}")
        if not same and a.apply:
            shutil.copy2(src, dst)

    # 2) laden in publieke templates
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".html") or SKIP.match(fn):
            continue
        path = os.path.join(tdir, fn)
        text = changes.get(path) or open(path, encoding="utf-8").read()
        if CSS in text or "</head>" not in text or "</body>" not in text:
            continue
        text = text.replace("</head>", LINK + "\n</head>", 1)
        idx = text.rfind("</body>")
        text = text[:idx] + SCRIPT + "\n" + text[idx:]
        changes[path] = text
        print(f"[2] templates/{fn}: correctielaag koppelen")

    # 3) Home & Living H1
    cpath = os.path.join(tdir, "category.html")
    if os.path.exists(cpath):
        text = changes.get(cpath) or open(cpath, encoding="utf-8").read()
        new, n = HL_H2_RE.subn(r"<h1>\1</h1>", text)
        if n:
            PRE_STEP3[cpath] = text  # versie mét correctielaag, zonder H1-wijziging
            changes[cpath] = new
            print("[3] templates/category.html: Home & Living krijgt <h1>")
        else:
            print("[3] templates/category.html: patroon niet gevonden -> overgeslagen (controleer handmatig)")

    # 4) Product JSON-LD
    ppath = os.path.join(tdir, "product.html")
    if os.path.exists(ppath):
        text = changes.get(ppath) or open(ppath, encoding="utf-8").read()
        m = PRODUCT_LD_RE.search(text)
        if "nv_schema" in text:
            print("[4] templates/product.html: al aangepast")
        elif m and '"offers"' in m.group(0):
            changes[ppath] = text[: m.start()] + NEW_PRODUCT_LD + text[m.end():]
            print("[4] templates/product.html: Product-JSON-LD zonder null-waarden")
        else:
            print("[4] templates/product.html: patroon niet gevonden -> overgeslagen (controleer handmatig)")

    # 5) alleen rapport
    src = open(os.path.join(app, "app.py"), encoding="utf-8").read()
    if re.search(r'@app\.route\("/over-trendmix"\)\s*\ndef \w+\(\):\s*\n\s*return redirect', src):
        print("[5] app.py: /over-trendmix stuurt al 301 door -> in orde")
    else:
        print("[5] app.py: /over-trendmix geeft geen 301 -> HANDMATIG: neem de routes uit GitHub main over "
              "(@app.route('/over-trendmix') -> redirect(url_for('over_nuvemixa'), code=301))")

    # valideren en schrijven
    print()
    bad = [p for p, t in changes.items() if not jinja_ok(t, os.path.relpath(p, app))]
    if bad:
        sys.exit("STOP: niets geschreven vanwege Jinja-fouten.")
    if a.apply:
        originals = {p: open(p, encoding="utf-8").read() for p in changes}
        for p, t in changes.items():
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(t)
        print(f"Klaar: {len(changes)} template(s) bijgewerkt.")
        verify(app, cpath, originals)
    else:
        print(f"Droge run OK: {len(changes)} template(s) zouden worden bijgewerkt. Voer uit met --apply.")


if __name__ == "__main__":
    main()
