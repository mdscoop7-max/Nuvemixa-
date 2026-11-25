import json
from datetime import timedelta
import app
import nv_catalog_manager as catalog
import nv_extra_pricing as pricing
from test_extra_producten import administrator, local_db
from test_nv_extra_editor import submit
from test_system_check import CSRF_TOKEN


def test_base_product_editor_preserves_identity_photos_price_and_private_fields(administrator,local_db):
    with app.app.test_request_context('/dashboard'):
        base=next(p for p in app.catalog_items() if p['category_slug']=='gadgets')
    day=pricing.today()
    settings=dict(slug=base['slug'],name=base['name'],price_mode='auto',price='0',
                  cost_price='0',offer_enabled='1',offer_shop='1',offer_list='1',offer_week='1',
                  sale_price=str(round(base['price']/2,2)),offer_start=day.isoformat(),offer_end=(day+timedelta(days=2)).isoformat(),
                  gallery=json.dumps(base['images']))
    response=submit(administrator,**settings)
    assert response.status_code==200,response.json
    with app.app.test_request_context('/dashboard'):
        saved=next(p for p in app.catalog_items() if p['slug']==base['slug'])
    assert saved['id']==base['id'] and saved['price']==base['price'] and saved['images']==base['images']
    assert not saved['extra']
    feed=app.app.test_client().get('/api/public/catalog').json
    row=next(p for p in feed['products'] if p['slug']==base['slug'])
    assert row['offer_week'] and row['offer_list'] and row['price']==float(settings['sale_price'])
    assert not {'cost_price','margin','price_history','shipping_cost'} & row.keys()
    page=administrator.get('/dashboard?section=extra-producten&view=edit&categorie=gadgets&edit='+base['slug'])
    assert page.status_code==200 and b'name="offer_week" value="1" checked' in page.data
    assert administrator.post('/admin/nv/catalog',data=dict(_csrf_token=CSRF_TOKEN,section='extra-producten',category='gadgets',slug=base['slug'],op='end_offer')).status_code==303
    row=app.app.test_client().get('/api/public/catalog').json['products'][0]
    assert row['price']==base['price'] and not row['offer_week'] and not row['offer_list'] and not row.get('old_price')


def test_week_selection_is_unique_and_invalid_offer_never_saves(administrator,local_db):
    day=pricing.today().isoformat()
    fields=dict(offer_enabled='1',offer_shop='1',offer_list='1',offer_week='1',offer_start=day,offer_end=day,sale_price='10')
    assert submit(administrator,name='Eerste week',**fields).status_code==200
    assert submit(administrator,name='Tweede week',**fields).status_code==200
    feed=app.app.test_client().get('/api/public/catalog').json['products']
    assert [p['name'] for p in feed if p['offer_week']]==['Tweede week']
    bad=submit(administrator,slug='tweede-week',name='Tweede week',**{**fields,'sale_price':'999'})
    assert bad.status_code==422
    assert [p['price'] for p in app.app.test_client().get('/api/public/catalog').json['products']]==[10,10]


def test_all_products_and_extra_overview_are_available(administrator,local_db):
    assert submit(administrator).status_code==200
    for path in ('/dashboard?section=producten','/dashboard?section=extra-producten','/dashboard?section=extra-producten&view=products','/dashboard?section=extra-producten&view=offers'):
        page=administrator.get(path)
        assert page.status_code==200
        assert b'data-filter="category"' in page.data
    assert b'Fotoproef' in administrator.get('/dashboard?section=extra-producten').data
