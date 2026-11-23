/* Keep the existing mobile design when a phone rotates beyond legacy width breakpoints.
   Uses screen size + touch capability, never a user-agent name or persisted preference.
   Reuses the site's loaded mobile CSS; original hero artwork and desktop CSS stay intact. */
(()=>{
 'use strict';
 const isPhone=()=>{
  const width=Number(screen.width),height=Number(screen.height);
  const touch=navigator.maxTouchPoints>0||matchMedia('(any-pointer:coarse)').matches;
  return touch&&Math.min(width,height)<=600&&Math.max(width,height)<=1400;
 };
 let mobileStyle;
 const mobileBreakpoint=/\(\s*max-width\s*:\s*(?:7[5-9]\d|8\d\d|9\d\d)px\s*\)/gi;
 function collect(rules){
  let css='';
  for(const rule of rules){
   if(rule.type===CSSRule.MEDIA_RULE){
    const condition=rule.conditionText;
    mobileBreakpoint.lastIndex=0;
    if(mobileBreakpoint.test(condition)){
     mobileBreakpoint.lastIndex=0;
     const adapted=condition.replace(mobileBreakpoint,'(min-width:0px)');
     css+='@media '+adapted+'{'+Array.from(rule.cssRules,r=>r.cssText).join('\n')+'}\n';
    }else{
     const nested=collect(rule.cssRules);
     if(nested)css+='@media '+condition+'{'+nested+'}\n';
    }
   }else if(rule.type===CSSRule.SUPPORTS_RULE){
    const nested=collect(rule.cssRules);
    if(nested)css+='@supports '+rule.conditionText+'{'+nested+'}\n';
   }
  }
  return css;
 }
 function setup(){
  mobileStyle=document.createElement('style');mobileStyle.id='nv-phone-mobile-rules';
  mobileStyle.media='not all';
  let css='';
  for(const sheet of document.styleSheets){
   try{
    if(sheet.href&&new URL(sheet.href,location.href).origin!==location.origin)continue;
    const rules=collect(sheet.cssRules);
    const media=sheet.media.mediaText;
    css+=media&&media!=='all'?'@media '+media+'{'+rules+'}':rules;
   }catch(_){/* Cross-origin styles are unrelated to our local mobile layout. */}
  }
  mobileStyle.textContent=css;document.head.appendChild(mobileStyle);
  refresh();
 }
 function refresh(){
  const phone=isPhone();document.documentElement.classList.toggle('nv-phone',phone);
  // Portrait retains its original narrow rules; only landscape/wide phone needs copies.
  if(mobileStyle)mobileStyle.media=phone&&innerWidth>760?'all':'not all';
 }
 window.nvPhoneLayout={isPhone,refresh};
 window.addEventListener('resize',refresh,{passive:true});
 window.addEventListener('pageshow',refresh);
 screen.orientation?.addEventListener('change',refresh);
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
