/* Local acceptance instrumentation only; loaded solely by tools/run_local.py. */
(()=>{
 const state={lcp:null,cls:0,clsSession:0,clsStart:0,clsLast:0,longTaskMs:0,longTaskMaxMs:0,startedVisible:document.visibilityState==='visible'};
 const observe=(type,fn)=>{try{new PerformanceObserver(list=>list.getEntries().forEach(fn)).observe({type,buffered:true})}catch(_){}};
 observe('largest-contentful-paint',e=>state.lcp={ms:e.startTime,element:e.element?.tagName||null,url:e.url?new URL(e.url,location.href).pathname:null});
 observe('layout-shift',e=>{if(e.hadRecentInput)return;if(e.startTime-state.clsLast<1000&&e.startTime-state.clsStart<5000)state.clsSession+=e.value;else{state.clsSession=e.value;state.clsStart=e.startTime}state.clsLast=e.startTime;state.cls=Math.max(state.cls,state.clsSession)});
 observe('longtask',e=>{state.longTaskMs+=Math.max(0,e.duration-50);state.longTaskMaxMs=Math.max(state.longTaskMaxMs,e.duration)});
 function sample(){
  const nav=performance.getEntriesByType('navigation')[0];
  if(!nav)return;
  const resources=performance.getEntriesByType('resource');
  const paints=performance.getEntriesByType('paint');
  let node=document.getElementById('nv-local-speed-metrics');
  if(!node){node=document.createElement('script');node.type='application/json';node.id='nv-local-speed-metrics';document.body.appendChild(node)}
  node.textContent=JSON.stringify({method:'Local browser, no network/CPU throttling; normal browser cache, not a PageSpeed score',
   elapsedMs:performance.now(),visibility:document.visibilityState,startedVisible:state.startedVisible,
   width:innerWidth,height:innerHeight,phone:document.documentElement.classList.contains('nv-phone'),
   ttfbMs:nav.responseStart-nav.requestStart,domContentLoadedMs:nav.domContentLoadedEventEnd,loadMs:nav.loadEventEnd,
   fcpMs:paints.find(e=>e.name==='first-contentful-paint')?.startTime??null,lcp:state.lcp,cls:state.cls,
   observedBlockingMs:state.longTaskMs,longTaskMaxMs:state.longTaskMaxMs,
   requests:resources.length+1,transferBytes:nav.transferSize+resources.reduce((n,e)=>n+e.transferSize,0),
   encodedBodyBytes:nav.encodedBodySize+resources.reduce((n,e)=>n+e.encodedBodySize,0),
   zeroTransferResources:resources.filter(e=>!e.transferSize).length,domElements:document.querySelectorAll('*').length,
   largestResources:resources.map(e=>({path:new URL(e.name,location.href).pathname,bytes:e.encodedBodySize,transfer:e.transferSize,durationMs:e.duration})).sort((a,b)=>b.bytes-a.bytes).slice(0,8)});
  node.dataset.ready=String(performance.now()>=3000);
 }
 window.addEventListener('load',()=>{sample();[500,1500,3000,5000].forEach(ms=>setTimeout(sample,ms))},{once:true});
})();
