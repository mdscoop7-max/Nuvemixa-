(() => {
  const copyCoupon = document.querySelector('[data-copy-coupon]');
  if (copyCoupon) {
    const code = document.querySelector('#nv-created-coupon');
    const status = document.querySelector('[data-copy-coupon-status]');
    copyCoupon.hidden = false;
    copyCoupon.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(code.textContent);
        status.textContent = 'Gekopieerd';
      } catch {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(code);
        selection.removeAllRanges();
        selection.addRange(range);
        status.textContent = 'Code geselecteerd. Kopieer de code met het toetsenbord of het contextmenu.';
      }
    });
  }

  const scan = document.querySelector('[data-run-system-scan]');
  if (scan) scan.addEventListener('click', () => {
    document.querySelector('[data-scan-progress]').textContent = 'Lokale controles worden uitgevoerd…';
  });
  const menu = document.querySelector('.nv-menu-shell');
  const mobile = matchMedia('(max-width: 760px)');
  if (menu) {
    menu.open = !mobile.matches;
    mobile.addEventListener('change', event => { menu.open = !event.matches; });
    menu.addEventListener('keydown', event => {
      const entries = [...menu.querySelectorAll('nav a, nav summary')].filter(item => item.getClientRects().length);
      const index = entries.indexOf(document.activeElement);
      if (index < 0) return;
      const next = {ArrowDown: (index+1)%entries.length, ArrowUp: (index+entries.length-1)%entries.length,
                    Home: 0, End: entries.length-1}[event.key];
      if (next === undefined) return;
      event.preventDefault();
      entries[next].focus();
    });
  }
  for (const form of document.querySelectorAll('[data-research-search]')) {
    const button = form.querySelector('button[type="submit"]');
    const status = form.querySelector('[role="status"]');
    const spinner = status.querySelector('span');
    const message = document.createTextNode('');
    status.append(message);
    form.addEventListener('submit', event => {
      if (button.disabled) {
        event.preventDefault();
        return;
      }
      form.setAttribute('aria-busy', 'true');
      button.disabled = true;
      spinner.hidden = false;
      const mode = form.elements.research_mode.value;
      message.textContent = ['suppliers', 'dropship', 'wholesale'].includes(mode)
        ? 'Leveranciers zoeken...' : 'Zoeken...';
    });
    window.addEventListener('pageshow', () => {
      form.removeAttribute('aria-busy');
      button.disabled = false;
      spinner.hidden = true;
      message.textContent = '';
    });
  }

  const forms = [...document.querySelectorAll('main form[method="post"]')];
  const dirty = new Set();
  const submitting = new WeakSet();
  window.addEventListener('beforeunload', event => {
    if (dirty.size) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) forms.forEach(form => {
      submitting.delete(form);
      form.removeAttribute('aria-busy');
    });
  });
  for (const form of forms) {
    const inputs = () => JSON.stringify([...form.elements]
      .filter(input => input.name && !['hidden', 'submit', 'button'].includes(input.type))
      .map(input => [input.name, input.type === 'checkbox' ? input.checked : input.value]));
    const initial = inputs();
    const mark = () => inputs() === initial ? dirty.delete(form) : dirty.add(form);
    form.addEventListener('input', mark);
    form.addEventListener('change', mark);
    form.addEventListener('submit', event => {
      if (submitting.has(form)) {
        event.preventDefault();
        return;
      }
      const action = form.elements.op;
      if (action && ['disable', 'reset'].includes(action.value)
          && !window.confirm('Wil je deze wijziging uitvoeren?')) {
        event.preventDefault();
        return;
      }
      if ([...dirty].some(other => other !== form)
          && !window.confirm('Een ander formulier heeft niet-opgeslagen wijzigingen. Doorgaan?')) {
        event.preventDefault();
        return;
      }
      dirty.clear();
      submitting.add(form);
      form.setAttribute('aria-busy', 'true');
    });
    const parent = form.closest('details');
    if (!parent) continue;
    const back = document.createElement('button');
    back.type = 'button';
    back.className = 'nv-form-back';
    back.textContent = '← Terug';
    back.addEventListener('click', () => {
      if ([...dirty].some(other => parent.contains(other))
          && !window.confirm('Wijzigingen staan nog in het formulier. Formulier sluiten?')) return;
      parent.open = false;
      parent.querySelector('summary').focus();
    });
    form.append(back);
  }
})();
