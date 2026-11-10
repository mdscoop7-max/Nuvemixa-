/* NUVEMIXA bilingual navigation and FAQ assistant.
   Only Dutch/English UI copy is translated; this is not a live AI API. */
(function(){
  'use strict';
  const storageKey='trendmix-language';
  const labels={nl:{menu:'Menu openen',close:'Sluiten',ask:'Stel je vraag…',help:'NUVEMIXA Hulp',intro:'Hoi! Ik kan helpen met vragen over NUVEMIXA. De webshop en assistent zijn nog in testfase.',none:'Ik kan je helpen met producten, bestellen, levering, retouren en privacy. Kijk ook bij de veelgestelde vragen of stuur een bericht via Contact.',returns:'De retourvoorwaarden zijn te lezen op de pagina Retour & herroeping. Het uiteindelijke retouradres en de verzendinstructies worden bevestigd zodra de leverancier gekoppeld is. Stuur niets zonder instructies terug.',shipping:'De leverancier en de verzendtarieven zijn nog niet bevestigd. Daarom doet NUVEMIXA momenteel geen definitieve belofte over bezorging of levertijd.',orders:'NUVEMIXA bevindt zich in de testfase. De winkelwagen en checkout zijn voor demonstratie. Er worden nog geen echte betalingen verwerkt.',contact:'Gebruik de pagina Contact voor vragen. Zolang onze maildienst niet is gekoppeld, kan het contactformulier nog geen echte berichten afleveren.',privacy:'Privacyinformatie en cookievoorkeuren vind je onderaan de website op de pagina’s Privacybeleid en Cookies.',products:'De productcollectie is voorlopig. Foto’s, prijzen, voorraad en details worden bevestigd wanneer de leverancier is aangesloten.',caution:'Deel in deze chat geen persoonsgegevens of bestelgegevens.'},
  en:{menu:'Open menu',close:'Close',ask:'Ask a question…',help:'NUVEMIXA Help',intro:'Hello! I can help with general NUVEMIXA questions. The shop and assistant are still in test mode.',none:'I can help with questions about products, ordering, shipping, returns and privacy. You can also check the FAQ or contact page.',returns:'Read the Returns & withdrawal page for our current policy. The final return address and shipping instructions will be confirmed once a supplier is connected. Do not return items without instructions.',shipping:'Our supplier and shipping costs are not yet confirmed. NUVEMIXA cannot promise delivery dates or shipping fees during this test period.',orders:'NUVEMIXA is still in test mode. The cart and checkout are for demonstration, and no real payments are processed.',contact:'Please use our Contact page for questions. Until the email service is configured, messages sent through the contact form cannot yet be delivered.',privacy:'You can read the Privacy Policy and Cookies pages linked in the footer.',products:'This is a provisional product collection. Photos, prices, stock levels and details will be confirmed after the supplier is connected.',caution:'Do not share personal information or order details here.'}};
  const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
  let lang='nl', returnFocus=null, opened=null;
  function stored(){try{return localStorage.getItem(storageKey)}catch(e){return null}}
  function save(k){try{localStorage.setItem(storageKey,k)}catch(e){}}
  const commonLabels={
    'Levering volgens productinformatie':'Delivery according to product details',
    'Retourinformatie':'Returns information',
    'Checkout in testfase':'Test checkout',
    'Klantenservice':'Customer service',
    'Favorieten':'Favorites',
    'Winkelwagen':'Cart',
    'Aanbiedingen':'Deals',
    'Alle producten':'All products',
    'Winkelen':'Shop',
    'Over NUVEMIXA':'About NUVEMIXA',
    'Over ons':'About us',
    'Algemene voorwaarden':'Terms and conditions',
    'Privacybeleid':'Privacy policy',
    'Cookiebeleid & voorkeuren':'Cookies and preferences',
    'Bestellen & levering':'Ordering and delivery',
    'Retour & herroeping':'Returns and withdrawal',
    'Mijn account':'My account',
    'Veelgestelde vragen':'FAQ',
    'Hulp nodig?':'Need help?',
    'Duidelijke prijzen':'Clear pricing',
    'Betalen':'Payment',
    'Levergebied':'Delivery area',
    'Bedrijfsinformatie':'Business details',
    'Taal':'Language'
  };
  function translateCommonUI(){
    const selectors='.topitems>span,.topitems>a,.footer-column>a,.footer-column>h2,.footer-column>h3,.tm-footer-help>h3,.tm-footer-trust strong,.tm-footer-info>div>strong,.footer-bottom a,.tm-newsletter-copy h2';
    $$(selectors).forEach(element=>{
      Array.from(element.childNodes).forEach(node=>{
        if(node.nodeType!==3)return;
        if(node.__tmOriginal===undefined)node.__tmOriginal=node.nodeValue;
        const raw=node.__tmOriginal;
        const text=raw.trim();
        const english=commonLabels[text];
        if(english)node.nodeValue=raw.replace(text,lang==='en'?english:text);
      });
    });
  }
  function translateInformationPage(){
    const root=$('[data-tm-info-root]');
    if(!root)return;
    $$('[data-tm-info-nl][data-tm-info-en]').forEach(node=>{
      const value=lang==='en'?node.dataset.tmInfoEn:node.dataset.tmInfoNl;
      if(value!==undefined)node.textContent=value;
    });
    const title=lang==='en'?root.dataset.tmPageTitleEn:root.dataset.tmPageTitleNl;
    const description=lang==='en'?root.dataset.tmPageDescriptionEn:root.dataset.tmPageDescriptionNl;
    if(title)document.title=title+' | NUVEMIXA';
    const meta=$('meta[name="description"]');
    if(meta&&description)meta.setAttribute('content',description);
  }
  function translateProductText(){
    $$('[data-tm-product-nl][data-tm-product-en]').forEach(node=>{
      const translated=lang==='en'?node.dataset.tmProductEn:node.dataset.tmProductNl;
      if(translated===undefined)return;
      if(node.tagName==='IMG')node.setAttribute('alt',translated);
      else node.textContent=translated;
      const card=node.closest('[data-product-card]');
      if(card&&node.tagName!=='IMG')card.dataset.name=translated.toLowerCase();
    });
    $$('[data-tm-product-label-nl][data-tm-product-label-en]').forEach(node=>{
      node.setAttribute('aria-label',lang==='en'?node.dataset.tmProductLabelEn:node.dataset.tmProductLabelNl);
    });
    const detail=$('.tm-product-page .detail-copy h1[data-tm-product-nl]');
    if(detail){
      document.title=(lang==='en'?detail.dataset.tmProductEn:detail.dataset.tmProductNl)+' | NUVEMIXA';
      const description=$('.tm-product-page .detail-description');
      const meta=$('meta[name="description"]');
      if(description&&meta)meta.setAttribute('content',lang==='en'?description.dataset.tmProductEn:description.dataset.tmProductNl);
    }
  }
  function translateRemainingText(){
    const dictionary=window.NUVEMIXAEnglishLabels||{};
    const extra={
      'Zoek naar producten, merken of specificaties…':'Search products, brands or specifications…',
      'Zoek producten…':'Search products…',
      'Zoek in deze collectie...':'Search this collection...',
      'Zoek producten':'Search products',
      'Zoekresultaten':'Search results',
      'Je e-mailadres':'Your email address',
      'Je naam':'Your name',
      'naam@voorbeeld.nl':'name@example.com',
      'jouw@email.nl':'you@example.com',
      'Vertel kort waarmee we je kunnen helpen...':'Tell us briefly how we can help...',
      'Waar kunnen we je mee helpen?':'How can we help?',
      'Aantal verminderen':'Decrease quantity',
      'Aantal verhogen':'Increase quantity',
      'Product verwijderen':'Remove product',
      'Toevoegen aan winkelwagen':'Add to cart',
      'Toevoegen aan favorieten':'Add to favourites',
      'Verwijderen uit favorieten':'Remove from favourites',
      'Bekijk producten in':'View products in',
      'Stuur ons direct een bericht':'Send us a message',
      'Geen resultaten gevonden.':'No results found.',
      'product gevonden':'product found',
      'producten gevonden':'products found',
      'Bericht':'Message'
    };
    const mapping={...dictionary,...extra};
    const excluded='script,style,noscript,textarea,option,select,[data-tm-product-nl],[data-tm-info-nl],[data-tm-tr],[data-i18n]';
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())){
      const element=node.parentElement;
      if(!element||element.closest(excluded))continue;
      if(node.__tmLocaleOriginal===undefined)node.__tmLocaleOriginal=node.__tmOriginal!==undefined?node.__tmOriginal:node.nodeValue;
      const original=node.__tmLocaleOriginal;
      const trimmed=original.trim();
      if(!trimmed||trimmed.length>800)continue;
      let english=mapping[trimmed];
      if(!english&&/^\d+ producten$/.test(trimmed))english=trimmed.replace('producten','products');
      if(!english&&/^\d+ resultaten$/.test(trimmed))english=trimmed.replace('resultaten','results');
      if(!english&&/^\d+ producten in /.test(trimmed))english=trimmed.replace('producten in','products in');
      if(lang==='en'&&english)node.nodeValue=original.replace(trimmed,english);
      else node.nodeValue=original;
    }
    // Attributes retain the Dutch original as a per-element data property.
    $$('[placeholder],[aria-label],[title]').forEach(node=>{
      if(node.closest('[data-tm-product-nl],[data-tm-info-nl]'))return;
      for(const attr of ['placeholder','aria-label','title']){
        if(!node.hasAttribute(attr))continue;
        const key='__tmOriginal'+attr.replace(/[^a-z]/g,'_');
        if(node[key]===undefined)node[key]=node.getAttribute(attr);
        const original=node[key];
        if(mapping[original])node.setAttribute(attr,lang==='en'?mapping[original]:original);
      }
    });
    if(!$('[data-tm-info-root]')&&!$('.tm-product-page')){
      if(document.__tmOriginalPageTitle===undefined)document.__tmOriginalPageTitle=document.title;
      const title=document.__tmOriginalPageTitle;
      document.title=lang==='en'?(mapping[title]||title):title;
    }
  }
  function setLanguage(value,propagate){
    lang=value==='en'?'en':'nl';
    document.documentElement.lang=lang;
    const globalSelect=$('#tmGlobalLanguage');
    if(globalSelect)globalSelect.value=lang;
    $$('[data-tm-tr]').forEach(node=>{
      const text=node.dataset[lang==='en'?'tmEn':'tmNl'];
      if(text!==undefined)node.textContent=text;
    });
    $$('[data-tm-language]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.tmLanguage===lang)));
    const input=$('[data-tm-ai-input]');if(input)input.placeholder=labels[lang].ask;
    $$('[data-tm-menu-trigger]').forEach(btn=>btn.setAttribute('aria-label',labels[lang].menu));
    save(lang);
    translateCommonUI();
    translateInformationPage();
    translateProductText();
    if(propagate){
      if(typeof window.applyLanguage==='function')window.applyLanguage(lang);
      const picker=$('#trendmixLanguage')||$('#languageSelect');
      if(picker && picker.value!==lang){
        picker.value=lang;picker.dispatchEvent(new Event('change',{bubbles:true}));
      }
    }
    // Dutch is the HTML default. Skip a costly document-wide text walk
    // on the first paint; still translate fully for English or switching back.
    if(lang==='en'||document.documentElement.dataset.tmWasEnglish==='1'){
      translateRemainingText();
    }
    document.documentElement.dataset.tmWasEnglish=(lang==='en'?'1':'0');
  }
  function lock(){document.body.classList.toggle('tm-mobile-overlay-open',!!opened)}
  function openDialog(kind,activator){
    const drawer=$('#tmMobileDrawer'),assist=$('#tmSmartAssistant');
    if(!drawer||!assist)return;
    if(opened)closeDialog(false);
    returnFocus=activator||document.activeElement;
    drawer.hidden=kind!=='drawer';
    assist.hidden=kind!=='ai';
    opened=kind;
    $$('[data-tm-menu-trigger]').forEach(b=>b.setAttribute('aria-expanded',String(kind==='drawer')));
    lock();
    const focus=kind==='drawer'?drawer.querySelector('[data-tm-drawer-close]'):assist.querySelector('[data-tm-ai-input]');
    if(focus)focus.focus({preventScroll:true});
  }
  function closeDialog(focusBack=true){
    const drawer=$('#tmMobileDrawer'),assist=$('#tmSmartAssistant');
    if(drawer)drawer.hidden=true;
    if(assist)assist.hidden=true;
    $$('[data-tm-menu-trigger]').forEach(b=>b.setAttribute('aria-expanded','false'));
    opened=null;lock();
    if(focusBack&&returnFocus&&typeof returnFocus.focus==='function')returnFocus.focus({preventScroll:true});
  }
  function topic(question){
    const t=String(question||'').toLowerCase();
    if(/retour|return|refund|terug|herroep|exchange|ruilen/.test(t))return 'returns';
    if(/lever|bezorg|verzend|shipping|deliver|postage|ship/.test(t))return 'shipping';
    if(/bestel|betaal|betalen|order|pay|checkout|payment|winkelwagen|cart/.test(t))return 'orders';
    if(/contact|klacht|mens|medewerker|employee|support|email|e-mail|whatsapp|helpdesk/.test(t))return 'contact';
    if(/privacy|cookie|data|persoonsgegev/.test(t))return 'privacy';
    if(/product|voorraad|foto|prijs|price|stock|gadgets|beauty|sport|shop|catalog|collectie/.test(t))return 'products';
    return 'none';
  }
  let sending=false;
  function addMessage(value,who){
    const list=$('[data-tm-ai-messages]');if(!list)return null;
    const bubble=document.createElement('div');
    bubble.className='tm-assist-bubble '+(who==='user'?'user':'bot');
    const span=document.createElement('span');
    span.textContent=String(value||'').slice(0,2000);
    bubble.appendChild(span);
    list.appendChild(bubble);
    list.scrollTop=list.scrollHeight;
    return bubble;
  }
  function addLinks(bubble,links){
    if(!bubble||!Array.isArray(links))return;
    const holder=document.createElement('div');
    holder.className='tm-assist-answer-links';
    links.slice(0,4).forEach(link=>{
      if(!link||typeof link.url!=='string'||!/^\/[a-z0-9\/-]+$/.test(link.url))return;
      const a=document.createElement('a');
      a.href=link.url;
      a.textContent=String(link.label||'Meer informatie').slice(0,90)+' →';
      holder.appendChild(a);
    });
    if(holder.childElementCount)bubble.appendChild(holder);
  }
  async function answer(question){
    const value=String(question||'').trim().slice(0,500);
    if(!value||sending)return;
    sending=true;
    const submit=$('[data-tm-ai-form] button[type="submit"]');
    if(submit)submit.disabled=true;
    addMessage(value,'user');
    const bubble=addMessage(lang==='en'?'Searching the catalog…':'Ik zoek het voor je op…','bot');
    const ctrl=new AbortController();
    const timer=setTimeout(()=>ctrl.abort(),12000);
    try{
      const res=await fetch('/api/trendmix-assistant',{
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({question:value,language:lang,page:window.location.pathname}),
        signal:ctrl.signal
      });
      const data=await res.json();
      if(!res.ok||!data.ok)throw Error(data.error||'unavailable');
      if(bubble){
        bubble.firstElementChild.textContent=String(data.answer||'').slice(0,2000);
        addLinks(bubble,data.links);
        const list=$('[data-tm-ai-messages]');if(list)list.scrollTop=list.scrollHeight;
      }
    }catch(err){
      if(bubble){
        bubble.firstElementChild.textContent=(err.message==='rate_limited')
          ?(lang==='en'?'Too many messages. Try again later.':'Te veel vragen. Probeer het later opnieuw.')
          :(lang==='en'?'Service temporarily unavailable. Please try again.':'De hulp is tijdelijk niet bereikbaar. Probeer het opnieuw.');
        addLinks(bubble,[{label:'FAQ',url:'/faq'}]);
      }
    }finally{
      clearTimeout(timer);
      sending=false;
      if(submit)submit.disabled=false;
    }
  }
  function trapTab(event,root){
    const list=Array.from(root.querySelectorAll('button:not([disabled]),input:not([disabled]),a[href]')).filter(node=>node.getClientRects().length>0);
    if(!list.length)return;
    const first=list[0],last=list[list.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }
  function boot(){
    lang=stored()==='en'?'en':'nl';setLanguage(lang,false);
    const globalSelect=$('#tmGlobalLanguage');
    if(globalSelect)globalSelect.addEventListener('change',()=>setLanguage(globalSelect.value,true));
    $$('[data-tm-language]').forEach(button=>button.addEventListener('click',()=>setLanguage(button.dataset.tmLanguage,true)));
    $$('[data-tm-menu-trigger]').forEach(btn=>btn.addEventListener('click',()=>{opened==='drawer'?closeDialog():openDialog('drawer',btn)}));
    $$('[data-tm-drawer-close]').forEach(btn=>btn.addEventListener('click',()=>closeDialog()));
    $$('[data-tm-ai-open]').forEach(btn=>btn.addEventListener('click',()=>{
      if(opened==='drawer')closeDialog(false);
      openDialog('ai',btn);
    }));
    $$('[data-tm-ai-close]').forEach(btn=>btn.addEventListener('click',()=>closeDialog()));
    $$('[data-tm-quick]').forEach(btn=>btn.addEventListener('click',()=>{
      const type=btn.dataset.tmQuick;
      const nl={shipping:'Levering',returns:'Retouren',orders:'Bestellen',contact:'Contact',products:'Welke producten verkoopt NUVEMIXA?',after:'Hulp na een bestelling'};
      const en={shipping:'Delivery',returns:'Returns',orders:'Ordering',contact:'Contact',products:'Which products does NUVEMIXA sell?',after:'Help after ordering'};
      answer((lang==='en'?en:nl)[type]||type,type);
    }));
    const form=$('[data-tm-ai-form]');
    if(form)form.addEventListener('submit',event=>{
      event.preventDefault();const input=$('[data-tm-ai-input]');if(!input)return;
      const value=input.value;input.value='';answer(value);
    });
    document.addEventListener('keydown',event=>{
      if(!opened)return;
      if(event.key==='Escape'){event.preventDefault();closeDialog();return;}
      if(event.key==='Tab')trapTab(event,opened==='drawer'?$('#tmMobileDrawer'):$('#tmSmartAssistant'));
    });
    const picker=$('#trendmixLanguage')||$('#languageSelect');
    if(picker)picker.addEventListener('change',()=>{if(picker.value==='nl'||picker.value==='en')setLanguage(picker.value,false)});
    window.addEventListener('storage',event=>{if(event.key===storageKey&&(event.newValue==='nl'||event.newValue==='en'))setLanguage(event.newValue,false)});
    if(window.matchMedia){
      const media=window.matchMedia('(min-width:761px)');
      if(typeof media.addEventListener==='function')media.addEventListener('change',()=>{if(opened==='drawer'&&media.matches)closeDialog(false)});
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();