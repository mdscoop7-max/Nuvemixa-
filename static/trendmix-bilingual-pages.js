/* Bilingual information and service pages. Browser language is an interface
   preference, not a claim that supplier or legal records are verified. */
(function(){
'use strict';
function current(){try{return localStorage.getItem('trendmix-language')==='en'?'en':'nl'}catch(_){return 'nl'}}
function render(lang){
 const root=document.querySelector('[data-tm-info-root]');
 if(root){
  document.querySelectorAll('[data-tm-info-nl][data-tm-info-en]').forEach(el=>{
   el.textContent=el.getAttribute('data-tm-info-'+lang)||'';
  });
  const name=root.getAttribute('data-tm-page-title-'+lang);
  const description=root.getAttribute('data-tm-page-description-'+lang);
  if(name)document.title=name+' | TrendMix';
  if(description){const meta=document.querySelector('meta[name="description"]');if(meta)meta.content=description}
 }
 document.querySelectorAll('[data-tm-service-nl][data-tm-service-en]').forEach(el=>{
   el.textContent=el.getAttribute('data-tm-service-'+lang)||'';
 });
 document.querySelectorAll('[data-tm-service-placeholder-en]').forEach(el=>{el.placeholder=lang==='en'?el.getAttribute('data-tm-service-placeholder-en'):'Vertel kort waarmee we je kunnen helpen...'});
 document.documentElement.lang=lang;
}
document.addEventListener('DOMContentLoaded',()=>{
 render(current());
 document.querySelectorAll('[data-language]').forEach(btn=>btn.addEventListener('click',()=>render(btn.dataset.language==='en'?'en':'nl')));
});
})();
