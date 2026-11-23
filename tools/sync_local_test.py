"""Copy source/assets only. Never copy real customer databases or secret files."""
import hashlib,json,os,shutil
from pathlib import Path
SOURCE=Path(__file__).resolve().parent.parent
TARGET=Path(r'C:\Users\user\NUVEMIXA-LOKALE-TEST')
skip={'.git','.venv','.venv-windows','__pycache__','herstelpunten','instance','.repair-deps','.repair-tmp','.repair-state','.venv-afwerking'}
copied=[]
for parent,dirs,files in os.walk(SOURCE):
    dirs[:]=[d for d in dirs if d not in skip]
    for name in files:
        f=Path(parent)/name;rel=f.relative_to(SOURCE)
        if name.startswith('.env') or 'secret' in name.lower() or '.sqlite' in name or f.suffix in {'.db','.log','.bin'}:continue
        dest=TARGET/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest);copied.append(str(rel))
(TARGET/'source-sync.json').write_text(json.dumps({'files':copied,'databases_copied':False,'secrets_copied':False},indent=2),encoding='utf-8')
print('Source files copied:',len(copied),'— no secrets or customer databases')
