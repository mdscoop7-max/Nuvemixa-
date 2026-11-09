/* TrendMix storefront: deterministic language chooser for visible shop controls.
   This complements app.js and never changes product data or the hero. */
(function(){
  'use strict';
  const dict={
    nl:{min:'Vanaf €',max:'Tot €',sort:'Sorteren',apply:'Toepassen',clear:'Filters wissen',countOne:'product gevonden',countMany:'producten gevonden',search:'Zoek producten...',searchButton:'Zoeken',english:'English',dutch:'Nederlands'},
    en:{min:'From €',max:'To €',sort:'Sort by',apply:'Apply filters',clear:'Clear filters',countOne:'product found',countMany:'products found',search:'Search products...',searchButton:'Search',english:'English',dutch:'Nederlands'}
  };
  function put(sel,value){document.querySelectorAll(sel).forEach(el=>{el.textContent=value;});}
  function update(lang){
    const t=dict[lang]||dict.nl;
    document.documentElement.lang=lang;
    put('label[for="tmMinPrice"]',t.min);
    put('label[for="tmMaxPrice"]',t.max);
    put('label[for="tmSort"]',t.sort);
    put('.tm-shop-filters .tm-filter-submit',t.apply);
    put('.tm-shop-filters .tm-filter-reset',t.clear);
    document.querySelectorAll('.product-count span').forEach(el=>{el.textContent=el.previousElementSibling?.textContent?.trim()==='1'?t.countOne:t.countMany});
    document.querySelectorAll('input.search-input,input[name="q"][type="search"]').forEach(el=>{el.placeholder=t.search});
    document.querySelectorAll('.header .search button[type="submit"]').forEach(el=>{el.textContent=t.searchButton});
    document.querySelectorAll('.tm-language-dropdown').forEach(menu=>{
      const curr=menu.querySelector('.tm-language-current');if(curr)curr.textContent=lang==='en'?'English':'Nederlands';
      const nl=menu.querySelector('.tm-flag-nl');if(nl)nl.hidden=lang==='en';
      const en=menu.querySelector('.tm-flag-en');if(en)en.hidden=lang!=='en';
      menu.querySelectorAll('[data-language]').forEach(button=>{
        const active=button.dataset.language===lang;
        button.classList.toggle('active',active);
        button.setAttribute('aria-pressed',String(active));
      });
    });
  }
  function persist(lang){
    if(!dict[lang])return;
    try{localStorage.setItem('trendmix-language',lang)}catch(e){}
    update(lang);
  }
  document.addEventListener('DOMContentLoaded',()=>{
    let saved='nl';try{saved=localStorage.getItem('trendmix-language')||'nl'}catch(e){}
    update(dict[saved]?saved:'nl');
    document.querySelectorAll('.tm-language-dropdown [data-language]').forEach(button=>{
      button.addEventListener('click',()=>{
        persist(button.dataset.language);
        button.closest('details')?.removeAttribute('open');
      });
    });
  });
})();
