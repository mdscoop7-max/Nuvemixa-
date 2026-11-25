(() => {
  "use strict";
  document.querySelectorAll('[data-confirm-delete]').forEach(button => button.addEventListener('click', event => {
    if (!confirm('Dit extra product verwijderen? Dit kan niet via het dashboard worden hersteld.')) event.preventDefault();
  }));
  const search = document.querySelector("#xp-search");
  if (search) {
    function filter() {
      let count = 0;
      document.querySelectorAll("[data-record]").forEach((row) => {
        const category = document.querySelector('[data-filter="category"]').value;
        const state = document.querySelector('[data-filter="state"]').value;
        const stock = document.querySelector('[data-filter="stock"]').value;
        row.hidden = !row.textContent.toLowerCase().includes(search.value.toLowerCase()) ||
          (category && row.dataset.category !== category) ||
          (state && !(state === 'offer' ? row.dataset.offer === '1' : row.dataset.state === state)) ||
          (stock && row.dataset.stock !== stock);
        if (!row.hidden) count++;
      });
      document.querySelector("[data-empty]").hidden = count > 0;
    }
    search.addEventListener("input", filter);
    document.querySelectorAll('[data-filter]').forEach(select => select.addEventListener('change', filter));
    filter();
  }
  const f = document.querySelector("#xp-editor");
  if (!f) return;
  const get = (name) => f.elements.namedItem(name);
  const el = (selector) => f.querySelector(selector);
  const on = (selector, action) =>
    el(selector).addEventListener("click", action);
  const euros = (cents) =>
    (cents / 100).toLocaleString("nl-NL", {
      style: "currency",
      currency: "EUR",
    });
  const cents = (field) => Math.round(Number(field.value || 0) * 100);
  const round = (a, b) => Math.floor((a + b / 2) / b);
  const error = (msg) => {
    el("[data-error]").textContent = msg;
  };
  let dirty = false,
    busy = false,
    current = 0;
  const photos = JSON.parse(el("#xp-photos").textContent)
    .map((url) => ({ url }));
  const editor = el("#xp-desc");
  function button(text, fn) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.onclick = fn;
    return b;
  }
  function showPhotos() {
    const main = el("[data-main]");
    current = Math.max(0, Math.min(current, photos.length - 1));
    main.hidden = !photos.length;
    el("[data-placeholder]").hidden = !!photos.length;
    el("[data-photo-actions]").hidden = !photos.length;
    if (photos.length) main.src = photos[current].url;
    for (const key of ["prev", "next", "zoom"])
      el("[data-" + key + "]").hidden =
        photos.length < (key === "zoom" ? 1 : 2);
    el("[data-thumbs]").replaceChildren(
      ...photos.map((p, i) => {
        const b = button("", () => {
            current = i;
            showPhotos();
          }),
          img = new Image();
        img.src = p.url;
        img.alt = "Foto " + (i + 1);
        b.append(img);
        b.setAttribute("aria-pressed", i === current);
        return b;
      }),
    );
  }
  function add(files) {
    if (files.length + photos.length > 8)
      return error("Kies maximaal acht foto’s.");
    if (files.some((file) => file.size > 5242880))
      return error("Een foto is groter dan 5 MB.");
    photos.push(
      ...files.map((file) => ({ file, url: URL.createObjectURL(file) })),
    );
    current = photos.length - 1;
    dirty = true;
    error("");
    showPhotos();
  }
  get("image_file").onchange = (e) => {
    add(Array.from(e.target.files));
    e.target.value = "";
  };
  el("[data-drop]").ondragover = (e) => e.preventDefault();
  el("[data-drop]").ondrop = (e) => {
    e.preventDefault();
    add(Array.from(e.dataTransfer.files));
  };
  on("[data-add-link]", () => {
    const link = el("[data-link]");
    if (
      !/^https:\/\//i.test(link.value) ||
      !link.validity.valid ||
      photos.length >= 8
    )
      return error("Controleer de HTTPS-link en het aantal foto’s.");
    photos.push({ url: link.value });
    current = photos.length - 1;
    link.value = "";
    dirty = true;
    showPhotos();
  });
  function reorder(to) {
    photos.splice(to, 0, photos.splice(current, 1)[0]);
    current = to;
    dirty = true;
    showPhotos();
  }
  on("[data-cover]", () => reorder(0));
  on("[data-left]", () => reorder(Math.max(0, current - 1)));
  on("[data-remove]", () => {
    const [p] = photos.splice(current, 1);
    if (p.file) URL.revokeObjectURL(p.url);
    dirty = true;
    showPhotos();
  });
  on("[data-prev]", () => {
    current = (current + photos.length - 1) % photos.length;
    showPhotos();
  });
  on("[data-next]", () => {
    current = (current + 1) % photos.length;
    showPhotos();
  });
  function zoom() {
    window.nvPhotoGallery(
      photos.map((p) => p.url),
      current,
      get("name").value,
    );
  }
  on("[data-main]", zoom);
  on("[data-zoom]", zoom);
  editor.onpaste = (e) => {
    e.preventDefault();
    document.execCommand(
      "insertText",
      false,
      e.clipboardData.getData("text/plain"),
    );
  };
  editor.ondrop = (e) => e.preventDefault();
  f.querySelectorAll("[data-format]").forEach((b) => {
    b.onmousedown = (e) => e.preventDefault();
    b.onclick = () => {
      let arg = null;
      if (b.dataset.format === "createLink") {
        arg = prompt("Volledige HTTPS-link");
        if (!arg || !/^https:\/\//i.test(arg)) return;
      }
      editor.focus();
      document.execCommand(b.dataset.format, false, arg);
      dirty = true;
    };
  });
  let category = get("category").value;
  get("category").addEventListener("change", () => {
    if (get("category").value !== "@offers") {
      category = get("category").value;
      return;
    }
    get("category").value = category;
    for (const key of ["offer_enabled", "offer_shop", "offer_list"])
      get(key).checked = true;
    get("sale_price").focus();
    error(
      "Aanbiedingen is toegevoegd als publicatiebestemming. Het product blijft in de gekozen categorie.",
    );
    update();
  });
  function update(recalculate = false) {
    const total = Array.from(f.querySelectorAll("[data-cost]")).reduce(
      (sum, c) => sum + cents(c),
      0,
    );
    const select = el("[data-margin]"),
      margin = get("margin");
    margin.parentElement.hidden = select.value !== "own";
    if (select.value !== "own") margin.value = select.value;
    const rate = cents(margin),
      vat = Number(get("vat").value),
      price = get("price");
    const automatic = get("price_mode").value === "auto";
    price.readOnly = automatic;
    let net = rate < 10000 ? round(total * 10000, 10000 - rate) : 0;
    if (automatic && recalculate)
      price.value = ((net + round(net * vat, 100)) / 100).toFixed(2);
    else net = round(cents(price) * 100, 100 + vat);
    const gross = cents(price),
      profit = net - total;
    const result = el("[data-result]");
    result.replaceChildren();
    for (const [key, value] of [
      ["Totale kosten (excl. btw)", euros(total)],
      ["Gewenste marge", margin.value + "%"],
      ["Verkoopprijs excl. btw", euros(net)],
      ["Btw (" + vat + "%)", euros(gross - net)],
      ["Verkoopprijs incl. btw", euros(gross)],
      [
        "Winst per stuk",
        euros(profit) +
          " (" +
          (net ? ((100 * profit) / net).toFixed(1) : "0") +
          "%)",
      ],
    ]) {
      const row = document.createElement("p"),
        strong = document.createElement("strong");
      strong.textContent = value;
      row.append(key + " ", strong);
      result.append(row);
    }
    el("[data-total]").textContent = euros(total);
    const sale = cents(get("sale_price")),
      saleNet = round(sale * 100, 100 + vat),
      gain = saleNet - total;
    el("[data-sale]").textContent =
      get("offer_enabled").checked && sale && gross
        ? "Korting " +
          ((1 - sale / gross) * 100).toFixed(1).replace(".", ",") +
          "% · Winst " +
          euros(gain) +
          " · Marge " +
          (saleNet ? (gain / saleNet) * 100 : 0).toFixed(1) +
          "%" +
          (gain < 0 ? " · Verliesgevend" : "")
        : "";
    el("[data-low]").textContent =
      get("stock_quantity").value !== "" &&
      get("minimum_stock").value !== "" &&
      Number(get("stock_quantity").value) <= Number(get("minimum_stock").value)
        ? "Lage voorraad"
        : "";
    el('[data-count="description"]').textContent =
      editor.innerText.length + " / 2000";
    el('[data-count="short_description"]').textContent =
      get("short_description").value.length + " / 160";
  }
  f.addEventListener("input", (event) => {
    dirty = true;
    const recalculate = event.target.matches('[data-cost], [data-margin], [name="margin"], [name="vat"], [name="price_mode"]');
    if (recalculate) get("recalculate_price").value = "1";
    update(recalculate);
  });
  document.querySelector('a[href="#xp-stock"]').onclick = () => {
    el("#xp-stock").open = true;
  };
  document.querySelector("[data-new]").onclick = (e) => {
    if (dirty && !confirm("Niet-opgeslagen wijzigingen verlaten?"))
      e.preventDefault();
  };
  on("[data-preview]", () => {
    const modal = document.createElement("dialog");
    modal.style.cssText =
      "max-width:min(600px,94vw);max-height:90dvh;overflow:auto;border:1px solid #cad7ee;border-radius:16px;padding:24px";
    const heading = document.createElement("h2");
    heading.textContent = get("name").value || "Productvoorbeeld";
    modal.append(heading);
    photos.forEach((p, i) => {
      const b = button("", () =>
        window.nvPhotoGallery(
          photos.map((x) => x.url),
          i,
          heading.textContent,
        ),
      );
      const img = new Image();
      img.src = p.url;
      img.width = i ? 55 : 140;
      img.alt = "Productfoto";
      b.append(img);
      modal.append(b);
    });
    for (const line of [
      get("category").selectedOptions[0].text,
      get("short_description").value,
      editor.innerText,
      euros(cents(get("price"))),
      get("offer_enabled").checked
        ? "Actieprijs " + euros(cents(get("sale_price")))
        : "",
      get("stock_status").selectedOptions[0].text,
    ]) {
      const p = document.createElement("p");
      p.textContent = line;
      modal.append(p);
    }
    modal.append(button("Sluiten", () => modal.close()));
    document.body.append(modal);
    modal.onclose = () => modal.remove();
    modal.showModal();
  });
  f.onsubmit = async (e) => {
    e.preventDefault();
    if (busy) return;
    busy = true;
    error("");
    try {
      const data = new FormData(f);
      data.set("category", get("category").value);
      data.set("intent", e.submitter?.value || "save");
      data.set("description", editor.innerText);
      data.set("description_html", editor.innerHTML);
      data.delete("image_file");
      let count = 0;
      data.set(
        "gallery",
        JSON.stringify(
          photos.map((p) => {
            if (!p.file) return p.url;
            data.append("image_file", p.file);
            return count++;
          }),
        ),
      );
      const r = await fetch(f.action, {
        method: "POST",
        body: data,
        headers: { Accept: "application/json" },
      });
      if (!r.headers.get("Content-Type")?.includes("application/json"))
        throw Error(
          r.status === 413
            ? "De upload is te groot."
            : "Opslaan mislukt. Controleer je sessie en probeer opnieuw.",
        );
      const reply = await r.json();
      if (!r.ok || !reply.ok) throw Error(reply.error || "Opslaan mislukt.");
      const url = new URL(location.href);
      url.searchParams.set("categorie", reply.category);
      url.searchParams.set("edit", reply.slug);
      url.searchParams.set("saved", "1");
      url.searchParams.set("view", "edit");
      location.assign(url);
    } catch (err) {
      error(err.message);
    } finally {
      busy = false;
    }
  };
  showPhotos();
  update(get("recalculate_price").value === "1");
  if (new URL(location.href).searchParams.has("saved"))
    el("[data-error]").textContent = "Product opgeslagen.";
})();
