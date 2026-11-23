"""Fetch two official PyPI wheels into the isolated test tree, without pip temp dirs.

The ordinary pip installer hit Windows temporary-file permission errors. Verify
PyPI's SHA-256 and extract only within .repair-deps; no global Python changes.
"""
import hashlib,json,urllib.request,zipfile
from pathlib import Path
TARGET=Path(r'C:\Users\user\NUVEMIXA-LOKALE-TEST\.repair-deps').resolve();TARGET.mkdir(exist_ok=True)
for name,version in [('Flask','3.1.3'),('Werkzeug','3.1.9')]:
    with urllib.request.urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=20) as response:info=json.load(response)
    wheel=next(x for x in info['urls'] if x['filename'].endswith('py3-none-any.whl'))
    with urllib.request.urlopen(wheel['url'],timeout=30) as response:raw=response.read()
    assert hashlib.sha256(raw).hexdigest()==wheel['digests']['sha256']
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            path=(TARGET/member.filename).resolve()
            if TARGET not in path.parents:raise ValueError('Wheel path outside isolated runtime')
            if member.is_dir():path.mkdir(parents=True,exist_ok=True)
            else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(member))
    print(name,version,'SHA-256 verified, isolated installation')
