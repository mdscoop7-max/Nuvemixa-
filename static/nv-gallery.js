window.nvPhotoGallery = function (urls, start = 0, title = 'Productfoto') {
  urls = urls.filter(url => typeof url === 'string' && url);
  if (!urls.length || document.getElementById('nv-photo-modal')) return;
  const origin = document.activeElement, modal = document.createElement('dialog');
  modal.id = 'nv-photo-modal'; modal.setAttribute('aria-label', title || 'Productfoto');
  const tools = document.createElement('div'); tools.className = 'nv-photo-tools';
  const caption = document.createElement('span'); caption.className = 'nv-photo-caption';
  caption.setAttribute('aria-live', 'polite'); tools.append(caption);
  const stage = document.createElement('div'); stage.className = 'nv-photo-stage';
  const photo = new Image(); photo.alt = title || 'Productfoto'; stage.append(photo);
  const navigation = document.createElement('div'); navigation.className = 'nv-photo-nav';
  modal.append(tools, stage, navigation);
  let index = Math.max(0, Math.min(Number(start) || 0, urls.length - 1)), scale = 1;
  function draw() {
    photo.src = urls[index]; photo.style.width = `${scale * 100}%`; photo.style.height = `${scale * 100}%`;
    stage.classList.toggle('is-enlarged', scale > 1); stage.scrollTo(0, 0);
    caption.textContent = `${title || 'Productfoto'} · ${index + 1} / ${urls.length}`;
  }
  function move(delta) { index = (index + delta + urls.length) % urls.length; scale = 1; draw(); }
  function button(parent, label, action) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
    b.setAttribute('aria-label', label); b.addEventListener('click', action); parent.append(b); return b;
  }
  button(tools, 'Verkleinen −', () => { scale = Math.max(1, scale - .5); draw(); });
  button(tools, 'Vergroten +', () => { scale = Math.min(3, scale + .5); draw(); });
  const close = button(tools, 'Sluiten ×', () => modal.close()); close.className = 'nv-photo-close';
  if (urls.length > 1) {
    button(navigation, '‹ Vorige foto', () => move(-1));
    button(navigation, 'Volgende foto ›', () => move(1));
  }
  modal.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); modal.close(); }
    if (urls.length > 1 && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
      event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1);
    }
  });
  modal.addEventListener('click', event => {
    if (event.target === stage || event.target === modal) modal.close();
    if (event.target === photo && scale === 1) {
      const box = photo.getBoundingClientRect();
      const ratio = Math.min(box.width / photo.naturalWidth, box.height / photo.naturalHeight);
      const w = photo.naturalWidth * ratio, h = photo.naturalHeight * ratio;
      if (event.clientX < box.left + (box.width-w)/2 || event.clientX > box.right - (box.width-w)/2 ||
          event.clientY < box.top + (box.height-h)/2 || event.clientY > box.bottom - (box.height-h)/2) modal.close();
    }
  });
  let touch;
  stage.addEventListener('touchstart', event => {
    if (event.touches.length === 1) touch = [event.touches[0].clientX, event.touches[0].clientY];
  }, {passive:true});
  stage.addEventListener('touchend', event => {
    if (!touch || scale !== 1 || urls.length < 2) return;
    const dx = event.changedTouches[0].clientX - touch[0], dy = event.changedTouches[0].clientY - touch[1];
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)*1.5) move(dx < 0 ? 1 : -1);
    touch = null;
  }, {passive:true});
  const overflow = document.documentElement.style.overflow;
  modal.addEventListener('close', () => {
    modal.remove(); document.documentElement.style.overflow = overflow;
    if (origin?.isConnected) origin.focus();
  }, {once:true});
  document.body.append(modal); draw(); modal.showModal();
  document.documentElement.style.overflow = 'hidden'; close.focus();
};
document.querySelectorAll('.detail-gallery').forEach(gallery => {
  const main = gallery.querySelector('.detail-image img'); if (!main) return;
  const thumbs = [...gallery.querySelectorAll('.detail-thumbnails button')];
  const data = document.getElementById('public-gallery');
  const urls = data ? JSON.parse(data.textContent) : thumbs.map(b => b.querySelector('img')?.src).filter(Boolean);
  if (!urls.length) urls.push(main.src);
  thumbs.forEach((b, i) => b.addEventListener('click', () => {
    main.src = urls[i]; thumbs.forEach((t,j) => t.classList.toggle('active', i === j));
  }));
  const trigger = gallery.querySelector('[data-public-zoom]') || main;
  trigger.tabIndex = 0; trigger.setAttribute('role','button'); trigger.setAttribute('aria-label','Productfoto vergroten');
  const open = () => window.nvPhotoGallery(urls, Math.max(0, urls.findIndex(url => new URL(url, location.href).href === main.src)), main.alt);
  trigger.addEventListener('click', open);
  trigger.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); }
  });
});
