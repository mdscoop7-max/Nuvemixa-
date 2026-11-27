(function () {
  "use strict";
  var box = document.getElementById("nv-tr"), form = document.getElementById("nv-tr-form");
  if (!box || !form || !window.fetch) return;
  var $ = function (id) { return document.getElementById(id); };
  var progress = $("nv-tr-progress"), status = $("nv-tr-status"), timer = $("nv-tr-timer"), steps = $("nv-tr-steps");
  var errorBox = $("nv-tr-error"), body = $("nv-tr-body"), button = $("nv-tr-submit");
  var canSave = box.dataset.canSave === "1", running = false;

  function el(tag, text, cls) { var e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; }
  function link(href, text) { if (!/^https:\/\//.test(href || "")) return null; var a = el("a", text); a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer nofollow"; return a; }
  var NICHE = {"gadgets": "Gadgets en elektronica", "smart-home": "Smart home", "beauty-care": "Beauty en persoonlijke verzorging", "home-living": "Huis en wonen", "lifestyle-sport": "Fitness en sport"};
  var CAT = {"gadgets": "Gadgets", "smart-home": "Smart Home", "beauty-care": "Beauty & Care", "home-living": "Home & Living", "lifestyle-sport": "Lifestyle & Sport"};

  function card(t, r) {
    var c = el("article", null, "nv-tr-card");
    c.appendChild(el("span", t.status, "nv-tr-badge"));
    c.appendChild(el("span", CAT[t.category] || t.category, "nv-tr-badge"));
    if (t.image && /^https:\/\//.test(t.image.url)) {
      var fig = el("figure", null, "nv-tr-img"), img = el("img");
      img.src = t.image.url; img.alt = t.name; img.loading = "lazy"; img.decoding = "async"; img.referrerPolicy = "no-referrer";
      img.addEventListener("error", function () { fig.remove(); });
      fig.appendChild(img);
      var cap = el("figcaption", "Afbeelding uit het artikel van " + t.image.source + " (" + t.image.date + ")");
      fig.appendChild(cap); c.appendChild(fig);
    }
    // Geen betrouwbare productafbeelding: neutrale plaatsaanduiding, nooit een willekeurige foto.
    function placeholder() {
      var ph = el("div", null, "nv-tr-ph"); ph.setAttribute("role", "img");
      ph.setAttribute("aria-label", "Geen betrouwbare productafbeelding beschikbaar");
      ph.appendChild(el("b", (t.name || "?").slice(0, 1).toUpperCase()));
      ph.appendChild(el("small", "Geen betrouwbare productafbeelding"));
      return ph;
    }
    if (!c.querySelector(".nv-tr-img")) c.appendChild(placeholder());
    else c.querySelector(".nv-tr-img img").addEventListener("error", function () { c.insertBefore(placeholder(), c.querySelector("h4")); });
    c.appendChild(el("h4", t.name));
    if (t.category_note) c.appendChild(el("p", t.category_note, "nv-tr-meta"));
    c.appendChild(el("p", t.reason, "nv-tr-meta"));
    c.appendChild(el("p", "Periode: " + r.period_label + " · bron(nen) van " + t.first + (t.last !== t.first ? " t/m " + t.last : "") +
      " · regio: " + t.regions.join(", ") + " · platform: " + t.platforms.join(", ") + " · gecontroleerd " + r.checked, "nv-tr-meta"));
    if (t.deal_only) c.appendChild(el("p", "Let op: alleen genoemd in aanbiedingsartikelen; dat is geen bewijs van groeiende belangstelling.", "nv-tr-meta"));
    var ul = el("ul", null, "nv-tr-ev");
    t.evidence.forEach(function (e) {
      var li = el("li"); var a = link(e.url, e.title); if (a) li.appendChild(a); else li.textContent = e.title;
      li.appendChild(document.createTextNode(" · " + e.source + " · " + e.date + (e.indicator ? " · ca. " + e.indicator + " zoekopdrachten" : "")));
      ul.appendChild(li);
    });
    c.appendChild(ul);
    var sup = t.suppliers;
    c.appendChild(el("p", sup ? "Beschikbare leveranciers: " + sup.count + (sup.count ? " (" + sup.names.join(", ") + (sup.count > sup.names.length ? ", …" : "") + ")" : "") +
      " · uit productonderzoek van " + sup.checked + (sup.verified ? ", " + sup.verified + " gecontroleerd" : "") :
      "Beschikbare leveranciers: nog niet onderzocht. Klik op Onderzoek dit product.", "nv-tr-meta nv-tr-sup"));
    var actions = el("div", null, "nv-tr-actions");
    var go = el("a", "Onderzoek dit product"); go.className = "nv-blue-action";
    go.href = "/dashboard?" + new URLSearchParams({section: "onderzoek", research_term: t.name.slice(0, 100), research_category: t.category, autorun: "1"}).toString();
    actions.appendChild(go);
    var m = el("a", "Bereken marge"); m.href = "/dashboard?" + new URLSearchParams({section: "onderzoek", margin_product: t.name.slice(0, 120)}).toString() + "#nv-product-margin";
    actions.appendChild(m);
    var vk = el("a", "Bewaar als viral-kandidaat");
    vk.href = "/dashboard?" + new URLSearchParams({section: "viral", viral_title: t.name.slice(0, 120), viral_niche: NICHE[t.category] || ""}).toString() + "#nv-vt-add";
    actions.appendChild(vk);
    if (canSave) {
      var b = el("button", "Bewaar als concept"); b.type = "button";
      b.addEventListener("click", function () {
        var fd = new FormData(); fd.set("_csrf_token", box.dataset.csrf); fd.set("titel", t.name.slice(0, 120));
        fd.set("bron_url", (t.evidence[0] || {}).url || ""); fd.set("bron_naam", ((t.evidence[0] || {}).source || "").slice(0, 80));
        fd.set("categorie", t.category); fd.set("notities", ("Trendonderzoek " + r.checked + ": " + t.status + " · " + t.reason).slice(0, 300));
        b.disabled = true; b.textContent = "Bezig…";
        fetch(box.dataset.concept, {method: "POST", body: fd, credentials: "same-origin"})
          .then(function (x) { b.textContent = /[?&]open=\d+/.test(x.url) ? "Bewaard als conceptproduct" : "Niet opgeslagen: controleer de gegevens"; if (!/[?&]open=\d+/.test(x.url)) b.disabled = false; })
          .catch(function () { b.textContent = "Opslaan mislukt"; b.disabled = false; });
      });
      actions.appendChild(b);
    }
    c.appendChild(actions);
    return c;
  }

  function render(r) {
    body.textContent = "";
    body.appendChild(el("p", r.trends.length + " product(en) met trendbewijs · " + r.category_label + " · " + r.period_label +
      " (vanaf " + r.since + ")" + (r.derived_from ? " · afgeleid uit bewaard onderzoek " + r.derived_from + ", geen nieuwe AI-kosten" :
      " · " + r.items_in_period + " gedateerde bronitems in de periode · " + r.elapsed_s + " s"), "nv-tr-meta"));
    body.appendChild(el("p", "Stijgende interesse = trending zoekonderwerp (Google Trends). Veelbesproken = in meerdere recente publicaties. Alleen aanbieding = alleen in kortingsartikelen genoemd. " +
      "Dit zijn geen verkoopcijfers. Hetzelfde product kan in 7, 14 en 30 dagen voorkomen als het in die hele periode aandacht krijgt.", "nv-tr-meta"));
    if (r.ai_message) body.appendChild(el("p", r.ai_message, "nv-tr-meta"));
    if (r.trends.length) {
      var g = el("div", null, "nv-tr-grid");
      r.trends.forEach(function (t) { g.appendChild(card(t, r)); });
      body.appendChild(g);
    } else body.appendChild(el("p", "Onvoldoende gegevens: in deze periode noemden de aangesloten bronnen geen producten in deze categorie.", "nv-tr-meta"));
    if (r.moved && r.moved.length) body.appendChild(el("p", "Hoort bij een andere webshopcategorie en is daarom niet getoond: " +
      r.moved.map(function (m) { return m.name + " (" + m.category + ")"; }).join(", ") + ".", "nv-tr-meta"));
    if (r.empty_categories.length) body.appendChild(el("p", "Onvoldoende gegevens voor: " + r.empty_categories.join(", ") + ".", "nv-tr-meta"));
    var d = el("details"); d.open = true;
    d.appendChild(el("summary", "Bronstatus (" + r.sources.length + ")"));
    var wrap = el("div", null, "nv-tr-table"), t = el("table"), h = el("tr");
    ["Bron", "Soort", "Status", "Items"].forEach(function (x) { h.appendChild(el("th", x)); }); t.appendChild(h);
    r.sources.forEach(function (s) {
      var row = el("tr"), name = el("td"); var a = link(s.url, s.name); if (a) name.appendChild(a); else name.textContent = s.name;
      row.appendChild(name); row.appendChild(el("td", s.kind)); row.appendChild(el("td", s.status)); row.appendChild(el("td", String(s.count)));
      t.appendChild(row);
    });
    wrap.appendChild(t); d.appendChild(wrap); body.appendChild(d);
  }

  function showSteps(list) { steps.textContent = ""; (list || []).forEach(function (s) { steps.appendChild(el("li", s.t + " s · " + s.text)); }); }
  function finish(label) { box.className = "panel nv-tr done"; status.textContent = label; running = false; button.disabled = false; }

  function poll(key, started) {
    fetch(box.dataset.status + "?key=" + encodeURIComponent(key), {credentials: "same-origin"})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        showSteps(d.steps); timer.textContent = Math.round((Date.now() - started) / 1000) + " s";
        if (d.state === "done" && d.result) { finish("Klaar"); render(d.result); return; }
        if (d.state === "failed" || d.ok === false) { finish("Niet voltooid"); errorBox.textContent = d.error || d.message || "Mislukt."; errorBox.hidden = false; return; }
        if (Date.now() - started > 240000) { finish("Duurt erg lang"); errorBox.textContent = "Het onderzoek loopt nog. Zoek straks opnieuw; het resultaat komt dan uit de cache."; errorBox.hidden = false; return; }
        setTimeout(function () { poll(key, started); }, 2500);
      })
      .catch(function () { setTimeout(function () { poll(key, started); }, 5000); });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (running) return;
    running = true; button.disabled = true;
    progress.hidden = false; box.className = "panel nv-tr"; errorBox.hidden = true; body.textContent = ""; showSteps([]);
    status.textContent = "AI onderzoekt trends…";
    var fd = new FormData(form); fd.set("_csrf_token", box.dataset.csrf);
    var started = Date.now();
    fetch(box.dataset.start, {method: "POST", body: fd, credentials: "same-origin"})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) { finish("Niet gestart"); errorBox.textContent = d.message || "Niet gestart."; errorBox.hidden = false; return; }
        showSteps(d.steps);
        if (d.state === "done" && d.result) { finish("Klaar (uit de permanente cache, geen kosten)"); render(d.result); return; }
        poll(d.key, started);
      })
      .catch(function () { finish("Niet gestart"); errorBox.textContent = "Verbinding met het dashboard mislukt."; errorBox.hidden = false; });
  });
})();
