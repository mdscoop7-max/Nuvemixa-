/* Platformkaarten (nv_platforms): de link van elke kaart volgt de gekozen webshopcategorie, periode, zoekterm en het
 * land. Geen AI, geen netwerkverzoeken: alleen het adres van de kaart verandert. Zelfde tokens als nv_platforms.resolve. */
(() => {
  'use strict';
  const CATS = ['gadgets', 'smart-home', 'beauty-care', 'home-living', 'lifestyle-sport'];
  const pick = (root, sel) => { if (!sel) return []; try { return [...document.querySelectorAll(sel)]; } catch (e) { return []; } };
  const iso = d => d.toISOString().slice(0, 10);

  function tokens(days, geo) {
    const week = days <= 7, since = new Date(Date.now() - days * 864e5);
    return {'{geo}': geo, '{days}': String(days), '{since}': iso(since), '{tbs}': week ? 'qdr:w' : 'qdr:m',
            '{gt}': week ? 'now%207-d' : 'today%201-m', '{yt}': week ? 'EgIIAw%253D%253D' : 'EgIIBA%253D%253D',
            '{rt}': week ? 'week' : 'month', '{ttp}': week ? '7' : '30'};
  }
  function fill(tpl, q) {
    const words = q.trim().split(/\s+/);
    return tpl.replace(/\{q\}/g, encodeURIComponent(q.trim()))
      .replace(/\{qt\}/g, encodeURIComponent(words.join('').toLowerCase()))
      .replace(/\{qd\}/g, encodeURIComponent(words.join('-')).replace(/%2D/g, '-'));
  }
  function note(kind, days) {
    if (kind === 'exact') return 'Periode toegepast: ' + days + ' dagen';
    if (kind === 'approx') return days <= 7 ? 'Periode toegepast: afgelopen week' :
      'Periode toegepast: afgelopen maand' + (days === 14 ? ' (14 dagen bestaat hier niet)' : '');
    if (kind === 'max7') return 'Toont alleen de laatste 7 dagen';
    return 'Periode niet via link in te stellen';
  }

  document.querySelectorAll('.nv-pcs').forEach(box => {
    const d = box.dataset;
    const catEls = d.catSource ? pick(box, d.catSource) : [...box.querySelectorAll('[data-pcs-cat]')];
    const perEls = d.periodSource ? pick(box, d.periodSource) : [...box.querySelectorAll('[data-pcs-period]')];
    const termEls = pick(box, d.termSource), landEls = pick(box, d.countrySource);
    const state = box.querySelector('[data-pcs-state]');
    const cards = [...box.querySelectorAll('.nv-pc')].map(a => {
      let links = {};
      try { links = JSON.parse(a.dataset.links || '{}'); } catch (e) { /* kaart houdt standaardlink */ }
      return {a, links, period: a.dataset.period, catlink: !!a.dataset.catlink, note: a.querySelector('[data-pcs-note]')};
    });
    const value = els => { const el = els.find(e => e.type !== 'radio' || e.checked); return el ? el.value : ''; };

    function update() {
      let cat = value(catEls);
      cat = CATS.includes(cat) ? cat : 'all';
      const raw = value(perEls), days = raw === '7' ? 7 : raw === '30' ? 30 : 14;
      const term = (value(termEls) || '').trim().slice(0, 100);
      const geo = /^[A-Z]{2}$/.test((value(landEls) || '').toUpperCase()) ? value(landEls).toUpperCase() : 'NL';
      const t = tokens(days, geo);
      cards.forEach(c => {
        let url = term.length >= 2 && c.links.term ? fill(c.links.term, term) : (c.links[cat] || c.links.all || c.a.href);
        Object.keys(t).forEach(k => { url = url.split(k).join(t[k]); });
        if (/^https:\/\//.test(url)) c.a.href = url;
        if (c.note) c.note.textContent = note(c.period, days) +
          (cat !== 'all' && !c.catlink && !(term.length >= 2 && c.links.term) ? ' · opent de algemene pagina (geen categorielink)' : '');
      });
      if (state) {
        const label = cat === 'all' ? 'Algemeen' : (catEls[0] && catEls[0].selectedOptions ? catEls[0].selectedOptions[0].textContent : cat);
        state.textContent = 'Links nu voor: ' + (term.length >= 2 ? '“' + term + '”' : label) + ' · ' +
          (raw === 'slim' ? 'Slim (14 dagen)' : days + ' dagen') + (geo !== 'NL' ? ' · land ' + geo : '') +
          '. Klik op een kaart om het platform te openen.';
      }
    }
    [...catEls, ...perEls, ...termEls, ...landEls].forEach(el => { el.addEventListener('change', update); el.addEventListener('input', update); });
    update();
  });
})();
