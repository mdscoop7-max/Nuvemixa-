(function () {
  "use strict";
  var box = document.getElementById("nv-rj");
  if (!box) return;
  var marker = document.querySelector('form[action="/dashboard"] input[name="research_block"][value="product"]');
  var form = marker && marker.form;
  if (!form || !window.fetch) return;   // zonder JavaScript blijft de bestaande zoekroute werken
  var $ = function (id) { return document.getElementById(id); };
  var steps = $("nv-rj-steps"), status = $("nv-rj-status"), timer = $("nv-rj-timer"), errorBox = $("nv-rj-error");
  var body = $("nv-rj-body"), title = $("nv-rj-title");
  var canSave = box.dataset.canSave === "1";
  var POLL_MS = 2500, MAX_WAIT_MS = 180000, running = false;
  form.parentNode.insertBefore(box, form.nextSibling);
  // 'Onderzoek dit product' vanuit Onderzoeksplatforms & trends: naam en categorie overnemen en direct onderzoeken.
  var start = new URLSearchParams(location.search);
  if (start.get("autorun") === "1" && start.get("research_term")) {
    setTimeout(function () {
      form.elements.research_term.value = start.get("research_term").slice(0, 100);
      var cat = start.get("research_category");
      if (cat && form.elements.research_category && [].some.call(form.elements.research_category.options, function (o) { return o.value === cat; })) {
        form.elements.research_category.value = cat;
      }
      if (typeof form.requestSubmit === "function") form.requestSubmit(); else form.dispatchEvent(new Event("submit", {cancelable: true}));
    }, 300);
  }

  function el(tag, text, cls) { var e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; }
  function link(href, text) {
    if (!/^https?:\/\//.test(href || "")) return null;
    var a = el("a", text); a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer nofollow"; return a;
  }
  function money(p) { return p ? p.currency + " " + p.amount.toFixed(2).replace(".", ",") : "Prijs onbekend"; }
  function regionName(code) { return {nl: "Nederland", eu: "Europese Unie", international: "Internationaal (buiten de EU)", unknown: "Land niet bevestigd"}[code]; }
  // Controleert het echte resultaat: de server stuurt ook bij een geweigerde invoer een gewone pagina terug.
  // Concept: succes = doorverwijzing naar het nieuwe concept (open=...). Kandidaat: bevestigingstekst op de pagina.
  function post(url, fields, button, done, kind) {
    var fd = new FormData(); fd.set("_csrf_token", box.dataset.csrf);
    Object.keys(fields).forEach(function (k) { fd.set(k, fields[k]); });
    button.disabled = true; button.textContent = "Bezig…";
    fetch(url, {method: "POST", body: fd, credentials: "same-origin"})
      .then(function (r) { return r.text().then(function (t) { return {r: r, t: t}; }); })
      .then(function (x) {
        var ok = x.r.ok && (kind === "concept" ? /[?&]open=\d+/.test(x.r.url) : !/staat al in de leverancierslijst|Opslaan is nu niet gelukt/i.test(x.t));
        var dup = /staat al in de leverancierslijst/i.test(x.t);
        button.textContent = ok ? done : dup ? "Stond al op de kandidatenlijst" : "Niet opgeslagen: controleer de gegevens";
        if (!ok && !dup) button.disabled = false;
      })
      .catch(function () { button.textContent = "Opslaan mislukt"; button.disabled = false; });
  }

  function productCard(p, category) {
    var c = el("article", null, "nv-rj-card");
    c.appendChild(el("h4", p.title));
    if (p.offer_count > 1) c.appendChild(el("p", p.offer_count + " aanbieders · " + p.same_product_note, "nv-rj-meta"));
    var ul = el("ul", null, "nv-rj-offers");
    p.offers.forEach(function (o) {
      var li = el("li");
      li.appendChild(el("strong", o.supplier || "Onbekende aanbieder"));
      var bits = [o.source, o.warehouse ? "magazijn " + o.warehouse : "", money(o.price)];
      if (o.eur && o.price && o.price.currency !== "EUR") bits.push("≈ € " + o.eur.eur.toFixed(2).replace(".", ",") + " (ECB " + o.eur.date + ")");
      if (o.dropship) bits.push("dropshipping bevestigd door platform");
      li.appendChild(document.createTextNode(" · " + bits.filter(Boolean).join(" · ") + " "));
      var a = link(o.url, "bekijk"); if (a) li.appendChild(a);
      ul.appendChild(li);
    });
    c.appendChild(ul);
    var actions = el("div", null, "nv-rj-actions");
    var first = p.offers[0] || {};
    var m = el("a", "Bereken marge"); m.className = "nv-blue-action";
    var q = new URLSearchParams({section: "onderzoek", margin_product: p.title.slice(0, 120)});
    if (first.price) { q.set("margin_amount", first.price.amount); q.set("margin_currency", first.price.currency); }
    m.href = "/dashboard?" + q.toString() + "#nv-product-margin";
    actions.appendChild(m);
    if (canSave) {
      var b = el("button", "Bewaar als concept"); b.type = "button";
      b.addEventListener("click", function () {
        post(box.dataset.concept, {titel: p.title.slice(0, 120), bron_url: first.url || "", bron_naam: (first.source || "").slice(0, 80),
          leverancier: (first.supplier || "").slice(0, 120), categorie: category || ""}, b, "Bewaard als conceptproduct", "concept");
      });
      actions.appendChild(b);
    }
    c.appendChild(actions);
    return c;
  }

  function supplierCard(s) {
    var c = el("article", null, "nv-rj-card");
    c.appendChild(el("span", s.verified ? "Gecontroleerd" : "Aanwijzing", "nv-rj-badge " + (s.verified ? "ok" : "hint")));
    s.sources.forEach(function (src) { c.appendChild(el("span", src, "nv-rj-badge")); });
    c.appendChild(el("h4", s.name));
    c.appendChild(el("p", [s.role, s.country ? s.country + (s.country_note ? " (" + s.country_note + ")" : "") : "land niet bevestigd", s.products ? s.products + " product(en) hierboven" : ""].filter(Boolean).join(" · "), "nv-rj-meta"));
    if (s.status && !s.verified) c.appendChild(el("p", s.status, "nv-rj-meta"));
    if (s.evidence) c.appendChild(el("blockquote", (s.sources.indexOf("AI-webonderzoek") >= 0 ? "Op de pagina: “" + s.evidence + "”" : s.evidence)));
    var links = el("div", null, "nv-rj-actions");
    [[s.page, "Gecontroleerde pagina"], [s.contact, "Contact / B2B"], [s.website, s.domain || "Website"]].forEach(function (x) { var a = link(x[0], x[1]); if (a) links.appendChild(a); });
    if (canSave) {
      var b = el("button", "Bewaar als kandidaat"); b.type = "button";
      b.addEventListener("click", function () {
        post(box.dataset.candidate, {name: s.name.slice(0, 120), url: s.page || s.website || "", model: s.dropship ? "A" : "B",
          notes: "Onderzoek " + new Date().toISOString().slice(0, 10) + ": " + (s.verified ? "gecontroleerd" : "aanwijzing") + " · " + s.sources.join(", ") + " · " + (s.role || "")}, b, "Bewaard op kandidatenlijst", "candidate");
      });
      links.appendChild(b);
    }
    c.appendChild(links);
    return c;
  }

  function table(headers, rows) {
    var wrap = el("div", null, "nv-rj-table-wrap"), t = el("table"), tr = el("tr");
    headers.forEach(function (h) { tr.appendChild(el("th", h)); });
    t.appendChild(tr);
    rows.forEach(function (r) { var row = el("tr"); r.forEach(function (v) { row.appendChild(el("td", v)); }); t.appendChild(row); });
    wrap.appendChild(t); return wrap;
  }

  function render(r) {
    body.textContent = "";
    title.textContent = "Onderzoek: “" + r.term + "”";
    var ai = r.ai;
    var summary = el("p", (r.counts.exact_products != null ? r.counts.exact_products + " passend, " : "") + r.counts.products + " product(en) totaal (" + r.counts.offers + " vermeldingen) · " + r.counts.suppliers +
      " unieke leverancier(s), waarvan " + r.counts.verified_suppliers + " gecontroleerd · categorie " + r.category_label +
      " (" + r.category_source + ") · " + r.filter_label + " · " + r.elapsed_s + " s");
    summary.className = "nv-rj-meta"; body.appendChild(summary);
    var aiText = ai.used ? "AI-zoekwoorden: " + ai.keywords_en.concat(ai.keywords_nl).join(", ") + ". AI-bijdrage: " +
      ai.products_via_ai_keywords + " product(en) alleen via AI-/vertaalde zoekwoorden, " + ai.web_suppliers +
      " gecontroleerde leverancier(s) via AI-webonderzoek, " + ai.removed_by_ai + " product(en) door AI weggefilterd."
      : "AI niet gebruikt: " + (ai.message || "niet ingesteld") + ". Gezocht met: " + r.queries.join(", ") + ".";
    body.appendChild(el("p", aiText, "nv-rj-meta"));
    if (r.fallback) body.appendChild(el("p", r.fallback, "nv-rj-meta"));

    var exact = r.products.filter(function (p) { return p.match !== "related"; });
    var related = r.products.filter(function (p) { return p.match === "related"; });
    body.appendChild(el("h3", "Passende producten (" + exact.length + ")"));
    if (exact.length) {
      var g = el("div", null, "nv-rj-grid");
      exact.forEach(function (p) { g.appendChild(productCard(p, r.category)); });
      body.appendChild(g);
    } else body.appendChild(el("p", "Geen product waarvan de naam de volledige zoekterm bevat. " + (related.length ? "Bekijk de verwante producten hieronder of " : "") + "zie de leveranciers hieronder; die zijn op het open web gezocht.", "nv-rj-meta"));
    if (related.length) {
      var rel = el("details");
      rel.appendChild(el("summary", "Verwante producten (" + related.length + "): passen alleen op een algemener zoekwoord"));
      var rg = el("div", null, "nv-rj-grid");
      related.forEach(function (p) { rg.appendChild(productCard(p, r.category)); });
      rel.appendChild(rg); body.appendChild(rel);
    }

    [["nl", "Leveranciers in Nederland"], ["eu", "Leveranciers in de EU"], ["unknown", "Leveranciers, land niet bevestigd"], ["international", "Internationale leveranciers (buiten de EU)"]].forEach(function (sec) {
      var list = r.suppliers[sec[0]] || [];
      if (!list.length) return;
      body.appendChild(el("h3", sec[1] + " (" + list.length + ")"));
      var grid = el("div", null, "nv-rj-grid");
      list.forEach(function (s) { grid.appendChild(supplierCard(s)); });
      body.appendChild(grid);
    });
    if (r.hidden_by_filter) body.appendChild(el("p", r.hidden_by_filter + " leverancier(s) verborgen door het filter “" + r.filter_label + "”.", "nv-rj-meta"));

    if (r.register.length || r.register_category.length || r.saved_suppliers.length) {
      body.appendChild(el("h3", "Uit het bestaande register (handmatig onderzocht, niet live gecontroleerd)"));
      var regRows = r.register.map(function (x) { return [x.name, x.type, x.status, "noemt: " + x.hits.join(", "), x.url]; })
        .concat(r.register_category.map(function (x) { return [x.name, x.type, x.status, "zelfde categorie", x.url]; }))
        .concat(r.saved_suppliers.map(function (x) { return [x.name, "Eigen leverancierslijst", "", x.notes, x.url]; }));
      body.appendChild(table(["Naam", "Soort", "Status", "Waarom getoond", "Website"], regRows));
    }

    var src = el("details"); src.open = true;
    src.appendChild(el("summary", "Doorzochte bronnen (" + r.sources.length + ")"));
    src.appendChild(table(["Bron", "Soort", "Status", "Resultaten"], r.sources.map(function (s) { return [s.name, s.kind, s.status, String(s.count)]; })));
    body.appendChild(src);
    if (r.removed.length) {
      var rem = el("details");
      rem.appendChild(el("summary", "Weggefilterd als niet passend (" + r.removed.length + ")"));
      var ul = el("ul"); r.removed.forEach(function (x) { ul.appendChild(el("li", x.title + " · " + (x.supplier || "") + " · " + x.reason)); });
      rem.appendChild(ul); body.appendChild(rem);
    }
  }

  function showSteps(list) {
    steps.textContent = "";
    (list || []).forEach(function (s) { steps.appendChild(el("li", s.t + " s · " + s.text)); });
  }

  function finish(label) { box.className = "panel nv-rj done"; status.textContent = label; running = false; }

  function poll(key, started) {
    fetch(box.dataset.status + "?key=" + encodeURIComponent(key), {credentials: "same-origin", headers: {Accept: "application/json"}})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        showSteps(d.steps);
        timer.textContent = Math.round((Date.now() - started) / 1000) + " s";
        if (d.state === "done" && d.result) { finish("Klaar"); render(d.result); return; }   // nieuw onderzoek, net afgerond
        if (d.state === "failed" || d.ok === false) { finish("Niet voltooid"); errorBox.textContent = d.error || d.message || "Onderzoek mislukt."; errorBox.hidden = false; return; }
        if (Date.now() - started > MAX_WAIT_MS) { finish("Duurt erg lang"); errorBox.textContent = "Het onderzoek loopt nog op de server. Vernieuw de pagina en zoek opnieuw; het resultaat komt dan uit de cache."; errorBox.hidden = false; return; }
        setTimeout(function () { poll(key, started); }, POLL_MS);
      })
      .catch(function () { setTimeout(function () { poll(key, started); }, POLL_MS * 2); });
  }

  form.addEventListener("submit", function (event) {
    var mode = (form.elements.research_mode || {}).value;
    if (mode === "news") return;               // nieuws en reviews: bestaande route
    event.preventDefault();
    if (running) return;
    var term = (form.elements.research_term || {}).value || "";
    if (term.trim().length < 2) { form.elements.research_term.focus(); return; }
    running = true;
    box.hidden = false; box.className = "panel nv-rj"; errorBox.hidden = true; body.textContent = "";
    title.textContent = "Onderzoek: “" + term.trim() + "”"; status.textContent = "Bezig… (dit mag langer dan 30 seconden duren)";
    showSteps([]);
    box.scrollIntoView({behavior: "smooth", block: "start"});
    var fd = new FormData(form); fd.set("_csrf_token", box.dataset.csrf);
    var started = Date.now();
    fetch(box.dataset.start, {method: "POST", body: fd, credentials: "same-origin", headers: {Accept: "application/json"}})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) { finish("Niet gestart"); errorBox.textContent = d.message || "Onderzoek kon niet starten."; errorBox.hidden = false; return; }
        showSteps(d.steps);
        if (d.state === "done" && d.result) {
          var age = Math.round((d.age_s || 0) / 60);
          finish("Klaar (uit de permanente cache van " + (age < 60 ? age + " min" : Math.round(age / 60) + " uur") + " geleden, geen kosten)");
          render(d.result); return;
        }
        poll(d.key, started);
      })
      .catch(function () { finish("Niet gestart"); errorBox.textContent = "Verbinding met het dashboard mislukt."; errorBox.hidden = false; });
  });
})();
