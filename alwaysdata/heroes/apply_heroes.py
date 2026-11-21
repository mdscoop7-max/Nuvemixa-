"""Past de hero-weergave en de nieuwe Home & Living-hero toe op de Alwaysdata-webshop.
Gebruik: .venv/bin/python apply_heroes.py <backupmap>  (vanuit /home/nuvemixa/www/nuvemixa)"""
import shutil
import sys
from pathlib import Path

backup = Path(sys.argv[1])
backup.mkdir(parents=True, exist_ok=True)
templates = [Path("templates/index.html"), Path("templates/category.html"), Path("templates/shop.html")]
for t in templates:
    shutil.copy2(t, backup / t.name)

LINK = '<link rel="stylesheet" href="/static/nv-hero-2026.css?v=20261121a">'
for t in templates:
    s = t.read_text(encoding="utf-8")
    if "nv-hero-2026.css" not in s:
        assert s.count("</head>") == 1, f"{t}: </head> niet uniek"
        s = s.replace("</head>", LINK + "\n</head>")
        t.write_text(s, encoding="utf-8")
    print(t, "link:", "nv-hero-2026.css" in t.read_text(encoding="utf-8"))

cat = Path("templates/category.html")
lines = cat.read_text(encoding="utf-8").split("\n")
prefix = "{% elif category_slug == 'home-living' %}"
idx = [i for i, l in enumerate(lines) if l.startswith(prefix)]
assert len(idx) == 1, f"home-living regel gevonden: {len(idx)}"
i = idx[0]
if 'nv-hl-new' not in lines[i]:
    assert 'class="nv-hl-hero"' in lines[i]
    lines[i] = (prefix + '<section class="tm-new-hero nv-hl-new" aria-label="Home &amp; Living">'
                '<a href="#producten" aria-label="Bekijk producten in Home &amp; Living" '
                'data-tm-label-nl="Bekijk producten in Home &amp; Living" data-tm-label-en="View products in Home &amp; Living">'
                '<img src="/static/images/hero/home-living-2026.jpg?v=20261121a" '
                'alt="NUVEMIXA Home &amp; Living: slimme oplossingen voor een praktisch thuis" '
                'width="1774" height="887" fetchpriority="high" decoding="async"></a></section>')
    cat.write_text("\n".join(lines), encoding="utf-8")
print("home-living hero:", "home-living-2026.jpg" in cat.read_text(encoding="utf-8"))
