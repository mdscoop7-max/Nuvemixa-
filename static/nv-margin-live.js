/* Live weergave van de gedeelde prijs- en margecalculator (Productonderzoek én de calculatorpagina).
 * Rekent uitsluitend via NVMargin.compute (static/nv-margin-core.js), dezelfde regels als de server
 * (nv_product_margin.unified_margin). Een leeg kostenveld blijft ONBEKEND: het wordt NIET als € 0 meegeteld,
 * maar vervangen door de zichtbare standaardaanname en apart vermeld. Een ingevulde 0 is een bewuste keuze.
 * Bovenaan staat alleen de samenvatting; de volledige tabel zit in 'Uitgebreide rekentabel'. */
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
  const LABELS = {shipping: 'Verzendkosten (verkoper)', advertising: 'Advertentiekosten', returns: 'Retourkosten',
    platform: 'Platformkosten', other: 'Invoer- en overige kosten'};

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function table(rows) {
    const t = el('table', 'admin-table');
    const body = t.createTBody();
    for (const [label, value, source, key] of rows) {
      const tr = body.insertRow();
      if (key) tr.className = 'nv-mkey';
      const th = el('th', '', label);
      if (source) th.append(' ', el('small', 'nv-msrc nv-msrc--' + source, source));
      tr.append(th);
      tr.insertCell().textContent = value;
    }
    return t;
  }

  function tile(label, value, note, key) {
    const box = el('div', key ? 'nv-msum__key' : '');
    box.append(el('span', '', label), el('strong', '', value));
    if (note) box.append(el('small', '', note));
    return box;
  }

  for (const form of document.querySelectorAll('form[data-margin-live]')) {
    const out = document.querySelector(form.dataset.marginLive);
    if (!out) continue;
    const summary = out.querySelector('[data-margin-summary]') || out;
    const tableBox = out.querySelector('[data-margin-table]');
    const field = name => form.elements[name];
    const value = (name, percent) => {
      const input = field(name);
      if (!input || input.value === '') return null;
      const n = Number(String(input.value).replace(',', '.'));
      return percent ? n : Math.round(n * 100);
    };
    const target = () => { const r = form.querySelector('input[name="target_margin"]:checked'); return r ? Number(r.value) : 25; };
    const shippingSelect = form.querySelector('[data-margin-shipping]');
    const ownShipping = form.querySelector('[data-margin-own-shipping]');
    const syncShipping = () => {
      if (ownShipping && shippingSelect) ownShipping.hidden = shippingSelect.value !== 'own';
    };
    const wait = text => { summary.replaceChildren(el('p', 'nv-margin-wait', text)); if (tableBox) tableBox.replaceChildren(); };

    const run = () => {
      syncShipping();
      const purchaseInput = field('purchase_cost');
      if (!purchaseInput || purchaseInput.value === '') {
        wait('Vul een inkoopprijs in en kies een marge: de voorlopige adviesprijs verschijnt direct.');
        return;
      }
      if ([...form.querySelectorAll('input[type=number]')].some(input => !input.validity.valid)) {
        const p = el('p', 'nv-margin-wait', 'Controleer de ingevulde bedragen (geen negatieve waarden, maximaal 2 decimalen, binnen het bereik).');
        p.setAttribute('role', 'alert');
        summary.replaceChildren(p);
        if (tableBox) tableBox.replaceChildren();
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
        own: value('selling_price'), actual, standard,
        shippingChoice: shippingSelect ? shippingSelect.value : 'own', customerShipping: value('customer_shipping') || 0});
      if (r.error) { wait(r.error); return; }
      const a = r.advice;
      const missing = [];
      for (const label of r.assumed) missing.push(label);

      // Samenvatting (altijd zichtbaar)
      const title = el('p', 'nv-margin-title');
      title.append(el('span', 'nv-mtag nv-mtag--' + r.kind.toLowerCase(),
        r.kind === 'A' ? 'A · Voorlopige adviesprijs' : 'B · Berekening met werkelijke kosten'), ' voor ' + r.target + '% winstmarge');
      const tiles = el('div', 'nv-msum');
      tiles.append(
        tile('Adviesverkoopprijs incl. btw', eur(a.selling),
          a.customer ? '+ ' + eur(a.customer) + ' verzending klant = ' + eur(a.total) : 'excl. btw ' + eur(a.revenue), true),
        tile('Btw-bedrag', eur(a.vat)), tile('Geschatte winst', eur(a.profit)), tile('Winstmarge', pct(a.margin)));
      const used = el('p', 'nv-msum__costs');
      used.append(el('small', '', 'Gebruikt: verzending ' + eur(r.used.shipping) + ' (' + r.sources.shipping + ') · advertenties ' +
        eur(r.used.advertising) + ' (' + r.sources.advertising + ') · retouren ' + eur(r.used.returns) + ' (' + r.sources.returns +
        ') · betaalprovider ' + eur(r.used.fee_fixed) + ' + ' + num(r.used.fee_pct) + '%'));
      const parts = [title, tiles, used];
      if (r.own) {
        const own = el('p', 'nv-msum__own');
        own.append(el('strong', '', 'Jouw prijs ' + eur(r.own.selling) + ':'), ' winst ' + eur(r.own.profit) + ' · ' + pct(r.own.margin) +
          ' — ' + (r.own.reaches ? 'haalt het doel' : eur(r.own.short) + ' te laag voor ' + r.target + '%'));
        parts.push(own);
      }
      parts.push(el('p', 'nv-margin-missing', missing.length
        ? 'Voorlopige berekening: ' + missing.length + ' kostenpost' + (missing.length !== 1 ? 'en' : '') + ' op aanname' +
          (missing.some(label => label.includes('nog onbekend')) ? ', verzendkosten nog onbekend' : '') +
          '. Onbekende kosten zijn NIET als € 0 meegeteld; details in de uitgebreide rekentabel.'
        : 'Alle kosten zijn werkelijk ingevuld. Indicatieve berekening, geen fiscaal advies.'));
      summary.replaceChildren(...parts);

      // Uitgebreide rekentabel
      if (!tableBox) return;
      const rows = [['Inkoopprijs excl. btw', eur(r.purchase)], ['Adviesverkoopprijs incl. btw', eur(a.selling), null, true]];
      if (a.customer) rows.push(['Verzendkosten aan klant incl. btw', eur(a.customer)], ['Totaal dat de klant betaalt', eur(a.total)]);
      rows.push(['Omzet excl. btw', eur(a.revenue)], ['Btw-bedrag (' + num(r.vat) + '%)', eur(a.vat)]);
      for (const key of ['shipping', 'advertising', 'returns']) rows.push([LABELS[key], eur(r.used[key]), r.sources[key]]);
      rows.push(['Betaalproviderkosten (' + eur(r.used.fee_fixed) + ' + ' + num(r.used.fee_pct) + '%)', eur(a.fee)]);
      for (const key of ['platform', 'other']) rows.push([LABELS[key], eur(r.used[key]), r.sources[key]]);
      rows.push(['Totale kosten incl. inkoop', eur(a.costs)], ['Brutowinst (na inkoop)', eur(a.gross) + ' · ' + pct(a.gross_pct)],
        ['Geschatte nettowinst', eur(a.profit) + ' · ' + pct(a.margin), null, true]);
      const tableParts = [table(rows)];
      if (r.own) {
        const o = r.own;
        const ownTitle = el('p', 'nv-margin-title');
        ownTitle.append(el('strong', '', 'Jouw verkoopprijs ' + eur(o.selling)));
        tableParts.push(ownTitle, table([['Omzet excl. btw', eur(o.revenue)], ['Btw-bedrag', eur(o.vat)],
          ['Betaalproviderkosten', eur(o.fee)], ['Brutowinst (na inkoop)', eur(o.gross) + ' · ' + pct(o.gross_pct)],
          ['Geschatte nettowinst', eur(o.profit) + ' · ' + pct(o.margin), null, true],
          ['Doel ' + r.target + '%', o.reaches ? 'Jouw prijs haalt dit' : 'Jouw prijs is ' + eur(o.short) + ' te laag']]));
      }
      tableBox.replaceChildren(...tableParts);
    };
    const reset = form.querySelector('[data-margin-reset]');
    if (reset) reset.addEventListener('click', () => {
      for (const input of form.querySelectorAll('input[data-default]')) input.value = input.dataset.default;
      run();
    });
    form.addEventListener('input', run);
    form.addEventListener('change', run);
    form.addEventListener('submit', event => { event.preventDefault(); run(); });
    // Zonder JavaScript is 'Bereken' nodig; met JavaScript rekent alles direct.
    const submit = form.querySelector('.nv-mcalc__submit');
    if (submit) submit.hidden = true;
    run();
  }
})();
