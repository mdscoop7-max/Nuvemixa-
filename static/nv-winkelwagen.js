/* Voorkomt dubbele/onbedoelde toevoegingen door dubbelklikken op "Toevoegen" of verzenden van het checkoutformulier. */
(function(){
  'use strict';
  var lock=new WeakSet();
  document.addEventListener('submit',function(event){
    var form=event.target;
    if(!form||form.tagName!=='FORM')return;
    var action=(form.getAttribute('action')||'');
    var isCart=action.indexOf('/winkelwagen')===0&&form.querySelector('input[name="action"]');
    var isCheckout=form.classList&&form.classList.contains('checkout-form');
    if(!isCart&&!isCheckout)return;
    // De knop "Korting berekenen" is geen definitieve verzending.
    var submitter=event.submitter;
    if(isCheckout&&submitter&&submitter.name==='checkout_action')return;
    if(lock.has(form)){event.preventDefault();return;}
    lock.add(form);
    form.setAttribute('aria-busy','true');
    Array.prototype.forEach.call(form.querySelectorAll('button[type="submit"]'),function(b){b.setAttribute('aria-disabled','true');b.style.pointerEvents='none';});
    // bfcache/terugknop: vergrendeling opheffen
    window.addEventListener('pageshow',function(){lock.delete(form);form.removeAttribute('aria-busy');Array.prototype.forEach.call(form.querySelectorAll('button[type="submit"]'),function(b){b.removeAttribute('aria-disabled');b.style.pointerEvents='';});});
  },true);
})();
