import hashlib,importlib.metadata,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent
deps=Path(r'C:\Users\user\NUVEMIXA-LOKALE-TEST\.repair-deps');sys.path.insert(0,str(deps))
versions={p:importlib.metadata.version(p) for p in ['Flask','Werkzeug','Jinja2','MarkupSafe','itsdangerous','click','blinker','gunicorn']}
(R/'requirements.lock').write_text('\n'.join(name+'=='+version for name,version in versions.items())+'\n',encoding='utf-8')
fingerprint=hashlib.sha256((R/'static/nv-platform.css').read_bytes()+(R/'static/nv-platform.js').read_bytes()).hexdigest()[:12]
head=R/'templates/_nv_platform_head.html';text=head.read_text(encoding='utf-8')
import re
head.write_text(re.sub(r'v=20261123[^"\s]*','v=20261123-'+fingerprint,text),encoding='utf-8')
(R/'docs/runtime-versions.json').write_text(json.dumps({'tested_runtime':versions,'source':'isolated PyPI wheels for Flask/Werkzeug; existing compatible installed transitive packages','asset_version':fingerprint},indent=2),encoding='utf-8')
print(json.dumps(versions))
