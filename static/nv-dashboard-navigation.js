(() => {
  const scan = document.querySelector('[data-run-system-scan]');
  if (scan) scan.addEventListener('click', () => {
    document.querySelector('[data-scan-progress]').textContent = 'Lokale controles worden uitgevoerd…';
  });
  const forms = [...document.querySelectorAll('main form[method="post"]')];
  const dirty = new Set();
  window.addEventListener('beforeunload', event => {
    if (dirty.size) {
      event.preventDefault();
      event.returnValue = '';
    }
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
      if ([...dirty].some(other => other !== form)
          && !window.confirm('Een ander formulier heeft niet-opgeslagen wijzigingen. Doorgaan?')) {
        event.preventDefault();
        return;
      }
      dirty.clear();
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
