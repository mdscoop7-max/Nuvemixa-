"""Read-only localhost crawl. No forms, accounts, external hosts or credentials."""
import json
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent.parent
if ROOT.name!='NUVEMIXA-LOKALE-TEST':raise SystemExit('Isolated test tree only')
ORIGIN='http://127.0.0.1:5001'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for key in ('href','src'):
            if a.get(key):self.links.append(a[key])
        if a.get('srcset'):
            self.links.extend(x.strip().split()[0] for x in a['srcset'].split(',') if x.strip())

pending=deque([ORIGIN+'/',ORIGIN+'/?lang=en']);seen=set();results=[];external=set();excluded=set()
while pending:
    url=pending.popleft()
    if url in seen:continue
    seen.add(url)
    if len(seen)>1800:raise SystemExit('Crawl unexpectedly large; inspect before expanding')
    try:
        response=urlopen(url,timeout=15);status=response.status;ctype=response.headers.get('Content-Type','');body=response.read()
    except HTTPError as exc:
        results.append({'url':url,'status':exc.code});continue
    results.append({'url':url,'status':status})
    if 'text/html' not in ctype:continue
    parser=Links();parser.feed(body.decode('utf-8'))
    for raw in parser.links:
        target=urldefrag(urljoin(url,raw))[0];part=urlsplit(target)
        if part.scheme not in ('http','https'):continue
        if part.netloc!=urlsplit(ORIGIN).netloc:external.add(part.netloc);continue
        if part.path.startswith(('/admin','/orders','/payments','/api/','/logout','/account/verify','/account/reset','/review-purchase')):
            excluded.add(part.path);continue
        if target not in seen:pending.append(target)
out=ROOT/'docs/eindcontrole-20261123';out.mkdir(parents=True,exist_ok=True)
report={'method':'GET only; public reachable internal href/src/srcset; no external requests, form submission or private URLs',
        'checked':len(results),'failures':[r for r in results if r['status']>=400],
        'external_hosts_not_requested':sorted(external),'private_paths_excluded':sorted(excluded),'results':results}
(out/'public-links.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False))
raise SystemExit(bool(report['failures']))
