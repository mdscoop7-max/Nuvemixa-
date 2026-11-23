const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/nv-phone-layout.js'),'utf8');
function fixture(width,height,touch,viewport){
 const classes=new Set(),listeners={},styles=[];
 const context={screen:{width,height},navigator:{maxTouchPoints:touch?5:0},innerWidth:viewport,
  matchMedia:()=>({matches:touch}),CSSRule:{MEDIA_RULE:4,SUPPORTS_RULE:12},location:{href:'http://127.0.0.1/',origin:'http://127.0.0.1'},URL,
  document:{readyState:'complete',documentElement:{classList:{toggle:(key,on)=>on?classes.add(key):classes.delete(key)}},
   styleSheets:[{href:null,media:{mediaText:''},cssRules:[{type:4,conditionText:'(max-width: 760px)',cssRules:[{cssText:'.tm-dock { display: grid; }'}]}]}],
   createElement:()=>({}),head:{appendChild:style=>styles.push(style)}}};
 context.window={addEventListener:(key,fn)=>listeners[key]=fn};
 vm.createContext(context);vm.runInContext(source,context);
 return {context,classes,styles,listeners};
}
const cases=[[390,844,true,390,true],[844,390,true,844,true],[430,932,true,932,true],[390,844,false,844,false],[768,1024,true,1024,false],[1920,1080,true,844,false],[1366,900,false,390,false]];
for(const [w,h,touch,v,expected] of cases){const f=fixture(w,h,touch,v);assert.equal(f.classes.has('nv-phone'),expected);assert.equal(f.styles[0].media,expected&&v>760?'all':'not all');}
const f=fixture(390,844,true,390);f.context.innerWidth=844;f.listeners.resize();assert.equal(f.styles[0].media,'all');assert(f.styles[0].textContent.includes('(min-width:0px)'));assert(f.styles[0].textContent.includes('.tm-dock'));
f.context.innerWidth=390;f.listeners.resize();assert.equal(f.styles[0].media,'not all');
console.log(JSON.stringify({passed:true,deviceCases:cases.length,portraitLandscapePortrait:true,reusedMobileStyles:true,physicalDevice:false}));
