import re, sys
COPY = '''<div class="tm-desktop-hero-copy">
{% set hc = {
 'gadgets': ('GADGETS','GADGETS','Unieke gadgets voor een slimmer leven','Unique gadgets for smarter living','Bijzondere gadgets die je dagelijks leven makkelijker en leuker maken.','Practical gadgets that make everyday life easier and more fun.','Bekijk gadgets →','Explore gadgets →'),
 'smart-home': ('SMART HOME','SMART HOME','Een slimmer thuis, elke dag','A smarter home, every day','Slimme oplossingen voor meer comfort, veiligheid en sfeer in huis.','Smart solutions for more comfort, safety and atmosphere at home.','Bekijk Smart Home →','Explore Smart Home →'),
 'beauty-care': ('BEAUTY & CARE','BEAUTY & CARE','Verzorging die bij jou past','Care that suits you','Ontdek hoogwaardige beautytools en verzorgingsproducten voor elke dag.','Discover quality beauty tools and care products for every day.','Bekijk Beauty & Care →','Explore Beauty & Care →'),
 'home-living': ('HOME & LIVING','HOME & LIVING','Sfeervol wonen, elke dag','Cosy living, every day','Ontdek stijlvolle en praktische producten voor een fijn thuis.','Discover stylish and practical products for a lovely home.','Bekijk Home & Living →','Explore Home & Living →'),
 'lifestyle-sport': ('LIFESTYLE & SPORT','LIFESTYLE & SPORT','De perfecte uitrusting voor een actieve levensstijl','The perfect gear for an active lifestyle','Sport- en lifestyleaccessoires voor meer energie en comfort.','Sports and lifestyle accessories for more energy and comfort.','Bekijk Lifestyle & Sport →','Explore Lifestyle & Sport →')
} %}{% set h = hc.get(category_slug, hc['lifestyle-sport']) %}
<span class="tm-desktop-brand">NUVEMIXA</span>
<span class="tm-desktop-tag" data-tm-tr data-tm-nl="{{ h[0] }}" data-tm-en="{{ h[1] }}">{{ h[0] }}</span>
<h2 data-tm-tr data-tm-nl="{{ h[2] }}" data-tm-en="{{ h[3] }}">{{ h[2] }}</h2>
<p data-tm-tr data-tm-nl="{{ h[4] }}" data-tm-en="{{ h[5] }}">{{ h[4] }}</p>
<span class="tm-desktop-cta" data-tm-tr data-tm-nl="{{ h[6] }}" data-tm-en="{{ h[7] }}">{{ h[6] }}</span>
</div></a></section>'''
p = 'templates/category.html'; s = open(p, encoding='utf-8').read()
s2, n = re.subn(r'<div class="tm-desktop-hero-copy"[^>]*>.*?</div></a></section>', lambda m: COPY, s, count=1, flags=re.S)
print('category.html hero vervangen:', n)
if n: open(p, 'w', encoding='utf-8').write(s2)
def attrs(path, pairs):
    try: s = open(path, encoding='utf-8').read()
    except FileNotFoundError: print(path, 'ontbreekt'); return
    for old, new in pairs:
        if old in s: s = s.replace(old, new, 1); print(path, 'OK:', old[:40])
        else: print(path, 'NIET GEVONDEN:', old[:50])
    open(path, 'w', encoding='utf-8').write(s)
T = lambda tag, cls, nl, en, extra='': (f'<{tag}{cls}{extra}>{nl}</', f'<{tag}{cls}{extra} data-tm-tr data-tm-nl="{nl}" data-tm-en="{en}">{nl}</')
attrs('templates/offers.html', [
 T('span',' class="tm-desktop-tag"','AANBIEDINGEN','DEALS'),
 T('h2','','Scherpe deals voor jou','Great deals for you'),
 T('p','','Bekijk ons aanbod. We tonen kortingen zodra de actieprijzen gecontroleerd zijn.','Browse our range. Discounts are shown once sale prices have been checked.'),
 ('>Bekijk aanbiedingen →</a>', ' data-tm-tr data-tm-nl="Bekijk aanbiedingen →" data-tm-en="View deals →">Bekijk aanbiedingen →</a>'),
])
attrs('templates/shop.html', [
 T('span',' class="tm-desktop-tag"','ALLE PRODUCTEN','ALL PRODUCTS'),
 T('h2','','Ontdek de volledige collectie','Discover the full collection'),
 T('p','','Van slimme gadgets en wonen tot verzorging en sport.','From smart gadgets and living to care and sport.'),
 T('span',' class="tm-desktop-cta"','Bekijk alle producten →','View all products →'),
])
