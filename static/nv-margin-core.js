/* NUVEMIXA rekenmodule voor prijs en marge. Eén formule voor 'Winstmarge per product' (Productonderzoek) en de
 * pagina 'Prijs & marge calculator'. Python-tegenhanger: nv_product_margin.unified_margin (zelfde regels, getest).
 *
 * Regels:
 * - Alle bedragen in centen; kosten exclusief btw; verkoopprijs inclusief btw.
 * - Marge = nettowinst / omzet exclusief btw.
 * - Betaalproviderkosten = vast bedrag + percentage van de verkoopprijs incl. btw.
 * - Een leeg werkelijk kostenveld is ONBEKEND: dan geldt de zichtbare standaardaanname en wordt dat zo gemeld.
 *   Een ingevulde 0 is een bewuste keuze en telt als werkelijke kosten.
 * - Afronding: half naar boven op hele centen.
 */
(function (root) {
  'use strict';
  const COSTS = [
    ['shipping', 'Verzend- en fulfilmentkosten'], ['advertising', 'Advertentiekosten'], ['returns', 'Retourkosten'],
    ['fee_fixed', 'Betaalprovider vast'], ['fee_pct', 'Betaalprovider %'], ['platform', 'Platformkosten'],
    ['other', 'Invoer- en overige kosten'],
  ];
  // Standaardaannames (zichtbaar en aanpasbaar in beide calculators). fee_pct is een percentage, de rest centen.
  const DEFAULTS = {shipping: 495, advertising: 300, returns: 100, fee_fixed: 35, fee_pct: 2.5, platform: 0, other: 0};
  const TARGETS = [15, 20, 25, 30, 35, 40];
  const roundHalfUp = value => Math.sign(value) * Math.round(Math.abs(value) + 1e-9);

  // selling = productprijs incl. btw; customer = verzendkosten die de klant daarbovenop betaalt (incl. btw).
  function priceFigures(selling, purchase, used, factor, customer) {
    customer = customer || 0;
    const total = selling + customer;
    const fee = used.fee_fixed + total * used.fee_pct / 100;
    const revenue = total / factor;
    const costs = purchase + used.shipping + used.advertising + used.returns + used.platform + used.other + fee;
    const profit = revenue - costs;
    return {
      selling: roundHalfUp(selling), customer: roundHalfUp(customer), total: roundHalfUp(total),
      revenue: roundHalfUp(revenue), vat: roundHalfUp(total - revenue),
      fee: roundHalfUp(fee), costs: roundHalfUp(costs), gross: roundHalfUp(revenue - purchase),
      profit: roundHalfUp(profit), gross_pct: revenue ? 100 * (revenue - purchase) / revenue : 0,
      margin: revenue ? 100 * profit / revenue : 0,
    };
  }

  // Keuze voor de verzendkosten van de VERKOPER (niet wat de klant betaalt):
  // standard = zichtbare aanname, free = bewust € 0 voor de verkoper, own = eigen bedrag, unknown = nog onbekend.
  const SHIPPING_CHOICES = ['standard', 'free', 'own', 'unknown'];

  /* input: {purchase (centen), vat (%), target (%), own (centen of null), actual: {key: waarde of null},
   *         standard: {key: waarde}, shippingChoice, customerShipping (centen incl. btw die de klant betaalt)}
   * → resultaat of {error} */
  function compute(input) {
    const vat = input.vat === undefined || input.vat === null ? 21 : input.vat;
    const target = input.target === undefined || input.target === null ? 25 : input.target;
    const standard = Object.assign({}, DEFAULTS, input.standard || {});
    const actual = Object.assign({}, input.actual || {});
    const choice = SHIPPING_CHOICES.includes(input.shippingChoice) ? input.shippingChoice : 'own';
    if (choice === 'free') actual.shipping = 0;
    if (choice === 'standard' || choice === 'unknown') actual.shipping = null;
    const customer = input.customerShipping > 0 ? input.customerShipping : 0;
    if (input.customerShipping < 0) return {error: 'Verzendkosten aan de klant kunnen niet negatief zijn.'};
    if (!(input.purchase > 0)) return {error: 'Vul een inkoopprijs groter dan € 0 in.'};
    if (!(vat >= 0 && vat <= 100)) return {error: 'Btw moet tussen 0 en 100% liggen.'};
    if (!(target >= 0 && target < 100)) return {error: 'Kies een geldige winstmarge.'};
    const used = {}, sources = {}, assumed = [];
    for (const [key, label] of COSTS) {
      const value = actual[key];
      if (value === null || value === undefined || Number.isNaN(value)) {
        const unknown = key === 'shipping' && choice === 'unknown';
        used[key] = standard[key]; sources[key] = unknown ? 'onbekend' : 'aanname';
        assumed.push(unknown ? label + ' (nog onbekend)' : label);
      } else {
        used[key] = value; sources[key] = value === 0 ? 'nul' : 'ingevuld';
      }
      if (!(used[key] >= 0) || (key === 'fee_pct' && used[key] >= 100)) return {error: 'Kosten kunnen niet negatief zijn.'};
    }
    const factor = 1 + vat / 100;
    const denominator = (1 - target / 100) / factor - used.fee_pct / 100;
    if (denominator <= 0) return {error: 'Deze marge is met deze betaalkosten en btw niet haalbaar.'};
    const fixed = input.purchase + used.shipping + used.advertising + used.returns + used.platform + used.other + used.fee_fixed;
    // Totaalbedrag voor de klant (product + verzending) dat de gekozen marge haalt; het productdeel is dat minus
    // de verzendkosten die de klant zelf betaalt.
    const total = roundHalfUp(fixed / denominator);
    if (total - customer <= 0) return {error: 'De verzendkosten die de klant betaalt dekken al alle kosten; controleer de bedragen.'};
    const advice = priceFigures(total - customer, input.purchase, used, factor, customer);
    const result = {
      kind: assumed.length ? 'A' : 'B', assumed, used, sources, purchase: input.purchase, vat, target, advice,
      own: null, shippingChoice: choice, customer,
    };
    if (input.own) {
      const own = priceFigures(input.own, input.purchase, used, factor, customer);
      own.reaches = input.own >= advice.selling;
      own.short = Math.max(0, advice.selling - input.own);
      result.own = own;
    }
    return result;
  }

  // Compatibel met de bestaande pariteitstest: alleen inkoop, alle standaardaannames.
  function adviceNumbers(purchaseCents, vatPct, targetPct) {
    const r = compute({purchase: purchaseCents, vat: vatPct, target: targetPct === undefined ? 25 : targetPct});
    const a = r.advice;
    return {selling: a.selling, revenue: a.revenue, vat: a.vat, shipping: r.used.shipping,
      advertising: r.used.advertising, returns: r.used.returns, fee: a.fee, total: a.costs, profit: a.profit,
      margin: a.margin};
  }

  const api = {COSTS, DEFAULTS, TARGETS, SHIPPING_CHOICES, compute, adviceNumbers, roundHalfUp};
  root.NVMargin = api;
  root.NVMarginAdvice = adviceNumbers;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
