/* NUVEMIXA eindafwerking 22-11-2026 (hoort bij nv-polish-20261122.css)
   - Zoekbalk: zelfde placeholder en knop (icoon + 'Zoeken') op alle pagina's
   - Reviews: officieel NUVEMIXA-logo (zelfde bestand als de kopbalk) i.p.v. tasje-met-M
   - Reviews: bij nul beoordelingen geen '0,0 / 5', maar 'Nog geen beoordelingen'
   Volledig optioneel: zonder dit script blijft de site werken zoals voorheen. */
(function () {
  'use strict';
  if (window.__nvPolish20261122) return; window.__nvPolish20261122 = true;
  if (/^\/(admin|dashboard|control|catalogus-overzicht)(\/|$)/.test(location.pathname || '/')) return;

  var TXT = {
    nl: { ph: 'Zoek producten of merken…', btn: 'Zoeken', none: 'Nog geen beoordelingen' },
    en: { ph: 'Search products or brands…', btn: 'Search', none: 'No ratings yet' }
  };
  var ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.5" cy="10.5" r="6.5"></circle><path d="m16 16 5 5"></path></svg>';

  function lang() {
    var l = '';
    try { l = localStorage.getItem('trendmix-language') || ''; } catch (e) {}
    if (!l) l = document.documentElement.getAttribute('lang') || 'nl';
    return /^en/i.test(l) ? 'en' : 'nl';
  }

  /* ---------- Zoekbalk ---------- */
  function polishSearch() {
    var t = TXT[lang()];
    var forms = document.querySelectorAll('body > header form.search, body > header form.search-bar');
    Array.prototype.forEach.call(forms, function (f) {
      var input = f.querySelector('input[type="search"], input[name="q"]');
      var btn = f.querySelector('button[type="submit"], button:not([type])');
      if (!input || !btn) return;
      input.removeAttribute('data-i18n-placeholder');
      if (input.getAttribute('placeholder') !== t.ph) input.setAttribute('placeholder', t.ph);
      input.setAttribute('aria-label', lang() === 'en' ? 'Search products' : 'Zoek producten');
      if (!btn.hasAttribute('data-nvp')) {
        btn.setAttribute('data-nvp', '1');
        btn.innerHTML = ICON + '<span class="nvp-search-label" data-tm-tr data-tm-nl="Zoeken" data-tm-en="Search">' + t.btn + '</span>';
      } else {
        var lab = btn.querySelector('.nvp-search-label');
        if (lab && lab.textContent !== t.btn) lab.textContent = t.btn;
      }
      btn.setAttribute('aria-label', t.btn);
    });
  }

  /* ---------- Reviews ---------- */
  function polishReviews() {
    var sec = document.querySelector('.nm-reviews');
    if (!sec) return;
    var t = TXT[lang()];

    var brand = sec.querySelector('.nm-reviews__brand');
    var official = document.querySelector('body > header img.nv-brand-image, header img.nv-brand-image');
    if (brand && !brand.classList.contains('nvp-brand-logo')) {
      var src = official ? official.getAttribute('src') : '/static/nuvemixa-logo-test.png?v=20261110-logo-test';
      var img = document.createElement('img');
      img.src = src; img.alt = 'NUVEMIXA'; img.decoding = 'async'; img.loading = 'lazy';
      img.width = 220; img.height = 64;
      img.onerror = function () { this.onerror = null; this.src = '/static/logo.svg'; };
      brand.textContent = '';
      brand.appendChild(img);
      brand.classList.add('nvp-brand-logo');
    }

    var score = sec.querySelector('.nm-reviews__score');
    var num = score && score.querySelector('.nm-reviews__number');
    if (score && num) {
      var value = parseFloat((num.textContent || '').replace(',', '.'));
      var allEl = sec.querySelector('.nm-reviews__all');
      var m = allEl && /\((\d+)\)/.exec(allEl.textContent || '');
      var count = m ? parseInt(m[1], 10) : NaN;
      var empty = (!isNaN(count) && count === 0) || (isNaN(count) && (!value || value === 0));
      if (empty) {
        score.classList.add('nvp-empty');
        score.setAttribute('aria-label', t.none);
        var strong = score.querySelector('strong');
        if (strong) {
          strong.setAttribute('data-tm-nl', TXT.nl.none);
          strong.setAttribute('data-tm-en', TXT.en.none);
          if (strong.textContent !== t.none) strong.textContent = t.none;
        }
      }
    }
  }

  /* ---------- Compact reviewblok (vervangt de grote reviewsectie) ---------- */
  var RT = {
    nl: { title: 'Klantenreviews', none: 'Nog geen beoordelingen.', write: 'Schrijf review', all: 'Alle reviews',
          based1: 'beoordeling', basedN: 'beoordelingen',
          t: ['EU-levering', 'Betrouwbaar', 'Retourinfo', 'Gecontroleerd'] },
    en: { title: 'Customer reviews', none: 'No ratings yet.', write: 'Write review', all: 'All reviews',
          based1: 'rating', basedN: 'ratings',
          t: ['EU delivery', 'Trustworthy', 'Return info', 'Moderated'] }
  };
  var SVG = function (d) { return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>'; };
  var IC = {
    pen: SVG('<path d="M4 20l4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20z"/><path d="M14 7l3 3"/>'),
    star: SVG('<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>'),
    truck: SVG('<path d="M2 6h11v10H2z"/><path d="M13 9h4l4 4v3h-8z"/><circle cx="6" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>'),
    shield: SVG('<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>'),
    rotate: SVG('<path d="M20 12a8 8 0 1 1-2.4-5.7"/><path d="M20 4v5h-5"/>'),
    check: SVG('<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="M8 12.5l3 3 5.5-6.5"/>')
  };
  function compactReviews() {
    var sec = document.querySelector('.nm-reviews');
    var inner = sec && sec.querySelector('.nm-reviews__inner');
    if (!inner) return;
    var L = lang(), t = RT[L];
    var openBtn = sec.querySelector('.nm-reviews__main [data-nv-review-open], .nm-reviews__button');
    var num = sec.querySelector('.nm-reviews__number');
    var allEl = sec.querySelector('.nm-reviews__all');
    var m = allEl && /\((\d+)\)/.exec(allEl.textContent || '');
    var count = m ? parseInt(m[1], 10) : 0;
    var avg = num ? (num.textContent || '').replace(/\s+/g, ' ').trim() : '';
    var logo = document.querySelector('body > header img.nv-brand-image, header img.nv-brand-image');
    var logoSrc = logo ? logo.getAttribute('src') : '/static/nuvemixa-logo-test.png?v=20261110-logo-test';
    var sub = count > 0
      ? '<span class="nvp-rev-score">' + IC.star + ' ' + avg.replace(/\s*\/\s*5/, '') + '<small>/5</small></span> · ' + count + ' ' + (count === 1 ? t.based1 : t.basedN)
      : t.none;

    var card = inner.querySelector('.nvp-rev');
    if (!card) {
      card = document.createElement('div');
      card.className = 'nvp-rev';
      inner.insertBefore(card, inner.firstChild);
      sec.classList.add('nvp-compact');
    }
    var html =
      '<div class="nvp-rev-top">' +
        '<a class="nvp-rev-logo" href="/" aria-label="NUVEMIXA"><img src="' + logoSrc + '" alt="NUVEMIXA" width="220" height="64" decoding="async" loading="lazy"></a>' +
        '<div class="nvp-rev-text"><h2 id="nm-reviews-heading">' + t.title + '</h2><p>' + sub + '</p></div>' +
        '<div class="nvp-rev-actions">' +
          '<button type="button" class="nvp-rev-write" aria-controls="nv-review-form" aria-expanded="false">' + IC.pen + '<span>' + t.write + '</span></button>' +
          '<button type="button" class="nvp-rev-all">' + IC.star + '<span>' + t.all + ' (' + count + ')</span></button>' +
        '</div>' +
      '</div>' +
      '<ul class="nvp-rev-trust">' +
        '<li>' + IC.truck + '<span>' + t.t[0] + '</span></li>' +
        '<li>' + IC.shield + '<span>' + t.t[1] + '</span></li>' +
        '<li>' + IC.rotate + '<span>' + t.t[2] + '</span></li>' +
        '<li>' + IC.check + '<span>' + t.t[3] + '</span></li>' +
      '</ul>';
    if (card.getAttribute('data-lang') === L && card.getAttribute('data-count') === String(count)) return;
    // Oude kop-id niet dubbel laten bestaan
    var oldH = sec.querySelector('.nm-reviews__header #nm-reviews-heading');
    if (oldH) oldH.removeAttribute('id');
    card.innerHTML = html;
    card.setAttribute('data-lang', L); card.setAttribute('data-count', String(count));

    var write = card.querySelector('.nvp-rev-write');
    var form = document.getElementById('nv-review-form');
    write.addEventListener('click', function () {
      if (openBtn) openBtn.click(); else if (form) form.classList.toggle('open');
      var open = !!(form && form.classList.contains('open'));
      write.setAttribute('aria-expanded', String(open));
      if (open && form.scrollIntoView) form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    card.querySelector('.nvp-rev-all').addEventListener('click', function () {
      var list = sec.querySelector('.nv-rev-list, .nm-reviews__list, .nv-rev-item');
      if (list && list.scrollIntoView) list.scrollIntoView({ behavior: 'smooth', block: 'start' });
      else if (allEl) allEl.click();
    });
    var close = sec.querySelector('[data-nv-review-close]');
    if (close) close.addEventListener('click', function () { write.setAttribute('aria-expanded', 'false'); });
  }

  function run() { try { polishSearch(); } catch (e) {} try { polishReviews(); } catch (e) {} try { compactReviews(); } catch (e) {} }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
  window.addEventListener('load', run);
  // Na een taalwissel opnieuw toepassen (andere scripts zetten teksten terug).
  document.addEventListener('click', function (e) {
    if (e.target && e.target.closest && e.target.closest('[data-lang], [data-tm-lang], .tm-locale-trigger, .tm-global-language, [data-language]')) {
      setTimeout(run, 60); setTimeout(run, 400);
    }
  }, true);
  window.addEventListener('storage', function (e) { if (e.key === 'trendmix-language') run(); });
})();
