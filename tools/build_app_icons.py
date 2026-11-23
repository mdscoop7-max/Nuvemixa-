"""Package the owner-confirmed header logo as app icons; never redraw the mark."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parent.parent
source=ROOT/'static/nuvemixa-logo-test.png'
original=source.read_bytes();image=Image.open(source).convert('RGBA')
outputs=[]
for size in [180,192,512]:
    canvas=Image.new('RGBA',(size,size),'#063cbb')
    fitted=ImageOps.contain(image,(round(size*.9),round(size*.9)),Image.Resampling.LANCZOS)
    canvas.alpha_composite(fitted,((size-fitted.width)//2,(size-fitted.height)//2))
    name='nuvemixa-app-'+str(size)+'-20261123.png';canvas.convert('RGB').save(ROOT/'static'/name)
    outputs.append({'file':name,'size':size,'source':'nuvemixa-logo-test.png'})
assert source.read_bytes()==original
(ROOT/'docs/app-icon-source.json').write_text(json.dumps({'source':'static/nuvemixa-logo-test.png','sha256':hashlib.sha256(original).hexdigest(),'owner_confirmed':True,'method':'exact source pixels resized and centred; no redrawing','icons':outputs},indent=2),encoding='utf-8')
manifest=ROOT/'static/manifest.webmanifest';data=json.loads(manifest.read_text(encoding='utf-8'))
data['icons']=[{'src':'/static/nuvemixa-app-'+str(size)+'-20261123.png','sizes':str(size)+'x'+str(size),'type':'image/png','purpose':'any'} for size in [192,512]]
manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
head=ROOT/'templates/_nv_platform_head.html';head.write_text(head.read_text(encoding='utf-8').replace('sizes="192x192" href="/static/nuvemixa-icon-192.png"','sizes="180x180" href="/static/nuvemixa-app-180-20261123.png"'),encoding='utf-8')
print('App icons use the owner-confirmed header logo; source unchanged.')
