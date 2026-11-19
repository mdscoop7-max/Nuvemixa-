/* Zoekgeschiedenis per zoekbalk (alleen in deze browser, localStorage). Zoekveld leeg bij openen; recente
 * zoekopdrachten als kleine knoppen onder het veld, met suggesties tijdens het typen en een wisknop. */
(() => {
  'use strict';
  const MAX = 8;
  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem(key) || '[]').filter(v => typeof v === 'string'); } catch (e) { return []; } },
    set(key, list) { try { localStorage.setItem(key, JSON.stringify(list)); } catch (e) { /* opslag niet beschikbaar */ } },
    clear(key) { try { localStorage.removeItem(key); } catch (e) { /* idem */ } },
  };
  const params = new URLSearchParams(location.search);
  const ran = ['research_run', 'mrun', 'run'].some(name => params.get(name) === '1');
  let counter = 0;
  for (const form of document.querySelectorAll('form[data-research-search]')) {
    const input = form.querySelector('input[type="search"]');
    if (!input) continue;
    const section = form.querySelector('input[name="section"]');
    const block = form.querySelector('input[name="research_block"]');
    const key = 'nv-zoekgeschiedenis:' + [section ? section.value : params.get('section') || 'dashboard',
      block ? block.value : '', input.name].join(':');
    // Leeg zoekveld bij openen (niet na een uitgevoerde zoekopdracht, dan blijft de term zichtbaar bij de resultaten).
    if (!ran) input.value = '';
    window.addEventListener('pageshow', event => { if (event.persisted && !ran) input.value = ''; });
    const list = document.createElement('datalist');
    list.id = 'nv-history-' + (++counter);
    input.setAttribute('list', list.id);
    input.setAttribute('autocomplete', 'off');
    const box = document.createElement('div');
    box.className = 'nv-history';
    box.setAttribute('aria-label', 'Recente zoekopdrachten');
    (input.closest('label') || input).after(box);
    form.append(list);
    const render = () => {
      const items = store.get(key);
      list.replaceChildren(...items.map(v => Object.assign(document.createElement('option'), {value: v})));
      box.replaceChildren();
      box.hidden = !items.length;
      if (!items.length) return;
      const label = document.createElement('span');
      label.className = 'nv-history__label';
      label.textContent = 'Recent:';
      box.append(label);
      for (const value of items) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'nv-history__chip';
        chip.textContent = value;
        chip.title = 'Zoek opnieuw naar ' + value;
        chip.addEventListener('click', () => {
          input.value = value;
          if (typeof form.requestSubmit === 'function') form.requestSubmit(); else form.submit();
        });
        box.append(chip);
      }
      const wipe = document.createElement('button');
      wipe.type = 'button';
      wipe.className = 'nv-history__clear';
      wipe.textContent = 'Wissen';
      wipe.addEventListener('click', () => { store.clear(key); render(); input.focus(); });
      box.append(wipe);
    };
    form.addEventListener('submit', () => {
      const value = input.value.trim();
      if (!value) return;
      const items = [value, ...store.get(key).filter(v => v.toLowerCase() !== value.toLowerCase())].slice(0, MAX);
      store.set(key, items);
    });
    render();
  }
})();
