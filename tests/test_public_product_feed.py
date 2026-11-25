import app
import nv_public_products as public


def test_base_override_updates_without_duplicate_and_preserves_id(monkeypatch):
    category='gadgets'
    original=app.base_products[category][0]
    slug=original.get('slug') or app.slugify(original['name'])
    edit=dict(id='preserved-id',name=original['name'],slug=slug,category_slug=category,extra=False,price=7.50,offer_list=True,offer_week=True,offer_end='2099-12-31',image=original['image'])
    monkeypatch.setattr(public,'fetch_extra_products',lambda:[edit])
    with app.app.test_request_context('/'):
        rows=public.merged_catalog(app.base_products)[category]
        assert len(rows)==len(app.base_products[category])
        assert rows[0]['price']==7.5 and rows[0]['offer_week']
        assert rows[0]['id']==original.get('id','preserved-id')
    response=app.app.test_client().get('/')
    assert response.status_code==200 and 'Aanbieding van de week' in response.text
    assert 'resterend' in response.text
    assert original['name'] in app.app.test_client().get('/aanbiedingen').text
    monkeypatch.setattr(public,'fetch_extra_products',lambda:[])
    response=app.app.test_client().get('/')
    assert 'class="nv-weekly-layout"' not in response.text


def test_hidden_base_product_is_removed_only_from_public_catalog(monkeypatch):
    original=app.base_products['gadgets'][0]
    slug=original.get('slug') or app.slugify(original['name'])
    monkeypatch.setattr(public,'fetch_extra_products',lambda:[dict(category_slug='gadgets',slug=slug,extra=False,hidden=True)])
    with app.app.test_request_context('/'):
        assert len(public.merged_catalog(app.base_products)['gadgets'])==len(app.base_products['gadgets'])-1
    assert app.base_products['gadgets'][0] is original
