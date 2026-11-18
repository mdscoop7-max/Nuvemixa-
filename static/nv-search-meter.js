/* NUVEMIXA zoekmeter: zichtbare voortgang bij iedere zoekbalk met data-research-search.
 * - verschijnt direct bij klikken op Zoeken; knop toont "Bezig met zoeken..." en blokkeert dubbel zoeken;
 * - toont de stappen die de server doorloopt, met een bewegende balk zonder verzonnen percentage;
 * - echte verstreken tijd, melding bij langdurig zoeken en een knop om te stoppen;
 * - herstelt zich bij terugnavigeren (pageshow) zodat de zoekbalk niet blijft hangen. */
(() => {
  'use strict';
  const DEFAULT_PHASES = ['Product analyseren...', 'Nederlandse en Engelse zoekwoorden controleren...',
    'Leveranciers zoeken...', 'EU- en internationale resultaten filteren...', 'AI analyseert zoekresultaten...',
    'Resultaten voorbereiden...'];
  const PHASE_MS = 2600, SLOW_S = 15, VERY_SLOW_S = 45;

  function build(form) {
    let meter = form.querySelector('.nv-search-meter');
    if (meter) return meter;
    const legacy = form.querySelector('.nv-search-progress');
    meter = document.createElement('div');
    meter.className = 'nv-search-meter';
    meter.hidden = true;
    meter.setAttribute('role', 'status');
    meter.setAttribute('aria-live', 'polite');
    meter.innerHTML = '<div class="nv-search-meter__head"><span class="nv-search-meter__spinner" aria-hidden="true"></span>' +
      '<strong class="nv-search-meter__phase"></strong><span class="nv-search-meter__time"></span></div>' +
      '<div class="nv-search-meter__bar" aria-hidden="true"><span></span></div>' +
      '<ol class="nv-search-meter__steps"></ol>' +
      '<p class="nv-search-meter__note">De exacte voortgang is niet meetbaar; de stappen tonen wat de zoekopdracht doorloopt.</p>' +
      '<p class="nv-search-meter__slow" hidden></p>' +
      '<button type="button" class="nv-search-meter__stop" hidden>Zoeken stoppen</button>';
    if (legacy) legacy.replaceWith(meter); else form.append(meter);
    return meter;
  }

  function setup(form) {
    const button = form.querySelector('button[type="submit"], button:not([type]), input[type="submit"]');
    const meter = build(form);
    const phase = meter.querySelector('.nv-search-meter__phase');
    const time = meter.querySelector('.nv-search-meter__time');
    const steps = meter.querySelector('.nv-search-meter__steps');
    const slow = meter.querySelector('.nv-search-meter__slow');
    const stop = meter.querySelector('.nv-search-meter__stop');
    const label = button ? (button.tagName === 'INPUT' ? button.value : button.textContent) : '';
    const phases = (form.dataset.searchPhases || '').split('|').map(s => s.trim()).filter(Boolean);
    const aiActive = document.body.dataset.aiState === 'active';
    // AI-stappen alleen tonen als AI werkelijk actief is; anders zou de meter iets beloven dat niet gebeurt.
    const list = (phases.length ? phases : DEFAULT_PHASES).filter(text => aiActive || !/^AI /.test(text));
    let running = false, timer = 0, started = 0;

    function setLabel(text) {
      if (!button) return;
      if (button.tagName === 'INPUT') button.value = text; else button.textContent = text;
    }
    function reset() {
      running = false;
      clearInterval(timer);
      form.removeAttribute('aria-busy');
      form.classList.remove('nv-searching');
      if (button) { button.disabled = false; setLabel(label); }
      meter.hidden = true;
      meter.classList.remove('is-slow', 'is-stopped');
      slow.hidden = true; stop.hidden = true;
      steps.textContent = '';
    }
    function tick() {
      const seconds = Math.floor((Date.now() - started) / 1000);
      time.textContent = seconds + ' s';
      const index = Math.min(list.length - 1, Math.floor((Date.now() - started) / PHASE_MS));
      if (phase.textContent !== list[index]) {
        phase.textContent = list[index];
        [...steps.children].forEach((li, i) => {
          li.classList.toggle('is-done', i < index);
          li.classList.toggle('is-current', i === index);
        });
      }
      if (seconds >= SLOW_S && slow.hidden) {
        slow.hidden = false;
        meter.classList.add('is-slow');
        slow.textContent = 'Dit duurt langer dan normaal. Bronnen reageren traag; NUVEMIXA wacht maximaal enkele seconden per bron.';
      }
      if (seconds >= VERY_SLOW_S) {
        slow.textContent = 'De zoekopdracht duurt erg lang. Je kunt nog even wachten of stoppen en opnieuw zoeken.';
        stop.hidden = false;
      }
    }
    stop.addEventListener('click', () => {
      try { window.stop(); } catch (e) { /* oudere browsers */ }
      reset();
      meter.hidden = false;
      meter.classList.add('is-stopped');
      phase.textContent = 'Zoeken gestopt. Pas de zoekopdracht aan of probeer het opnieuw.';
      time.textContent = '';
    });
    form.addEventListener('submit', event => {
      if (running) { event.preventDefault(); return; }
      if (event.defaultPrevented) return;
      running = true;
      started = Date.now();
      form.setAttribute('aria-busy', 'true');
      form.classList.add('nv-searching');
      steps.textContent = '';
      list.forEach(text => { const li = document.createElement('li'); li.textContent = text.replace(/\.\.\.$/, ''); steps.append(li); });
      meter.hidden = false;
      phase.textContent = '';
      tick();
      // Pas na het opbouwen van de formuliergegevens uitschakelen, zodat de knopwaarde meegaat.
      setTimeout(() => { if (button && running) { button.disabled = true; setLabel('Bezig met zoeken...'); } }, 0);
      if (button) setLabel('Bezig met zoeken...');
      timer = setInterval(tick, 500);
      if (matchMedia('(max-width: 760px)').matches) meter.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    });
    // Alleen bij terugnavigeren uit de cache; de eerste pageshow kan pas na een (snelle) klik op Zoeken komen.
    window.addEventListener('pageshow', event => { if (event.persisted) reset(); });
    form.nvSearchMeterReset = reset;
  }

  document.querySelectorAll('form[data-research-search]').forEach(setup);
  window.NVSearchMeter = {setup};
})();
