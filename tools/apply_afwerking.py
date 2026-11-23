"""One-time controlled source migration; no customer data or secrets are read."""
from pathlib import Path
import re, shutil, json
R=Path(__file__).resolve().parent.parent
p=R/'app.py';s=p.read_text(encoding='utf-8')
s=s.replace("app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32).hex()",'''def _persistent_session_secret():
    configured = os.getenv('SECRET_KEY')
    if configured:
        return configured
    if os.getenv('NUVEMIXA_ENV') == 'production':
        raise RuntimeError('SECRET_KEY must be configured in production')
    target = Path(os.getenv('NUVEMIXA_SECRET_FILE') or Path(__file__).resolve().parent / 'instance' / 'session.key')
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('x', encoding='ascii') as stream:
            stream.write(secrets.token_hex(48))
        os.chmod(target, 0o600)
    except FileExistsError:
        pass
    return target.read_text(encoding='ascii').strip()

app.config['SECRET_KEY'] = _persistent_session_secret()
app.config['SESSION_COOKIE_NAME'] = os.getenv('NUVEMIXA_SESSION_COOKIE', 'nuvemixa_session')''')
s=s.replace('BASE_DIR = Path(__file__).resolve().parent','''BASE_DIR = Path(__file__).resolve().parent
if os.getenv('NUVEMIXA_ENV') != 'production':
    os.environ.setdefault('NUVEMIXA_REVIEWS_DB', str(BASE_DIR / 'instance' / 'reviews.sqlite3'))
    Path(os.environ['NUVEMIXA_REVIEWS_DB']).parent.mkdir(parents=True, exist_ok=True)''',1)
s=s.replace('_CUSTOMER_DB = BASE_DIR / "nuvemixa_customers.sqlite3"','_CUSTOMER_DB = Path(os.getenv("NUVEMIXA_CUSTOMER_DB") or BASE_DIR / "nuvemixa_customers.sqlite3")')
s=s.replace('if __name__ == "__main__":\n    app.run(debug=False)\n','')
s=s.replace('os.path.join(os.path.dirname(os.path.abspath(__file__)), "nv_reviews_sso_used.sqlite3")','os.getenv("NUVEMIXA_SSO_USED_DB") or str(BASE_DIR / "instance" / "sso-used.sqlite3")')
s=s.replace('request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()','request.remote_addr or ""')
s=s.replace('if not admin_is_authenticated():\n        return redirect(url_for("admin_login"))\n    rows, error', 'if not (admin_is_authenticated() or session.get("nv_review_role") is True):\n        return redirect(url_for("admin_login"))\n    rows, error')
s=s.replace('if not admin_is_authenticated():\n        abort(403)\n    from nv_reviews import update_review','if not (admin_is_authenticated() or session.get("nv_review_role") is True):\n        abort(403)\n    from nv_reviews import update_review')
# Generic review moderation may not assert purchase verification without an order link.
s=s.replace('verified=request.form.get("verified") == "1")','verified=False)')
s=s.replace('float(product.get("price", 0) or 0)','product.get("price", 0)').replace('float(item.get("price", 0) or 0)','item.get("price", 0)')
s += '''

# Register every route/hook before any server starts (CLI, WSGI and direct startup).
from nv_platform import register as register_local_platform
register_local_platform(__import__(__name__))
from nv_presentation import register as register_presentation
register_presentation(app)

if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=False)
'''
p.write_text(s,encoding='utf-8')
p=R/'nv_reviews_sso.py';s=p.read_text(encoding='utf-8').replace('session["nv_admin"] = True','session["nv_review_role"] = True');p.write_text(s,encoding='utf-8')
p=R/'nv_reviews.py';s=p.read_text(encoding='utf-8').replace('with connect() as conn:\n        recent_email', 'with connect() as conn:\n        conn.execute("BEGIN IMMEDIATE")\n        recent_email');p.write_text(s,encoding='utf-8')
p=R/'nv_openai.py';s=p.read_text(encoding='utf-8').replace('            import nv_dashboard_postgres\n            if not nv_dashboard_postgres.runtime_enabled():\n                db.execute(SQLITE_TABLE)','            db.execute(SQLITE_TABLE)');p.write_text(s,encoding='utf-8')
# Templates are adjusted structurally; approved hero CSS and every hero asset stay unchanged.
for p in (R/'templates').glob('*.html'):
    if 'backup' in p.name:continue
    s=p.read_text(encoding='utf-8')
    s=re.sub(r'<script>\(function\(\)\{try\{var h=JSON.parse\(localStorage.getItem\(\'nv-hdr-20261120e\'.*?</script>','',s,flags=re.S)
    s=s.replace('<link rel="expect" href="#nv-ready-20261120e" blocking="render">','')
    # Original PNG must only preload for the mobile layout where it is visible.
    s=s.replace('<link rel="preload" as="image"','<link rel="preload" media="(max-width: 991px)" as="image"')
    s=s.replace('<head>','<head>{% include "_nv_platform_head.html" %}',1)
    s=re.sub(r'<script(?![^>]*nonce=)(?=[\s>])','<script nonce="{{ g.nv_nonce }}"',s)
    s=s.replace('Herhaal wachtwoord</span>','{{ nv_tr("Herhaal wachtwoord","Repeat password") }}</span>')
    p.write_text(s,encoding='utf-8')
p=R/'templates/_tm_category_nav.html';s=p.read_text(encoding='utf-8');s+='\n{% include "_nv_campaign_banner.html" %}\n';p.write_text(s,encoding='utf-8')
p=R/'templates/_header.html';s=p.read_text(encoding='utf-8');s+='\n{% include "_nv_campaign_banner.html" %}\n';p.write_text(s,encoding='utf-8')
p=R/'templates/_footer.html';s=p.read_text(encoding='utf-8');s+='\n<nav class="nv-platform-links" aria-label="NUVEMIXA service"><a href="/herroepen">{{ nv_tr("Overeenkomst herroepen","Withdraw from a contract") }}</a><a href="/herroepingsformulier">{{ nv_tr("Modelformulier","Model withdrawal form") }}</a>{% if session.get("nv_admin") %}<a href="/admin/commerce">{{ nv_tr("Lokaal beheer","Local administration") }}</a>{% endif %}</nav>\n';p.write_text(s,encoding='utf-8')
shutil.copyfile(Path(r'C:\Users\user\Downloads\NUVEMIXA Welkomstkorting Banner.png'),R/'static/nuvemixa-welkomst-referentie.png')
(R/'requirements.txt').write_text('Flask==3.1.3\nWerkzeug==3.1.9\ngunicorn==23.0.0\n',encoding='utf-8')
(R/'.gitignore').open('a',encoding='utf-8').write('\n# Private state and restoration points (never deploy)\nherstelpunten/\n*.sqlite3\n*.sqlite3-*\n.nv_reviews_sso_secret\n.repair-deps/\n.venv-afwerking/\n')
# Preserve the legacy text dictionary as data; disable competing whole-page walkers.
p=R/'static/nv-fix-20261120e.js';s=p.read_text(encoding='utf-8');match=re.search(r'var DICT = (\{.*?\});',s)
if match:(R/'content/legacy-ui-translations.json').write_text(json.dumps(json.loads(match[1])['nl2en'],ensure_ascii=False,indent=2),encoding='utf-8')
s=s.replace('function translate(root) {','function translate(root) { return; // Server-owned language; legacy layout helpers remain.\n')
s=s.replace('setTimeout(rememberHeader, 600);','/* Header colours come from CSS, never untrusted localStorage. */')
p.write_text(s,encoding='utf-8')
p=R/'static/app.js';s=p.read_text(encoding='utf-8').replace('function applyLanguage(lang){','function applyLanguage(lang){ return; // Server-owned NL/EN; storage key remains compatible.\n');p.write_text(s,encoding='utf-8')
(R/'static/languages.js').write_text('/* NL/EN are rendered by nv_presentation.py. Historical dictionaries are in the restoration point. */\n',encoding='utf-8')
p=R/'static/trendmix-ui-2026.js';s=p.read_text(encoding='utf-8').replace('      translateRemainingText();','      /* Full-page translation is server-owned. */');p.write_text(s,encoding='utf-8')
print('Source migration complete; hero source files preserved.')
