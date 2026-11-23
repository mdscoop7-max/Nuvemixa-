/* One server-owned language preference; legacy storage key retained for compatibility. */
document.addEventListener('DOMContentLoaded',()=>{
 const lang=document.documentElement.lang==='en'?'en':'nl';
 const select=document.getElementById('tmGlobalLanguage');if(select)select.value=lang;
 const changeLanguage=next=>{if(!['nl','en'].includes(next))return;try{localStorage.setItem('trendmix-language',next)}catch(_){}const u=new URL(location.href);u.searchParams.set('lang',next);location.assign(u.href)};
 const expireBanner=b=>{const remaining=Number(b.dataset.nvEnd)*1000-Date.now();if(remaining<=0)b.remove();else setTimeout(()=>expireBanner(b),Math.min(remaining,2147483647))};
 document.querySelectorAll('[data-nv-end]').forEach(expireBanner);
 document.addEventListener('change',e=>{if(e.target.id==='tmGlobalLanguage'){e.stopImmediatePropagation();changeLanguage(e.target.value)}},true);
 document.addEventListener('click',e=>{const choice=e.target.closest('[data-tm-language],[data-language]');if(choice){const value=choice.dataset.tmLanguage||choice.dataset.language;if(['nl','en'].includes(value)){e.preventDefault();e.stopImmediatePropagation();changeLanguage(value)}}},true);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.querySelectorAll('details[open]').forEach(d=>{d.open=false;d.querySelector('summary')?.focus()});}const tab=e.target.closest('[role=tab]');if(tab&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){const tabs=[...tab.parentElement.querySelectorAll('[role=tab]')];const i=tabs.indexOf(tab);const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;e.preventDefault();tabs[next].click();tabs[next].focus();}});
 document.addEventListener('click',e=>{document.querySelectorAll('details.tm-category-dropdown[open]').forEach(d=>{if(!d.contains(e.target))d.open=false})});
 if('serviceWorker' in navigator&&(location.protocol==='https:'||['127.0.0.1','localhost'].includes(location.hostname)))navigator.serviceWorker.register('/service-worker.js').catch(()=>{});
});
