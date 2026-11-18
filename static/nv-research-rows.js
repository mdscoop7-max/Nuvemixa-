/* Compacte productrijen: 'Details' klapt de onderbouwing open. Zonder JavaScript blijft alles zichtbaar. */
(() => {
  'use strict';
  document.querySelectorAll('[data-prow-details]').forEach(el => { el.hidden = true; });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-prow-toggle]');
    if (!button) return;
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    if (!panel) return;
    const open = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(open));
    button.textContent = open ? 'Sluiten' : 'Details';
    panel.hidden = !open;
  });
})();
