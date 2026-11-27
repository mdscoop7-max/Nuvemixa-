/* Leverancierskoppelingen: zoeken bij CJdropshipping (alleen als de koppeling actief is), voorraad en verzendkosten
 * op verzoek, 'Bereken marge' en 'Bewaar als concept'. Alles alleen-lezen bij CJ; er wordt niets besteld. */
(() => {
  'use strict';
  const box = document.getElementById('nv-koppelingen');
  if (!box || !window.fetch) return;
  const base = box.dataset.cj;
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; };
  const usd = v => v == null ? 'onbekend' : '$ ' + v.toLocaleString('nl-NL', {minimumFractionDigits: 2, maximumFractionDigits: 2});

  function post(what, data) {
    const fd = new FormData();
    fd.set('_csrf_token', box.dataset.csrf);
    Object.keys(data).forEach(k => fd.set(k, data[k]));
    return fetch(base + what, {method: 'POST', body: fd, credentials: 'same-origin'})
      .then(r => r.json().catch(() => ({ok: false, message: 'Onleesbaar antwoord (HTTP ' + r.status + ').'})));
  }

  function card(p, category) {
    const c = el('article', null, 'nv-sl__prod');
    if (/^https:\/\//.test(p.image)) {
      const img = el('img'); img.src = p.image; img.alt = p.name; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.remove());
      c.appendChild(img);
    }
    const body = el('div');
    body.appendChild(el('h4', p.name));
    body.appendChild(el('p', 'SKU ' + p.sku + ' · inkoopprijs ' + usd(p.price_usd) + ' (CJ, excl. verzending) · ' + (p.category || 'categorie onbekend'), 'nv-sl__meta'));
    body.appendChild(el('p', 'Voorraad volgens CJ: ' + (p.inventory == null ? 'onbekend' : p.inventory) +
      (p.delivery_cycle ? ' · verwerkingstijd ' + p.delivery_cycle + ' dagen' : '') +
      ' · CE-certificaat volgens CJ: ' + (p.ce ? 'ja (zelf controleren)' : 'niet vermeld'), 'nv-sl__meta'));
    const out = el('p', null, 'nv-sl__meta'); body.appendChild(out);
    const actions = el('div', null, 'nv-sl__actions');
    const stock = el('button', 'Voorraad ophalen'); stock.type = 'button';
    stock.addEventListener('click', () => {
      stock.disabled = true; out.textContent = 'Voorraad opvragen bij CJ…';
      post('voorraad', {q: p.sku}).then(d => {
        stock.disabled = false;
        out.textContent = d.ok ? 'Voorraad per magazijn: ' + (d.stock.map(s => s.country + ' ' + (s.total == null ? '?' : s.total)).join(' · ') || 'geen gegevens') +
          ' (opgehaald ' + new Date().toLocaleString('nl-NL') + ')' : d.message;
      });
    });
    const ship = el('button', 'Verzending naar NL'); ship.type = 'button';
    ship.addEventListener('click', () => {
      ship.disabled = true; out.textContent = 'Verzendopties opvragen bij CJ…';
      post('verzending', {q: p.pid, country: 'NL'}).then(d => {
        ship.disabled = false;
        out.textContent = d.ok ? 'Naar NL (variant ' + (d.variant || '?') + '): ' +
          (d.options.map(o => o.name + ' ' + usd(o.price_usd) + ', ' + o.days + ' dagen').join(' · ') || 'geen verzendopties') : d.message;
      });
    });
    actions.append(stock, ship);
    if (p.margin_url) { const m = el('a', 'Bereken marge'); m.href = p.margin_url; actions.appendChild(m); }
    if (box.dataset.canSave === '1') {
      const save = el('button', 'Bewaar als concept'); save.type = 'button';
      save.addEventListener('click', () => {
        const fd = new FormData();
        fd.set('_csrf_token', box.dataset.csrf); fd.set('titel', p.name.slice(0, 120)); fd.set('leverancier', 'CJdropshipping');
        fd.set('bron_naam', 'CJdropshipping API'); if (category) fd.set('categorie', category);
        if (/\.(jpe?g|png|webp)$/i.test(p.image)) fd.set('afbeeldingen', p.image);
        fd.set('notities', ('CJ SKU ' + p.sku + ', inkoop ' + usd(p.price_usd) + ' op ' + new Date().toISOString().slice(0, 10) +
          '. GPSR, CE en documentatie nog controleren.').slice(0, 300));
        save.disabled = true; save.textContent = 'Bezig…';
        fetch(box.dataset.concept, {method: 'POST', body: fd, credentials: 'same-origin'})
          .then(r => { const ok = /[?&]open=\d+/.test(r.url); save.textContent = ok ? 'Bewaard als concept (niet gepubliceerd)' : 'Niet opgeslagen: controleer de gegevens'; save.disabled = ok; })
          .catch(() => { save.textContent = 'Opslaan mislukt'; save.disabled = false; });
      });
      actions.appendChild(save);
    }
    body.appendChild(actions);
    c.appendChild(body);
    return c;
  }

  box.querySelectorAll('form[data-cj-search]').forEach(form => {
    const results = form.parentNode.querySelector('[data-cj-results]');
    form.addEventListener('submit', e => {
      e.preventDefault();
      if (form.hasAttribute('data-inactive')) return;
      const q = form.elements.q.value.trim();
      if (q.length < 2) { form.elements.q.focus(); return; }
      results.textContent = 'Zoeken bij CJdropshipping…';
      post('zoeken', {q, category: form.elements.category.value, country: form.elements.country.value}).then(d => {
        results.textContent = '';
        if (!d.ok) { results.appendChild(el('p', d.message, 'notice')); return; }
        results.appendChild(el('p', d.products.length + ' product(en) van CJdropshipping voor “' + q + '” · opgehaald ' +
          new Date(d.checked).toLocaleString('nl-NL') + '. Prijzen in USD; de calculator rekent om met de ECB-koers.', 'nv-sl__meta'));
        d.products.forEach(p => results.appendChild(card(p, form.elements.category.value)));
      }).catch(() => { results.textContent = 'Verbinding met het dashboard mislukt.'; });
    });
  });
})();
