/* NUVEMIXA zoekindicator: toont dat een zoekopdracht loopt, zonder verzonnen percentage.
   De pagina laadt volledig opnieuw na een zoekopdracht; de indicator verdwijnt dan vanzelf. */
(() => {
  "use strict";
  const SELECTOR = "form[method='get' i].nv-research-form,form[method='get' i].nv-market-form,form[method='get' i].nv-partner-form," +
    "form[method='get' i].nv-research-followup,form[method='get' i].nv-admin-form,form[method='get' i][role='search']";
  const MESSAGES = {
    onderzoek: "Producten en leveranciers worden gezocht…", internationaal: "Internationale bronnen worden doorzocht…",
    viral: "Trendsignalen en producten worden gezocht…", leveranciers: "Leveranciers worden gezocht…",
    partners: "Partners worden gezocht…", trends: "Niches worden vergeleken…",
  };
  const SLOW_MS = 30000, TIMEOUT_MS = 90000;
  let busy = false;

  function sectionOf(form) {
    const field = form.querySelector("input[name='section']");
    return (field && field.value) || new URLSearchParams(location.search).get("section") || "";
  }
  function sourcesOf(form) {
    const boxes = Array.from(form.querySelectorAll("input[type='checkbox'][name$='platform']:checked"));
    return boxes.map((b) => b.value).filter(Boolean);
  }
  function build(form, message) {
    const box = document.createElement("div");
    box.className = "nv-search-status";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    const sources = sourcesOf(form);
    const sourceLine = sources.length
      ? "Bronnen: " + sources.join(", ") + ". Het aantal afgeronde bronnen is tijdens het zoeken niet meetbaar; de balk toont daarom alleen dat er gewerkt wordt."
      : "De backend meldt geen tussentijdse voortgang; de balk toont alleen dat er gewerkt wordt.";
    box.innerHTML = '<p class="nv-search-text"><span class="nv-search-icon" aria-hidden="true"></span><strong></strong></p>' +
      '<div class="nv-search-bar" aria-hidden="true"><span></span></div><p class="nv-search-note"></p>';
    box.querySelector("strong").textContent = message;
    box.querySelector(".nv-search-note").textContent = sourceLine;
    return box;
  }
  function reset(form, button, original, box) {
    busy = false;
    form.removeAttribute("aria-busy");
    if (button) { button.disabled = false; button.removeAttribute("aria-disabled"); if (original !== null) button.textContent = original; }
    if (box && box.parentNode) box.parentNode.removeChild(box);
  }
  function start(form, event) {
    if (form.hasAttribute("data-nv-nosearch")) return;
    if (busy) { event.preventDefault(); return; }  // dubbele zoekopdracht voorkomen
    if (typeof form.checkValidity === "function" && !form.checkValidity()) return;
    busy = true;
    const button = (event.submitter && event.submitter.tagName === "BUTTON") ? event.submitter : form.querySelector("button[type='submit'],button:not([type])");
    const original = button ? button.textContent : null;
    const message = MESSAGES[sectionOf(form)] || "Er wordt gezocht…";
    const box = build(form, message);
    form.setAttribute("aria-busy", "true");
    form.appendChild(box);
    if (button) {
      // uitstellen: een direct uitgeschakelde knop zou zijn eigen waarde niet meesturen
      setTimeout(() => { button.disabled = true; button.setAttribute("aria-disabled", "true"); button.textContent = "Bezig met zoeken…"; }, 0);
    }
    setTimeout(() => { if (busy) box.querySelector(".nv-search-note").textContent = "Dit duurt langer dan normaal (gratis server of trage bron). Even geduld."; }, SLOW_MS);
    setTimeout(() => {
      if (!busy) return;
      reset(form, button, original, null);
      box.classList.add("is-error");
      box.setAttribute("role", "alert");
      box.querySelector("strong").textContent = "De zoekopdracht kreeg geen antwoord (time-out na 90 seconden).";
      box.querySelector(".nv-search-note").textContent = "Er is niets verloren gegaan. Probeer het opnieuw of zoek met minder bronnen.";
    }, TIMEOUT_MS);
  }
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form && form.matches && form.matches(SELECTOR) && !form.classList.contains("top-search")) start(form, event);
  });
  window.addEventListener("pageshow", (event) => {  // terugknop: nooit een vastgelopen indicator tonen
    if (!event.persisted) return;
    busy = false;
    document.querySelectorAll(".nv-search-status").forEach((n) => n.remove());
    document.querySelectorAll("form[aria-busy]").forEach((f) => {
      f.removeAttribute("aria-busy");
      f.querySelectorAll("button[disabled]").forEach((b) => { b.disabled = false; b.removeAttribute("aria-disabled"); if (/Bezig met zoeken/.test(b.textContent)) b.textContent = "Zoeken"; });
    });
  });
  window.addEventListener("offline", () => {
    const box = document.querySelector(".nv-search-status");
    if (busy && box) { box.classList.add("is-error"); box.setAttribute("role", "alert"); box.querySelector("strong").textContent = "Geen internetverbinding. De zoekopdracht kan niet worden afgerond."; }
  });
})();
