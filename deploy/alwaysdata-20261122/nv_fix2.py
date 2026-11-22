#!/usr/bin/env python3
"""NUVEMIXA herstel 2 (22-11-2026) — voor de live Alwaysdata-map.

  python nv_fix2.py --app /home/nuvemixa/www/nuvemixa            # droge run
  python nv_fix2.py --app /home/nuvemixa/www/nuvemixa --apply    # uitvoeren

A) static/languages.js: tweede 'const commerceTranslations' (service-teksten) krijgt een
   eigen naam. Nu weigert de browser het hele bestand (SyntaxError), waardoor geen enkele
   vertaling uit dat bestand werkt.
B) Templates: versienummer van languages.js ophogen, zodat browsers (cache 7 dagen) direct
   de herstelde versie laden.
C) app.py: /over-trendmix -> 301 naar /over-nuvemixa, en canonical van /over-nuvemixa
   naar zichzelf. Toegevoegd als losse, zelfstandige hooks onderaan app.py.
D) Alleen RAPPORT: is de map dashboard-test ergens in gebruik?

Alles wordt eerst gecontroleerd (JS-syntaxis, Python-compilatie, testclient). Gaat iets
mis, dan worden de originele bestanden direct teruggezet.
"""
import argparse
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

NEW_VER = "20261122b"
POLISH_VER = "20261122c"
KIT = os.path.dirname(os.path.abspath(__file__))
HOOK_MARK = "# NUVEMIXA herstel 2 (22-11-2026)"
HOOK = '''

''' + HOOK_MARK + ''': /over-trendmix permanent naar /over-nuvemixa en juiste canonical.
from flask import redirect as _nv2_redirect, request as _nv2_request


@app.before_request
def _nv2_over_trendmix_redirect():
    if _nv2_request.path.rstrip("/") == "/over-trendmix":
        return _nv2_redirect("/over-nuvemixa", code=301)
    return None


@app.after_request
def _nv2_over_nuvemixa_canonical(response):
    try:
        if _nv2_request.path.rstrip("/") == "/over-nuvemixa" and response.mimetype == "text/html" and not response.direct_passthrough:
            body = response.get_data(as_text=True)
            fixed = re.sub(r'(<link rel="canonical" href="[^"]*?)/over-trendmix"', r'\\1/over-nuvemixa"', body)
            if fixed != body:
                response.set_data(fixed)
    except Exception:  # nooit de pagina breken
        pass
    return response
'''

CHECK = r'''
import json, re
from app import app
c = app.test_client()
out = {}
r = c.get("/over-trendmix")
out["over-trendmix"] = {"status": r.status_code, "location": r.headers.get("Location")}
r = c.get("/over-nuvemixa")
h = r.get_data(as_text=True)
m = re.search(r'rel="canonical" href="([^"]*)"', h)
out["over-nuvemixa"] = {"status": r.status_code, "canonical": m.group(1) if m else None}
for p in ("/", "/gadgets", "/home-living", "/shop", "/winkelwagen"):
    rr = c.get(p, follow_redirects=True)
    hh = rr.get_data(as_text=True)
    lm = re.search(r'languages\.js\?v=([\w-]+)', hh)
    pm = re.search(r'nv-polish-20261122\.css\?v=([\w-]+)', hh)
    out[p] = {"status": rr.status_code, "languages_v": lm.group(1) if lm else None, "polish_v": pm.group(1) if pm else None}
print(json.dumps(out))
'''


def js_ok(path):
    node = shutil.which("node") or shutil.which("nodejs")
    if node:
        r = subprocess.run([node, "--check", path], capture_output=True, text=True)
        return r.returncode == 0, ("node --check OK" if r.returncode == 0 else r.stderr.strip()[-300:])
    text = open(path, encoding="utf-8").read()
    names = re.findall(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=", text)
    dup = sorted({n for n in names if names.count(n) > 1})
    return (not dup), ("geen dubbele const-namen (node niet beschikbaar)" if not dup else f"dubbel: {dup}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    app = os.path.abspath(a.app)
    lang = os.path.join(app, "static", "languages.js")
    apppy = os.path.join(app, "app.py")
    tdir = os.path.join(app, "templates")
    for p in (lang, apppy, tdir):
        if not os.path.exists(p):
            sys.exit(f"STOP: {p} niet gevonden")
    print(f"NUVEMIXA herstel 2 — {'UITVOEREN' if a.apply else 'DROGE RUN (niets wordt gewijzigd)'}\nApp-map: {app}\n")
    new = {}

    # A) languages.js
    js = open(lang, encoding="utf-8").read()
    decls = [m.start() for m in re.finditer(r"\bconst\s+commerceTranslations\s*=", js)]
    if len(decls) >= 2:
        start = decls[1]
        end_m = re.compile(r"Object\.keys\(commerceTranslations\)[^\n]*\n").search(js, start)
        if not end_m:
            sys.exit("STOP: einde van het tweede blok niet gevonden")
        block = js[start:end_m.end()].replace("commerceTranslations", "commerceServiceTranslations")
        new[lang] = js[:start] + block + js[end_m.end():]
        print("[A] static/languages.js: tweede 'commerceTranslations' -> 'commerceServiceTranslations'")
    else:
        print(f"[A] static/languages.js: {len(decls)} declaratie(s) — niets te doen")

    # A2) namen die óók bovenaan in app.js staan (gedeelde globale scope in de browser)
    appjs_path = os.path.join(app, "static", "app.js")
    if os.path.exists(appjs_path):
        appjs = open(appjs_path, encoding="utf-8").read()
        top = lambda t: set(re.findall(r"^(?:const|let|class)\s+([A-Za-z_$][\w$]*)", t, re.M))
        cur = new.get(lang, js)
        for name in sorted(top(appjs) & top(cur)):
            cur = re.sub(r"(?<![\w$.])" + re.escape(name) + r"(?![\w$])", "nvLang_" + name, cur)
            print(f"[A] static/languages.js: '{name}' bestaat ook in app.js -> 'nvLang_{name}'")
        if cur != js:
            new[lang] = cur

    # B) versienummer in templates
    vre = re.compile(r"(filename=['\"]languages\.js['\"]\s*,\s*v=['\"])([\w-]+)(['\"])|(/static/languages\.js\?v=)([\w-]+)")
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".html"):
            continue
        p = os.path.join(tdir, fn)
        t = new.get(p) or open(p, encoding="utf-8").read()
        t2 = vre.sub(lambda m: (m.group(1) + NEW_VER + m.group(3)) if m.group(1) else (m.group(4) + NEW_VER), t)
        if t2 != t:
            new[p] = t2
            print(f"[B] templates/{fn}: languages.js-versie -> {NEW_VER}")

    # C) app.py hooks
    src = open(apppy, encoding="utf-8").read()
    if HOOK_MARK in src:
        print("[C] app.py: herstel-hooks al aanwezig")
    else:
        if not re.search(r"^\s*import re\b|^\s*import .*\bre\b", src, re.M):
            hook = HOOK.replace("from flask import", "import re\nfrom flask import", 1)
        else:
            hook = HOOK
        new[apppy] = src.rstrip("\n") + "\n" + hook
        print("[C] app.py: 301 /over-trendmix -> /over-nuvemixa en canonical-correctie toevoegen (onderaan)")

    # E) nieuwe correctielaag (compact reviewblok) + versienummer ophogen (cache 7 dagen)
    for fn in ("nv-polish-20261122.css", "nv-polish-20261122.js"):
        src_p = os.path.join(KIT, "static", fn)
        dst_p = os.path.join(app, "static", fn)
        if os.path.exists(src_p):
            src_t = open(src_p, encoding="utf-8").read()
            cur_t = open(dst_p, encoding="utf-8").read() if os.path.exists(dst_p) else ""
            if src_t != cur_t:
                new[dst_p] = src_t
                print(f"[E] static/{fn}: nieuwe versie (compact reviewblok)")
    pre = re.compile(r"(nv-polish-20261122\.(?:css|js)\?v=)([\w-]+)")
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".html"):
            continue
        p = os.path.join(tdir, fn)
        t = new.get(p) or open(p, encoding="utf-8").read()
        t2 = pre.sub(lambda m: m.group(1) + POLISH_VER, t)
        if t2 != t:
            new[p] = t2
            print(f"[E] templates/{fn}: correctielaag-versie -> {POLISH_VER}")

    # D) rapport dashboard-test
    used = []
    for fn in os.listdir(app):
        if fn.endswith((".py", ".wsgi")) and os.path.isfile(os.path.join(app, fn)):
            try:
                if "dashboard-test" in open(os.path.join(app, fn), encoding="utf-8", errors="ignore").read():
                    used.append(fn)
            except OSError:
                pass
    print(f"[D] dashboard-test: {'GEBRUIKT in ' + ', '.join(used) if used else 'niet genoemd in Python-code van de webshop'}")

    # validatie op tijdelijke kopieën
    with tempfile.TemporaryDirectory() as tmp:
        if lang in new:
            tp = os.path.join(tmp, "languages.js")
            combined = ""
            if os.path.exists(os.path.join(app, "static", "app.js")):
                combined = open(os.path.join(app, "static", "app.js"), encoding="utf-8").read() + "\n;\n"
            open(tp, "w", encoding="utf-8").write(combined + new[lang])
            ok, msg = js_ok(tp)
            msg = "app.js + languages.js samen: " + msg
            print(f"    JS-controle: {msg}")
            if not ok:
                sys.exit("STOP: languages.js niet geldig — niets geschreven")
        if apppy in new:
            tp = os.path.join(tmp, "app_check.py")
            open(tp, "w", encoding="utf-8").write(new[apppy])
            try:
                py_compile.compile(tp, doraise=True)
                print("    Python-controle app.py: OK")
            except py_compile.PyCompileError as exc:
                sys.exit(f"STOP: app.py compileert niet — niets geschreven\n{exc}")

    if not a.apply:
        print(f"\nDroge run OK: {len(new)} bestand(en) zouden worden aangepast. Uitvoeren met --apply.")
        return

    originals = {p: open(p, encoding="utf-8").read() for p in new}
    for p, t in new.items():
        open(p, "w", encoding="utf-8").write(t)
    print(f"\nGeschreven: {len(new)} bestand(en). Controle met testclient…")
    r = subprocess.run([sys.executable, "-c", CHECK], cwd=app, capture_output=True, text=True, timeout=180)
    ok = False
    if r.returncode == 0:
        out = json.loads(r.stdout.strip().splitlines()[-1])
        print("Controle:", json.dumps(out, ensure_ascii=False))
        pages_ok = all(out[p]["status"] == 200 for p in ("/", "/gadgets", "/home-living", "/shop", "/winkelwagen"))
        redirect_ok = out["over-trendmix"]["status"] == 301 and (out["over-trendmix"]["location"] or "").endswith("/over-nuvemixa")
        canon_ok = (out["over-nuvemixa"]["canonical"] or "").endswith("/over-nuvemixa")
        ok = pages_ok and redirect_ok and canon_ok
        print(f"  pagina's 200: {pages_ok} | 301: {redirect_ok} | canonical: {canon_ok}")
    else:
        print("Controle kon niet draaien:\n" + r.stderr[-1500:])
    if not ok:
        for p, t in originals.items():
            open(p, "w", encoding="utf-8").write(t)
        sys.exit("RESULTAAT: NIET OK — alle bestanden zijn teruggezet. Er is niets veranderd.")
    print("RESULTAAT: OK — herstart nu de site in het beheerpaneel (Web → Sites → Herstarten).")


if __name__ == "__main__":
    main()
