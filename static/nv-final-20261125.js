/* Targeted review disclosure and measured dock clearance. */
(()=>{'use strict';
 const en=()=>document.documentElement.lang==='en',t=(nl,eng)=>en()?eng:nl;
 let cursor=null,busy=false;
 function rating(sec,stats){
  sec.dataset.reviewCount=stats.count;sec.dataset.reviewAverage=stats.average;
  const card=sec.querySelector('.nvp-rev'),line=card?.querySelector('.nvp-rev-text p');
  if(line){
   line.replaceChildren();
   if(!stats.count)line.textContent=t('Nog geen beoordelingen.','No ratings yet.');
   else{
    const stars=document.createElement('span');stars.className='nv-average-stars';stars.textContent='☆☆☆☆☆';stars.setAttribute('aria-hidden','true');
    const fill=document.createElement('span');fill.textContent='★★★★★';fill.style.width=(Math.max(0,Math.min(5,stats.average))*20)+'%';stars.append(fill);
    const score=document.createElement('span');score.className='nvp-rev-score';score.textContent=Number(stats.average).toFixed(1).replace('.',en()?'.':',')+'/5';
    line.append(stars,' ',score,' · '+stats.count+' '+t(stats.count===1?'beoordeling':'beoordelingen',stats.count===1?'rating':'ratings'));
   }
  }
  const btn=sec.querySelector('.nvp-rev-all'),panel=sec.querySelector('#nv-review-panel');
  if(btn){btn.setAttribute('aria-expanded',String(!panel.hidden));btn.setAttribute('aria-controls',panel.id);
   const label=btn.querySelector('span');if(label)label.textContent=t('Alle reviews','All reviews')+' ('+stats.count+')';
   if(!btn.querySelector('.nv-review-chevron')){const arrow=document.createElement('span');arrow.className='nv-review-chevron';arrow.textContent='⌄';arrow.setAttribute('aria-hidden','true');btn.append(arrow);}
  }
 }
 function makeReview(rv,index){
  const article=document.createElement('article');article.className='nv-rev-item';article.dataset.rating=rv.rating;
  const node=(tag,cls,value)=>{const n=document.createElement(tag);if(cls)n.className=cls;n.textContent=value;return n;};
  const top=node('div','nv-rev-top',''),avatar=node('div','nv-rev-av',rv.name.slice(0,1).toUpperCase());avatar.style.background=['#1e6fe0','#14864b','#c2410c','#7c3aed','#0e7490','#be185d'][index%6];avatar.setAttribute('aria-hidden','true');
  const author=node('div','','');author.append(node('div','nv-rev-name',rv.name),node('div','nv-rev-date',rv.created_at.slice(8,10)+'-'+rv.created_at.slice(5,7)+'-'+rv.created_at.slice(0,4)));
  top.append(avatar,author);article.append(top);
  const stars=node('div','nv-rev-stars sm','★'.repeat(rv.rating)+'☆'.repeat(5-rv.rating));stars.setAttribute('aria-label',rv.rating+'/5');article.append(stars);
  if(rv.title)article.append(node('h3','',rv.title));article.append(node('p','',rv.body));
  if(rv.product)article.append(node('div','nv-rev-prod','Product: '+rv.product));
  if(rv.reply)article.append(node('div','nv-rev-reply',t('Reactie van NUVEMIXA: ','Reply from NUVEMIXA: ')+rv.reply));
  // Public moderation flags alone are not proof of a purchase; no purchase badge.
  return article;
 }
 async function load(sec,first){
  if(busy)return;busy=true;
  const more=sec.querySelector('[data-review-more]'),msg=sec.querySelector('[data-review-message]'),list=sec.querySelector('.nv-rev-list');
  more.disabled=true;list.setAttribute('aria-busy','true');msg.textContent='';
  try{
   const response=await fetch('/reviews/page'+(!first&&cursor?'?cursor='+encodeURIComponent(cursor):''),{headers:{Accept:'application/json'},cache:'no-store'});
   if(!response.ok)throw Error();const data=await response.json();
   if(first)list.replaceChildren();
   for(const rv of data.reviews)list.append(makeReview(rv,list.children.length));
   cursor=data.next_cursor;more.hidden=!cursor;more.textContent=t('Meer reviews laden','Load more reviews');
   if(!data.stats.count)msg.textContent=t('Nog geen beoordelingen.','No ratings yet.');
   rating(sec,data.stats);
  }catch(_){msg.textContent=t('Reviews laden lukt nu niet. Probeer opnieuw.','Unable to load reviews. Please try again.');more.hidden=false;more.textContent=t('Opnieuw proberen','Try again');}
  finally{busy=false;more.disabled=false;list.removeAttribute('aria-busy');}
 }
 function refreshReview(){
  const sec=document.getElementById('reviews');if(!sec)return;
  const original=sec.querySelector('.nm-reviews__all'),match=original?.textContent.match(/\((\d+)\)/);
  rating(sec,{count:Number(sec.dataset.reviewCount??match?.[1]??0),average:Number(sec.dataset.reviewAverage??sec.querySelector('.nm-reviews__number')?.textContent.replace(',','.').split('/')[0]??0)});
 }
 document.addEventListener('click',e=>{
  const btn=e.target.closest('.nvp-rev-all');if(btn){const sec=btn.closest('#reviews'),panel=sec.querySelector('#nv-review-panel');panel.hidden=!panel.hidden;btn.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)load(sec,true);}
  if(e.target.closest('[data-review-more]'))load(e.target.closest('#reviews'),cursor===null);
  if(e.target.closest('[data-tm-lang], [data-lang], .tm-lang'))setTimeout(refreshReview,500);
 });
 let scheduled=false;
 function clearance(){
  scheduled=false;const dock=document.querySelector('nav.tm-dock'),root=document.documentElement;
  const rect=dock?.getBoundingClientRect(),visible=rect&&rect.height>0&&getComputedStyle(dock).display!=='none';
  if(visible){const height=Math.ceil(innerHeight-rect.top);root.style.setProperty('--nv-dock-clearance',height+'px');root.classList.add('nv-dock-visible');}
  else root.classList.remove('nv-dock-visible');
 }
 const schedule=()=>{if(!scheduled){scheduled=true;requestAnimationFrame(clearance);}};
 function init(){refreshReview();schedule();const dock=document.querySelector('nav.tm-dock');if(dock&&window.ResizeObserver)new ResizeObserver(schedule).observe(dock);}
 addEventListener('resize',schedule,{passive:true});addEventListener('orientationchange',schedule);addEventListener('pageshow',schedule);
 addEventListener('load',()=>{refreshReview();schedule();});
 new MutationObserver(()=>setTimeout(refreshReview,500)).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(init,0),{once:true});else init();
})();

(()=>{'use strict';
 const form=document.querySelector('[data-nv-checkout]');if(!form)return;
 let serial=0;
 async function recalculate(){
  const requestId=++serial,msg=form.querySelector('[data-quote-message]'),submit=form.querySelector('button:not([formnovalidate])');
  submit.disabled=true;msg.textContent=document.documentElement.lang==='en'?'Updating summary…':'Overzicht bijwerken…';
  try{
   const response=await fetch('/checkout/quote',{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}}),result=await response.json();
   if(requestId!==serial)return;
   if(!response.ok)throw Error();
   document.querySelector('[data-price-summary]').innerHTML=result.html;msg.textContent='';submit.disabled=false;
  }catch(_){if(requestId===serial)msg.textContent=document.documentElement.lang==='en'?'Check the country and coupon, then update the summary.':'Controleer land en kortingscode en werk het overzicht bij.';}
 }
 form.addEventListener('change',e=>{if(['country','coupon'].includes(e.target.name))recalculate();});
})();
