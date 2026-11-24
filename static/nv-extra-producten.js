/* Extra producten: fotovoorbeeld, live webshopvoorbeeld en prijsadvies (zelfde rekenkern als de calculator). */
(function () {
  'use strict';
  var MAX = 5 * 1024 * 1024;
  function euro(cents) {
    return '€ ' + (cents / 100).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }
  function cents(input) {
    var v = parseFloat(String(input.value || '').replace(',', '.'));
    return isFinite(v) && v > 0 ? Math.round(v * 100) : null;
  }
  function setup(form) {
    var file = form.querySelector('[data-xp-file]'), drop = form.querySelector('[data-xp-drop]');
    var link = form.querySelector('[data-xp-link]'), img = form.querySelector('[data-xp-img]');
    var name = form.querySelector('[data-xp-name]'), shortText = form.querySelector('[data-xp-short]');
    var cost = form.querySelector('[data-xp-cost]'), price = form.querySelector('[data-xp-price]');
    var advice = form.querySelector('[data-xp-advice]'), advicePrice = form.querySelector('[data-xp-advice-price]');
    var marginLine = form.querySelector('[data-xp-margin]'), use = form.querySelector('[data-xp-use]');
    var target = 30, adviceCents = null, objectUrl = null;

    function showImage(src) {
      img.textContent = '';
      if (!src) { var s = document.createElement('span'); s.textContent = 'Nog geen foto'; img.appendChild(s); return; }
      var el = document.createElement('img'); el.alt = ''; el.src = src; img.appendChild(el);
    }
    function pickFile(f) {
      if (!f) return;
      if (f.size > MAX) { alertLine(drop, 'Deze foto is groter dan 5 MB. Kies een kleinere foto.'); file.value = ''; return; }
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(f);
      showImage(objectUrl);
      drop.classList.add('has-file');
      drop.querySelector('strong').textContent = f.name;
    }
    function alertLine(el, text) {
      var p = el.parentNode.querySelector('.nv-xp-err') || document.createElement('p');
      p.className = 'nv-xp-err'; p.setAttribute('role', 'alert'); p.textContent = text;
      el.parentNode.insertBefore(p, el.nextSibling);
    }
    if (file) {
      file.addEventListener('change', function () { pickFile(file.files[0]); });
      ['dragenter', 'dragover'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
      ['dragleave', 'drop'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove('over'); }); });
      drop.addEventListener('drop', function (e) {
        var f = e.dataTransfer && e.dataTransfer.files[0];
        if (!f) return;
        try { var dt = new DataTransfer(); dt.items.add(f); file.files = dt.files; } catch (err) { /* oudere browser */ }
        pickFile(f);
      });
    }
    if (link) link.addEventListener('input', function () {
      if (file && file.files && file.files.length) return;
      showImage(/^https:\/\/\S+$/.test(link.value.trim()) ? link.value.trim() : null);
    });
    function text() {
      form.querySelector('[data-xp-pname]').textContent = name.value.trim() || 'Productnaam';
      form.querySelector('[data-xp-pshort]').textContent = shortText.value.trim() || 'Korte omschrijving';
    }
    name.addEventListener('input', text); shortText.addEventListener('input', text);

    function prices() {
      var core = window.NVMargin, buy = cents(cost), sell = cents(price);
      form.querySelector('[data-xp-pprice]').textContent = euro(sell || 0);
      advice.hidden = !(core && buy);
      adviceCents = null;
      if (core && buy) {
        var r = core.compute({purchase: buy, vat: 21, target: target});
        adviceCents = r && r.advice && !r.error ? r.advice.selling : null;
        advicePrice.textContent = adviceCents ? euro(adviceCents) : '—';
      }
      marginLine.textContent = '';
      if (core && buy && sell) {
        var own = core.compute({purchase: buy, vat: 21, target: target, own: sell}).own;
        if (own) {
          marginLine.textContent = 'Bij deze prijs: geschatte winst ' + euro(own.profit) + ' per stuk, winstmarge ' +
            own.margin.toFixed(1).replace('.', ',') + '% (met standaardaannames voor verzending, advertenties, retouren en betaalkosten).';
          marginLine.className = 'nv-xp-margin' + (own.profit <= 0 ? ' bad' : own.margin < 15 ? ' low' : ' ok');
        }
      }
    }
    cost.addEventListener('input', prices); price.addEventListener('input', prices);
    var targetSelect = form.querySelector('[data-xp-target]');
    targetSelect.addEventListener('change', function () {
      target = Number(targetSelect.value);
      prices();
      if (adviceCents) { price.value = (adviceCents / 100).toFixed(2); prices(); }
    });
    img.addEventListener('click', function () {
      var photo = img.querySelector('img');
      if (!photo) return;
      var dialog = document.createElement('dialog');
      dialog.style.cssText = 'max-width:95vw;max-height:95vh;border:0;border-radius:12px;padding:12px';
      var close = document.createElement('button');
      close.type = 'button'; close.textContent = 'Sluiten ×';
      var enlarged = document.createElement('img');
      enlarged.src = photo.src; enlarged.alt = name.value;
      enlarged.style.cssText = 'display:block;max-width:85vw;max-height:80vh;object-fit:contain';
      dialog.append(close, enlarged); document.body.appendChild(dialog);
      close.addEventListener('click', function () { dialog.close(); });
      dialog.addEventListener('close', function () { dialog.remove(); });
      dialog.showModal();
    });
    img.style.cursor = 'zoom-in';
    use.addEventListener('click', function () { if (adviceCents) { price.value = (adviceCents / 100).toFixed(2); prices(); } });
    text(); prices();
  }
  function init() { document.querySelectorAll('[data-xp-form]').forEach(setup); }
  // Na DOMContentLoaded: dan is ook de rekenkern (nv-margin-core.js, later in de pagina) geladen.
  if (document.readyState === 'complete') init(); else document.addEventListener('DOMContentLoaded', init);
})();
