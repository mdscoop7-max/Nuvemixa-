(function () {
  "use strict";
  var form = document.getElementById("nv-ai-form");
  if (!form) return;
  var button = document.getElementById("nv-ai-submit");
  var box = document.getElementById("nv-ai-progress");
  var status = document.getElementById("nv-ai-status");
  var timer = document.getElementById("nv-ai-timer");
  var steps = document.getElementById("nv-ai-steps");
  var slow = document.getElementById("nv-ai-slow");
  var errorBox = document.getElementById("nv-ai-error");
  var results = document.getElementById("nv-ai-results");
  var running = false;
  var label0 = button.textContent, disabled0 = button.disabled;
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    running = false; button.disabled = disabled0; button.textContent = label0; box.hidden = true;
  });
  var CLIENT_TIMEOUT_MS = 28000;
  var SLOW_AFTER_S = 8;

  function step(text) {
    var item = document.createElement("li");
    item.textContent = text;
    steps.appendChild(item);
  }
  function fail(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }
  function row(list, label, value) {
    var dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    if (value === "Niet bevestigd") dd.className = "nv-unconfirmed";
    list.appendChild(dt);
    list.appendChild(dd);
  }
  function link(parent, href, text) {
    if (!/^https:\/\//.test(href)) { parent.textContent = text; return; }
    var a = document.createElement("a");
    a.href = href; a.rel = "noopener noreferrer"; a.target = "_blank"; a.textContent = text;
    parent.appendChild(a);
  }
  function card(item) {
    var el = document.createElement("article");
    el.className = "nv-ai-card";
    var title = document.createElement("h3");
    title.textContent = item.name;
    el.appendChild(title);
    var list = document.createElement("dl");
    row(list, "Land", item.country);
    var site = document.createElement("dd"), siteLabel = document.createElement("dt");
    siteLabel.textContent = "Website";
    link(site, item.website, item.website.replace(/^https:\/\//, ""));
    list.appendChild(siteLabel); list.appendChild(site);
    row(list, "Productcategorie", item.categories);
    row(list, "Dropshipping", item.dropshipping);
    row(list, "WooCommerce", item.woocommerce);
    row(list, "Sell The Trend", item.sell_the_trend);
    row(list, "Levertijd en landen", item.delivery);
    row(list, "Contact", item.contact);
    var src = document.createElement("dd"), srcLabel = document.createElement("dt");
    srcLabel.textContent = "Bron";
    link(src, item.source.href, item.source.label);
    src.appendChild(document.createTextNode(" · " + item.source.origin));
    list.appendChild(srcLabel); list.appendChild(src);
    el.appendChild(list);
    return el;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (running) return;
    if (!form.reportValidity()) return;
    running = true;
    button.disabled = true;
    button.textContent = "Bezig met zoeken...";
    errorBox.hidden = true; slow.hidden = true;
    results.textContent = ""; steps.textContent = "";
    box.hidden = false; box.className = "nv-ai-progress";
    status.textContent = "Product analyseren en AI zoekt leveranciers…";
    var started = Date.now();
    timer.textContent = "0 s";
    var tick = setInterval(function () {
      var seconds = Math.floor((Date.now() - started) / 1000);
      timer.textContent = seconds + " s";
      if (seconds >= SLOW_AFTER_S) slow.hidden = false;
    }, 1000);
    var controller = new AbortController();
    var abort = setTimeout(function () { controller.abort(); }, CLIENT_TIMEOUT_MS);
    step("Zoekopdracht verzonden.");
    step("AI-antwoord wordt afgewacht…");
    function finish(label) {
      clearInterval(tick); clearTimeout(abort);
      timer.textContent = Math.floor((Date.now() - started) / 1000) + " s";
      status.textContent = label;
      box.className = "nv-ai-progress done";
      slow.hidden = true;
      running = false;
      button.disabled = false;
      button.textContent = label0;
    }
    fetch(form.action, {method: "POST", body: new FormData(form), credentials: "same-origin",
                        headers: {"Accept": "application/json"}, signal: controller.signal})
      .then(function (response) {
        return response.text().then(function (text) {
          var data = null;
          try { data = JSON.parse(text); } catch (e) { data = null; }
          return {status: response.status, data: data, text: text};
        });
      })
      .then(function (reply) {
        var data = reply.data;
        if (!data) {
          step("Antwoord van het dashboard kon niet worden gelezen.");
          finish("Zoekopdracht mislukt");
          fail(reply.status === 503 && reply.text && reply.text.length < 400
            ? reply.text.trim()
            : "Het dashboard gaf een onleesbaar antwoord (HTTP " + reply.status + "). Vernieuw de pagina en probeer opnieuw.");
          return;
        }
        if (!data.ok) {
          step("Zoekopdracht niet voltooid.");
          finish("Zoekopdracht niet voltooid");
          fail(data.message || "De zoekopdracht is mislukt.");
          return;
        }
        var meta = data.meta || {};
        if (meta.cached) step("Resultaat uit een eerdere identieke zoekopdracht (geen nieuwe AI-aanroep).");
        else step("AI-antwoord ontvangen. Bronnen gecontroleerd: " + meta.citations_received + " verwijzingen ontvangen, " + meta.sources_accepted + " geaccepteerd.");
        step("Resultaten worden weergegeven.");
        finish(data.results.length ? data.results.length + " leverancier(s) gevonden" : "Klaar");
        if (!data.results.length) fail(data.message || "Geen controleerbare bron gevonden.");
        data.results.forEach(function (item) { results.appendChild(card(item)); });
      })
      .catch(function (error) {
        step("Geen antwoord ontvangen.");
        finish("Zoekopdracht mislukt");
        fail(error && error.name === "AbortError"
          ? "Time-out: het dashboard antwoordde niet binnen " + (CLIENT_TIMEOUT_MS / 1000) + " seconden. De zoekopdracht is mogelijk wel verwerkt; wacht even voor je opnieuw zoekt."
          : "Verbinding met het dashboard mislukt (Failed to fetch). Controleer je internetverbinding en probeer opnieuw.");
      });
  });
})();
