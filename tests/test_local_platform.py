"""Acceptance tests: fake data, local SQLite, no external services."""
import concurrent.futures
import json
import os
import secrets
import sqlite3
from pathlib import Path
import pytest
import nv_store as store
from app import app
import app as mod

@pytest.fixture
def tmp_path():
    # Windows sandbox cannot reopen mode-0700 directories created by tempfile.
    # Ordinary project-owned directories keep the same isolation without chmod.
    root=Path(os.environ['NUVEMIXA_STORE_DB']).parent/'cases'/secrets.token_hex(10)
    root.mkdir(parents=True,exist_ok=False)
    return root

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('NUVEMIXA_STORE_DB',str(tmp_path/'store.sqlite3'))
    monkeypatch.setenv('NUVEMIXA_ADMIN_DB',str(tmp_path/'store.sqlite3'))
    monkeypatch.setattr(mod,'_CUSTOMER_DB',tmp_path/'customers.sqlite3')
    import nv_reviews
    monkeypatch.setattr(nv_reviews,'REVIEWS_DB',tmp_path/'reviews.sqlite3')
    monkeypatch.delenv('NUVEMIXA_ADMIN_PASSWORD_HASH',raising=False)
    app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False,SECRET_KEY='isolated-test-secret',SESSION_COOKIE_NAME='nv_test_acceptance')
    def denied(*a,**kw):raise AssertionError('External I/O forbidden in acceptance tests')
    import urllib.request,smtplib
    monkeypatch.setattr(urllib.request,'urlopen',denied);monkeypatch.setattr(smtplib,'SMTP',denied)

def token(client):
    client.get('/account')
    with client.session_transaction() as s:return s['_tm_csrf']
def post(client,path,data=None,**kw):return client.post(path,data={'_csrf_token':token(client),**(data or {})},**kw)
def register(client,email='audit@example.invalid'):
    return post(client,'/account/register',{'name':'Fictieve testklant','email':email,'password':'A-long-fake-password!','password_confirm':'A-long-fake-password!'})
def account_id(client):
    with client.session_transaction() as s:return s['nv_customer_id']
def mail_link(kind):
    with store.db() as c:return c.execute('SELECT body FROM nv_mail WHERE kind=? ORDER BY created DESC,id DESC',(kind,)).fetchone()[0].split(': ',1)[-1]
def extract_token(kind):
    import re
    return re.search(r'token=([^&\s]+)',mail_link(kind))[1]
def campaign(kind='welcome',**kw):
    d={'kind':kind,'percent':15 if kind=='welcome' else 20,'active':True,'start':store.now()-60,'end':store.now()+86400,'valid_days':1,'minimum_cents':0,'terms_nl':'Alleen test, persoonlijk en eenmalig.','terms_en':'Test only, personal and single use.'};d.update(kw);store.save_record('nv_campaigns',kind,d);return d
def line(**kw):
    data={'product_id':'1','id':'1','name':'Fictief testartikel','en_name':'Fake test item','unit_cents':2495,'qty':1,'vat_bps':2100,'demo':True,'category':'gadgets'};data.update(kw);return data
def addr():return {'first_name':'Test','last_name':'Audit','email':'audit@example.invalid','address_1':'Fictieve straat 12','postcode':'1234 AB','city':'Teststad','country':'NL'}
def issue(client):
    register(client);campaign();post(client,'/account/verify-email',{'token':extract_token('verify')})
    with store.db() as c:body=c.execute("SELECT body FROM nv_mail WHERE kind='coupon'").fetchone()[0]
    return body.split(': ',1)[1].split('\n')[0]

def test_registration_preserves_cart_and_persists_favorites():
    c=app.test_client();post(c,'/winkelwagen',{'action':'add','product_id':'1'});post(c,'/wishlist',{'product_id':'1'})
    assert register(c).status_code==303
    with c.session_transaction() as s:assert s['trendmix_cart'] and s['trendmix_wishlist']
    assert store.favorites(account_id(c))==['1']
    post(c,'/account/logout');post(c,'/account/login',{'email':'audit@example.invalid','password':'A-long-fake-password!'})
    with c.session_transaction() as s:assert s['trendmix_cart'] and s['trendmix_wishlist']==['1']

def test_verification_single_use_and_welcome_coupon():
    c=app.test_client();campaign();register(c);raw=extract_token('verify')
    assert post(c,'/account/verify-email',{'token':raw}).status_code==200
    assert post(c,'/account/verify-email',{'token':raw}).status_code==400
    with store.db() as db:
        assert db.execute('SELECT COUNT(*) FROM nv_coupons').fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM nv_mail WHERE kind='coupon'").fetchone()[0]==1

def test_campaigns_off_by_default_and_expired():
    c=app.test_client();assert b'nv-promo-banner wrap' not in c.get('/').data
    campaign(active=False);assert b'nv-promo-banner wrap' not in c.get('/').data
    campaign(end=store.now()-1);assert b'nv-promo-banner wrap' not in c.get('/').data
    campaign();assert b'nv-promo-banner wrap' in c.get('/').data

def test_password_reset_expiry_replay_and_session_invalidation():
    c=app.test_client();register(c);post(c,'/account/forgot-password',{'email':'audit@example.invalid'});raw=extract_token('reset')
    assert post(c,'/account/reset-password',{'token':raw,'password':'Another-long-password!','password_confirm':'Another-long-password!'}).status_code==200
    assert post(c,'/account/reset-password',{'token':raw,'password':'Another-long-password!','password_confirm':'Another-long-password!'}).status_code==400
    c.get('/account')
    with c.session_transaction() as s:assert not s.get('nv_customer_id')
    assert post(c,'/account/login',{'email':'audit@example.invalid','password':'A-long-fake-password!'}).status_code==401
    assert post(c,'/account/login',{'email':'audit@example.invalid','password':'Another-long-password!'}).status_code==303

def test_money_and_coupon_exact_totals():
    c=app.test_client();code=issue(c);quote=store.quotation([line(qty=3)],'NL',code,account_id(c))
    assert quote['subtotal_cents']==7485 and quote['discount_cents']==1123 and quote['total_cents']==6362
    assert sum(p['total_cents'] for p in quote['lines'])==quote['total_cents']
    assert store.cents('1.005')==101

def test_coupon_personal_minimum_exclusion_and_stacking():
    c=app.test_client();code=issue(c)
    with pytest.raises(ValueError):store.quotation([line()],'NL',code,999)
    campaign(minimum_cents=3000)
    with pytest.raises(ValueError):store.quotation([line()],'NL',code,account_id(c))
    campaign(excluded_products=['1'])
    with pytest.raises(ValueError):store.quotation([line()],'NL',code,account_id(c))
    campaign()
    with pytest.raises(ValueError):store.quotation([line(on_offer=True)],'NL',code,account_id(c))
    with pytest.raises(ValueError):store.quotation([line()],'NL',code+','+code,account_id(c))

def test_concurrent_coupon_reservation_only_one_order():
    c=app.test_client();code=issue(c);id=account_id(c)
    def attempt(n):
        try:return store.create_order([line()],addr(),id,'owner'+str(n),'idempotency-key-'+str(n),code)['id']
        except ValueError:return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[1,2]))
    assert sum(x is not None for x in results)==1

def test_double_click_and_double_event_no_duplicate():
    a=store.create_order([line()],addr(),None,'owner','idempotency-key-1');b=store.create_order([line()],addr(),None,'owner','idempotency-key-1')
    assert a['id']==b['id']
    assert store.transition(a['id'],'event-paid-001','paid')['status']=='paid'
    assert store.transition(a['id'],'event-paid-001','paid')['status']=='paid'
    with pytest.raises(ValueError):store.transition(a['id'],'event-expired-1','expired')
    with store.db() as db:assert db.execute('SELECT COUNT(*) FROM nv_events').fetchone()[0]==1

@pytest.mark.parametrize('target',['cancelled','failed','expired'])
def test_cancel_timeout_failure_release_reservation(target):
    c=app.test_client();code=issue(c);order=store.create_order([line()],addr(),account_id(c),'owner','idempotency-key-1',code)
    store.transition(order['id'],'event-release-1',target)
    assert store.quotation([line()],'NL',code,account_id(c))['discount_cents']==374

def test_refund_capped_and_idempotent():
    order=store.create_order([line()],addr(),None,'owner','idempotency-key-1');store.transition(order['id'],'event-paid-1','paid')
    store.refund(order['id'],1000,'refund-event-1');assert store.refund(order['id'],1000,'refund-event-1')['refunded']==1000
    with pytest.raises(ValueError):store.refund(order['id'],2000,'refund-event-2')
    assert store.refund(order['id'],1495,'refund-event-3')['status']=='refunded'

@pytest.mark.parametrize('rating',[1,5])
def test_review_reward_equal_no_fake_verified_review(rating):
    c=app.test_client();issue(c);campaign('review');id=account_id(c)
    o=store.create_order([line()],addr(),id,'owner','idempotency-key-1');store.transition(o['id'],'event-paid-1','paid');store.transition(o['id'],'fulfilled-event-1','fulfilled')
    raw=store.invite_review(o['id']);store.purchase_review(raw,id,rating,'Een volledig fictieve eerlijke auditervaring.')
    with store.db() as db:
        r=db.execute('SELECT * FROM nv_purchase_reviews').fetchone();assert r['incentivized']==1 and r['verified']==0 and r['status']=='pending'
        assert db.execute("SELECT COUNT(*) FROM nv_coupons WHERE campaign_id='review'").fetchone()[0]==1
    with pytest.raises(ValueError):store.purchase_review(raw,id,rating,'Een volledig fictieve eerlijke auditervaring.')

def test_foreign_order_cannot_be_read_or_paid():
    a=app.test_client();register(a);order=store.create_order([line()],addr(),account_id(a),'owner','idempotency-key-1')
    b=app.test_client();register(b,'other@example.invalid')
    assert b.get('/orders/'+order['id']).status_code==404
    assert post(b,'/orders/'+order['id']+'/simulate',{'event':'paid'}).status_code==404

def test_address_validation_and_no_live_webhook():
    c=app.test_client();post(c,'/winkelwagen',{'action':'add','product_id':'1'})
    for country,postcode in [('US','1234 AB'),('NL','x'),('BE','x')]:
        data=addr();data.update(country=country,postcode=postcode,checkout_consent='yes',idempotency='idempotency-key-1');assert post(c,'/afrekenen',data).status_code==400
    data=addr();data.update(checkout_consent='yes',idempotency='idempotency-key-1');assert post(c,'/afrekenen',data).status_code==303
    assert post(c,'/payments/webhook').status_code==503
    assert mod.live_orders_enabled() is False

def test_review_sso_has_no_general_admin_scope(monkeypatch,tmp_path):
    import nv_reviews_sso
    monkeypatch.setenv('NUVEMIXA_REVIEWS_SSO_SECRET',secrets.token_urlsafe(32))
    monkeypatch.setenv('NUVEMIXA_ADMIN_PASSWORD_HASH',generate_fake_hash())
    c=app.test_client();raw=nv_reviews_sso.maak_token();r=c.get('/admin/reviews/sso?t='+raw)
    assert r.status_code==302
    with c.session_transaction() as s:assert s.get('nv_review_role') is True and not s.get('nv_admin')
    assert c.get('/control').status_code==302
    assert c.get('/admin/commerce').status_code==303
    assert c.get('/admin/reviews/sso?t='+raw).status_code==403
def generate_fake_hash():
    from werkzeug.security import generate_password_hash
    return generate_password_hash('test-only-strong-secret')

def test_private_caching_csp_nonce_static_blob_blocked():
    c=app.test_client();r=c.get('/account');assert 'no-store' in r.headers['Cache-Control'];assert 'noindex' in r.headers['X-Robots-Tag']
    assert "'unsafe-inline'" not in r.headers['Content-Security-Policy'].split('script-src ')[1].split(';')[0]
    assert c.get('/static/nvx-7a7e6c734b67c602e78fabce.bin').status_code==404
    assert b'Server-owned' not in c.get('/').data # no debug internals in markup

def test_pwa_no_private_or_price_cache():
    c=app.test_client();m=c.get('/static/manifest.webmanifest').get_json();assert m['name']=='NUVEMIXA' and m['display']=='standalone'
    worker=c.get('/service-worker.js');assert worker.status_code==200 and b'caches.put' not in worker.data and b'cache.add' not in worker.data
    assert worker.headers['Service-Worker-Allowed']=='/'
    for icon in m['icons']:assert c.get(icon['src']).status_code==200

def test_catalog_publication_offer_and_expiry():
    c=app.test_client();allp=c.get('/shop');assert allp.status_code==200
    assert store.publication_errors({'demo':True})
    p={'demo':False,'published':True,'price_cents':3000,'offer':{'active':True,'start':store.now()-1,'end':store.now()+60,'verified':True,'price_cents':2500,'reference_cents':3000,'reference_evidence':'Fictief testbewijs'}}
    assert store.price(p)==(2500,3000);assert store.price(p,store.now()+61)==(3000,None)
    p['demo']=True;assert store.price(p)==(3000,None)

def test_withdrawal_idempotent_guest_and_acknowledgement():
    o=store.create_order([line()],addr(),None,'owner','idempotency-key-1');a=store.withdraw(o['id'],addr()['email']);assert a and store.withdraw(o['id'],addr()['email'])==a
    with store.db() as c:assert c.execute("SELECT COUNT(*) FROM nv_mail WHERE kind='withdrawal'").fetchone()[0]==1

def test_server_english_and_metadata():
    c=app.test_client();r=c.get('/account?lang=en');assert b'<html lang="en"' in r.data and b'Repeat password' in r.data and b'Herhaal wachtwoord' not in r.data
    r=c.get('/shop?q=zzzzzz&lang=en');assert b'Search results for' in r.data and b'Geen producten gevonden' not in r.data
    assert 'noindex' in r.headers['X-Robots-Tag']

def test_central_rate_limit_and_input_limit():
    c=app.test_client();responses=[post(c,'/account/login',{'email':'no@example.invalid','password':'invalid-password'}) for _ in range(9)]
    assert responses[-1].status_code==429
    assert c.post('/contact',data='x'*70000,content_type='application/x-www-form-urlencoded').status_code==413

def test_expired_token_and_coupon(monkeypatch):
    c=app.test_client();code=issue(c);post(c,'/account/forgot-password',{'email':'audit@example.invalid'});raw=extract_token('reset')
    stamp=store.now();monkeypatch.setattr(store,'now',lambda:stamp+90000)
    with pytest.raises(ValueError):store.consume(raw,'reset',lambda c,row:pytest.fail('Expired token executed an action'))
    with pytest.raises(ValueError):store.quotation([line()],'NL',code,account_id(c))

def test_administration_requires_authorization_and_keeps_campaign_inactive(monkeypatch):
    c=app.test_client();assert c.get('/admin/commerce').status_code==303
    monkeypatch.setenv('NUVEMIXA_ADMIN_PASSWORD_HASH',generate_fake_hash())
    with c.session_transaction() as s:s['nv_admin']=True
    assert c.get('/admin/commerce').status_code==200
    assert post(c,'/admin/commerce/campaign',{'id':'welcome','data':json.dumps(campaign(active=False))}).status_code==303
    assert store.records('nv_campaigns')['welcome']['active'] is False
    assert c.get('/admin/commerce/banner-preview').status_code==200
    assert b'nv-promo-banner wrap' not in c.get('/').data

def test_publication_requires_evidence_then_offer_is_shared(monkeypatch):
    c=app.test_client();id='/gadgets/draadloze-bluetooth-oordopjes'
    with pytest.raises(ValueError):store.publish(id)
    store.save_record('nv_suppliers','audit',{'approved':True,'evidence':'Fictieve testleverancier'})
    data={'demo':False,'published':False,'sku':'TEST-ONLY-SKU','brand':'Fictief testmerk','supplier_id':'audit','name_nl':'Fictief testartikel','name_en':'Fake test item','description_nl':'Uitsluitend fictieve gecontroleerde testgegevens.','description_en':'Fictitious controlled test information only.','image':'/static/favicon.svg','specifications':{'test':'fictief'},'delivery_nl':'Fictieve testtermijn','delivery_en':'Fictitious test period','safety':'Fictief testdocument','price_cents':3000,'stock':3,'vat_bps':2100,'variants':[]}
    for flag in ['supplier_verified','price_verified','image_verified','data_verified','delivery_verified','safety_verified']:data[flag]=True
    data['offer']={'active':True,'start':store.now()-1,'end':store.now()+60,'verified':True,'price_cents':2500,'reference_cents':3000,'reference_evidence':'Uitsluitend testbewijs'}
    store.save_record('nv_products',id,data);store.publish(id)
    assert b'Fictief testartikel' in c.get('/aanbiedingen').data
    post(c,'/winkelwagen',{'action':'add','product_id':'1'})
    with app.test_request_context('/'):
        app.preprocess_request()
        p=mod.find_product('1');assert p['price_cents']==2500 and p['demo'] is False
    stamp=store.now();monkeypatch.setattr(store,'now',lambda:stamp+61)
    assert b'Fictief testartikel' not in c.get('/aanbiedingen').data

def test_curated_cart_recommendations_are_existing_and_bounded():
    c=app.test_client()
    with app.test_request_context('/'):
        app.preprocess_request();p=next(p for p in mod.load_all_products() if p['slug']=='yogamat')
        suggested=mod.nv_recommendations([p])
        assert 1<=len(suggested)<=4 and all(q['id']!=p['id'] for q in suggested)
        assert all(mod.find_product(q['id']) is not None and q['reason'] for q in suggested)
    post(c,'/winkelwagen',{'action':'add','product_id':str(p['id'])})
    assert b'Bijpassende producten' in c.get('/winkelwagen').data

def test_all_public_pages_products_and_templates_render():
    c=app.test_client()
    pages=['/','/shop','/aanbiedingen','/account','/wishlist','/winkelwagen','/contact','/faq','/meer','/bestellen','/retouren','/voorwaarden','/privacy','/cookies','/over-nuvemixa','/herroepen','/herroepingsformulier','/offline']+['/'+k for k in mod.CATEGORIES]
    for locale in ['nl','en']:
        for path in pages:
            r=c.get(path+'?lang='+locale);assert r.status_code==200,(path,r.status_code)
            assert ('<html lang="'+locale+'"').encode() in r.data
    with app.test_request_context('/'):
        app.preprocess_request();products=mod.load_all_products()
    for p in products:assert c.get(p['product_url']).status_code==200,p['product_url']
    for name in app.jinja_env.list_templates():
        if name.endswith('.html'):app.jinja_env.get_template(name)

def test_sitemap_canonical_redirect_and_svg_integrity():
    c=app.test_client();r=c.get('/sitemap.xml');assert b'/over-trendmix<' not in r.data and b'/shop<' in r.data
    assert c.get('/over-trendmix').status_code==301
    page=c.get('/smart-home?lang=en').get_data(as_text=True)
    assert 'href="http://localhost/smart-home?lang=en"' in page
    assert '<path' in page and '/>' in page
    import re
    policy=c.get('/account').headers['Content-Security-Policy'];assert 'nonce-' in policy

def test_largest_remainder_never_overdiscounts_small_lines():
    weights=[6]*39+[1];cuts=store.allocate(47,weights)
    assert sum(cuts)==47 and all(0<=x<=w for x,w in zip(cuts,weights))
    with pytest.raises(ValueError):store.allocate(2,[1])

def test_full_refund_vat_lines_reconcile_after_partial_refund():
    items=[line(product_id='1',unit_cents=6,vat_bps=900),line(product_id='2',unit_cents=1234,vat_bps=2100),line(product_id='3',unit_cents=1,vat_bps=0)]
    o=store.create_order(items,addr(),None,'owner','idempotency-key-1');store.transition(o['id'],'pay-event-refund','paid')
    store.refund(o['id'],1,'partial-refund-1');store.refund(o['id'],1240,'remaining-refund-2')
    with store.db() as c:
        r=c.execute('SELECT SUM(amount_cents),SUM(vat_cents) FROM nv_refund_lines WHERE order_id=?',(o['id'],)).fetchone()
        assert r[0]==1241 and r[1]==json.loads(o['totals'])['vat_cents']

def test_event_id_cannot_be_reused_for_another_order():
    a=store.create_order([line()],addr(),None,'owner','idempotency-key-1');b=store.create_order([line()],addr(),None,'owner','idempotency-key-2')
    store.transition(a['id'],'same-event-id','paid')
    with pytest.raises(ValueError):store.transition(b['id'],'same-event-id','paid')
    with pytest.raises(ValueError):store.transition(a['id'],'same-event-id','cancelled')

def test_mail_adapter_never_sends_test_messages(monkeypatch):
    import nv_mail
    assert nv_mail.enabled() is False
    with pytest.raises(RuntimeError):nv_mail.dispatch('fake')
    c=app.test_client();register(c)
    with store.db() as db:r=db.execute("SELECT id,status FROM nv_mail WHERE kind='verify'").fetchone()
    assert r['status']=='test'
    monkeypatch.setattr(nv_mail,'enabled',lambda:True)
    with pytest.raises(ValueError):nv_mail.dispatch(r['id'])

def test_atomic_ai_budget_across_workers_without_provider_calls():
    def attempt(n):
        try:return store.reserve_ai('0.004','0.004',100)
        except ValueError:return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[1,2]))
    assert sum(x is not None for x in results)==1
    id=next(x for x in results if x);store.settle_ai(id,'0.003')
    with pytest.raises(ValueError):store.reserve_ai('0.002','0.004',100)

def test_private_backup_restore_with_fake_database(tmp_path):
    from tools.manage_storage import snapshot
    source=tmp_path/'source.sqlite3'
    with sqlite3.connect(source) as c:c.execute('CREATE TABLE fixture(value TEXT)');c.execute("INSERT INTO fixture VALUES('fake only')")
    backup=snapshot(source,tmp_path/'backup.sqlite3');restored=snapshot(backup,tmp_path/'restored.sqlite3')
    with sqlite3.connect(restored) as c:assert c.execute('SELECT value FROM fixture').fetchone()[0]=='fake only'
    with pytest.raises(ValueError):snapshot(source,backup)

def test_account_address_is_private_and_prefills_checkout():
    c=app.test_client();register(c);assert post(c,'/account/address',addr()).status_code==303
    post(c,'/winkelwagen',{'action':'add','product_id':'1'})
    assert b'value="Fictieve straat 12"' in c.get('/afrekenen').data
    other=app.test_client();register(other,'other@example.invalid');assert b'Fictieve straat 12' not in other.get('/account').data
    post(c,'/account/logout')
    with c.session_transaction() as s:assert 'nv_guest_owner' not in s and s.get('trendmix_cart')
