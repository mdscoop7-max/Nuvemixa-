"""Local, fail-closed storefront integration. All payments and mail are simulations."""
import functools
import hashlib
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from flask import abort, g, has_request_context, make_response, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import nv_store as store

def register(mod):
    app=mod.app
    def lang():return getattr(g,'nv_language','nl')
    def tr(nl,en):return en if lang()=='en' else nl
    def customer():return mod._current_customer()
    def client_key():
        # Never trust arbitrary X-Forwarded-For. ProxyFix may be configured at deployment only.
        return request.remote_addr or 'unknown'
    def auth_session(id):
        keep={k:session[k] for k in ['trendmix_cart','trendmix_wishlist','nv_language','nv_guest_owner'] if k in session}
        session.clear();session.update(keep);session['nv_customer_id']=id
        a=customer();state=store.account(id,a['email']);session['nv_auth_version']=state['auth_version']
        session['trendmix_wishlist']=store.favorites(id,session.get('trendmix_wishlist',[]))
    def page(title,**kwargs):
        return render_template('nv_page.html',title=title,categories=mod.CATEGORIES,**kwargs)
    def error(code,status=400):
        messages={
            'invalid_token':('Deze link is ongeldig, verlopen of al gebruikt. Vraag een nieuwe link aan.','This link is invalid, expired or already used. Request a new link.'),
            'invalid_coupon':('Deze code is niet geldig voor dit account of deze bestelling.','This code is not valid for this account or order.'),
            'unsupported_country':('Het ingevulde bezorgland wordt niet ondersteund.','The delivery country you entered is not supported.'),
            'shipping_unconfigured':('Verzendkosten zijn nog niet bevestigd. Commerciële verkoop is geblokkeerd.','Shipping fees are unconfirmed. Commercial sales are blocked.'),
            'invalid_address':('Controleer je naam, e-mailadres, straat, huisnummer, postcode, plaats en land.','Check your name, email, street, house number, postal code, city and country.'),
            'invalid_transition':('Deze statusovergang is niet toegestaan.','This status transition is not allowed.'),
            'invalid_refund':('Dit terugbetalingsbedrag is niet toegestaan.','This refund amount is not allowed.'),
        }
        return page(tr('Controleer je gegevens','Check your details'),message=tr(*messages.get(str(code),('De handeling kon niet worden uitgevoerd. Controleer de invoer.','The action could not be completed. Check your input.')))),status
    def require_customer(fn):
        @functools.wraps(fn)
        def wrapped(*a,**kw):
            if not customer():return redirect('/account',code=303)
            return fn(*a,**kw)
        return wrapped
    def require_admin(fn):
        @functools.wraps(fn)
        def wrapped(*a,**kw):
            if not mod.admin_is_authenticated():return redirect('/admin/login',code=303)
            return fn(*a,**kw)
        return wrapped
    def request_limit(key,n,seconds=900):
        if not store.limit(key+':'+client_key(),n,seconds):abort(429)
    def email_lookup(email):
        with mod._customer_conn() as c:
            row=c.execute('SELECT id,name,email FROM customers WHERE email=?',(email.casefold(),)).fetchone()
            return dict(row) if row else None
    original_enrich=mod.enrich_product
    def enrich(raw,category,index):
        p=original_enrich(raw,category,index)
        changes=getattr(g,'nv_product_overrides',{}) if has_request_context() else store.records('nv_products')
        data=changes.get(p['product_url'],{})
        suppliers=getattr(g,'nv_supplier_overrides',{}) if has_request_context() else store.records('nv_suppliers')
        real=data.get('published') is True and not store.publication_errors(data,suppliers)
        p.update(demo=not real,price_cents=store.cents(p['price']),vat_bps=2100,published=real)
        if real:
            unit,ref=store.price(data)
            p.update(name=data['name_nl'],en_name=data['name_en'],description=data['description_nl'],en_description=data['description_en'],short_description=data['description_nl'][:180],en_short_description=data['description_en'][:180],price_cents=unit,price=store.money(unit),old_price=store.money(ref) if ref else None,on_offer=bool(ref),stock_status='in_stock' if data['stock']>0 else 'out_of_stock',stock_quantity=data['stock'],image=data['image'],images=[data['image']],brand=data['brand'],specifications=data['specifications'],delivery_time=tr(data['delivery_nl'],data['delivery_en']),vat_bps=data['vat_bps'],sku=data['sku'],variants=data.get('variants',[]),safety=data['safety'])
        p['price']=store.money(p['price_cents'])
        if has_request_context() and request.path==p['product_url']:
            g.nv_product_meta={'title':(p['en_name'] if lang()=='en' else p['name'])+' | NUVEMIXA','description':p['en_short_description'] if lang()=='en' else p['short_description']}
        return p
    mod.enrich_product=enrich
    original_cart=mod.cart_items
    def cart_items():
        rows=original_cart()
        for p in rows:
            source=mod.find_product(p['id'])
            p.update(price=store.money(source['price_cents']),unit_cents=source['price_cents'],product_id=str(source['id']),demo=source['demo'],vat_bps=source['vat_bps'],category=source['category_slug'],product_url=source['product_url'],on_offer=bool(source.get('old_price')),stock_status=source['stock_status'])
        return rows
    mod.cart_items=cart_items
    mod.cart_total=lambda:sum((p['price']*p['qty'] for p in cart_items()),Decimal('0.00'))
    mod.format_eur=lambda amount:'€'+format(Decimal(str(amount)),'.2f').replace('.',',')
    mod.live_orders_enabled=lambda:False
    mod.app.config['NUVEMIXA_LIVE_PAYMENTS']=False
    app.jinja_env.filters['from_json']=json.loads
    from werkzeug.exceptions import HTTPException
    @app.errorhandler(HTTPException)
    def public_error(exc):
        import html
        en=request.args.get('lang',request.cookies.get('nv_language','nl'))=='en'
        messages={400:('Controleer de invoer.','Check your input.'),403:('Deze handeling is niet toegestaan. Vernieuw de pagina en probeer opnieuw.','This action is not allowed. Reload the page and try again.'),404:('Deze pagina is niet gevonden.','This page was not found.'),413:('De invoer is te groot.','The submitted content is too large.'),429:('Te veel pogingen. Probeer het later opnieuw.','Too many attempts. Please try again later.'),503:('Deze functie is nog niet beschikbaar. Echte betalingen blijven uitgeschakeld.','This feature is not yet available. Real payments remain disabled.')}
        message=messages.get(exc.code,('De aanvraag kon niet worden verwerkt.','The request could not be processed.'))[1 if en else 0]
        return ('<!doctype html><html lang="'+('en' if en else 'nl')+'"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NUVEMIXA</title><main><h1>'+str(exc.code)+'</h1><p>'+html.escape(message)+'</p><a href="/">NUVEMIXA home</a></main></html>',exc.code)

    @app.before_request
    def platform_context():
        g.nv_language=request.args.get('lang') if request.args.get('lang') in ['nl','en'] else request.cookies.get('nv_language','nl')
        if g.nv_language not in ['nl','en']:g.nv_language='nl'
        g.nv_product_overrides=store.records('nv_products')
        g.nv_supplier_overrides=store.records('nv_suppliers')
        g.nv_nonce=secrets.token_urlsafe(20)
        # No arbitrary static archives or secret/binary payloads are public.
        if request.path.startswith('/static/') and re.search(r'\.bin$|\.bak|backup|before-|\.sqlite|\.log$',request.path,re.I):abort(404)
        if session.get('nv_customer_id'):
            a=customer()
            if a:
                state=store.account(a['id'],a['email'])
                if session.get('nv_auth_version',0)!=state['auth_version']:
                    session.pop('nv_customer_id',None)
                else:session['trendmix_wishlist']=store.favorites(a['id'])
        if request.method=='POST':
            if request.path in ['/account/register','/account/forgot-password','/account/resend-verification']:request_limit(request.path,6)
            if request.path=='/account/login':request_limit('customer-login',8)
            if request.path=='/admin/login':request_limit('admin-login',6)
            if request.path=='/contact':request_limit('contact',5)
            if request.path in ['/reviews','/review-purchase']:request_limit('review',5,86400)
            if request.path=='/api/trendmix-assistant':request_limit('assistant',12,60)

    @app.context_processor
    def context():
        camp=store.active_campaign('welcome')
        review_campaign=store.active_campaign('review')
        return {'nv_tr':tr,'nv_lang':lang(),'nv_welcome':camp[1] if camp else None,'nv_review_campaign':review_campaign[1] if review_campaign else None,'nv_company':store.setting('company',{}),'nv_demo_notice':True,'nv_money':lambda n:mod.format_eur(store.money(n)),'nv_csrf':mod.csrf_token,'nv_admin_authenticated':mod.admin_is_authenticated()}

    def account_view():
        a=customer();state=store.account(a['id'],a['email']) if a else None
        orders=[]
        if a:
            with store.db() as c:orders=[dict(r) for r in c.execute('SELECT id,status,totals,created,refunded FROM nv_orders WHERE customer_id=? ORDER BY created DESC',(a['id'],))]
        return render_template('nv_account.html',categories=mod.CATEGORIES,customer=a,state=state,orders=orders,account_error=None)
    def register_customer():
        name=request.form.get('name','').strip();email=request.form.get('email','').strip().casefold();pw=request.form.get('password','')
        if not 1<=len(name)<=100 or not re.fullmatch(r'[^@\s]{1,64}@[^@\s]{1,185}\.[^@\s]{2,}',email) or not 12<=len(pw)<=128 or pw!=request.form.get('password_confirm'):
            return error('invalid_address')
        try:
            with mod._customer_conn() as c:cur=c.execute('INSERT INTO customers(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(pw,method='scrypt')));id=cur.lastrowid
        except sqlite3.IntegrityError:return error('invalid_address')
        auth_session(id);store.token(customer(),'verify',lang());return redirect('/account?notice=verification',code=303)
    def login():
        email=request.form.get('email','').strip().casefold();pw=request.form.get('password','')
        if len(email)>254 or not 1<=len(pw)<=128:return error('invalid_token',401)
        with mod._customer_conn() as c:row=c.execute('SELECT id,password_hash FROM customers WHERE email=?',(email,)).fetchone()
        if not row or not check_password_hash(row['password_hash'],pw):return error('invalid_token',401)
        auth_session(row['id']);return redirect('/account',code=303)
    def logout():
        keep={k:session[k] for k in ['trendmix_cart'] if k in session};session.clear();session.update(keep)
        return redirect('/account',code=303)
    app.view_functions.update(account=account_view,customer_register=register_customer,customer_login=login,customer_logout=logout)

    @app.route('/account/verify-email',methods=['GET','POST'])
    def nv_verify():
        raw=request.values.get('token','')
        if request.method=='GET':return page(tr('E-mailadres verifiëren','Verify email address'),form='verify',token=raw)
        try:store.verify(raw,lang())
        except ValueError as e:return error(e)
        return page(tr('E-mailadres geverifieerd','Email address verified'),message=tr('Je e-mailadres is bevestigd. Een eventuele actieve welkomstactie wordt één keer verwerkt. E-mails staan in de lokale testpostbus.','Your email is confirmed. Any active welcome campaign is processed once. Emails are in the local test mailbox.'))
    @app.post('/account/resend-verification')
    @require_customer
    def nv_resend():
        if not store.account(customer()['id'],customer()['email'])['verified']:store.token(customer(),'verify',lang())
        return redirect('/account?notice=verification',code=303)
    @app.route('/account/forgot-password',methods=['GET','POST'])
    def nv_forgot():
        if request.method=='POST':
            a=email_lookup(request.form.get('email','')[:254])
            if a:store.token(a,'reset',lang())
            return page(tr('Controleer je e-mail','Check your email'),message=tr('Als dit adres bekend is, is een herstelbericht klaargezet. In deze lokale omgeving wordt niets extern verzonden.','If this address is registered, a reset message has been queued. Nothing is sent externally in this local environment.'))
        return page(tr('Wachtwoord vergeten','Forgot password'),form='forgot')
    @app.route('/account/reset-password',methods=['GET','POST'])
    def nv_reset():
        raw=request.values.get('token','')
        if request.method=='GET':return page(tr('Wachtwoord herstellen','Reset password'),form='reset',token=raw)
        pw=request.form.get('password','')
        if not 12<=len(pw)<=128 or pw!=request.form.get('password_confirm'):return error('invalid_token')
        def reset_action(c,row):
            # ATTACH makes token consumption, auth invalidation and credential change atomic.
            c.execute('ATTACH DATABASE ? AS credentials',(str(mod._CUSTOMER_DB),))
            c.execute('UPDATE credentials.customers SET password_hash=? WHERE id=?',(generate_password_hash(pw,method='scrypt'),row['customer_id']))
            c.execute('UPDATE nv_customers SET auth_version=auth_version+1 WHERE id=?',(row['customer_id'],))
            c.execute('UPDATE nv_tokens SET used=1 WHERE customer_id=?',(row['customer_id'],))
        try:store.consume(raw,'reset',reset_action)
        except ValueError as e:return error(e)
        return page(tr('Wachtwoord gewijzigd','Password changed'),message=tr('Log opnieuw in met je nieuwe wachtwoord.','Sign in again with your new password.'))
    @app.post('/account/settings')
    @require_customer
    def nv_settings():
        a=customer();pw=request.form.get('current_password','');name=request.form.get('name','').strip()
        if not 1<=len(name)<=100 or len(pw)>128:return error('invalid_address')
        with mod._customer_conn() as c:
            row=c.execute('SELECT password_hash FROM customers WHERE id=?',(a['id'],)).fetchone()
            if not check_password_hash(row[0],pw):return error('invalid_token',403)
            c.execute('UPDATE customers SET name=? WHERE id=?',(name,a['id']))
        return redirect('/account',code=303)

    old_wishlist=app.view_functions['wishlist']
    def wishlist():
        response=old_wishlist()
        if request.method=='POST' and customer():store.set_favorites(customer()['id'],session.get('trendmix_wishlist',[]))
        return response
    app.view_functions['wishlist']=wishlist
    old_cart=app.view_functions['winkelwagen']
    def recommendations(cart):
        selected={str(p['id']) for p in cart};catalog=mod.load_all_products();byid={str(p['id']):p for p in catalog};result=[]
        # Explicit editorial relationships only; never infer compatibility from a category.
        defaults=json.loads((Path(__file__).parent/'content/product-relations.json').read_text(encoding='utf-8'))
        relations=store.setting('recommendations',defaults)
        for p in cart:
            for relation in relations.get(p.get('product_url',''),[]):
                other=byid.get(str(relation.get('product_id'))) or next((p for p in catalog if p['product_url']==relation.get('product_url')),None)
                if other and str(other['id']) not in selected and relation.get('reason_nl') and relation.get('reason_en'):
                    if relation.get('compatible') and not relation.get('evidence'):continue
                    result.append(dict(other,reason=tr(relation['reason_nl'],relation['reason_en'])))
                    selected.add(str(other['id']))
        return result[:4]
    def current_quote(rows,country='NL'):
        a=customer()
        return store.quotation(rows,country,session.get('nv_coupon',''),a['id'] if a else None)
    def cart():
        if request.method=='POST':
            action=request.form.get('action')
            if action in ['apply_coupon','remove_coupon']:
                if action=='remove_coupon':session.pop('nv_coupon',None)
                else:
                    a=customer();code=request.form.get('coupon','').strip()
                    try:store.quotation(cart_items(),'NL',code,a['id'] if a else None)
                    except ValueError as e:return error(e)
                    if code:session['nv_coupon']=code
                    else:session.pop('nv_coupon',None)
                session.pop('nv_checkout_key',None)
                return redirect('/winkelwagen',code=303)
            p=mod.find_product(request.form.get('product_id',''))
            if p and not p['demo'] and action in ['add','change']:
                existing=next((r['qty'] for r in cart_items() if str(r['id'])==str(p['id'])),0)
                try:desired=existing+(1 if action=='add' else int(request.form.get('delta',0)))
                except ValueError:return error('invalid_address')
                if desired>int(p.get('stock_quantity') or 0):return error('insufficient_stock')
            session.pop('nv_checkout_key',None)
            if action=='clear':session.pop('nv_coupon',None)
            return old_cart()
        rows=cart_items();quote=None;coupon_error=False
        if rows:
            try:quote=current_quote(rows)
            except ValueError as exc:
                if str(exc)=='invalid_coupon':
                    session.pop('nv_coupon',None);coupon_error=True;quote=current_quote(rows)
                elif str(exc)!='shipping_unconfigured':return error(exc)
        else:session.pop('nv_coupon',None)
        return render_template('nv_cart.html',categories=mod.CATEGORIES,cart=rows,cart_total=mod.cart_total(),quote=quote,coupon_error=coupon_error,recommendations=recommendations(rows))
    app.view_functions['winkelwagen']=cart
    def offers():
        products=[p for p in mod.load_all_products() if p.get('published') and not p.get('demo') and p.get('old_price')]
        return render_template('offers.html',products=products,category='Aanbiedingen',search='',categories=mod.CATEGORIES,deals_page=True)
    app.view_functions['deals']=offers
    def sitemap():
        from xml.sax.saxutils import escape
        from nv_presentation import site
        urls=['/','/shop','/aanbiedingen','/faq','/contact','/over-nuvemixa','/bestellen','/retouren','/voorwaarden','/privacy','/cookies']+['/'+c for c in mod.CATEGORIES]+[p['product_url'] for p in mod.load_all_products()]
        xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(site()+p)+'</loc></url>' for p in urls)+'</urlset>'
        return mod.Response(xml,mimetype='application/xml')
    app.view_functions['sitemap']=sitemap
    def address():
        a={k:request.form.get(k,'').strip() for k in ['first_name','last_name','email','address_1','postcode','city','country']}
        a['email']=a['email'].casefold()
        country=a['country'].casefold()
        aliases={'nederland':'NL','netherlands':'NL','nl':'NL','belgië':'BE','belgie':'BE','belgium':'BE','belgique':'BE','be':'BE'}
        a['country']=aliases.get(country,a['country'].upper())
        if not all(a.values()) or any(len(v)>254 for v in a.values()) or not re.fullmatch(r'[^@\s]{1,64}@[^@\s]{1,185}\.[^@\s]{2,}',a['email']):raise ValueError('invalid_address')
        if a['country'] not in store.setting('shipping',{'NL':None,'BE':None}):raise ValueError('unsupported_country')
        pattern={'NL':r'[1-9][0-9]{3}\s?[A-Za-z]{2}','BE':r'[1-9][0-9]{3}'}
        if a['country'] in pattern and not re.fullmatch(pattern[a['country']],a['postcode']):raise ValueError('invalid_address')
        if not re.search(r'\d',a['address_1']) or len(a['city'])<2:raise ValueError('invalid_address')
        return a
    def quote_country(value):
        return {'nederland':'NL','netherlands':'NL','belgië':'BE','belgie':'BE','belgium':'BE','belgique':'BE'}.get(value.casefold(),value.upper())
    def checkout_quote(rows):
        a=customer();code=request.form.get('coupon',session.get('nv_coupon','')).strip()
        country=quote_country(request.form.get('country','NL').strip() or 'NL')
        result=store.quotation(rows,country,code,a['id'] if a else None)
        if code:session['nv_coupon']=code
        else:session.pop('nv_coupon',None)
        return result
    @app.post('/checkout/quote')
    def nv_checkout_quote():
        rows=cart_items()
        if not rows:abort(400)
        try:quote=checkout_quote(rows)
        except ValueError as e:return {'error':str(e)},400
        response=make_response({'html':render_template('_nv_price_summary.html',quote=quote),'total_cents':quote['total_cents']})
        response.headers['Cache-Control']='private, no-store';response.headers['X-Robots-Tag']='noindex, nofollow';return response
    def checkout():
        rows=cart_items()
        if not rows:return redirect('/winkelwagen',code=303)
        owner=session.setdefault('nv_guest_owner',secrets.token_urlsafe(32));a=customer()
        if request.method=='POST':
            try:
                quote=checkout_quote(rows)
                if request.form.get('action')!='quote':
                    if request.form.get('checkout_consent')!='yes':return error('invalid_address')
                    addr=address();oid=store.create_order(rows,addr,a['id'] if a else None,owner,request.form.get('idempotency',''),request.form.get('coupon',session.get('nv_coupon','')),lang())
                    return redirect('/orders/'+oid['id'],code=303)
            except ValueError as e:return error(e)
        else:
            try:quote=current_quote(rows)
            except ValueError as e:return error(e)
        nonce=session.setdefault('nv_checkout_key',secrets.token_urlsafe(24))
        profile=dict(request.form) if request.method=='POST' else json.loads(store.account(a['id'],a['email'])['profile']) if a else {}
        return render_template('nv_checkout.html',categories=mod.CATEGORIES,cart=rows,quote=quote,idempotency=nonce,countries=store.setting('shipping',{'NL':None,'BE':None}),customer=a,profile=profile)
    app.view_functions['afrekenen']=checkout
    @app.post('/account/address')
    @require_customer
    def nv_address_settings():
        try:data=address()
        except ValueError as e:return error(e)
        with store.db(True) as c:c.execute('UPDATE nv_customers SET profile=? WHERE id=?',(json.dumps(data),customer()['id']))
        return redirect('/account',code=303)
    def owned_order(id):
        with store.db() as c:r=c.execute('SELECT * FROM nv_orders WHERE id=?',(id,)).fetchone()
        if not r:abort(404)
        a=customer()
        if not ((a and r['customer_id']==a['id']) or (not r['customer_id'] and r['owner_hash']==store.digest(session.get('nv_guest_owner','')))):abort(404)
        return dict(r)
    @app.get('/orders/<id>')
    def nv_order(id):
        order=owned_order(id)
        if order['status']=='pending' and order['expires']<=store.now():order=store.transition(id,'expiry:'+id,'expired')
        return render_template('nv_order.html',categories=mod.CATEGORIES,order=order,totals=json.loads(order['totals']),items=json.loads(order['items']),address=json.loads(order['address']))
    @app.get('/orders/<id>/receipt')
    def nv_receipt(id):
        order=owned_order(id)
        return render_template('nv_receipt.html',categories=mod.CATEGORIES,order=order,totals=json.loads(order['totals']),items=json.loads(order['items']),address=json.loads(order['address']),order_date=datetime.fromtimestamp(order['created'],timezone.utc).strftime('%d-%m-%Y %H:%M UTC'))
    @app.post('/orders/<id>/simulate')
    def nv_simulate(id):
        owned_order(id);target=request.form.get('event','')
        if target not in ['paid','cancelled','failed','expired']:abort(400)
        try:store.transition(id,'sim:'+id+':'+target,target)
        except ValueError as e:return error(e)
        if target=='paid':session.pop('trendmix_cart',None);session.pop('nv_checkout_key',None)
        return redirect('/orders/'+id,code=303)
    @app.get('/account/orders')
    @require_customer
    def nv_orders():return redirect('/account#orders',code=303)
    @app.post('/payments/webhook')
    def nv_webhook():
        # No public endpoint can mint a paid state. Implement signed provider adapter only after acceptance.
        abort(503)

    @app.route('/review-purchase',methods=['GET','POST'])
    @require_customer
    def nv_review_purchase():
        raw=request.values.get('token','')
        if request.method=='POST':
            if request.form.get('consent')!='1':return error('invalid_token')
            try:store.purchase_review(raw,customer()['id'],int(request.form.get('rating',0)),request.form.get('body','').strip(),lang())
            except ValueError as e:return error(e)
            return page(tr('Bedankt voor je eerlijke review','Thank you for your honest review'),message=tr('De beloning hangt nooit af van je sterren of publicatie. Een simulatiereview wordt nooit als echte aankoopreview gepubliceerd.','Your reward never depends on your rating or publication. A simulated review is never published as a genuine purchase review.'))
        return page(tr('Je eerlijke ervaring','Your honest experience'),form='review',token=raw)
    original_returns=app.view_functions['retouren']
    def returns_view():
        fields=['name','email','order_number','product','reason']
        g.nv_return_values={key:request.form.get(key,'').strip() for key in fields}
        g.nv_return_errors=[];g.nv_return_validated=False
        if request.method=='POST':
            data=g.nv_return_values
            if not 1<=len(data['name'])<=120:g.nv_return_errors.append(tr('Vul je naam in (maximaal 120 tekens).','Enter your name (up to 120 characters).'))
            if not re.fullmatch(r'[^@\s]{1,64}@[^@\s]{1,185}\.[^@\s]{2,}',data['email']):g.nv_return_errors.append(tr('Vul een geldig e-mailadres in.','Enter a valid email address.'))
            if len(data['order_number'])>80 or not re.fullmatch(r'#?[A-Za-z0-9][A-Za-z0-9 ._/-]{0,79}',data['order_number']):g.nv_return_errors.append(tr('Vul een geldig bestelnummer in (maximaal 80 tekens).','Enter a valid order number (up to 80 characters).'))
            if not 1<=len(data['product'])<=200:g.nv_return_errors.append(tr('Vul het product in (maximaal 200 tekens).','Enter the product (up to 200 characters).'))
            if len(data['reason'])>2000:g.nv_return_errors.append(tr('De retourreden mag maximaal 2000 tekens bevatten.','The return reason must be at most 2000 characters.'))
            g.nv_return_validated=not g.nv_return_errors
        # Local validation only: no database, mail, order or return-state mutation.
        return make_response(original_returns(),400 if g.nv_return_errors else 200)
    app.view_functions['retouren']=returns_view

    @app.route('/herroepen',methods=['GET','POST'])
    def nv_withdraw():
        if request.method=='POST':
            request_limit('withdrawal',6)
            if request.form.get('confirm')!='yes':return error('invalid_address')
            receipt=store.withdraw(request.form.get('order_id','')[:100],request.form.get('email','')[:254],customer()['id'] if customer() else None,lang())
            if not receipt:return error('invalid_address')
            return page(tr('Herroepingsmelding ontvangen','Withdrawal notice received'),message=tr('Als de bestelgegevens overeenkomen, is je verklaring met datum en tijd geregistreerd en een ontvangstbevestiging klaargezet. Dit betreft uitsluitend lokale simulatieorders.','If the order details match, your declaration has been recorded with a timestamp and an acknowledgement queued. This covers local simulation orders only.'))
        return page(tr('Overeenkomst herroepen','Withdraw from a contract'),form='withdrawal')
    @app.get('/herroepingsformulier')
    def nv_withdraw_form():return page(tr('Modelformulier voor herroeping','Model withdrawal form'),form='model')

    def contact():
        if request.method=='POST':
            if request.form.get('website'):return redirect('/contact?queued=1',code=303)
            email=request.form.get('email','').strip();name=request.form.get('name','').strip();body=request.form.get('message','').strip()
            if not re.fullmatch(r'[^@\s]{1,64}@[^@\s]{1,185}\.[^@\s]{2,}',email) or not 1<=len(name)<=120 or not 10<=len(body)<=5000:return error('invalid_address')
            with store.db(True) as c:store.queue(c,None,'local-support@example.invalid','contact','NUVEMIXA — Contact',name+'\n'+email+'\n'+body,lang(),'contact:'+secrets.token_urlsafe(20))
            if request.args.get('ajax')=='1':return {'ok':True,'mode':'local_test'}
            return page(tr('Bericht lokaal opgeslagen','Message saved locally'),message=tr('Je bericht staat in de lokale testpostbus. Er is geen externe e-mail verstuurd.','Your message is in the local test mailbox. No external email was sent.'))
        return page('Contact',form='contact')
    app.view_functions['contact']=contact
    app.view_functions['contact_page']=contact
    # Never let old optional mail or paid AI paths cause an external side effect.
    mod.nv_send_mail=lambda *a,**kw:False
    import nv_openai
    nv_openai.configured=lambda:False

    @app.get('/admin/commerce')
    @require_admin
    def nv_admin():
        with store.db() as c:
            orders=[dict(r) for r in c.execute('SELECT id,status,created,refunded,totals FROM nv_orders ORDER BY created DESC LIMIT 100')]
            mails=[dict(r) for r in c.execute('SELECT id,subject,kind,status,created FROM nv_mail ORDER BY created DESC LIMIT 100')]
            reviews=[dict(r) for r in c.execute('SELECT * FROM nv_purchase_reviews ORDER BY id DESC LIMIT 100')]
        return render_template('nv_admin.html',categories=mod.CATEGORIES,catalog=mod.load_all_products(),products=store.records('nv_products'),suppliers=store.records('nv_suppliers'),campaigns=store.records('nv_campaigns'),orders=orders,mails=mails,purchase_reviews=reviews,company=store.setting('company',{}),shipping=store.setting('shipping',{'NL':None,'BE':None}),relations=store.setting('recommendations',{}))
    def control_entry():
        return redirect('/admin/commerce' if mod.admin_is_authenticated() else '/admin/login')
    app.view_functions['control']=control_entry
    @app.post('/admin/commerce/<kind>')
    @require_admin
    def nv_admin_save(kind):
        try:
            if kind in ['product','supplier','campaign']:
                data=json.loads(request.form['data']) if 'data' in request.form else dict(request.form);id=request.form.get('id','').strip()
                if not isinstance(data,dict) or not id or len(id)>254:raise ValueError('invalid_data')
                def date(value):return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())
                if kind=='campaign':
                    if 'data' not in request.form:
                        data.update(percent=int(data['percent']),active=data.get('active')=='1',start_iso=data['start'],end_iso=data['end'],start=date(data['start']),end=date(data['end']),valid_days=int(data.get('valid_days',30)),minimum_cents=store.cents(data.get('minimum','0').replace(',','.')),maximum_discount_cents=store.cents(data['maximum'].replace(',','.')) if data.get('maximum') else None,excluded_products=[x.strip() for x in data.get('excluded_products','').split(',') if x.strip()],excluded_categories=[x.strip() for x in data.get('excluded_categories','').split(',') if x.strip()],include_offers=data.get('include_offers')=='1')
                    store.campaign_valid(data)
                if kind=='supplier' and 'data' not in request.form:
                    data['approved']=data.get('approved')=='1'
                    if data['approved'] and not data.get('evidence'):raise ValueError('verification_evidence_required')
                if kind=='product':
                    if id not in {p['product_url'] for p in mod.load_all_products()}:raise ValueError('unknown_product')
                    if 'data' not in request.form:
                        data.update(demo=data.get('real')!='1',price_cents=store.cents((data.get('price') or '0').replace(',','.')),stock=int(data.get('stock',0)),vat_bps=int(data.get('vat_bps',2100)),specifications=dict(line.split(':',1) for line in data.get('specifications_text','').splitlines() if ':' in line),variants=[x.strip() for x in data.get('variants_text','').splitlines() if x.strip()])
                        for flag in ['supplier_verified','price_verified','image_verified','data_verified','delivery_verified','safety_verified']:data[flag]=data.get(flag)=='1'
                        if data.get('offer_start') and data.get('offer_end'):
                            data['offer']={'active':data.get('offer_active')=='1','start':date(data['offer_start']),'end':date(data['offer_end']),'start_iso':data['offer_start'],'end_iso':data['offer_end'],'price_cents':store.cents((data.get('offer_price') or '0').replace(',','.')),'reference_cents':store.cents((data.get('reference_price') or '0').replace(',','.')),'reference_evidence':data.get('reference_evidence',''),'verified':data.get('offer_verified')=='1'}
                    data['published']=False # Every edit returns to draft; approval is explicit.
                    if data.get('sku') and any(p.get('sku')==data['sku'] for key,p in store.records('nv_products').items() if key!=id):raise ValueError('duplicate_sku')
                data.pop('_csrf_token',None)
                store.save_record({'product':'nv_products','supplier':'nv_suppliers','campaign':'nv_campaigns'}[kind],id,data)
            elif kind=='publish':store.publish(request.form.get('id',''))
            elif kind in ['company','shipping','recommendations']:
                data=json.loads(request.form['data']) if 'data' in request.form else dict(request.form)
                if not isinstance(data,dict):raise ValueError('invalid_data')
                if 'data' not in request.form:
                    if kind=='company':data={k:v for k,v in data.items() if k!='_csrf_token'};data['legal_reviewed']=data.get('legal_reviewed')=='1'
                    elif kind=='shipping':data={k:store.cents(request.form[k].replace(',','.')) if request.form.get(k) else None for k in ['NL','BE']}
                    else:
                        current=store.setting('recommendations',{});source=data['source'];target=data['target']
                        catalog=mod.load_all_products();sourcep=next((p for p in catalog if p['product_url']==source),None);targetp=next((p for p in catalog if str(p['id'])==target),None)
                        if not sourcep or not targetp or str(sourcep['id'])==target:raise ValueError('invalid_relationship')
                        if data.get('compatible')=='1' and not data.get('evidence'):raise ValueError('compatibility_evidence_required')
                        relation={k:data.get(k,'') for k in ['reason_nl','reason_en','evidence']};relation.update(product_id=target,compatible=data.get('compatible')=='1')
                        current[source]=[r for r in current.get(source,[]) if str(r['product_id'])!=target]+[relation];data=current
                if kind=='shipping' and any(k not in ['NL','BE'] or (v is not None and (not isinstance(v,int) or v<0)) for k,v in data.items()):raise ValueError('invalid_shipping')
                store.configure(kind,data)
            elif kind=='order':
                id=request.form.get('id','');target=request.form.get('status','')
                if target=='refund':store.refund(id,int(request.form.get('amount_cents',0)),request.form.get('event_id',''))
                else:
                    store.transition(id,request.form.get('event_id',''),target)
                    if target=='fulfilled' and store.active_campaign('review'):
                        with store.db() as c:
                            eligible=c.execute('SELECT u.verified FROM nv_orders o JOIN nv_customers u ON u.id=o.customer_id WHERE o.id=?',(id,)).fetchone()
                        if eligible and eligible['verified']:store.invite_review(id,lang())
            elif kind=='review':
                # Simulated reviews cannot be promoted to real public reviews.
                with store.db(True) as c:
                    id=int(request.form.get('id',0));row=c.execute('SELECT * FROM nv_purchase_reviews WHERE id=?',(id,)).fetchone()
                    if not row or not row['verified']:raise ValueError('simulation_review_not_publishable')
                    status=request.form.get('status')
                    if status not in ['published','hidden']:raise ValueError('invalid_status')
                    if status=='hidden' and not request.form.get('reason','').strip():raise ValueError('reason_required')
                    c.execute('UPDATE nv_purchase_reviews SET status=? WHERE id=?',(status,id));store.audit(c,'review:'+status+':'+request.form.get('reason','')[:200],id)
            else:abort(404)
        except (ValueError,TypeError,KeyError) as e:return page(tr('Controleer de beheerinvoer','Check admin input'),message=str(e)),400
        return redirect('/admin/commerce',code=303)
    @app.get('/admin/commerce/mail/<id>')
    @require_admin
    def nv_mail_preview(id):
        with store.db() as c:r=c.execute('SELECT * FROM nv_mail WHERE id=?',(id,)).fetchone()
        if not r:abort(404)
        return page(tr('Lokale e-mailpreview — niet verzonden','Local email preview — not sent'),mail=dict(r))
    @app.get('/admin/commerce/readiness.json')
    @require_admin
    def nv_readiness():return store.readiness()
    @app.get('/admin/commerce/banner-preview')
    @require_admin
    def nv_banner_preview():
        return render_template('nv_banner_preview.html',categories=mod.CATEGORIES,nv_banner_preview=True)
    @app.get('/service-worker.js')
    def nv_service_worker():
        response=make_response((Path(__file__).parent/'static'/'nv-service-worker.js').read_text(encoding='utf-8'))
        response.mimetype='application/javascript';response.headers['Cache-Control']='no-cache';response.headers['Service-Worker-Allowed']='/'
        return response
    @app.get('/offline')
    def nv_offline():return page(tr('Je bent offline','You are offline'),message=tr('Verbind met internet om actuele producten, prijzen, je account en winkelwagen te gebruiken. Privégegevens worden niet offline opgeslagen.','Connect to the internet for current products, prices, your account and cart. Private information is not stored offline.'))
    @app.get('/reviews/page')
    def nv_public_reviews_page():
        from nv_reviews import review_page,review_stats
        try:result=review_page(request.args.get('cursor',''))
        except ValueError:abort(400)
        result['stats']=review_stats()
        response=make_response(result)
        response.headers['Cache-Control']='no-store'
        return response
    @app.get('/products.json')
    def nv_catalog_json():
        return {'products':[{'id':p['id'],'name':p['en_name'] if lang()=='en' else p['name'],'url':p['product_url'],'demo':p['demo']} for p in mod.load_all_products()]}
    # References in templates and helpers are kept compatible; authority lives here.
    mod.nv_recommendations=recommendations
