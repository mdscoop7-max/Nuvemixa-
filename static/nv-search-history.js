/* Zoekgeschiedenis zoals bij Google: verschijnt pas als je de zoekbalk aanklikt of begint te typen, direct onder
 * het veld. Filtert tijdens het typen, geen dubbele termen, één term verwijderen of alles wissen. Opslag is permanent
 * en per gebruiker op de server (/dashboard/zoekgeschiedenis); er worden geen AI-kosten gemaakt.
 * Werkt op elke zoekbalk met data-history="<veld>" of in een form[data-research-search]. */
(() => {
  'use strict';
  const URL_ = '/dashboard/zoekgeschiedenis';
  const csrf = () => (document.querySelector('input[name="_csrf_token"]') || {}).value || '';
  const params = new URLSearchParams(location.search);
  const ran = ['research_run', 'mrun', 'run', 'autorun'].some(name => params.get(name) === '1');

  function fieldsOnPage() {
    const found = new Map();
    document.querySelectorAll('input[data-history]').forEach(input => found.set(input, input.dataset.history));
    document.querySelectorAll('form[data-research-search] input[type="search"]').forEach(input => {
      if (found.has(input)) return;
      const form = input.form;
      const section = form.querySelector('input[name="section"]');
      const block = form.querySelector('input[name="research_block"]');
      found.set(input, [section ? section.value : params.get('section') || 'dashboard', block ? block.value : '', input.name]
        .filter(Boolean).join(':').toLowerCase().replace(/[^a-z0-9_:.-]/g, ''));
    });
    return found;
  }

  function setup(input, field) {
    let items = [], loaded = false, active = -1;
    input.setAttribute('autocomplete', 'off');
    input.removeAttribute('list');
    if (!ran && !params.get(input.name)) input.value = '';
    const wrap = document.createElement('div');
    wrap.className = 'nv-hist';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const list = document.createElement('div');
    list.className = 'nv-hist__list';
    list.setAttribute('role', 'listbox');
    list.hidden = true;
    wrap.appendChild(list);

    const save = (actie, term) => {
      const fd = new FormData();
      fd.set('_csrf_token', csrf()); fd.set('veld', field); fd.set('actie', actie); fd.set('term', term || '');
      return fetch(URL_, {method: 'POST', body: fd, credentials: 'same-origin'})
        .then(r => r.ok ? r.json() : null).then(d => { if (d && d.ok) items = d.items; }).catch(() => {});
    };
    const load = () => loaded ? Promise.resolve() : fetch(URL_ + '?veld=' + encodeURIComponent(field), {credentials: 'same-origin'})
      .then(r => r.ok ? r.json() : {items: []}).then(d => { items = d.items || []; loaded = true; }).catch(() => { loaded = true; });

    const close = () => { list.hidden = true; active = -1; };
    const choose = value => {
      input.value = value; close();
      const form = input.form;
      if (form) { if (typeof form.requestSubmit === 'function') form.requestSubmit(); else form.submit(); }
    };
    const render = () => {
      const q = input.value.trim().toLowerCase();
      const shown = items.filter(v => !q || v.toLowerCase().includes(q)).slice(0, 8);
      list.replaceChildren();
      if (!shown.length) { close(); return; }
      shown.forEach((value, i) => {
        const row = document.createElement('div');
        row.className = 'nv-hist__row' + (i === active ? ' is-active' : '');
        row.setAttribute('role', 'option');
        const pick = document.createElement('button');
        pick.type = 'button'; pick.className = 'nv-hist__pick'; pick.textContent = value;
        pick.addEventListener('mousedown', e => { e.preventDefault(); choose(value); });
        const del = document.createElement('button');
        del.type = 'button'; del.className = 'nv-hist__del'; del.textContent = '×';
        del.setAttribute('aria-label', 'Verwijder ' + value + ' uit de zoekgeschiedenis');
        del.addEventListener('mousedown', e => { e.preventDefault(); save('verwijderen', value).then(render); });
        row.append(pick, del);
        list.appendChild(row);
      });
      const clear = document.createElement('button');
      clear.type = 'button'; clear.className = 'nv-hist__clear'; clear.textContent = 'Alles wissen';
      clear.addEventListener('mousedown', e => { e.preventDefault(); save('wissen').then(close); });
      list.appendChild(clear);
      list.hidden = false;
    };
    input.addEventListener('focus', () => load().then(render));
    input.addEventListener('input', () => { active = -1; load().then(render); });
    input.addEventListener('blur', () => setTimeout(close, 120));
    input.addEventListener('keydown', e => {
      const rows = list.querySelectorAll('.nv-hist__pick');
      if (list.hidden || !rows.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % rows.length; render(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + rows.length) % rows.length; render(); }
      else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(rows[active].textContent); }
      else if (e.key === 'Escape') close();
    });
    if (input.form) input.form.addEventListener('submit', () => {
      const value = input.value.trim();
      if (value.length >= 2) save('toevoegen', value);
      close();
    });
  }

  fieldsOnPage().forEach((field, input) => { if (field) setup(input, field); });
})();
