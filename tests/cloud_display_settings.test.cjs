const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const prefs=require('../reports/weak-early-beta-interactions.js');
const themeSource=fs.readFileSync(require('node:path').join(__dirname,'../reports/weak-early-beta-theme-init.js'),'utf8');
function theme(storage={},darkOS=false,blocked=false){const root={dataset:{},removeAttribute(){delete this.dataset.theme;}};vm.runInNewContext(themeSource,{document:{documentElement:root},window:{matchMedia:()=>({matches:darkOS})},localStorage:{getItem:k=>{if(blocked)throw Error('blocked');return storage[k]??null;}}});return root.dataset;}
test('fresh and blocked-storage views default dark without requesting permission',()=>{
 assert.equal(theme().theme,'dark');assert.equal(theme({},false,true).theme,'dark');
 assert.ok(!themeSource.includes('requestPermission'));
});
test('saved explicit light and system choices survive the new dark default',()=>{
 assert.equal(theme({'weakEarlyBetaTheme:v1':'light'}).theme,undefined);
 assert.equal(theme({'cloudReportDisplay:v1':JSON.stringify({theme:'light',fontSize:'large',pageSize:50})}).fontSize,'large');
 assert.equal(theme({'cloudReportDisplay:v1':JSON.stringify({theme:'system'})},false).theme,undefined);
 assert.equal(theme({'cloudReportDisplay:v1':JSON.stringify({theme:'system'})},true).theme,'dark');
});
test('display storage validates themes, fonts and pagination together',()=>{
 for(const theme of ['light','dark','system'])for(const fontSize of ['small','standard','large'])for(const pageSize of [20,50,100])assert.deepEqual(prefs.normalizeDisplay({theme,fontSize,pageSize}),{theme,fontSize,pageSize});
 for(const invalid of [{theme:'unknown'},{fontSize:'100px'},{pageSize:1000},{pageSize:'20'}])assert.throws(()=>prefs.normalizeDisplay({theme:'dark',fontSize:'standard',pageSize:20,...invalid}));
});
