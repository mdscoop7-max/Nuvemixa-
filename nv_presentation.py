"""Server-rendered NL/EN, consistent metadata and nonce-backed script policy."""
import html
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from flask import g, request, session

ROOT=Path(__file__).parent
UI=json.loads((ROOT/'content/ui-translations.json').read_text(encoding='utf-8'))
PAIRS={UI['nl'][k]:v for k,v in UI['en'].items() if k in UI['nl']}
if (ROOT/'content/legacy-ui-translations.json').exists():PAIRS.update(json.loads((ROOT/'content/legacy-ui-translations.json').read_text(encoding='utf-8')))
PAIRS.update({
 'Mijn account':'My account','Je winkelwagen':'Your cart','Overzicht':'Summary','Herhaal wachtwoord':'Repeat password',
 'Geen producten gevonden':'No products found','Bekijk de producten die overeenkomen met je zoekopdracht.':'View products matching your search.',
 'We konden geen producten vinden die bij je zoekopdracht passen. Probeer een andere zoekterm of bekijk alle producten.':'We could not find matching products. Try another search or view all products.',
 'Nog geen actuele aanbiedingen':'No verified deals yet','Er zijn op dit moment geen bevestigde aanbiedingen. We tonen pas kortingen zodra de actieprijzen gecontroleerd zijn.':'There are currently no verified deals. Discounts are displayed only after promotional prices are checked.',
 'Bekijk onze actuele aanbiedingen.':'View our current offers.','Ontdek onze producten':'Discover our products',
 'NUVEMIXA · Slimme gadgets en meer':'NUVEMIXA · Smart gadgets and more',
 'In favorieten':'Saved to favourites','Bewaar als favoriet':'Save to favourites','Voorbeeldproduct':'Demonstration product',
 'Klantenservice':'Customer service','Aanbiedingen':'Deals','Alle producten →':'All products →','Bekijk alle producten →':'View all products →',
 'Menu openen':'Open menu','Sluiten':'Close','Favorieten':'Favourites','Winkelwagen':'Cart','Zoeken':'Search',
 'Slimme gadgets en meer':'Smart gadgets and more','Bestellen binnenkort mogelijk':'Ordering available soon',
 'Levering volgens productinformatie':'Delivery as shown with product','Retourinformatie':'Returns information',
 'Nog geen beoordelingen':'No ratings yet','Veelgestelde vragen':'Frequently asked questions',
 '← Terug naar NUVEMIXA':'← Back to NUVEMIXA','← Terug naar de collectie':'← Back to collection',
 'Onze collecties':'Our collections','Bekijk producten':'View products','Alle categorieën →':'All categories →',
})
def translated(text):
    lead=text[:len(text)-len(text.lstrip())];trail=text[len(text.rstrip()):]
    value=text.strip()
    if value in PAIRS:return lead+PAIRS[value]+trail
    if value.startswith('Zoekresultaten voor '):return lead+value.replace('Zoekresultaten voor ','Search results for ',1)+trail
    return text

class Translate(HTMLParser):
    def __init__(self,language):super().__init__(convert_charrefs=False);self.lang=language;self.out=[];self.stack=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);out=dict(a);parent_skip=any(x.get('skip') for x in self.stack);replacement=None
        if tag=='html':out['lang']=self.lang
        for prefix in ['data-tm-','data-tm-product-','data-tm-info-']:
            if prefix+self.lang in a:replacement=a[prefix+self.lang];break
        if a.get('data-i18n') in UI[self.lang]:replacement=UI[self.lang][a['data-i18n']]
        if tag=='img' and replacement is not None:out['alt']=replacement;replacement=None
        if a.get('data-i18n-placeholder') in UI[self.lang]:out['placeholder']=UI[self.lang][a['data-i18n-placeholder']]
        if self.lang=='en':
            for key in ['alt','title','aria-label','placeholder','content']:
                if key in out:out[key]=translated(out[key] or '')
        if tag=='meta' and a.get('property')=='og:image' and str(out.get('content','')).startswith('/'):
            out['content']=site()+out['content']
        # No inline event attributes; equivalent progressive fallbacks live in platform.js.
        out={k:v for k,v in out.items() if not k.lower().startswith('on')}
        if not parent_skip:self.out.append('<'+tag+''.join(' '+k+('="'+html.escape(v,quote=True)+'"' if v is not None else '') for k,v in out.items())+'>')
        if tag in ['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']:return
        item={'tag':tag,'skip':parent_skip or replacement is not None,'raw':tag in ['script','style']}
        self.stack.append(item)
        if replacement is not None and not parent_skip:
            safe=html.escape(replacement)
            safe=re.sub(r'&lt;(/?(?:em|strong|br)\s*/?)&gt;',r'<\1>',safe)
            self.out.append(safe)
    def handle_startendtag(self,tag,attrs):
        before=len(self.stack);count=len(self.out);self.handle_starttag(tag,attrs)
        if len(self.stack)>before:self.stack.pop()
        if len(self.out)>count and self.out[-1].endswith('>'):self.out[-1]=self.out[-1][:-1]+'/>'
    def handle_endtag(self,tag):
        index=next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i]['tag']==tag),None)
        if index is None:return
        parent_skip=any(x['skip'] for x in self.stack[:index]);self.stack=self.stack[:index]
        if not parent_skip:self.out.append('</'+tag+'>')
    def handle_data(self,data):
        if any(x['skip'] for x in self.stack):return
        if self.stack and self.stack[-1]['raw']:self.out.append(data)
        else:self.out.append(html.escape(translated(data) if self.lang=='en' else data,quote=False))
    def handle_entityref(self,name):
        if not any(x['skip'] for x in self.stack):self.out.append('&'+name+';')
    def handle_charref(self,name):
        if not any(x['skip'] for x in self.stack):self.out.append('&#'+name+';')
    def handle_decl(self,decl):self.out.append('<!'+decl+'>')
    def handle_comment(self,data):self.out.append('<!--'+data+'-->')

def site():
    value=os.getenv('SITE_URL','').rstrip('/')
    if value and not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?',value):raise RuntimeError('SITE_URL must be an HTTPS origin')
    return value or request.host_url.rstrip('/')

def register(app):
    @app.after_request
    def present(response):
        language=getattr(g,'nv_language','nl');nonce=getattr(g,'nv_nonce','')
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer' if 'token=' in request.query_string.decode(errors='ignore') else 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'; manifest-src 'self'; worker-src 'self'"
        if request.path.startswith(('/account','/orders','/admin','/payments','/herroep','/review-purchase')) or request.path in ['/winkelwagen','/wishlist','/afrekenen','/contact','/control','/dashboard','/catalogus-overzicht']:
            response.headers['Cache-Control']='private, no-store'
            response.headers['X-Robots-Tag']='noindex, nofollow, noarchive'
        if request.args.get('lang') in ['nl','en']:response.set_cookie('nv_language',language,max_age=31536000,secure=app.config['SESSION_COOKIE_SECURE'],httponly=True,samesite='Lax')
        if response.mimetype=='text/html' and not response.direct_passthrough:
            response.headers.setdefault('Cache-Control','private, no-cache')
            data=response.get_data(as_text=True)
            parser=Translate(language);parser.feed(data);data=''.join(parser.out)
            data=data.replace('https://nuvemixa.alwaysdata.net',site())
            metadata=getattr(g,'nv_product_meta',None)
            if metadata:
                data=re.sub(r'<title>.*?</title>',lambda m:'<title>'+html.escape(metadata['title'])+'</title>',data,flags=re.S)
                for key,value in [('description',metadata['description']),('og:title',metadata['title']),('og:description',metadata['description'])]:
                    data=re.sub(r'(<meta[^>]*(?:name|property)="'+re.escape(key)+r'"[^>]*content=")[^"]*',lambda m:m[1]+html.escape(value,quote=True),data)
            # All templates share one canonical origin; query search pages are not indexed.
            canonical=site()+request.path+('?lang=en' if language=='en' else '')
            data=re.sub(r'(<link[^>]+rel="canonical"[^>]+href=")[^"]*',lambda m:m[1]+html.escape(canonical,quote=True),data)
            if request.args.get('q'):response.headers['X-Robots-Tag']='noindex, follow'
            # Public demo data must not be announced as a real commercial offer.
            if '"@type": "Product"' in data or '"@type":"Product"' in data:
                if 'provisional' in data or 'voorlopig' in data:
                    def no_demo_offer(match):
                        try:
                            item=json.loads(match[1])
                            if isinstance(item,dict) and item.get('@type')=='Product':item.pop('offers',None)
                            return '<script type="application/ld+json">'+json.dumps(item,ensure_ascii=False).replace('<','\\u003c')+'</script>'
                        except ValueError:return match[0]
                    data=re.sub(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',no_demo_offer,data,flags=re.S)
            response.set_data(data);response.headers['Content-Language']=language
            response.headers['Vary']='Cookie'
        return response
