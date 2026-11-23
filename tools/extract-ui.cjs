// Export our existing translation data, without running DOM callbacks or network code.
const fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({document:{readyState:'loading',documentElement:{lang:'nl',setAttribute(){}},addEventListener(){},querySelector(){return null},querySelectorAll(){return []},getElementById(){return null}},localStorage:{getItem(){return 'nl'},setItem(){}},navigator:{languages:['nl'],language:'nl'},window:{},console:{log(){}}});
for(const name of ['static/app.js','static/languages.js'])vm.runInContext(fs.readFileSync(name,'utf8'),context,{timeout:2000});
const translations=JSON.parse(vm.runInContext('JSON.stringify(translations)',context));
fs.writeFileSync('content/ui-translations.json',JSON.stringify({nl:translations.nl,en:translations.en},null,2));
console.log('Exported NL/EN translation data');
