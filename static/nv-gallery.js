// A modal shared by the product editor and the storefront.
window.nvPhotoGallery = function (urls, start, title) {
  if (!urls.length) return;
  const modal = document.createElement("dialog");
  modal.style.cssText =
    "border:0;border-radius:14px;padding:12px;max-width:96vw;max-height:94dvh";
  modal.setAttribute("aria-label", title || "Productfoto’s");
  const frame = document.createElement("div"),
    photo = new Image();
  frame.style.cssText =
    "width:min(80vw,900px);height:min(70dvh,750px);overflow:auto";
  photo.alt = title || "Productfoto";
  frame.append(photo);
  let index = Math.max(0, start),
    scale = 1;
  function draw() {
    photo.src = urls[index];
    photo.style.cssText =
      "object-fit:contain;max-width:none;width:" +
      scale * 100 +
      "%;height:" +
      scale * 100 +
      "%";
  }
  function move(delta) {
    index = (index + delta + urls.length) % urls.length;
    scale = 1;
    draw();
  }
  function button(label, action) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.addEventListener("click", action);
    modal.append(b);
  }
  modal.append(frame);
  if (urls.length > 1) {
    button("← Vorige", () => move(-1));
    button("Volgende →", () => move(1));
  }
  button("Vergroten +", () => {
    scale = Math.min(scale + 0.5, 3);
    draw();
  });
  button("Verkleinen −", () => {
    scale = Math.max(scale - 0.5, 1);
    draw();
  });
  button("Sluiten ×", () => modal.close());
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.close();
  });
  modal.addEventListener("close", () => modal.remove());
  modal.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") move(-1);
    if (e.key === "ArrowRight") move(1);
  });
  document.body.append(modal);
  draw();
  modal.showModal();
};
const galleryButton = document.querySelector("[data-public-zoom]");
if (galleryButton)
  galleryButton.addEventListener("click", () => {
    const urls = JSON.parse(
      document.getElementById("public-gallery").textContent,
    );
    const main = document.querySelector(".detail-image img");
    window.nvPhotoGallery(
      urls,
      urls.findIndex((url) => new URL(url, location.href).href === main.src),
      main.alt,
    );
  });
