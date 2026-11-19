/* Live weergave van de gedeelde prijs- en margecalculator (Productonderzoek én de calculatorpagina).
 * Rekent uitsluitend via NVMargin.compute (static/nv-margin-core.js), dezelfde regels als de server
 * (nv_product_margin.unified_margin). Een leeg kostenveld blijft ONBEKEND: het wordt NIET als € 0 meegeteld,
 * maar vervangen door de zichtbare standaardaanname en apart vermeld. Een ingevulde 0 is een bewuste keuze. */
(() => {
  'use strict';
  const core = window.NVMargin;
  if (!core) return;
  const eur = cents => new Intl.NumberFormat('nl-NL', {style: 'currency', currency: 'EUR'}).format(cents / 100);
  const pct = v => v.toLocaleString('nl-NL', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%';
  const num = v => v.toLocaleString('nl-NL', {maximumFractionDigits: 2});
  const ACTUAL = {shipping: 'shipping_cost', advertising: 'advertising_cost', returns: 'returns_reserve',
    fee_fixed: 'transaction_fee', fee_pct: 'transaction_pct', platform: 'platform_fee', other: 'other_cost'};
  const STANDARD = {shipping: 'std_shipping', advertising: 'std_advertising', returns: 'std_returns',
    fee_fixed: 'std_fee_fixed', fee_pct: 'std_fee_pct', platform: 'std_platform', other: 'std_other'};
  const LABELS = {shipping: 'Verzend- en fulfilmentkosten', advertising: 'Advertentiekosten', returns: 'Retourkosten',
    platform: 'Platformkosten', other: 'Invoer- en overige kosten'};

  function table(rows) {
    const t = document.createElement('table');
    t.className = 'admin-table';
    const body = t.createTBody();
    for (const [label, value, source, key] of rows) {
      const tr = body.insertRow();
      if (key) tr.className = 'nv-mkey';
      const th = document.createElement('th');
      th.textContent = label;
      if (source) {
        const tag = document.createElement('small');
        tag.className = 'nv-msrc nv-msrc--' + source;
        tag.textContent = source;
        th.append(' ', tag);
      }
      tr.append(th);
      tr.insertCell().textContent = value;
    }
    return t;
  }

  function paragraph(className, html) {
    const p = document.createElement('p');
    p.className = className;
    p.innerHTML = html;
    return p;
  }

  for (const form of document.querySelectorAll('form[data-margin-live]')) {
    const out = document.querySelector(form.dataset.marginLive);
    if (!out) continue;
    const field = name => form.elements[name];
    const value = (name, percent) => {
      const input = field(name);
      if (!input || input.value === '') return null;
      const n = Number(String(input.value).replace(',', '.'));
      return percent ? n : Math.round(n * 100);
    };
    const target = () => { const r = form.querySelector('input[name="target_margin"]:checked'); return r ? Number(r.value) : 25; };
    const run = () => {
      const purchaseInput = field('purchase_cost');
      if (!purchaseInput || purchaseInput.value === '') {
        out.innerHTML = '<p class="nv-margin-wait">Vul een inkoopprijs in: de voorlopige adviesprijs voor de gekozen marge verschijnt direct.</p>';
        return;
      }
      if ([...form.querySelectorAll('input[type=number]')].some(input => !input.validity.valid)) {
        out.innerHTML = '<p class="nv-margin-wait" role="alert">Controleer de ingevulde bedragen (geen negatieve waarden, maximaal 2 decimalen, binnen het bereik).</p>';
        return;
      }
      const actual = {}, standard = {};
      for (const key of Object.keys(ACTUAL)) {
        actual[key] = value(ACTUAL[key], key === 'fee_pct');
        const s = value(STANDARD[key], key === 'fee_pct');
        if (s !== null) standard[key] = s;
      }
      const vat = value('vat_rate', true);
      const r = core.compute({purchase: value('purchase_cost'), vat: vat === null ? 21 : vat, target: target(),
        own: value('selling_price'), actual, standard});
      if (r.error) { out.innerHTML = ''; out.append(paragraph('nv-margin-wait', '')); out.firstChild.textContent = r.error; return; }
      const a = r.advice;
      const missing = [];
      for (const label of r.assumed) missing.push(label);
      const title = paragraph('nv-margin-title', '');
      const tag = document.createElement('span');
      tag.className = 'nv-mtag nv-mtag--' + r.kind.toLowerCase();
      tag.textContent = r.kind === 'A' ? 'A · Voorlopige adviesprijs' : 'B · Berekening met werkelijke kosten';
      title.append(tag, ' voor ' + r.target + '% winstmarge');
      const rows = [['Inkoopprijs excl. btw', eur(r.purchase)], ['Adviesprijs incl. btw', eur(a.selling), null, true],
        ['Verkoopprijs excl. btw', eur(a.revenue)], ['Btw-bedrag (' + num(r.vat) + '%)', eur(a.vat)]];
      for (const key of ['shipping', 'advertising', 'returns']) rows.push([LABELS[key], eur(r.used[key]), r.sources[key]]);
      rows.push(['Betaalproviderkosten (' + eur(r.used.fee_fixed) + ' + ' + num(r.used.fee_pct) + '%)', eur(a.fee)]);
      for (const key of ['platform', 'other']) rows.push([LABELS[key], eur(r.used[key]), r.sources[key]]);
      rows.push(['Totale kosten incl. inkoop', eur(a.costs)], ['Brutowinst (na inkoop)', eur(a.gross) + ' · ' + pct(a.gross_pct)],
        ['Geschatte nettowinst', eur(a.profit) + ' · ' + pct(a.margin), null, true]);
      const parts = [title, table(rows)];
      if (r.own) {
        const o = r.own;
        const ownTitle = paragraph('nv-margin-title', '');
        const strong = document.createElement('strong');
        strong.textContent = 'Jouw verkoopprijs ' + eur(o.selling);
        ownTitle.append(strong);
        parts.push(ownTitle, table([['Verkoopprijs excl. btw', eur(o.revenue)], ['Btw-bedrag', eur(o.vat)],
          ['Betaalproviderkosten', eur(o.fee)], ['Brutowinst (na inkoop)', eur(o.gross) + ' · ' + pct(o.gross_pct)],
          ['Geschatte nettowinst', eur(o.profit) + ' · ' + pct(o.margin), null, true],
          ['Doel ' + r.target + '%', o.reaches ? 'Jouw prijs haalt dit' : 'Jouw prijs is ' + eur(o.short) + ' te laag']]));
      }
      const note = paragraph('nv-margin-missing', '');
      note.textContent = missing.length
        ? 'Voorlopig: ' + missing.length + ' kostenpost' + (missing.length !== 1 ? 'en' : '') + ' op standaardaanname (' + missing.join(', ') +
          '). Onbekende kosten zijn NIET als € 0 meegeteld maar als zichtbare aanname. Vul de werkelijke kosten in voor uitkomst B.'
        : 'Alle kosten zijn werkelijk ingevuld. Indicatieve berekening, geen fiscaal advies.';
      parts.push(note);
      out.replaceChildren(...parts);
    };
    const reset = form.querySelector('[data-margin-reset]');
    if (reset) reset.addEventListener('click', () => {
      for (const input of form.querySelectorAll('input[data-default]')) input.value = input.dataset.default;
      run();
    });
    form.addEventListener('input', run);
    form.addEventListener('change', run);
    form.addEventListener('submit', event => { event.preventDefault(); run(); });
    run();
  }
})();
