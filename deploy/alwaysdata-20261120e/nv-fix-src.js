/* NUVEMIXA 2026-11-20e — mobiele afwerking:
   1) infoblok (levering / retour / bestellen / klantenservice) onder de producten op elke pagina
   2) winkelwagenknop even groot en op dezelfde hoogte als de accountknop
   3) volledige NL/EN-vertaling van losse teksten die nog in de verkeerde taal stonden
   4) land vrij invullen bij afrekenen (met EU-suggesties)
   5) kopbalk-kleur onthouden tegen witte flits; sneller navigeren (vooraf laden bij aanraken) */
(function () {
  'use strict';
  if (window.__nvFix20261120e) return; window.__nvFix20261120e = true;
  var path = location.pathname || '/';
  if (/^\/(admin|dashboard|control|catalogus-overzicht)(\/|$)/.test(path)) return;

  var DICT = __DICT__;
  var EU = {
    nl: ['Nederland','België','Duitsland','Frankrijk','Luxemburg','Oostenrijk','Ierland','Italië','Spanje','Portugal','Denemarken','Zweden','Finland','Polen','Tsjechië','Slowakije','Hongarije','Slovenië','Kroatië','Roemenië','Bulgarije','Griekenland','Cyprus','Malta','Estland','Letland','Litouwen'],
    en: ['Netherlands','Belgium','Germany','France','Luxembourg','Austria','Ireland','Italy','Spain','Portugal','Denmark','Sweden','Finland','Poland','Czechia','Slovakia','Hungary','Slovenia','Croatia','Romania','Bulgaria','Greece','Cyprus','Malta','Estonia','Latvia','Lithuania']
  };

  function lang() {
    var v = null;
    try { v = localStorage.getItem('trendmix-language'); } catch (e) {}
    if (v !== 'nl' && v !== 'en') v = (document.documentElement.getAttribute('lang') || 'nl').slice(0, 2).toLowerCase();
    return v === 'en' ? 'en' : (v === 'nl' ? 'nl' : null);
  }

  /* ---------- 3) vertalen ---------- */
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, CODE: 1, PRE: 1, svg: 1, SVG: 1 };
  var PRE_RE = /^([←✓✔→]\s*)/, POST_RE = /(\s*(?:→|…|\.\.\.|\*|:))+$/;
  function lookup(text, map) {
    if (map[text] !== undefined) return map[text];
    var pre = '', post = '', core = text, m = core.match(PRE_RE);
    if (m) { pre = m[1]; core = core.slice(pre.length); }
    m = core.match(POST_RE);
    if (m) { post = m[0]; core = core.slice(0, core.length - post.length); }
    if ((pre || post) && map[core] !== undefined) return pre + map[core] + post;
    var cm = text.match(/^(Winkelwagen|Cart|Favorieten|Favourites|Favorites)\s*\((\d+)\)$/);
    if (cm) { var enW = { Winkelwagen: 'Cart', Favorieten: 'Favourites' }, nlW = { Cart: 'Winkelwagen', Favourites: 'Favorieten', Favorites: 'Favorieten' }; var tw = map === DICT.en2nl ? nlW[cm[1]] : enW[cm[1]]; if (tw) return tw + ' (' + cm[2] + ')'; }
    if (text.length > 2 && text === text.toUpperCase() && /[A-Z]/.test(text)) {
      var cap = text.charAt(0) + text.slice(1).toLowerCase();
      if (map[cap] !== undefined) return map[cap].toUpperCase();
    }
    var n = text.match(/^(\d+)\s+(products?|producten?|items?|artikelen|resultaten|results)$/i);
    if (n) {
      var nl = /^(products?|producten?)$/i.test(n[2]) ? (n[1] === '1' ? 'product' : 'producten') : (/^(items?|artikelen)$/i.test(n[2]) ? (n[1] === '1' ? 'artikel' : 'artikelen') : 'resultaten');
      var en = /^(products?|producten?)$/i.test(n[2]) ? (n[1] === '1' ? 'product' : 'products') : (/^(items?|artikelen)$/i.test(n[2]) ? (n[1] === '1' ? 'item' : 'items') : 'results');
      var want = map === DICT.en2nl ? nl : en;
      if (want !== n[2]) return n[1] + ' ' + want;
    }
    return undefined;
  }
  function trText(node, map) {
    var raw = node.nodeValue; if (!raw) return;
    var t = raw.trim(); if (t.length < 2 || t.length > 600) return;
    var r = lookup(t, map);
    if (r !== undefined && r !== t) {
      var c = node.__nvc = (node.__nvc || 0) + 1; if (c > 6) return; /* nooit eindeloos heen-en-weer */
      node.nodeValue = raw.replace(t, r);
    }
  }
  function trAttr(el, a, map) {
    var v = el.getAttribute(a); if (!v) return;
    var t = v.trim(), r = lookup(t, map);
    if (r !== undefined && r !== t) el.setAttribute(a, r);
  }
  function translate(root) {
    var L = lang(); if (!L) return;
    var map = L === 'en' ? DICT.nl2en : DICT.en2nl;
    root = root || document.body; if (!root) return;
    /* eigen elementen met vaste NL/EN-teksten */
    var own = root.querySelectorAll ? root.querySelectorAll('[data-nv-nl]') : [];
    for (var i = 0; i < own.length; i++) { if (/^(IMG|SOURCE|PICTURE|VIDEO|IFRAME|LINK|META|SCRIPT|INPUT)$/.test(own[i].nodeName) || /^(\/|https?:)/.test(own[i].getAttribute('data-nv-nl') || '')) continue; var want = own[i].getAttribute('data-nv-' + L); if (want !== null && own[i].textContent !== want) own[i].textContent = want; }
    var ph = root.querySelectorAll ? root.querySelectorAll('[data-nv-ph-nl]') : [];
    for (i = 0; i < ph.length; i++) { var pv = ph[i].getAttribute('data-nv-ph-' + L) || ''; if (ph[i].getAttribute('placeholder') !== pv) ph[i].setAttribute('placeholder', pv); }
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        for (var p = n.parentNode; p && p !== root.parentNode; p = p.parentNode) {
          if (p.nodeType === 1 && (SKIP[p.nodeName] || p.isContentEditable || (p.hasAttribute && (p.hasAttribute('data-nv-nl') || p.hasAttribute('data-nv-notr'))))) return NodeFilter.FILTER_REJECT;
          if (p.classList && (p.classList.contains('tm-assistant-log') || p.classList.contains('tm-assist-msg'))) return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n; while ((n = w.nextNode())) trText(n, map);
    var els = root.querySelectorAll ? root.querySelectorAll('[placeholder],[aria-label],[title],input[type=submit],input[type=button],option') : [];
    for (i = 0; i < els.length; i++) {
      var el = els[i];
      trAttr(el, 'placeholder', map); trAttr(el, 'aria-label', map); trAttr(el, 'title', map);
      if (el.nodeName === 'INPUT') trAttr(el, 'value', map);
    }
    var sv = document.getElementById('nv-services-e'); if (sv && sv.getAttribute('lang') !== L) sv.setAttribute('lang', L);
    if (document.title) { var tt = lookup(document.title.trim(), map); if (tt !== undefined && tt !== document.title) document.title = tt; }
    var dl = document.getElementById('nv-eu-landen');
    if (false && dl && dl.getAttribute('data-l') !== L) {
      dl.setAttribute('data-l', L);
      dl.innerHTML = EU[L].map(function (c) { return '<option value="' + c + '"></option>'; }).join('');
    }
  }

  try { Array.prototype.forEach.call(document.querySelectorAll('img[data-nv-nl]'), function (im) { while (im.firstChild) im.removeChild(im.firstChild); }); } catch (e) {}

  try {
    var oc = document.createElement('style');
    oc.textContent = 'html,body{overflow-x:clip}'
      /* desktop: dezelfde originele hero-afbeeldingen tonen als op mobiel (geen losse teksthero) */
      + '@media (min-width:992px){html body main.wrap>.tm-new-hero:not(#nv-x),html body main .tm-offers-hero:not(#nv-x),html body .page-section.shop-page>.tm-shop-hero:not(#nv-x){position:relative!important;height:clamp(380px,34.5vw,460px)!important;min-height:0!important;max-height:none!important;border-radius:22px!important;overflow:hidden!important;background:#0b0f1f!important;padding:0!important;display:block!important;margin-top:16px!important;margin-bottom:16px!important}html body main.wrap>.tm-new-hero:not(#nv-x)>a{position:absolute!important;inset:0!important;display:block!important;height:100%!important;width:100%!important}html body main.wrap>.tm-new-hero:not(#nv-x) img,html body main .tm-offers-hero:not(#nv-x) img,html body .page-section.shop-page>.tm-shop-hero:not(#nv-x) img{display:block!important;position:absolute!important;right:0!important;left:auto!important;top:50%!important;transform:translateY(-50%)!important;width:166.7%!important;max-width:none!important;height:auto!important;max-height:none!important;margin:0!important;border-radius:0!important;object-fit:contain!important;z-index:0!important}html body main.wrap>.tm-new-hero:not(#nv-x)::after,html body main .tm-offers-hero:not(#nv-x)::after,html body .page-section.shop-page>.tm-shop-hero:not(#nv-x)::after{content:"";position:absolute;inset:0;z-index:1;background:linear-gradient(90deg,#0b0f1f 0%,rgba(11,15,31,.92) 34%,rgba(11,15,31,.35) 58%,rgba(11,15,31,0) 75%);pointer-events:none}html body main.wrap>.tm-new-hero:not(#nv-x) .tm-desktop-hero-copy,html body main .tm-offers-hero:not(#nv-x) .tm-desktop-hero-copy,html body .page-section.shop-page>.tm-shop-hero:not(#nv-x) .tm-desktop-hero-copy{display:flex!important;flex-direction:column!important;align-items:flex-start!important;justify-content:center!important;position:absolute!important;left:0!important;top:0!important;bottom:0!important;z-index:2!important;width:46%!important;padding:0 0 0 56px!important;background:none!important;margin:0!important;transform:none!important}html body main.wrap>.tm-new-hero:not(#nv-x) .tm-desktop-hero-copy h2,html body main.wrap>.tm-new-hero:not(#nv-x) .tm-desktop-hero-copy p,html body main.wrap>.tm-new-hero:not(#nv-x) .tm-desktop-hero-copy .tm-desktop-brand,html body main .tm-offers-hero:not(#nv-x) .tm-desktop-hero-copy h2,html body main .tm-offers-hero:not(#nv-x) .tm-desktop-hero-copy p,html body main .tm-offers-hero:not(#nv-x) .tm-desktop-hero-copy .tm-desktop-brand,html body .page-section.shop-page>.tm-shop-hero:not(#nv-x) .tm-desktop-hero-copy h2,html body .page-section.shop-page>.tm-shop-hero:not(#nv-x) .tm-desktop-hero-copy p,html body .page-section.shop-page>.tm-shop-hero:not(#nv-x) .tm-desktop-hero-copy .tm-desktop-brand{color:#fff!important;opacity:1!important}html body .page-section.shop-page>.tm-shop-hero:not(#nv-x) img{top:auto!important;bottom:-4%!important;transform:none!important}}'
      /* Favorieten-knop naast Account en Cart (desktop) */
      + 'html body .tm-header-actions>a.nv-fav-btn:not(#nv-x){background:linear-gradient(135deg,#fb7185,#e11d48)!important;color:#fff!important;border-color:rgba(255,255,255,.55)!important}html body .tm-header-actions>a.nv-fav-btn svg:not(#nv-x){stroke:#fff!important;fill:none!important}@media (max-width:991px){html body .tm-header-actions>a.nv-fav-btn{display:none!important}}@media (min-width:992px){html body>div.topline:not(#nv-x) .topitems>a[href="/wishlist"]:not(#nv-x){display:none!important}html body>div.topline:not(#nv-x) .topitems>span:nth-last-of-type(1):not(#nv-x){border-right:0!important}}'
      /* bovenbalk desktop: optie C (wit, rode lijn boven, rode icoontjes, geen dubbele Account/Cart) */
      + '@media (min-width:992px){html body>div.topline:not(#nv-x){background:#fff!important;border-image:none!important;border-top:3px solid #e11d48!important;border-bottom:1px solid #e5e9f2!important;box-shadow:none!important}html body>div.topline:not(#nv-x) .topitems:not(#nv-x){gap:0!important}html body>div.topline:not(#nv-x) .topitems>span:not(#nv-x),html body>div.topline:not(#nv-x) .topitems>a:not(#nv-x){color:#0f1b33!important;font-weight:600!important;font-size:13.5px!important;opacity:1!important;text-shadow:none!important;padding:0 16px!important;border-right:1px solid #d9e1ef!important;line-height:22px!important}html body>div.topline:not(#nv-x) .topitems>span:first-child:not(#nv-x){padding-left:0!important}html body>div.topline:not(#nv-x) .topitems>a[href="/wishlist"]:not(#nv-x){border-right:0!important}html body>div.topline:not(#nv-x) .topitems>span svg:not(#nv-x),html body>div.topline:not(#nv-x) .topitems>a svg:not(#nv-x){color:#e11d48!important;stroke:#e11d48!important}html body>div.topline:not(#nv-x) .topitems>a[href="/account"]:not(#nv-x),html body>div.topline:not(#nv-x) .topitems>a[href="/winkelwagen"]:not(#nv-x){display:none!important}html body>div.topline:not(#nv-x) .tm-locale-trigger:not(#nv-x){background:#fff!important;border:1.5px solid #c9d5ea!important;box-shadow:none!important}html body>div.topline:not(#nv-x) .tm-locale-trigger *:not(#nv-x):not(img){color:#1d4ed8!important}}';
    document.head.appendChild(oc);
  } catch (e) {}

  /* ---------- 1) infoblok overal ---------- */
  function placeServices() {
    var mine = document.getElementById('nv-services-e'); if (!mine) return;
    if (mine.getAttribute('data-placed')) return;
    var old = Array.prototype.filter.call(document.querySelectorAll('section.services, .services'), function (s) { return s !== mine && !mine.contains(s) && !s.closest('footer'); });
    var foot = mine.closest('footer') || document.querySelector('footer, .site-footer, .footer');
    if (old.length) {
      old[0].parentNode.insertBefore(mine, old[0]);
      old.forEach(function (s) { s.style.display = 'none'; s.setAttribute('aria-hidden', 'true'); });
    } else if (foot && foot.parentNode) {
      var mainEl = document.querySelector('main');
      if (mainEl && mainEl.compareDocumentPosition(foot) & Node.DOCUMENT_POSITION_FOLLOWING && !mainEl.contains(foot)) mainEl.appendChild(mine);
      else foot.parentNode.insertBefore(mine, foot);
    }
    mine.hidden = false; mine.setAttribute('data-placed', '1');
  }

  /* ---------- 2) winkelwagen gelijk aan account ---------- */
  function topVisible(sel) {
    var list = document.querySelectorAll(sel);
    for (var i = 0; i < list.length; i++) {
      var el = list[i]; if (el.closest('.tm-dock, nav.tm-dock, .nv-dock, [data-mobile-nav], .tm-mobile-drawer, footer')) continue;
      var r = el.getBoundingClientRect();
      if (r.width > 8 && r.height > 8 && r.top < 260 && r.bottom > -40) return el;
    }
    return null;
  }
  var cartDy = 0;
  function alignCart() {
    if (window.innerWidth > 1024) return;
    var acc = topVisible('a[href="/account"],a[href$="/account"],a[href*="/account?"]');
    var cart = topVisible('a[href="/winkelwagen"],a[href$="/winkelwagen"],a[href="/cart"],a.cart-link');
    if (!acc || !cart || acc.contains(cart) || cart.contains(acc)) return;
    var a = acc.getBoundingClientRect();
    if (Math.abs(cart.offsetWidth - acc.offsetWidth) > 2 || Math.abs(cart.offsetHeight - acc.offsetHeight) > 2) {
      cart.style.setProperty('width', acc.offsetWidth + 'px', 'important');
      cart.style.setProperty('height', acc.offsetHeight + 'px', 'important');
      cart.style.setProperty('min-width', '0', 'important');
      cart.style.setProperty('min-height', '0', 'important');
      cart.style.setProperty('box-sizing', 'border-box', 'important');
      cart.style.setProperty('padding', getComputedStyle(acc).padding, 'important');
      cart.style.setProperty('border-radius', getComputedStyle(acc).borderRadius, 'important');
    }
    cart.style.setProperty('margin-top', '0', 'important');
    cart.style.setProperty('margin-bottom', '0', 'important');
    cart.style.setProperty('align-self', 'center', 'important');
    var c = cart.getBoundingClientRect();
    var rawTop = c.top - cartDy;
    var d = Math.round((a.top + a.height / 2) - (rawTop + c.height / 2));
    if (Math.abs(d) <= 1) d = 0;
    if (d !== cartDy) {
      cartDy = d;
      cart.style.setProperty('transform', d ? 'translateY(' + d + 'px)' : 'none', 'important');
    }
    cart.classList.add('nv-cart-aligned');
  }

  /* ---------- 4) land vrij invullen ---------- */
  function freeCountry() {
    var ci = document.querySelector('input[name="country"][list]'); if (ci) ci.removeAttribute('list');
    var sel = document.querySelector('select[name="country"]'); if (!sel) return;
    var inp = document.createElement('input');
    inp.type = 'text'; inp.name = 'country'; inp.id = sel.id || 'f-country';
    inp.required = sel.required; inp.autocomplete = 'country-name'; inp.maxLength = 100; inp.minLength = 2;
    inp.className = (sel.className || '') + ' nv-country-input';
    inp.setAttribute('data-nv-ph-nl', 'Bijv. Nederland'); inp.setAttribute('data-nv-ph-en', 'E.g. Netherlands');
    var cur = sel.value && sel.selectedIndex > 0 ? sel.options[sel.selectedIndex].text : '';
    inp.value = cur;
    ['aria-invalid', 'aria-describedby'].forEach(function (a) { if (sel.hasAttribute(a)) inp.setAttribute(a, sel.getAttribute(a)); });
    sel.parentNode.replaceChild(inp, sel);
    if (!document.getElementById('nv-eu-landen')) { var dl = document.createElement('datalist'); dl.id = 'nv-eu-landen'; inp.parentNode.appendChild(dl); }
    var small = inp.parentNode.querySelector('small');
    if (small && !small.hasAttribute('data-nv-nl') && /levergebied|delivery area|livegang|launch/i.test(small.textContent)) {
      small.setAttribute('data-nv-nl', 'We leveren alleen binnen de EU. Typ je land, bijvoorbeeld Nederland of België.');
      small.setAttribute('data-nv-en', 'We only deliver within the EU. Type your country, for example Netherlands or Belgium.');
    }
  }

  /* ---------- 5) kopbalk-kleur onthouden (tegen witte flits) ---------- */
  function rememberHeader() {
    try {
      var stack = document.elementsFromPoint(Math.min(40, innerWidth / 4), 30) || [];
      for (var i = 0; i < stack.length; i++) {
        var el = stack[i]; if (el === document.documentElement || el === document.body) break;
        if (/^(IMG|SVG|PICTURE|A|BUTTON)$/i.test(el.tagName) || el.getBoundingClientRect().width < innerWidth * 0.6) continue;
        var cs = getComputedStyle(el);
        if (cs.position === 'fixed' && el.getBoundingClientRect().height > 200) continue;
        var bg = cs.backgroundImage !== 'none' ? cs.backgroundImage : '';
        var col = cs.backgroundColor;
        if (bg.indexOf('url(') >= 0) bg = '';
        if (!bg && (!col || col === 'transparent' || /rgba\(.*,\s*0\)$/.test(col))) continue;
        var sel = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + Array.prototype.slice.call(el.classList, 0, 3).filter(function (c) { return /^[a-zA-Z_][\w-]*$/.test(c); }).map(function (c) { return '.' + c; }).join('');
        if (sel === 'div' || sel === 'a' || sel === 'span' || sel === 'form' || sel === 'input') continue;
        localStorage.setItem('nv-hdr-20261120e', JSON.stringify({ s: sel, c: col, i: bg }));
        break;
      }
    } catch (e) {}
  }

  /* ---------- 5b) sneller navigeren: vooraf laden bij aanraken (val-terug zonder speculation rules) ---------- */
  var fetched = {};
  var noPre = /^\/(winkelwagen|afrekenen|account|admin|api|dashboard|control|wishlist)(\/|$)|logout/;
  function prefetch(e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null; if (!a) return;
    if (a.target || a.hasAttribute('download') || a.origin !== location.origin) return;
    var p = a.pathname; if (noPre.test(p) || a.href === location.href || fetched[a.href]) return;
    if (HTMLScriptElement.supports && HTMLScriptElement.supports('speculationrules')) return;
    fetched[a.href] = 1;
    var l = document.createElement('link'); l.rel = 'prefetch'; l.href = a.href; document.head.appendChild(l);
  }
  document.addEventListener('touchstart', prefetch, { passive: true, capture: true });
  document.addEventListener('mouseover', prefetch, { passive: true, capture: true });


  /* ---------- Favorieten-knop in de kop (desktop) ---------- */
  function favButton() {
    var box = document.querySelector('.tm-header-actions'); if (!box || box.querySelector('.nv-fav-btn')) return;
    var cart = box.querySelector('a[href="/winkelwagen"]');
    var en = lang() === 'en';
    var a = document.createElement('a');
    a.className = 'tm-header-action nv-fav-btn'; a.href = '/wishlist';
    a.setAttribute('aria-label', en ? 'Favourites' : 'Favorieten');
    a.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.4 5.6a5.4 5.4 0 0 0-7.6 0l-.8.8-.8-.8a5.4 5.4 0 0 0-7.6 7.6L12 21l8.4-7.8a5.4 5.4 0 0 0 0-7.6z"></path></svg><span class="tm-action-text" data-nv-nl="Favorieten" data-nv-en="Favourites">' + (en ? 'Favourites' : 'Favorieten') + '</span>';
    if (cart && cart.nextSibling) box.insertBefore(a, cart.nextSibling); else box.appendChild(a);
  }


  /* ---------- desktop-hero: tekstblok voor de homepage, "sport" in Lifestyle & Sport ---------- */
  function heroCopy() {
    var hero = document.querySelector('main.wrap > .tm-new-hero');
    if (hero && !hero.querySelector('.tm-desktop-hero-copy')) {
      var holder = hero.querySelector('a') || hero;
      var d = document.createElement('div'); d.className = 'tm-desktop-hero-copy nv-home-copy'; d.setAttribute('aria-hidden', 'true');
      d.innerHTML = '<span class="tm-desktop-brand">NUVEMIXA</span><span class="tm-desktop-tag">GADGETS</span>'
        + '<h2 data-nv-nl="Unieke gadgets voor een slimmer leven" data-nv-en="Unique gadgets for smarter living">Unieke gadgets voor een slimmer leven</h2>'
        + '<p data-nv-nl="Bijzondere gadgets die je dagelijks leven makkelijker en leuker maken." data-nv-en="Special gadgets that make everyday life easier and more fun.">Bijzondere gadgets die je dagelijks leven makkelijker en leuker maken.</p>'
        + '<span class="tm-desktop-cta" data-nv-nl="Bekijk Gadgets →" data-nv-en="Explore Gadgets →">Bekijk Gadgets →</span>';
      holder.appendChild(d);
    }
    Array.prototype.forEach.call(document.querySelectorAll('.tm-desktop-hero-copy h2'), function (h) {
      if (h.hasAttribute('data-nv-nl')) return;
      if (/actieve levensstijl|active lifestyle/i.test(h.textContent) && !/sport/i.test(h.textContent)) {
        h.setAttribute('data-nv-nl', 'De perfecte uitrusting voor sport en een actieve levensstijl');
        h.setAttribute('data-nv-en', 'The perfect gear for sport and an active lifestyle');
      }
    });
  }

  /* ---------- starten ---------- */
  function run() {
    try { freeCountry(); } catch (e) {}
    try { placeServices(); } catch (e) {}
    try { favButton(); } catch (e) {}
    try { heroCopy(); } catch (e) {}
    try { translate(document.body); } catch (e) {}
    try { alignCart(); } catch (e) {}
  }
  run();
  document.addEventListener('DOMContentLoaded', run);
  window.addEventListener('load', function () { run(); setTimeout(run, 400); setTimeout(rememberHeader, 600); });
  window.addEventListener('pageshow', run);
  var raf = 0;
  function later() { if (!raf) raf = requestAnimationFrame(function () { raf = 0; try { translate(document.body); alignCart(); } catch (e) {} }); }
  window.addEventListener('resize', later, { passive: true });
  var sraf = 0; window.addEventListener('scroll', function () { if (!sraf) sraf = requestAnimationFrame(function () { sraf = 0; try { alignCart(); } catch (e) {} }); }, { passive: true });
  document.addEventListener('click', function () { setTimeout(later, 60); setTimeout(later, 450); }, true);
  window.addEventListener('storage', later);
  if (window.MutationObserver) {
    new MutationObserver(later).observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['lang', 'placeholder'] });
  }
})();
