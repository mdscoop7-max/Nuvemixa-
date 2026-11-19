/* Winstmarge per product: rekent automatisch zodra verkoopprijs, inkoopprijs en btw geldig zijn ingevuld.
 * Zelfde regels als de server (nv_product_margin.calculate_margin): kosten zijn excl. btw; een leeg kostenveld
 * blijft ONBEKEND en wordt niet als € 0 meegeteld, maar apart als ontbrekend vermeld. */
(() => {
  'use strict';
  const LABELS = {shipping_cost: 'Verzending', advertising_cost: 'Advertenties', transaction_fee: 'Transactiekosten',
    platform_fee: 'Platformkosten', returns_reserve: 'Retourreserve', other_cost: 'Invoer en afhandeling'};
  const eur = cents => new Intl.NumberFormat('nl-NL', {style: 'currency', currency: 'EUR'}).format(cents / 100);
  const pct = v => v.toLocaleString('nl-NL', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%';
  // Automatisch verkoopadvies uit alleen de inkoopprijs: exact dezelfde vaste aannames als
  // nv_product_margin.automatic_margin op de server (indicatief, duidelijk vermeld, geen echte kosten).
  const roundHalfUp = value => Math.sign(value) * Math.round(Math.abs(value) + 1e-9);
  function adviceNumbers(purchaseCents, vatPct) {
    const shipping = 495, advertising = 300, returns = 100, fixed = 35, pctFee = 0.025, target = 0.25;
    const factor = 1 + vatPct / 100;
    const denominator = (1 - target) / factor - pctFee;
    const selling = roundHalfUp((purchaseCents + shipping + advertising + returns + fixed) / denominator);
    const fee = fixed + selling * pctFee;
    const revenue = selling / factor;
    const total = purchaseCents + shipping + advertising + returns + fee;
    const profit = revenue - total;
    return {selling, revenue: roundHalfUp(revenue), vat: roundHalfUp(selling - revenue), shipping, advertising, returns,
      fee: roundHalfUp(fee), total: roundHalfUp(total), profit: roundHalfUp(profit), margin: revenue ? 100 * profit / revenue : 0};
  }
  window.NVMarginAdvice = adviceNumbers;
  function advice(out, purchaseCents, vatPct) {
    const n = adviceNumbers(purchaseCents, vatPct);
    const rows = [['Inkoopprijs excl. btw', eur(purchaseCents)], ['Adviesverkoopprijs incl. btw', eur(n.selling)],
      ['Omzet excl. btw', eur(n.revenue)], ['Btw in verkoopprijs', eur(n.vat)], ['Geschatte verzending', eur(n.shipping)],
      ['Geschatte reclamekosten', eur(n.advertising)], ['Geschatte transactiekosten', eur(n.fee)],
      ['Geschatte retourreserve', eur(n.returns)], ['Totale kosten incl. inkoop', eur(n.total)],
      ['Geschatte winst per verkoop', eur(n.profit)], ['Geschatte winstmarge', pct(n.margin)]];
    const title = document.createElement('p');
    title.className = 'nv-margin-title';
    title.innerHTML = '<strong>Automatisch verkoopadvies</strong> (vaste aannames)';
    const table = document.createElement('table');
    table.className = 'admin-table';
    const body = table.createTBody();
    for (const [label, value] of rows) {
      const tr = body.insertRow();
      const th = document.createElement('th'); th.textContent = label; tr.append(th);
      tr.insertCell().textContent = value;
    }
    const note = document.createElement('p');
    note.className = 'nv-margin-missing';
    note.textContent = 'Indicatief scenario: ' + String(vatPct).replace('.', ',') + '% btw, € 4,95 verzending, € 3,00 reclame, € 1,00 retourreserve en € 0,35 + 2,5% transactiekosten; verkoopadvies op circa 25% marge over de omzet excl. btw. Dit zijn aannames, geen bevestigde leverancierskosten. Vul een verkoopprijs in om met je eigen bedragen te rekenen.';
    out.replaceChildren(title, table, note);
  }
  for (const form of document.querySelectorAll('form[data-margin-live]')) {
    const out = document.querySelector(form.dataset.marginLive);
    if (!out) continue;
    const field = name => form.elements[name];
    const cents = name => Math.round(Number(String(field(name).value).replace(',', '.')) * 100);
    const run = () => {
      const purchaseInput = field('purchase_cost'), sellingInput = field('selling_price');
      if (purchaseInput && purchaseInput.value !== '' && purchaseInput.validity.valid && Number(purchaseInput.value) > 0
          && (!sellingInput || sellingInput.value === '')) {
        advice(out, cents('purchase_cost'), field('vat_rate') && field('vat_rate').value !== '' && field('vat_rate').validity.valid
          ? Number(String(field('vat_rate').value).replace(',', '.')) : 21);
        return;
      }
      const required = ['selling_price', 'purchase_cost', 'vat_rate'].map(field);
      if (required.some(input => !input || input.value === '')) {
        out.innerHTML = '<p class="nv-margin-wait">Vul een inkoopprijs in voor een automatisch verkoopadvies, of vul ook verkoopprijs en btw in voor je eigen berekening.</p>';
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
