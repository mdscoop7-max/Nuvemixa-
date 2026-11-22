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

  function run() { try { polishSearch(); } catch (e) {} try { polishReviews(); } catch (e) {} }

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
