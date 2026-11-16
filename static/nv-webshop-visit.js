/* NUVEMIXA bezoekersteller — cookievrij. Plaats op de webshop met één regel:
   <script src="https://trendmix.onrender.com/static/nv-webshop-visit.js" defer></script>
   Er wordt niets op het apparaat opgeslagen. Do Not Track en Global Privacy Control worden gerespecteerd. */
(function () {
  try {
    var nav = navigator;
    if (nav.doNotTrack === "1" || nav.globalPrivacyControl === true || window.doNotTrack === "1") return;
    var script = document.currentScript;
    if (!script || !script.src) return;
    var endpoint = new URL(script.src).origin + "/api/webshop-visit";
    var body = JSON.stringify({ p: location.pathname });
    if (nav.sendBeacon && nav.sendBeacon(endpoint, new Blob([body], { type: "text/plain" }))) return;
    fetch(endpoint, { method: "POST", body: body, keepalive: true, mode: "no-cors", credentials: "omit",
                      headers: { "Content-Type": "text/plain" } });
  } catch (e) { /* tellen mag de webshop nooit storen */ }
})();
