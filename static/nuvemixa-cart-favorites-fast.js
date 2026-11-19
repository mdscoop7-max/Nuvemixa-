/* NUVEMIXA progressive enhancements for cart quantities and favourites.
   Existing forms remain functional without JavaScript. */
(function () {
  'use strict';
  if (!window.fetch || !window.DOMParser) return;

  function wishlistBadge(count) {
    document.querySelectorAll('[data-wishlist-count]').forEach(function (badge) {
      badge.textContent = String(count);
      badge.hidden = count <= 0;
    });
  }
  function favoriteState(id, saved) {
    document.querySelectorAll('form[action="/wishlist"] input[name="product_id"]').forEach(function (input) {
      if (input.value !== id) return;
      var button = input.form && input.form.querySelector('button[type="submit"]');
      if (!button) return;
      var mark = button.querySelector('.tm-heart-mark');
      if (mark) mark.classList.toggle('tm-heart-selected', saved);
      button.setAttribute('aria-pressed', saved ? 'true' : 'false');
      button.setAttribute('aria-label', saved ? 'Verwijderen uit favorieten' : 'Toevoegen aan favorieten');
      var title = button.querySelector('[data-wishlist-action]');
      if (title) title.textContent = saved ? 'In favorieten' : 'Bewaar als favoriet';
    });
  }
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    if (form.matches('form[action="/wishlist"]') && form.querySelector('input[name="product_id"]')) {
      event.preventDefault();
      var button = form.querySelector('button[type="submit"]');
      if (button && button.disabled) return;
      if (button) button.disabled = true;
      var id = form.querySelector('input[name="product_id"]').value;
      fetch(form.action, {
        method: 'POST', credentials: 'same-origin',
        headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        body: new FormData(form)
      }).then(function (response) {
        if (!response.ok) throw new Error('Favorieten konden niet worden bijgewerkt');
        return response.json();
      }).then(function (data) {
        if (!data.ok || typeof data.count !== 'number') throw new Error('Ongeldig antwoord');
        wishlistBadge(data.count);
        favoriteState(id, Boolean(data.saved));
        if (window.location.pathname === '/wishlist') window.location.reload();
      }).catch(function () {
        window.location.reload();
      }).finally(function () { if (button) button.disabled = false; });
      return;
    }

    if (window.location.pathname !== '/winkelwagen' ||
        !form.matches('.cart-page .cart-actions form') ||
        !form.querySelector('input[name="delta"]')) return;
    event.preventDefault();
    var row = form.closest('.cart-row');
    if (!row || row.dataset.cartBusy === '1') return;
    row.dataset.cartBusy = '1';
    row.querySelectorAll('.cart-actions button').forEach(function (button) { button.disabled = true; });
    fetch(form.action, {
      method: 'POST', credentials: 'same-origin',
      headers: {'X-Requested-With': 'XMLHttpRequest'},
      body: new FormData(form)
    }).then(function (response) {
      if (!response.ok) throw new Error('Winkelwagen kon niet worden bijgewerkt');
      return response.text();
    }).then(function (html) {
      var parsed = new DOMParser().parseFromString(html, 'text/html');
      var current = document.querySelector('main.cart-page');
      var next = parsed.querySelector('main.cart-page');
      if (!current || !next) throw new Error('Winkelwagen niet gevonden');
      var productId = form.querySelector('input[name="product_id"]').value;
      var scrollPosition = window.scrollY;
      current.innerHTML = next.innerHTML;
      var newRow = Array.from(current.querySelectorAll('.cart-row')).find(function (candidate) {
        var field = candidate.querySelector('input[name="product_id"]');
        return field && field.value === productId;
      });
      if (newRow) {
        var plus = newRow.querySelector('input[name="delta"][value="1"]');
        var focus = plus && plus.form && plus.form.querySelector('button');
        if (focus) focus.focus({preventScroll:true});
      }
      var count = parsed.querySelector('[data-cart-count]');
      if (count) document.querySelectorAll('[data-cart-count]').forEach(function (badge) {
        badge.textContent = count.textContent;
      });
      window.scrollTo({top:scrollPosition,behavior:'instant'});
    }).catch(function () {
      window.location.reload();
    });
  }, false);
})();
