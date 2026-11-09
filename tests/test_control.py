from app import CATEGORY_DIRS, app, load_all_products


def secure_post(client, *args, **kwargs):
    """Submit a real storefront CSRF token rather than bypassing protection."""
    client.get("/")
    with client.session_transaction() as data:
        csrf_token = data["_tm_csrf"]
    form = kwargs.pop("data", {}) or {}
    kwargs["data"] = {**form, "_csrf_token": csrf_token}
    return client.post(*args, **kwargs)


def test_control_page_exists():
    client = app.test_client()
    response = client.get("/control")

    assert response.status_code == 200
    assert b"TrendMix Control" in response.data or b"Controle" in response.data


def test_shop_categories_have_20_products_with_images():
    products = load_all_products()
    category_counts = {}

    for product in products:
        category_counts[product.get("category")] = category_counts.get(product.get("category"), 0) + 1

    assert len(category_counts) >= 5

    for category_name, folder_name in CATEGORY_DIRS.items():
        matches = [p for p in products if p.get("category") == category_name]
        assert len(matches) >= 20, f"{category_name} heeft te weinig producten: {len(matches)}"
        assert all(p.get("image") or p.get("image_url") for p in matches), f"{category_name} mist afbeeldingen"


def test_all_main_category_pages_render():
    client = app.test_client()
    for category_slug in CATEGORY_DIRS.values():
        response = client.get(f"/{category_slug}")
        assert response.status_code == 200, f"{category_slug} returned {response.status_code}"


def test_core_customer_pages_render():
    client = app.test_client()
    for path in ("/", "/faq", "/contact", "/over-trendmix", "/bestellen", "/retouren", "/voorwaarden", "/privacy", "/cookies", "/robots.txt", "/sitemap.xml"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_cart_and_checkout_test_flow():
    client = app.test_client()
    product = load_all_products()[0]
    response = secure_post(client, "/winkelwagen", data={"action": "add", "product_id": product["id"]}, follow_redirects=True)
    assert response.status_code == 200
    assert product["name"].encode() in response.data
    response = client.get("/afrekenen")
    assert response.status_code == 200
    assert b"Testmodus" in response.data


def test_catalog_is_exactly_100_products():
    products = load_all_products()
    assert len(products) == 100


def test_homepage_has_hero_image_fallbacks():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"/img/product/" in response.data


def test_sitemap_has_verified_public_collection_urls_only():
    client = app.test_client()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert b"<urlset" in response.data
    assert b"/gadgets</loc>" in response.data
    assert b"/shop</loc>" in response.data
    # Supplier-unverified demo products must not be submitted as live listings.
    assert b"/gadgets/" not in response.data


def test_no_obsolete_affiliate_faq_copy_on_faq_page():
    client = app.test_client()
    response = client.get("/faq")
    assert response.status_code == 200
    assert b"externe aanbieder" not in response.data.lower()
    assert b"affiliate links" not in response.data.lower()


def test_language_bundle_has_no_obsolete_affiliate_store_model():
    from pathlib import Path
    content = Path("static/languages.js").read_text(encoding="utf-8").lower()
    for obsolete in ("independent product catalog", "onafhankelijke productcatalogus", "external retailer", "externe aanbieder"):
        assert obsolete not in content


def test_language_bundle_keeps_all_six_languages():
    from pathlib import Path
    content = Path("static/languages.js").read_text(encoding="utf-8")
    for language in ("nl:", "en:", "de:", "fr:", "it:", "es:"):
        assert language in content


def test_homepage_seo_and_search_action_metadata():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b'"SearchAction"' in response.data
    assert b'property="og:url"' in response.data
    assert b'name="twitter:card"' in response.data


def test_category_pages_have_resilient_images_and_social_metadata():
    client = app.test_client()
    for slug in CATEGORY_DIRS.values():
        response = client.get(f"/{slug}")
        assert response.status_code == 200
        assert b"/img/product/" in response.data
        assert b'property="og:url"' in response.data


def test_product_page_uses_light_theme_and_structured_data():
    client = app.test_client()
    product = load_all_products()[0]
    response = client.get(product["product_url"])
    assert response.status_code == 200
    assert b'<meta name="theme-color" content="#f6f7fb">' in response.data
    assert b'"Product"' in response.data
    assert b'"BreadcrumbList"' in response.data


def test_search_matches_description_content():
    client = app.test_client()
    product = load_all_products()[0]
    words = [w.strip(".,:;()").lower() for w in str(product.get("description") or "").split() if len(w.strip(".,:;()")) > 5]
    assert words
    response = client.get("/?q=" + words[0])
    assert response.status_code == 200
    assert product["name"].encode() in response.data


def test_mobile_navigation_contains_core_shopping_tasks():
    client = app.test_client()
    response = client.get("/")
    for target in (b'tmMobileDrawer', b'tmSmartAssistant', b'/shop', b'/wishlist', b'/aanbiedingen', b'/winkelwagen', b'/contact'):
        assert target in response.data


def test_no_stale_production_trust_claims_in_client_translation_layers():
    from pathlib import Path
    app_js = Path("static/app.js").read_text(encoding="utf-8").lower()
    language_js = Path("static/languages.js").read_text(encoding="utf-8").lower()
    for stale in ("secure payment", "sichere zahlung", "14-day returns", "14 tage rückgabe"):
        assert stale not in app_js
    assert "shopbysubcategory" not in language_js.lower()


def test_base_design_tokens_match_light_storefront():
    from pathlib import Path
    tokens = Path("static/design-tokens.css").read_text(encoding="utf-8").lower()
    assert "--tm-bg:#f6f7fb" in tokens
    assert "--tm-text:#172033" in tokens
    assert "--tm-accent:#6555df" in tokens


def test_rankfix_audit_home_and_categories_have_one_h1():
    client = app.test_client()
    for path in ("/", "/gadgets", "/smart-home", "/beauty-care", "/lifestyle-sport", "/home-living"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True).lower()
        assert html.count("<h1") == 1, f"{path} heeft geen unieke h1"


def test_rankfix_audit_canonicals_and_meta_descriptions():
    client = app.test_client()
    for path in ("/shop", "/contact", "/privacy", "/over-trendmix", "/aanbiedingen"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert 'rel="canonical"' in html, f"{path} mist canonical"
        assert 'name="description"' in html, f"{path} mist description"


def test_session_cookie_security_flags():
    client = app.test_client()
    product = load_all_products()[0]
    response = secure_post(client, "/winkelwagen", data={"action": "add", "product_id": product["id"]})
    header = response.headers.get("Set-Cookie", "")
    assert ("Secure" in header) == app.config["SESSION_COOKIE_SECURE"]
    assert "HttpOnly" in header
    assert "SameSite=Lax" in header


def test_mobile_drawer_and_assistant_translations_are_available():
    client = app.test_client()
    for path in ("/", "/shop", "/winkelwagen", "/beauty-care/elektrische-gezichtsroller"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert 'id="tmMobileDrawer"' in html
        assert 'id="tmSmartAssistant"' in html
        assert "trendmix-ui-2026.css" in html
        assert "trendmix-ui-2026.js" in html
        assert 'data-tm-language="en"' in html
        assert 'data-tm-language="nl"' in html


def test_cart_numeric_product_id_quantity_and_remove_work():
    client = app.test_client()
    product = load_all_products()[0]
    pid = str(product["id"])
    secure_post(client, "/winkelwagen", data={"action": "add", "product_id": pid})
    response = secure_post(client, "/winkelwagen", data={"action": "change", "product_id": pid, "delta": "1"}, follow_redirects=True)
    assert response.status_code == 200
    with client.session_transaction() as data:
        cart = data.get("trendmix_cart", [])
        assert len(cart) == 1
        assert cart[0]["qty"] == 2
        assert set(cart[0]) == {"id", "qty"}, "Do not keep old item prices in browser cookies."
    secure_post(client, "/winkelwagen", data={"action": "remove", "product_id": pid})
    with client.session_transaction() as data:
        assert not data.get("trendmix_cart")


def test_contact_message_is_not_falsely_confirmed_without_mail(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("CONTACT_FROM_EMAIL", raising=False)
    client = app.test_client()
    response = secure_post(client, 
        "/contact?ajax=1",
        data={"name": "Test", "email": "test@example.com", "message": "Controle"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 503
    assert response.get_json()["ok"] is False


def test_live_orders_require_explicit_enable_flag(monkeypatch):
    from app import live_orders_enabled
    monkeypatch.setenv("WOOCOMMERCE_URL", "https://example.com")
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_KEY", "test")
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_SECRET", "test")
    monkeypatch.delenv("TRENDMIX_LIVE_ORDERS", raising=False)
    assert live_orders_enabled() is False


def test_global_language_dropdown_is_present_across_storefront():
    client = app.test_client()
    pages = ("/", "/gadgets", "/smart-home", "/beauty-care", "/lifestyle-sport",
             "/shop", "/wishlist", "/winkelwagen", "/contact", "/faq",
             "/over-trendmix", "/account", "/aanbiedingen",
             "/beauty-care/elektrische-gezichtsroller")
    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert html.count('class="tm-language-dropdown"') == 1, path
        assert 'data-language="nl"' in html, path
        assert 'data-language="en"' in html, path
        assert 'tm-global-language' in html, path
        assert 'tm-flag-nl' in html and 'tm-flag-en' in html, path
        assert 'viewBox="0 0 24 16"' in html, path


def test_original_category_menu_and_svg_icons_survive_redesign():
    from pathlib import Path
    client = app.test_client()
    for path in ("/", "/smart-home", "/beauty-care", "/aanbiedingen", "/shop"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert 'class="categories tm-digital-nav tm-menu-compact"' in html, path
        assert 'class="tm-nav-icon"' in html, path
        assert '<svg' in html, path
        for category in ("/gadgets", "/smart-home", "/beauty-care",
                         "/lifestyle-sport", "/shop"):
            assert f'href="{category}"' in html
    css = Path("static/trendmix-ui-2026.css").read_text(encoding="utf-8")
    assert "min-height:54px!important" in css
    assert "display:block!important" in css


def test_product_buttons_render_accessible_vector_icons():
    client = app.test_client()
    response = client.get("/shop")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'tm-unified-icon' in html
    assert 'class="heartform"' in html
    assert 'class="add"' in html


def test_information_pages_have_professional_bilingual_content():
    from pathlib import Path
    import json
    client = app.test_client()
    expected_sections = {
        "over-trendmix": 7,
        "voorwaarden": 12,
        "privacy": 11,
        "cookies": 9,
        "bestellen": 9,
        "retouren": 9,
    }
    for slug, minimum in expected_sections.items():
        source = Path("content/information") / f"{slug}.json"
        content = json.loads(source.read_text(encoding="utf-8"))
        assert content["slug"] == slug
        for language in ("nl", "en"):
            document = content[language]
            assert len(document["sections"]) >= minimum
            assert len(document["lead"]) > 90
            assert document["title"] and document["description"]
        assert len(content["nl"]["sections"]) == len(content["en"]["sections"])
        response = client.get("/" + slug)
        assert response.status_code == 200, slug
        html = response.get_data(as_text=True)
        assert 'data-tm-info-root' in html, slug
        assert 'class="tm-info-toc"' in html, slug
        assert 'data-tm-info-en=' in html, slug
        assert 'data-tm-info-nl=' in html, slug
        assert html.count('class="tm-info-section"') >= minimum
        assert html.count("<h1") == 1, slug
        assert 'rel="canonical"' in html, slug
        assert "trendmix-info.css" in html, slug


def test_information_page_translation_bundle_and_original_hero_untouched():
    from pathlib import Path
    script = Path("static/trendmix-ui-2026.js").read_text(encoding="utf-8")
    assert "function translateInformationPage()" in script
    assert "$$('[data-tm-info-nl][data-tm-info-en]').forEach" in script
    assert "$$('[data-tm-tr]').forEach" in script
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert 'images/hero/gadgets.jpg' in response.get_data(as_text=True)


def test_all_test_products_have_curated_english_names():
    import json
    from pathlib import Path
    names = json.loads(Path("content/product-names-en.json").read_text(encoding="utf-8"))
    assert len(names) == 5
    for slug, group in names.items():
        assert len(group) == 20, slug
    from app import load_all_products, filter_products
    products = load_all_products()
    assert len(products) == 100
    assert all(p["en_name"] and p["en_short_description"] and p["en_description"] for p in products)
    product = next(p for p in products if p["category_slug"] == "gadgets")
    results = filter_products(products, search=product["en_name"])
    assert any(p["id"] == product["id"] for p in results)


def test_catalog_product_cards_and_detail_are_bilingual():
    client = app.test_client()
    for path in ("/", "/shop", "/gadgets", "/beauty-care/elektrische-gezichtsroller", "/winkelwagen"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        if path != "/winkelwagen":
            assert "data-tm-product-nl=" in html, path
            assert "data-tm-product-en=" in html, path
    from pathlib import Path
    source = Path("static/trendmix-ui-2026.js").read_text(encoding="utf-8")
    assert "function translateProductText()" in source
    assert "$$('[data-tm-product-nl][data-tm-product-en]')" in source


def test_extended_english_labels_across_website():
    from pathlib import Path
    script = Path("static/trendmix-english-labels.js").read_text(encoding="utf-8")
    assert "TrendMixEnglishLabels" in script
    assert '"Je winkelwagen": "Your shopping cart"' in script
    assert '"Algemene voorwaarden": "Terms and Conditions"' in script
    translator = Path("static/trendmix-ui-2026.js").read_text(encoding="utf-8")
    assert "function translateRemainingText()" in translator
    assert "translateRemainingText();" in translator
    client = app.test_client()
    for path in ("/", "/shop", "/wishlist", "/winkelwagen", "/contact",
                 "/privacy", "/retouren", "/beauty-care/elektrische-gezichtsroller"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "trendmix-english-labels.js" in response.get_data(as_text=True)
