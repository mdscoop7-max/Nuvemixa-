/* Winstmarge per product: rekent automatisch zodra verkoopprijs, inkoopprijs en btw geldig zijn ingevuld.
 * Zelfde regels als de server (nv_product_margin.calculate_margin): kosten zijn excl. btw; een leeg kostenveld
 * blijft ONBEKEND en wordt niet als € 0 meegeteld, maar apart als ontbrekend vermeld. */
(() => {
  'use strict';
  const LABELS = {shipping_cost: 'Verzending', advertising_cost: 'Advertenties', transaction_fee: 'Transactiekosten',
    platform_fee: 'Platformkosten', returns_reserve: 'Retourreserve', other_cost: 'Invoer en afhandeling'};
  const eur = cents => new Intl.NumberFormat('nl-NL', {style: 'currency', currency: 'EUR'}).format(cents / 100);
  const pct = v => v.toLocaleString('nl-NL', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%';
  for (const form of document.querySelectorAll('form[data-margin-live]')) {
    const out = document.querySelector(form.dataset.marginLive);
    if (!out) continue;
    const field = name => form.elements[name];
    const cents = name => Math.round(Number(String(field(name).value).replace(',', '.')) * 100);
    const run = () => {
      const required = ['selling_price', 'purchase_cost', 'vat_rate'].map(field);
      if (required.some(input => !input || input.value === '')) {
        out.innerHTML = '<p class="nv-margin-wait">Vul verkoopprijs, inkoopprijs en btw in; de berekening verschijnt dan automatisch.</p>';
        return;
      }
      const all = [...form.querySelectorAll('input[type=number]')];
      if (all.some(input => !input.validity.valid)) {
        out.innerHTML = '<p class="nv-margin-wait" role="alert">Controleer de ingevulde bedragen (geen negatieve waarden, maximaal 2 decimalen).</p>';
        return;
      }
      const selling = cents('selling_price'), purchase = cents('purchase_cost');
      const vat = Number(String(field('vat_rate').value).replace(',', '.'));
      const revenue = Math.round(selling / (1 + vat / 100));
      const entered = [], missing = [];
      for (const [name, label] of Object.entries(LABELS)) {
        const input = field(name);
        if (!input) continue;
        if (input.value === '') missing.push(label); else entered.push([label, cents(name)]);
      }
      const costs = purchase + entered.reduce((sum, [, value]) => sum + value, 0);
      const gross = revenue - purchase, profit = revenue - costs;
      const rows = [['Omzet exclusief btw', eur(revenue)], ['Btw in verkoopprijs', eur(selling - revenue)], ['Inkoop', eur(purchase)],
        ...entered.map(([label, value]) => [label, eur(value)]),
        ['Brutowinst na inkoop', eur(gross) + (revenue ? ' · ' + pct(100 * gross / revenue) : '')],
        [missing.length ? 'Geschatte winst na ingevulde kosten (onvolledig)' : 'Geschatte winst', eur(profit) + (revenue ? ' · ' + pct(100 * profit / revenue) : '')]];
      const table = document.createElement('table');
      table.className = 'admin-table';
      const body = table.createTBody();
      for (const [label, value] of rows) {
        const tr = body.insertRow();
        const th = document.createElement('th'); th.textContent = label; tr.append(th);
        tr.insertCell().textContent = value;
      }
      out.replaceChildren(table);
      const note = document.createElement('p');
      note.textContent = missing.length
        ? 'Ontbrekende kosten: ' + missing.join(', ') + '. Deze zijn onbekend en NIET als € 0 meegeteld; de werkelijke winst is lager zodra ze bekend zijn.'
        : 'Alle kostenposten zijn ingevuld. Indicatieve berekening, geen fiscaal advies.';
      if (missing.length) note.className = 'nv-margin-missing';
      out.append(note);
    };
    form.addEventListener('input', run);
    run();
  }
})();
