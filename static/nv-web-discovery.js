(function () {
  "use strict";
  var form = document.getElementById("nv-wd-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var button = $("nv-wd-submit"), box = $("nv-wd-progress"), status = $("nv-wd-status"), timer = $("nv-wd-timer");
  var errorBox = $("nv-wd-error"), results = $("nv-wd-results"), summary = $("nv-wd-summary");
  var more = $("nv-wd-more"), exclude = $("nv-wd-exclude"), skipped = $("nv-wd-skipped"), hints = $("nv-wd-hints");
  var hintList = hints.querySelector(".nv-ai-results"), hintCount = hints.querySelector("summary span");
  var label0 = button.textContent, running = false, shown = [], total = 0, verified = 0;
  var CLIENT_TIMEOUT_MS = 29000;

  function text(tag, value, cls) {
    var el = document.createElement(tag);
    el.textContent = value;
    if (cls) el.className = cls;
    return el;
  }
  function link(href, value) {
    if (!/^https?:\/\//.test(href || "")) return null;
    var a = text("a", value);
    a.href = href; a.rel = "noopener noreferrer nofollow"; a.target = "_blank";
    return a;
  }
  function card(item) {
    var el = document.createElement("article");
    el.className = "nv-ai-card";
    el.appendChild(text("span", item.status, "nv-wd-badge " + (item.verified ? "ok" : "hint")));
    el.appendChild(text("span", "Live gevonden", "nv-wd-badge"));
    if (item.model_label) el.appendChild(text("span", "Model " + item.model_label, "nv-wd-badge"));
    if (item.register) {
      el.appendChild(text("span", "Ook in register: " + item.register.models.join(", ") + " · " + item.register.status +
        " (handmatig onderzocht " + item.register.checked + ")", "nv-wd-badge"));
    }
    el.appendChild(text("h3", item.name));
    var list = document.createElement("dl");
    (item.facts || []).forEach(function (fact) {
      list.appendChild(text("dt", fact.label));
      var dd = text("dd", fact.value, fact.status === "onbekend" ? "nv-unconfirmed" : "");
      if (fact.quote) dd.appendChild(text("blockquote", "Op de pagina: “" + fact.quote + "”"));
      list.appendChild(dd);
    });
    el.appendChild(list);
    var links = document.createElement("p");
    links.className = "nv-wd-links";
    [[item.url, "Gecontroleerde pagina"], [item.contact, "Contact / B2B-pagina"], [item.home, item.domain]]
      .forEach(function (pair) { var a = link(pair[0], pair[1]); if (a) links.appendChild(a); });
    el.appendChild(links);
    if (form.dataset.saveUrl) el.appendChild(saveButton(item));
    return el;
  }
  function saveButton(item) {
    var b = text("button", "Bewaar op kandidatenlijst", "nv-blue-action");
    b.type = "button";
    b.addEventListener("click", function () {
      var fd = new FormData();
      fd.set("_csrf_token", form._csrf_token.value);
      fd.set("name", item.name); fd.set("url", item.url);
      fd.set("model", item.role === "Dropshippingleverancier" ? "A" : "B");
      fd.set("notes", "Live webonderzoek " + new Date().toISOString().slice(0, 10) + ": " + item.status + " · " + item.role + " · " + item.url);
      b.disabled = true; b.textContent = "Bezig met bewaren…";
      fetch(form.dataset.saveUrl, {method: "POST", body: fd, credentials: "same-origin"})
        .then(function (r) { b.textContent = r.ok ? "Bewaard op kandidatenlijst (Partners zoeken)" : "Bewaren mislukt (HTTP " + r.status + ")"; })
        .catch(function () { b.textContent = "Bewaren mislukt"; b.disabled = false; });
    });
    return b;
  }
  function finish(label) {
    status.textContent = label;
    box.className = "nv-ai-progress done";
    running = false; button.disabled = false; button.textContent = label0; more.disabled = false;
  }
  function run(append) {
    if (running || !form.reportValidity()) return;
    running = true;
    if (!append) { shown = []; total = 0; verified = 0; results.textContent = ""; hintList.textContent = ""; hints.hidden = true; skipped.hidden = true; skipped.querySelector("ul").textContent = ""; }
    exclude.value = shown.join(",");
    button.disabled = true; more.disabled = true; button.textContent = "Bezig met zoeken…";
    errorBox.hidden = true; box.hidden = false; box.className = "nv-ai-progress";
    status.textContent = "AI zoekt op het web; daarna worden de pagina's gecontroleerd…";
    var started = Date.now();
    var tick = setInterval(function () { timer.textContent = Math.floor((Date.now() - started) / 1000) + " s"; }, 1000);
    var controller = new AbortController();
    var stop = setTimeout(function () { controller.abort(); }, CLIENT_TIMEOUT_MS);
    fetch(form.action, {method: "POST", body: new FormData(form), credentials: "same-origin",
                        headers: {"Accept": "application/json"}, signal: controller.signal})
      .then(function (r) { return r.text().then(function (t) { try { return JSON.parse(t); } catch (e) { return {ok: false, message: "Onleesbaar antwoord (HTTP " + r.status + ")."}; } }); })
      .then(function (data) {
        clearInterval(tick); clearTimeout(stop);
        if (!data.ok) { finish("Niet voltooid"); errorBox.textContent = data.message || "Zoekopdracht mislukt."; errorBox.hidden = false; return; }
        var added = 0;
        data.results.forEach(function (item) {
          if (shown.indexOf(item.domain) !== -1) return;
          added += 1;
          shown.push(item.domain); total += 1; if (item.verified) verified += 1;
          (item.verified ? results : hintList).appendChild(card(item));
        });
        hintCount.textContent = hintList.children.length; hints.hidden = !hintList.children.length;
        var m = data.meta || {};
        summary.hidden = false;
        summary.textContent = total + " unieke bedrijven (" + verified + " gecontroleerd) voor “" + data.term + "” · "
          + data.kind_label + " · " + data.category_label + (data.cached ? " · uit cache, geen kosten" :
          " · AI-zoekacties: " + (m.searches || 0) + ", kandidaten: " + (m.candidates || 0) + ", tijd: " + Math.round((m.elapsed_ms || 0) / 1000) + " s");
        var list = skipped.querySelector("ul");
        var known = [].map.call(list.children, function (li) { return li.textContent; });
        (data.skipped || []).forEach(function (reason) { if (known.indexOf(reason) === -1) list.appendChild(text("li", reason)); });
        if (data.outside_scope) list.appendChild(text("li", data.outside_scope + " bedrijf/bedrijven buiten het gekozen land of de regio."));
        skipped.hidden = !list.children.length;
        more.hidden = false;
        finish(verified ? "Klaar" : "Klaar · geen gecontroleerde bedrijven");
        if (append && !added) {
          errorBox.textContent = "Deze extra zoekronde vond geen nieuwe bedrijven" + ((data.meta || {}).repeated ? " (AI noemde " + data.meta.repeated + " al getoonde bedrijven opnieuw; die zijn weggelaten)" : "") + ". Probeer een andere zoekterm, categorie of land.";
          errorBox.hidden = false;
          return;
        }
        if (!verified) { errorBox.textContent = "Nog geen bedrijf gevonden waarvan de pagina het product en een zakelijk signaal bevat (zie eventueel de aanwijzingen hieronder). Probeer een bredere zoekterm, een andere categorie of een ander land."; errorBox.hidden = false; }
      })
      .catch(function (error) {
        clearInterval(tick); clearTimeout(stop);
        finish("Niet voltooid");
        errorBox.textContent = error && error.name === "AbortError" ? "Time-out: geen antwoord binnen 29 seconden. Probeer het opnieuw; een geslaagd deel staat daarna in de cache." : "Verbinding met het dashboard mislukt.";
        errorBox.hidden = false;
      });
  }
  form.addEventListener("submit", function (event) { event.preventDefault(); run(false); });
  // Partners: zoekterm uit het register direct ook live laten zoeken (één klik, geen automatische AI-kosten).
  if (form.dataset.prefill) {
    var live = text("button", "Zoek ook live met AI naar “" + form.dataset.prefill + "”", "nv-blue-action");
    live.type = "button";
    live.addEventListener("click", function () { form.elements.term.value = form.dataset.prefill; run(false); });
    form.parentNode.insertBefore(live, form);
  }
  more.addEventListener("click", function () { run(true); });
})();
