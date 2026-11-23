"""Isolated local acceptance server. External I/O fails closed."""
import os,sys,secrets,socket,smtplib,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if ROOT.name!='NUVEMIXA-LOKALE-TEST':raise SystemExit('Run this launcher in NUVEMIXA-LOKALE-TEST only')
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.repair-deps'))
for key in list(os.environ):
    if any(word in key.upper() for word in ['API_KEY','SMTP','WOOCOMMERCE','LIVE_ORDERS','DATABASE_URL','ADMIN_PASSWORD','SSO_SECRET','CONTACT_TO','RESEND']):os.environ.pop(key,None)
state=ROOT/'.repair-state';state.mkdir(exist_ok=True)
os.environ.update(NUVEMIXA_ENV='local',SECRET_KEY='local-isolated-test-session-only-not-production',NUVEMIXA_COOKIE_SECURE='false',NUVEMIXA_SESSION_COOKIE='nv_repair_test',NUVEMIXA_STORE_DB=str(state/'commerce.sqlite3'),NUVEMIXA_CUSTOMER_DB=str(state/'customers.sqlite3'),NUVEMIXA_REVIEWS_DB=str(state/'reviews.sqlite3'),NUVEMIXA_SSO_USED_DB=str(state/'sso.sqlite3'),NUVEMIXA_ADMIN_DB=str(state/'commerce.sqlite3'))
def denied(*a,**kw):raise urllib.error.URLError('External I/O disabled in local acceptance server')
urllib.request.urlopen=denied;smtplib.SMTP=denied;socket.create_connection=denied
from app import app
# Explicit local diagnostic only: exercise phone classification and rotation in
# a browser tool without touch-emulation support. Never copied into production
# request handling. This mocks screen/touch API values, not a physical device.
from flask import request,g
import re
@app.after_request
def local_phone_diagnostic(response):
    value=request.args.get('local_phone','')
    match=re.fullmatch(r'(3[2-9][0-9]|[4-5][0-9]{2})x([6-9][0-9]{2}|1[0-3][0-9]{2})',value)
    if match and response.mimetype=='text/html' and not response.direct_passthrough:
        width,height=map(int,match.groups())
        script=(f'<script nonce="{g.nv_nonce}">'
                f'Object.defineProperty(screen,"width",{{get:()=>{width}}});'
                f'Object.defineProperty(screen,"height",{{get:()=>{height}}});'
                'Object.defineProperty(navigator,"maxTouchPoints",{get:()=>5});'
                '</script>')
        response.set_data(response.get_data(as_text=True).replace('<head>','<head>'+script,1))
        response.headers['X-NUVEMIXA-Test-Device']='mocked screen/touch; not physical-device acceptance'
    if request.args.get('local_speed')=='1' and response.mimetype=='text/html' and not response.direct_passthrough:
        script=f'<script nonce="{g.nv_nonce}" src="/__local-speed-probe.js"></script>'
        response.set_data(response.get_data(as_text=True).replace('<head>','<head>'+script,1))
    return response
@app.get('/__local-speed-probe.js')
def local_speed_probe():
    from flask import Response
    return Response((ROOT/'tools/speed_probe.js').read_text(encoding='utf-8'),mimetype='text/javascript',headers={'Cache-Control':'no-store'})
if '--demo-admin' in sys.argv:
    from werkzeug.security import generate_password_hash
    password=secrets.token_urlsafe(24)
    os.environ['NUVEMIXA_ADMIN_PASSWORD_HASH']=generate_password_hash(password)
    (state/'local-admin.txt').write_text(password,encoding='utf-8')
    print('Temporary local admin password saved in .repair-state/local-admin.txt (never deploy)')
app.run(host='127.0.0.1',port=5001,debug=False,use_reloader=False)
