/* Network only. No account, cart, price, order, token or page cache exists. */
const VERSION='nuvemixa-shell-v1';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET'||event.request.mode!=='navigate')return;
 event.respondWith(fetch(event.request).catch(()=>new Response('<!doctype html><html lang="nl"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NUVEMIXA — offline</title><main><h1>NUVEMIXA</h1><p>Je bent offline. Verbind met internet voor actuele gegevens.</p><p>You are offline. Connect to the internet for current information.</p><a href="/">Opnieuw proberen / Try again</a></main></html>',{status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})));
});
