/* Alleen presentatie: statusteksten in tabellen/lijsten krijgen een kleurlabel. */
(function () {
  var warn = /^(niet (gekoppeld|ingesteld|geactiveerd|bevestigd|getest)|nog niet|geen (actieve )?koppeling|ontbreekt)/i;
  var ok = /^(gekoppeld|ingesteld|beschikbaar|beveiligd|actief)/i;
  document.querySelectorAll('main td, main .status-cell').forEach(function (cell) {
    if (cell.children.length || cell.dataset.nvChip) return;
    var t = cell.textContent.trim();
    var cls = warn.test(t) ? 'nvm-chip-warn' : ok.test(t) ? 'nvm-chip-ok' : '';
    if (!cls || t.length > 90) return;
    cell.dataset.nvChip = '1';
    var chip = document.createElement('span');
    chip.className = 'nvm-chip ' + cls;
    chip.textContent = t;
    cell.textContent = '';
    cell.appendChild(chip);
  });
})();
