"""Local commerce authority. No provider, network or email side effects.

Money is integer EUR cents; dates are UTC unix seconds. SQLite transactions
serialize reservations. External dashboard adapters must use this service.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS nv_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nv_products(id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nv_suppliers(id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nv_campaigns(id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nv_customers(id INTEGER PRIMARY KEY,email TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,auth_version INTEGER NOT NULL DEFAULT 0,profile TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS nv_tokens(hash TEXT PRIMARY KEY,customer_id INTEGER NOT NULL,purpose TEXT NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0,version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS nv_favorites(customer_id INTEGER NOT NULL,product_id TEXT NOT NULL,PRIMARY KEY(customer_id,product_id));
CREATE TABLE IF NOT EXISTS nv_mail(id TEXT PRIMARY KEY,customer_id INTEGER,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,language TEXT NOT NULL,kind TEXT NOT NULL,dedupe TEXT NOT NULL UNIQUE,status TEXT NOT NULL DEFAULT 'test',created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS nv_coupons(hash TEXT PRIMARY KEY,customer_id INTEGER NOT NULL,campaign_id TEXT NOT NULL,source TEXT NOT NULL,expires INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'available',order_id TEXT,UNIQUE(customer_id,campaign_id,source));
CREATE TABLE IF NOT EXISTS nv_orders(id TEXT PRIMARY KEY,customer_id INTEGER,owner_hash TEXT NOT NULL,idempotency TEXT NOT NULL UNIQUE,mode TEXT NOT NULL CHECK(mode='simulation'),status TEXT NOT NULL,items TEXT NOT NULL,address TEXT NOT NULL,totals TEXT NOT NULL,coupon_hash TEXT,created INTEGER NOT NULL,expires INTEGER NOT NULL,refunded INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS nv_events(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,event TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS nv_refund_lines(event_id TEXT NOT NULL,order_id TEXT NOT NULL,product_id TEXT NOT NULL,amount_cents INTEGER NOT NULL,vat_cents INTEGER NOT NULL,PRIMARY KEY(event_id,product_id));
CREATE TABLE IF NOT EXISTS nv_review_invites(hash TEXT PRIMARY KEY,order_id TEXT NOT NULL UNIQUE,customer_id INTEGER NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS nv_purchase_reviews(id INTEGER PRIMARY KEY,order_id TEXT NOT NULL UNIQUE,customer_id INTEGER NOT NULL,rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),body TEXT NOT NULL,incentivized INTEGER NOT NULL,verified INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',reply TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS nv_withdrawals(id TEXT PRIMARY KEY,order_id TEXT NOT NULL UNIQUE,customer_id INTEGER,email TEXT NOT NULL,created INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'received');
CREATE TABLE IF NOT EXISTS nv_limits(bucket TEXT NOT NULL,at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS nv_limits_bucket ON nv_limits(bucket,at);
CREATE TABLE IF NOT EXISTS nv_audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,object_id TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ai_usage(period TEXT PRIMARY KEY,usd REAL NOT NULL DEFAULT 0,calls INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS nv_ai_reservations(id TEXT PRIMARY KEY,month TEXT NOT NULL,day TEXT NOT NULL,estimated_micros INTEGER NOT NULL,actual_micros INTEGER);
'''

def now(): return int(time.time())
def digest(value): return hashlib.sha256(str(value).encode()).hexdigest()
def public_link(path):
    import re
    origin=os.getenv('SITE_URL','').rstrip('/')
    return (origin if re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?',origin) else '')+path
def cents(value):
    value=Decimal(str(value))
    if not value.is_finite() or value<0: raise ValueError('invalid_money')
    return int((value*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def money(value): return Decimal(int(value))/100
def allocate(total,weights):
    """Largest-remainder cents allocation, bounded by each gross line amount."""
    denominator=sum(weights)
    if not 0<=total<=denominator:raise ValueError('invalid_allocation')
    if not denominator:return [0]*len(weights)
    cuts=[total*w//denominator for w in weights]
    remaining=total-sum(cuts)
    order=sorted(range(len(weights)),key=lambda i:(-(total*weights[i]%denominator),i))
    for i in order[:remaining]:cuts[i]+=1
    return cuts
def path():
    value=os.getenv('NUVEMIXA_STORE_DB','').strip()
    if not value: value=str(Path(__file__).parent/'instance'/'commerce.sqlite3')
    result=Path(value).resolve()
    if 'static' in result.parts: raise RuntimeError('Private database cannot be public')
    if os.getenv('NUVEMIXA_ENV')=='production' and Path(__file__).parent in result.parents:
        raise RuntimeError('Production database must be outside the checkout')
    return result

@contextmanager
def db(write=False):
    target=path();target.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(target,timeout=15,isolation_level=None);conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000');conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript(SCHEMA)
    try:
        conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally: conn.close()

def setting(key,default=None,conn=None):
    if conn is None:
        with db() as c:return setting(key,default,c)
    row=conn.execute('SELECT value FROM nv_settings WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else default
def configure(key,value):
    with db(True) as c:c.execute('INSERT INTO nv_settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))
def readiness():
    company=setting('company',{});shipping=setting('shipping',{'NL':None,'BE':None})
    missing=['company.'+k for k in ['legal_name','address','email','kvk','vat','return_address','privacy_contact'] if not company.get(k)]
    if company.get('legal_reviewed') is not True:missing.append('final_legal_review')
    if not shipping or any(v is None for v in shipping.values()):missing.append('verified_shipping_fees')
    real=[p for p in records('nv_products').values() if p.get('published') and not publication_errors(p)]
    if not real:missing.append('verified_real_catalogue')
    from nv_mail import enabled
    if not enabled():missing.append('accepted_external_email_configuration')
    # No environment flag can bypass a provider implementation and its separate acceptance.
    missing+=['payment_provider_sandbox_and_production_acceptance','operational_returns_and_refund_acceptance','physical_device_acceptance']
    return {'commercial_release':False,'mode':'simulation','missing':missing,'verified_real_products':len(real)}
def records(table):
    if table not in {'nv_products','nv_suppliers','nv_campaigns'}:raise ValueError('invalid_table')
    with db() as c:return {r['id']:json.loads(r['data']) for r in c.execute('SELECT * FROM '+table)}
def audit(c,action,object_id):c.execute('INSERT INTO nv_audit(actor,action,object_id,created) VALUES(?,?,?,?)',('admin',action,str(object_id),now()))
def save_record(table,id,data):
    if table not in {'nv_products','nv_suppliers','nv_campaigns'}:raise ValueError('invalid_table')
    with db(True) as c:
        c.execute('INSERT INTO '+table+' VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(str(id),json.dumps(data,ensure_ascii=False)))
        audit(c,table,str(id))
def campaign_valid(data):
    if not isinstance(data.get('active',False),bool):raise ValueError('invalid_campaign')
    if data.get('kind') not in {'welcome','review'} or data.get('percent') not in {15,20}:raise ValueError('invalid_campaign')
    if data['percent'] != (15 if data['kind']=='welcome' else 20):raise ValueError('invalid_campaign')
    if int(data.get('end',0))<=int(data.get('start',0)):raise ValueError('invalid_dates')
    if not 1<=int(data.get('valid_days',30))<=365 or int(data.get('minimum_cents',0))<0:raise ValueError('invalid_campaign')
    if not all(data.get(k) for k in ['terms_nl','terms_en']):raise ValueError('terms_required')
    return data
def active(data,at=None):
    at=now() if at is None else at
    return data.get('active') is True and int(data.get('start',0))<=at<int(data.get('end',0))
def active_campaign(kind):
    return next(((key,v) for key,v in records('nv_campaigns').items() if v.get('kind')==kind and active(v)),None)
def publication_errors(p,suppliers=None):
    suppliers=records('nv_suppliers') if suppliers is None else suppliers
    errors=[]
    for key in ['sku','brand','name_nl','name_en','description_nl','description_en','image','specifications','delivery_nl','delivery_en','safety','supplier_id']:
        if not p.get(key):errors.append(key)
    if p.get('demo') is not False:errors.append('real_product_required')
    if suppliers.get(str(p.get('supplier_id')),{}).get('approved') is not True:errors.append('supplier_not_verified')
    for key in ['supplier_verified','price_verified','image_verified','data_verified','delivery_verified','safety_verified']:
        if p.get(key) is not True:errors.append(key)
    for key in ['price_cents','stock']:
        if not isinstance(p.get(key),int) or isinstance(p.get(key),bool) or p[key]<(1 if key=='price_cents' else 0):errors.append(key)
    if p.get('vat_bps') not in {0,900,2100}:errors.append('vat_bps')
    if not str(p.get('image','')).startswith(('/static/','https://')):errors.append('image_url')
    if not isinstance(p.get('variants',[]),list):errors.append('variants')
    elif p.get('variants'):errors.append('variant_sales_require_separate_acceptance')
    return errors
def publish(id):
    p=records('nv_products').get(str(id),{});errors=publication_errors(p)
    if errors:raise ValueError(', '.join(errors))
    p['published']=True;save_record('nv_products',id,p)
def price(p,at=None):
    base=int(p['price_cents']);offer=p.get('offer') or {}
    if p.get('demo') is False and p.get('published') and active(offer,at) and offer.get('verified') is True:
        sale=offer.get('price_cents');ref=offer.get('reference_cents')
        if isinstance(sale,int) and isinstance(ref,int) and 0<sale<base and sale<ref and offer.get('reference_evidence'):
            return sale,ref
    return base,None

def limit(bucket,maximum,seconds):
    with db(True) as c:
        # Expired entries are retained only for a bounded operational window.
        c.execute('DELETE FROM nv_limits WHERE at<?',(now()-86400,))
        n=c.execute('SELECT COUNT(*) FROM nv_limits WHERE bucket=? AND at>?',(digest(bucket),now()-seconds)).fetchone()[0]
        if n>=maximum:return False
        c.execute('INSERT INTO nv_limits VALUES(?,?)',(digest(bucket),now()));return True
def reserve_ai(estimate_usd,monthly_usd,daily_calls):
    micros=int((Decimal(str(estimate_usd))*1000000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    maximum=int(Decimal(str(monthly_usd))*1000000)
    if micros<0 or maximum<=0 or daily_calls<=0:raise ValueError('invalid_budget')
    month=time.strftime('%Y-%m',time.gmtime(now()));day=time.strftime('%Y-%m-%d',time.gmtime(now()))
    with db(True) as c:
        used=c.execute('SELECT COALESCE(SUM(COALESCE(actual_micros,estimated_micros)),0) FROM nv_ai_reservations WHERE month=?',(month,)).fetchone()[0]
        calls=c.execute('SELECT COUNT(*) FROM nv_ai_reservations WHERE day=?',(day,)).fetchone()[0]
        if used+micros>maximum or calls>=daily_calls:raise ValueError('ai_budget_or_daily_limit')
        id=secrets.token_urlsafe(20);c.execute('INSERT INTO nv_ai_reservations VALUES(?,?,?,?,NULL)',(id,month,day,micros));return id
def settle_ai(id,actual_usd):
    amount=int((Decimal(str(actual_usd))*1000000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    if amount<0:raise ValueError('invalid_budget')
    with db(True) as c:
        c.execute('UPDATE nv_ai_reservations SET actual_micros=? WHERE id=? AND actual_micros IS NULL',(amount,id))
def account(id,email):
    with db(True) as c:
        c.execute('INSERT OR IGNORE INTO nv_customers(id,email) VALUES(?,?)',(id,email))
        return dict(c.execute('SELECT * FROM nv_customers WHERE id=?',(id,)).fetchone())
def queue(c,customer_id,email,kind,subject,body,language,dedupe):
    from nv_mail import enabled
    status='pending' if enabled() and not email.endswith('.invalid') else 'test'
    c.execute('INSERT OR IGNORE INTO nv_mail(id,customer_id,recipient,subject,body,language,kind,dedupe,status,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(secrets.token_urlsafe(18),customer_id,email,subject,body,language,kind,dedupe,status,now()))
def token(customer,purpose,lang='nl'):
    raw=secrets.token_urlsafe(32);expires=now()+(1800 if purpose=='reset' else 86400)
    a=account(customer['id'],customer['email'])
    with db(True) as c:
        c.execute('UPDATE nv_tokens SET used=1 WHERE customer_id=? AND purpose=?',(customer['id'],purpose))
        c.execute('INSERT INTO nv_tokens VALUES(?,?,?,?,0,?)',(digest(raw),customer['id'],purpose,expires,a['auth_version']))
        route='/account/reset-password' if purpose=='reset' else '/account/verify-email'
        english=lang=='en';subject=('Reset your password' if purpose=='reset' else 'Verify your email') if english else ('Herstel je wachtwoord' if purpose=='reset' else 'Verifieer je e-mailadres')
        body=('Use this personal, single-use link: ' if english else 'Gebruik deze persoonlijke, eenmalige link: ')+public_link(route)+'?token='+raw+'&lang='+lang
        queue(c,customer['id'],customer['email'],purpose,'NUVEMIXA — '+subject,body,lang,'token:'+digest(raw))
    return raw
def consume(raw,purpose,action):
    with db(True) as c:
        row=c.execute('SELECT t.*,u.auth_version,u.email FROM nv_tokens t JOIN nv_customers u ON u.id=t.customer_id WHERE hash=?',(digest(raw),)).fetchone()
        if not row or row['purpose']!=purpose or row['used'] or row['expires']<=now() or row['version']!=row['auth_version']:raise ValueError('invalid_token')
        action(c,dict(row));c.execute('UPDATE nv_tokens SET used=1 WHERE hash=?',(digest(raw),))
        return row['customer_id']
def issue_coupon(c,customer_id,campaign_id,source,language='nl'):
    row=c.execute('SELECT data FROM nv_campaigns WHERE id=?',(campaign_id,)).fetchone()
    if not row:return None
    data=json.loads(row[0]);customer=c.execute('SELECT * FROM nv_customers WHERE id=?',(customer_id,)).fetchone()
    if not active(data) or not customer or not customer['verified']:return None
    if c.execute('SELECT 1 FROM nv_coupons WHERE customer_id=? AND campaign_id=? AND source=?',(customer_id,campaign_id,source)).fetchone():return None
    raw='NV-'+secrets.token_urlsafe(15);expiry=min(int(data['end']),now()+int(data.get('valid_days',30))*86400)
    c.execute('INSERT INTO nv_coupons(hash,customer_id,campaign_id,source,expires) VALUES(?,?,?,?,?)',(digest(raw),customer_id,campaign_id,source,expiry))
    en=language=='en';subject='Your personal discount code' if en else 'Je persoonlijke kortingscode'
    body=(f"Your personal {data['percent']}% code: " if en else f"Je persoonlijke {data['percent']}%-code: ")+raw+'\n'+data['terms_en' if en else 'terms_nl']+'\n'+time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(expiry))
    queue(c,customer_id,customer['email'],'coupon',subject,body,language,'coupon:'+digest(raw));return raw
def verify(raw,lang):
    def action(c,row):
        c.execute('UPDATE nv_customers SET verified=1 WHERE id=?',(row['customer_id'],))
        for cam in c.execute('SELECT * FROM nv_campaigns'):
            if json.loads(cam['data']).get('kind')=='welcome':issue_coupon(c,row['customer_id'],cam['id'],'welcome',lang)
    return consume(raw,'verify',action)
def favorites(id,guest=None):
    with db(True) as c:
        for item in (guest or [])[:100]:c.execute('INSERT OR IGNORE INTO nv_favorites VALUES(?,?)',(id,str(item)))
        return [r[0] for r in c.execute('SELECT product_id FROM nv_favorites WHERE customer_id=?',(id,))]
def set_favorites(id,items):
    with db(True) as c:
        c.execute('DELETE FROM nv_favorites WHERE customer_id=?',(id,))
        c.executemany('INSERT OR IGNORE INTO nv_favorites VALUES(?,?)',[(id,str(i)) for i in items[:100]])

def quotation(lines,country,coupon='',customer_id=None,conn=None,at=None):
    if conn is None:
        with db() as c:return quotation(lines,country,coupon,customer_id,c,at)
    at=now() if at is None else at
    shipping=setting('shipping',{'NL':None,'BE':None},conn)
    if country not in shipping:raise ValueError('unsupported_country')
    subtotal=sum(int(p['unit_cents'])*int(p['qty']) for p in lines)
    discount=0;coupon_hash=None;eligible=[]
    if coupon:
        coupon_hash=digest(coupon.strip());row=conn.execute('SELECT * FROM nv_coupons WHERE hash=?',(coupon_hash,)).fetchone()
        if not row or row['customer_id']!=customer_id or row['state']!='available' or row['expires']<=at:raise ValueError('invalid_coupon')
        cr=conn.execute('SELECT data FROM nv_campaigns WHERE id=?',(row['campaign_id'],)).fetchone();cam=json.loads(cr[0])
        if not active(cam,at) or subtotal<int(cam.get('minimum_cents',0)):raise ValueError('invalid_coupon')
        eligible=[i for i,p in enumerate(lines) if str(p['product_id']) not in cam.get('excluded_products',[]) and p.get('category') not in cam.get('excluded_categories',[]) and (not p.get('on_offer') or cam.get('include_offers') is True)]
        eligible_total=sum(lines[i]['unit_cents']*lines[i]['qty'] for i in eligible)
        discount=int((Decimal(eligible_total)*int(cam['percent'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        discount=min(discount,int(cam.get('maximum_discount_cents') or discount))
        if discount<=0:raise ValueError('invalid_coupon')
    allocated=[]
    cuts=dict(zip(eligible,allocate(discount,[lines[i]['unit_cents']*lines[i]['qty'] for i in eligible])))
    for i,p in enumerate(lines):
        gross=p['unit_cents']*p['qty'];cut=0
        if i in eligible:cut=cuts[i]
        netgross=gross-cut;vat=int((Decimal(netgross)*int(p.get('vat_bps',2100))/(10000+int(p.get('vat_bps',2100)))).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        snapshot={k:v for k,v in p.items() if k!='price'}
        allocated.append(dict(snapshot,gross_cents=gross,discount_cents=cut,total_cents=netgross,vat_cents=vat))
    # Demo delivery is explicitly fictional. Real shipping is unknown until configured.
    simulation=any(p.get('demo',True) for p in lines)
    fee=0 if simulation else shipping[country]
    if fee is None:raise ValueError('shipping_unconfigured')
    fee=int(fee)
    groups={}
    for p in allocated:
        rate=int(p.get('vat_bps',2100))
        group=groups.setdefault(rate,{'vat_bps':rate,'goods_cents':0,'vat_cents':0})
        group['goods_cents']+=p['total_cents'];group['vat_cents']+=p['vat_cents']
    rates=sorted(groups);weights=[groups[r]['goods_cents'] for r in rates]
    # Shipping may exceed the goods amount: allocate() itself deliberately caps
    # discounts, so proportionally distribute shipping separately here.
    denominator=sum(weights)
    fees=[fee*w//denominator for w in weights] if denominator else [0]*len(rates)
    if denominator:
        order=sorted(range(len(rates)),key=lambda i:(-(fee*weights[i]%denominator),i))
        for i in order[:fee-sum(fees)]:fees[i]+=1
    elif fee:raise ValueError('shipping_without_taxable_goods')
    shipping_vat=0
    for rate,part in zip(rates,fees):
        tax=int((Decimal(part)*rate/(10000+rate)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        shipping_vat+=tax
        groups[rate].update(shipping_cents=part,shipping_vat_cents=tax)
        groups[rate]['vat_cents']+=tax
        groups[rate]['net_cents']=groups[rate]['goods_cents']+part-groups[rate]['vat_cents']
    vat=sum(p['vat_cents'] for p in allocated)+shipping_vat
    total=subtotal-discount+fee
    return {'subtotal_cents':subtotal,'discount_cents':discount,'after_discount_cents':subtotal-discount,
            'shipping_cents':fee,'shipping_known':not simulation,'shipping_vat_cents':shipping_vat,
            'vat_cents':vat,'net_cents':total-vat,'vat_breakdown':[groups[r] for r in rates],
            'total_cents':total,'coupon_hash':coupon_hash,'coupon_code':coupon.strip() if coupon_hash else '',
            'discount_percent':int(cam['percent']) if coupon_hash else 0,'lines':allocated,'simulation':True}

def quote_text(quote,en=False):
    labels=[('Products','Producten',quote['subtotal_cents']),('Discount','Korting',-quote['discount_cents']),
            ('Products after discount','Producten na korting',quote['subtotal_cents']-quote['discount_cents']),
            ('Shipping (simulation)' if not quote.get('shipping_known',True) else 'Shipping',
             'Verzending (simulatie)' if not quote.get('shipping_known',True) else 'Verzending',quote['shipping_cents']),
            ('Excluding VAT','Exclusief btw',quote['total_cents']-quote['vat_cents'])]
    result=[(a if en else b)+': EUR '+format(money(v),'.2f') for a,b,v in labels]
    if quote.get('coupon_code'):result.insert(1,('Coupon: ' if en else 'Kortingscode: ')+quote['coupon_code'])
    for group in quote.get('vat_breakdown',[]):
        result.append(('VAT ' if en else 'Btw ')+format(Decimal(group['vat_bps'])/100,'g')+'%: EUR '+format(money(group['vat_cents']),'.2f'))
    result.extend([('Total: EUR ' if en else 'Totaal: EUR ')+format(money(quote['total_cents']),'.2f'),('Savings: EUR ' if en else 'Besparing: EUR ')+format(money(quote['discount_cents']),'.2f')])
    return '\n'.join(result)


def create_order(lines,address,customer_id,owner,idempotency,coupon='',lang='nl'):
    if not lines:raise ValueError('empty_cart')
    if not isinstance(idempotency,str) or not 16<=len(idempotency)<=128:raise ValueError('invalid_idempotency')
    if any(not isinstance(p.get('qty'),int) or not 1<=p['qty']<=99 or not isinstance(p.get('unit_cents'),int) or p['unit_cents']<0 for p in lines):raise ValueError('invalid_order_line')
    with db(True) as c:
        expired=[r[0] for r in c.execute("SELECT id FROM nv_orders WHERE status='pending' AND expires<=?",(now(),))]
        for stale in expired:
            c.execute("UPDATE nv_orders SET status='expired' WHERE id=?",(stale,))
            c.execute("UPDATE nv_coupons SET state='available',order_id=NULL WHERE order_id=? AND state='reserved'",(stale,))
        previous=c.execute('SELECT * FROM nv_orders WHERE idempotency=?',(digest(owner+idempotency),)).fetchone()
        if previous:return dict(previous)
        quote=quotation(lines,address['country'],coupon,customer_id,c)
        quote['language']=lang
        quote['invoice']={'simulation':True,'company':setting('company',{},c),'currency':'EUR','not_a_tax_invoice':True}
        oid='SIM-'+secrets.token_hex(10).upper()
        if quote['coupon_hash']:
            n=c.execute("UPDATE nv_coupons SET state='reserved',order_id=? WHERE hash=? AND state='available'",(oid,quote['coupon_hash'])).rowcount
            if n!=1:raise ValueError('invalid_coupon')
        c.execute('INSERT INTO nv_orders(id,customer_id,owner_hash,idempotency,mode,status,items,address,totals,coupon_hash,created,expires) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(oid,customer_id,digest(owner),digest(owner+idempotency),'simulation','pending',json.dumps(quote['lines']),json.dumps(address),json.dumps(quote),quote['coupon_hash'],now(),now()+1800))
        en=lang=='en'
        item_lines='\n'.join(str(p['qty'])+' × '+p.get('en_name' if en else 'name','')+' — EUR '+format(money(p['total_cents']),'.2f') for p in quote['lines'])
        body=('SIMULATION ONLY — no payment or delivery.\n' if en else 'UITSLUITEND SIMULATIE — geen betaling of levering.\n')+oid+'\n'+item_lines+'\n'+quote_text(quote,en)+'\n'+('Status: pending — not paid' if en else 'Status: pending — niet betaald')+'\n/orders/'+oid+'\n'+('This is not a tax invoice.' if en else 'Dit is geen fiscale factuur.')
        queue(c,customer_id,address['email'],'order','NUVEMIXA — '+('Simulated order' if en else 'Simulatiebestelling'),body,lang,'order:'+oid)
        return dict(c.execute('SELECT * FROM nv_orders WHERE id=?',(oid,)).fetchone())
TRANSITIONS={'pending':{'paid','cancelled','failed','expired'},'paid':{'fulfilled'},'fulfilled':set(),'cancelled':set(),'failed':set(),'expired':set(),'refunded':set()}
def transition(order_id,event_id,target):
    if target not in TRANSITIONS:raise ValueError('invalid_status')
    if not isinstance(event_id,str) or not 8<=len(event_id)<=200:raise ValueError('invalid_event')
    with db(True) as c:
        row=c.execute('SELECT * FROM nv_orders WHERE id=?',(order_id,)).fetchone()
        if not row:raise ValueError('unknown_order')
        seen=c.execute('SELECT * FROM nv_events WHERE id=?',(event_id,)).fetchone()
        if seen:
            if seen['order_id']!=order_id or seen['event']!=target:raise ValueError('event_conflict')
            return dict(row)
        if target!=row['status'] and target not in TRANSITIONS[row['status']]:raise ValueError('invalid_transition')
        if row['status']=='pending' and row['expires']<=now() and target=='paid':raise ValueError('expired_order')
        c.execute('INSERT INTO nv_events VALUES(?,?,?,?)',(event_id,order_id,target,now()))
        c.execute('UPDATE nv_orders SET status=? WHERE id=?',(target,order_id))
        if row['coupon_hash']:
            if target=='paid':c.execute("UPDATE nv_coupons SET state='redeemed' WHERE order_id=?",(order_id,))
            elif target in {'cancelled','failed','expired'}:c.execute("UPDATE nv_coupons SET state='available',order_id=NULL WHERE order_id=? AND state='reserved'",(order_id,))
        return dict(c.execute('SELECT * FROM nv_orders WHERE id=?',(order_id,)).fetchone())
def refund(order_id,amount,event_id):
    if not isinstance(event_id,str) or not 8<=len(event_id)<=200:raise ValueError('invalid_event')
    with db(True) as c:
        row=c.execute('SELECT * FROM nv_orders WHERE id=?',(order_id,)).fetchone()
        if not row:raise ValueError('unknown_order')
        seen=c.execute('SELECT * FROM nv_events WHERE id=?',(event_id,)).fetchone()
        if seen:
            if seen['order_id']!=order_id or seen['event']!='refund:'+str(amount):raise ValueError('event_conflict')
            return dict(row)
        if row['status'] not in {'paid','fulfilled'} or not isinstance(amount,int) or amount<=0 or row['refunded']+amount>json.loads(row['totals'])['total_cents']:raise ValueError('invalid_refund')
        c.execute('UPDATE nv_orders SET refunded=refunded+? WHERE id=?',(amount,order_id))
        c.execute('INSERT INTO nv_events VALUES(?,?,?,?)',(event_id,order_id,'refund:'+str(amount),now()))
        totals=json.loads(row['totals']);lines=json.loads(row['items'])
        components=[(str(p['product_id']),p['total_cents'],p['vat_cents']) for p in lines]
        shipping_vat=totals['vat_cents']-sum(p['vat_cents'] for p in lines)
        if totals['shipping_cents']:components.append(('__shipping__',totals['shipping_cents'],shipping_vat))
        remaining=[]
        for pid,gross,vat in components:
            past=c.execute('SELECT COALESCE(SUM(amount_cents),0),COALESCE(SUM(vat_cents),0) FROM nv_refund_lines WHERE order_id=? AND product_id=?',(order_id,pid)).fetchone()
            if gross>past[0]:remaining.append((pid,gross-past[0],vat-past[1]))
        refund_cuts=allocate(amount,[v[1] for v in remaining])
        for i,(pid,gross,vat) in enumerate(remaining):
            cut=refund_cuts[i]
            tax=vat if cut==gross else int((Decimal(cut)*vat/gross).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            c.execute('INSERT INTO nv_refund_lines VALUES(?,?,?,?,?)',(event_id,order_id,pid,cut,min(tax,vat)))
        if row['refunded']+amount==json.loads(row['totals'])['total_cents']:c.execute("UPDATE nv_orders SET status='refunded' WHERE id=?",(order_id,))
        locale=json.loads(row['totals']).get('language','nl');en=locale=='en'
        queue(c,row['customer_id'],json.loads(row['address'])['email'],'refund','NUVEMIXA — '+('Simulated refund' if en else 'Gesimuleerde terugbetaling'),order_id+'\n'+('Simulated refund: EUR ' if en else 'Gesimuleerde terugbetaling: EUR ')+format(money(amount),'.2f')+'\n'+('No real money was transferred.' if en else 'Er is geen echt geld overgemaakt.'),locale,'refund:'+event_id)
        return dict(c.execute('SELECT * FROM nv_orders WHERE id=?',(order_id,)).fetchone())
def invite_review(order_id,lang='nl'):
    raw=secrets.token_urlsafe(32)
    with db(True) as c:
        order=c.execute('SELECT * FROM nv_orders WHERE id=?',(order_id,)).fetchone()
        if not order or order['status']!='fulfilled' or not order['customer_id']:raise ValueError('ineligible_order')
        if c.execute('SELECT 1 FROM nv_review_invites WHERE order_id=?',(order_id,)).fetchone():return None
        c.execute('INSERT INTO nv_review_invites VALUES(?,?,?,?,0)',(digest(raw),order_id,order['customer_id'],now()+30*86400))
        a=c.execute('SELECT * FROM nv_customers WHERE id=?',(order['customer_id'],)).fetchone()
        if not a or not a['verified']:raise ValueError('unverified_email')
        body=public_link('/review-purchase')+'?token='+raw+'&lang='+lang+'\n'+('Positive and negative experiences qualify equally for any active incentive. Simulation reviews are never presented as genuine purchases.' if lang=='en' else 'Positieve en negatieve ervaringen komen gelijk in aanmerking voor een eventuele actieve beloning. Simulatiereviews worden nooit als echte aankopen gepresenteerd.')
        queue(c,a['id'],a['email'],'review','NUVEMIXA — '+('Your honest review' if lang=='en' else 'Je eerlijke review'),body,lang,'review:'+order_id)
    return raw
def purchase_review(raw,customer_id,rating,body,lang='nl'):
    if not isinstance(rating,int) or not 1<=rating<=5 or not 10<=len(body)<=1500:raise ValueError('invalid_review')
    with db(True) as c:
        row=c.execute('SELECT i.*,o.mode,o.status FROM nv_review_invites i JOIN nv_orders o ON o.id=i.order_id WHERE i.hash=?',(digest(raw),)).fetchone()
        if not row or row['used'] or row['expires']<=now() or row['customer_id']!=customer_id or row['status']!='fulfilled':raise ValueError('invalid_invitation')
        cam=next((r for r in c.execute('SELECT * FROM nv_campaigns') if json.loads(r['data']).get('kind')=='review' and active(json.loads(r['data']))),None)
        # Simulated purchases never become genuine verified public reviews.
        c.execute('INSERT INTO nv_purchase_reviews(order_id,customer_id,rating,body,incentivized,verified,created) VALUES(?,?,?,?,?,?,?)',(row['order_id'],customer_id,rating,body,1 if cam else 0,0 if row['mode']=='simulation' else 1,now()))
        c.execute('UPDATE nv_review_invites SET used=1 WHERE hash=?',(digest(raw),))
        if cam:issue_coupon(c,customer_id,cam['id'],'review:'+row['order_id'],lang)
def withdraw(order,email,customer_id=None,language='nl'):
    with db(True) as c:
        r=c.execute('SELECT * FROM nv_orders WHERE id=?',(order,)).fetchone()
        if not r or json.loads(r['address'])['email'].casefold()!=email.casefold():return None
        previous=c.execute('SELECT id FROM nv_withdrawals WHERE order_id=?',(order,)).fetchone()
        if previous:return previous[0]
        id='HER-'+secrets.token_hex(8)
        c.execute('INSERT INTO nv_withdrawals VALUES(?,?,?,?,?,?)',(id,order,customer_id,email,now(),'received'))
        en=language=='en';stamp=time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(now()))
        queue(c,customer_id,email,'withdrawal','NUVEMIXA — '+('Withdrawal received' if en else 'Herroeping ontvangen'),id+'\n'+order+'\n'+('Received: ' if en else 'Ontvangen: ')+stamp+'\n'+('Local simulated contract; no actual refund or external email.' if en else 'Lokale simulatieovereenkomst; geen echte terugbetaling of externe e-mail.'),language,'withdrawal:'+order)
        return id
