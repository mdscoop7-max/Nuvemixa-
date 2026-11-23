import os,sys,socket,smtplib,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if ROOT.name!='NUVEMIXA-LOKALE-TEST':raise SystemExit('Run acceptance tests only in the isolated local-test tree')
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.repair-deps'))
state=ROOT/'.repair-state-tests';state.mkdir(exist_ok=True)
for key in list(os.environ):
    if any(word in key.upper() for word in ['API_KEY','SMTP','WOOCOMMERCE','LIVE_ORDERS','DATABASE_URL','ADMIN_PASSWORD','SSO_SECRET','RESEND']):os.environ.pop(key,None)
os.environ.update(SECRET_KEY='isolated-acceptance-key',NUVEMIXA_COOKIE_SECURE='false',NUVEMIXA_ENV='local',NUVEMIXA_STORE_DB=str(state/'store.sqlite3'),NUVEMIXA_CUSTOMER_DB=str(state/'customers.sqlite3'),NUVEMIXA_REVIEWS_DB=str(state/'reviews.sqlite3'),NUVEMIXA_SSO_USED_DB=str(state/'sso.sqlite3'),NUVEMIXA_ADMIN_DB=str(state/'store.sqlite3'),TEMP=str(state),TMP=str(state))
def denied(*a,**kw):raise urllib.error.URLError('External I/O forbidden in acceptance tests')
urllib.request.urlopen=denied;smtplib.SMTP=denied;socket.create_connection=denied
import pytest
import json,importlib.metadata
class Evidence:
    def __init__(self):self.tests=[]
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:self.tests.append({'test':report.nodeid,'stage':report.when,'outcome':report.outcome,'detail':str(report.longrepr)[-1600:] if report.failed else ''})
evidence=Evidence()
code=pytest.main([*(sys.argv[1:] or ['tests/test_local_platform.py']),'-q','-p','no:cacheprovider','--tb=short'],plugins=[evidence])
out=ROOT/'docs/eindcontrole-20261123';out.mkdir(parents=True,exist_ok=True)
(out/'pytest-results.json').write_text(json.dumps({'exit_code':int(code),'tests':evidence.tests,'versions':{p:importlib.metadata.version(p) for p in ['Flask','Werkzeug','pytest']},'external_io':'blocked'},ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(code)
