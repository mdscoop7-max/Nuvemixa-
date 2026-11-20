# NUVEMIXA 2026-11-20e: gerichte template-aanpassingen (idempotent). Uitvoeren vanuit de app-map.
import glob, os, re, sys
HEAD = open(sys.argv[1], encoding='utf-8').read()
SKIP = re.compile(r'(^|/)(admin|dashboard|control|nv_|_dashboard|_)')
n_head = 0
for p in sorted(glob.glob('templates/*.html')):
    name = os.path.basename(p)
    if SKIP.search(name) or name.endswith('.backup'):
        continue
    s = open(p, encoding='utf-8').read()
    if '</head>' not in s or 'NUVEMIXA 2026-11-20e head' in s:
        continue
    s = s.replace('</head>', HEAD.rstrip() + '\n</head>', 1)
    open(p, 'w', encoding='utf-8').write(s); n_head += 1
print('kop (head) toegevoegd aan', n_head, 'templates')

# Land vrij invullen bij afrekenen (EU-suggesties via datalist)
p = 'templates/checkout.html'
if os.path.exists(p):
    s = open(p, encoding='utf-8').read()
    m = re.search(r'<select\b([^>]*\bname="country"[^>]*)>.*?</select>', s, flags=re.S)
    if m:
        attrs = m.group(1)
        jinja = ' '.join(re.findall(r'\{\{.*?\}\}', attrs))
        idm = re.search(r'\bid="([^"]+)"', attrs)
        new = ('<input type="text" id="%s" name="country" list="nv-eu-landen" autocomplete="country-name" '
               'maxlength="100" minlength="2" required class="nv-country-input" '
               'placeholder="Bijv. Nederland" data-nv-ph-nl="Bijv. Nederland" '
               'data-nv-ph-en="E.g. Netherlands" '
               'value="{{ ((customer or {}).get(\'country\', \'\')) if customer is defined else \'\' }}"%s>'
               '<datalist id="nv-eu-landen"></datalist>') % ((idm.group(1) if idm else 'f-country'), (' ' + jinja) if jinja else '')
        s = s[:m.start()] + new + s[m.end():]
        s = re.sub(r'<small>(?:Definitief levergebied wordt vóór livegang bevestigd\.|The final delivery area will be confirmed before launch\.)</small>',
                   '<small data-nv-nl="We leveren alleen binnen de EU. Typ je land, bijvoorbeeld Nederland of België." '
                   'data-nv-en="We only deliver within the EU. Type your country, for example Netherlands or Belgium.">'
                   'We leveren alleen binnen de EU. Typ je land, bijvoorbeeld Nederland of België.</small>', s, count=1)
        open(p, 'w', encoding='utf-8').write(s)
        print('afrekenen: landkeuze vervangen door vrij invulveld')
    else:
        print('afrekenen: geen land-keuzelijst gevonden (al vrij veld of andere opbouw) - overgeslagen')

# Productfoto's in kaarten pas laden als ze in beeld komen
n_img = 0
for p in ('templates/_storefront_card.html', 'templates/_product_card.html'):
    if not os.path.exists(p):
        continue
    s = open(p, encoding='utf-8').read()
    s2, k = re.subn(r'<img\b(?![^>]*\bloading=)', '<img loading="lazy" decoding="async"', s)
    if k:
        open(p, 'w', encoding='utf-8').write(s2); n_img += k
print('lazy-loading toegevoegd aan', n_img, 'productfoto(s)')
