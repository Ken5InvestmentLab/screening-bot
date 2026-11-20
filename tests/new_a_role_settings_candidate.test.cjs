const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const assets = path.join(__dirname,'../weak-early-beta-gate/scripts/new-a-ui-source/assets');
const source = name => readFileSync(path.join(assets,name),'utf8');
const modelContext = {module:{exports:{}},structuredClone};
vm.runInNewContext(source('member-settings.js'),modelContext);
const { state,specs } = modelContext.module.exports;
const preferences = {
 price_cap_yen:425.5,exit_endpoint:'a20_close',base_shares:200,cost_percent:1,year_scope:'2025',allocation:'stacked',
 initial_cash_yen:10000000,max_positions:20,per_order_cap_yen:500000,
};
const view_preferences = {trial_preset:'profit',theme:'dark',font_size:'standard',page_size:20};
const saved = {revision:3,save_binding:'b'.repeat(64),preferences,view_preferences};
const flush = () => new Promise(resolve => setImmediate(resolve));

test('only current inputs are editable and legacy account values survive cancel and save',() => {
 assert.deepEqual(Array.from(specs,item=>item.key),[
  'initial_cash_yen','max_positions','per_order_cap_yen','cost_percent','theme','font_size','page_size',
 ]);
 const model = state();
 model.load(saved);
 model.edit('preferences','initial_cash_yen',2000000);
 assert.deepEqual(model.cancel().preferences,preferences);
 assert.throws(()=>model.edit('preferences','price_cap_yen',1));
 assert.throws(()=>model.edit('preferences','notifications',true));
 assert.throws(()=>model.edit('view_preferences','trial_preset','defensive'));
 model.edit('view_preferences','theme','light');
 assert.deepEqual(model.begin().preferences,preferences);
});

test('save binds the original revision, locks edits and verifies its receipt',() => {
 const model = state();
 model.load(saved);
 model.edit('view_preferences','theme','light');
 const body = model.begin();
 assert.equal(body.expected_revision,3);
 assert.equal(body.save_binding,saved.save_binding);
 assert.throws(()=>model.cancel());
 assert.throws(()=>model.edit('view_preferences','theme','dark'));
 model.verify({...saved,revision:4,view_preferences:{...view_preferences,theme:'light'}});
 assert.equal(model.cancel().view_preferences.theme,'light');
});

test('wrong readback is not a success and an explicit conflict reload replaces the draft',() => {
 const model = state();
 model.load(saved);
 model.edit('preferences','initial_cash_yen',2000000);
 model.begin();
 assert.throws(()=>model.verify({...saved,revision:4}));
 model.fail();
 assert.equal(model.draft().preferences.initial_cash_yen,2000000);
 model.load({...saved,revision:7});
 assert.equal(model.draft().preferences.initial_cash_yen,preferences.initial_cash_yen);
});

function element(tag) {
 return {
  tag,children:[],events:{},attrs:{},dataset:{},hidden:false,disabled:false,isConnected:true,style:{},
  get lastElementChild() { return this.children.at(-1); },
  append(...nodes){ this.children.push(...nodes); },
  replaceChildren(...nodes){ this.children=nodes; },
  setAttribute(key,value){ this.attrs[key]=value; },
  addEventListener(type,handler){ this.events[type]=handler; },
  focus(){ this.focused=true; },
 };
}
function items(node) { return [node,...node.children.flatMap(items)]; }
function settingsHarness(owner) {
 const dialog = element('dialog');
 dialog.showModal = () => { dialog.open=true; };
 dialog.close = () => { dialog.open=false; dialog.events.close(); };
 const content = element('div'), status = element('p'), close = element('button'), retry = element('button');
 const nodes = { 'cloud-settings-dialog':dialog,'cloud-settings-content':content,'cloud-settings-status':status,
  'cloud-settings-close':close,'cloud-settings-retry':retry };
 const events = {}, paths = [];
 const document = { createElement:element,getElementById:id=>nodes[id],addEventListener:(name,fn)=>{events[name]=fn;} };
 let pref = {...saved};
 let savedCallback = null;
 const route = owner ? '/api/cloud/new-a-finite/preferences' : '/api/cloud/new-a-view/preferences';
 const transport = async (url,init={}) => {
  const method = init.method ?? 'GET';
  paths.push([method,url]);
  assert.equal(url,route);
  if (!owner) assert.equal(init.headers['x-cloud-member-session'],'s'.repeat(64));
  const fields = owner ? {schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,default_proposal_verified:false} : {};
  if (method==='PUT') {
   const sent=JSON.parse(init.body);
   assert.equal(sent.expected_revision,pref.revision);
   assert.equal(sent.save_binding,pref.save_binding);
   assert.deepEqual(sent.preferences,owner?preferences:{...preferences,cost_percent:2});
   if (!owner) assert.deepEqual(sent.view_preferences,view_preferences);
   pref={revision:pref.revision+1,save_binding:'c'.repeat(64),preferences:sent.preferences,view_preferences:sent.view_preferences};
   return Response.json({...fields,...pref,request_id:sent.request_id});
  }
  return Response.json({...fields,...pref});
 };
 const context = vm.createContext({document,structuredClone,AbortController,fetch:transport,addEventListener(){},removeEventListener(){}});
 for (const name of ['../settings-dialog.js','member-settings.js','finite-controller.js','owner-settings.js']) vm.runInContext(source(name),context);
 context.CloudSettingsDialog.connect((out,message,ui)=>owner
  ? context.mountOwnerSettings(out,message,{...ui,transport,onRevoked(){assert.fail('unexpected role loss');},
   onSaved(state,trialChanged){savedCallback={state,trialChanged};}})
  : context.mountMemberSettings(out,message,{...ui,session:'s'.repeat(64),verifyAccess:async()=>true,
   accessDenied(){assert.fail('unexpected role loss');},onSaved(state){savedCallback={state};}}));
 const trigger=element('a');
 trigger.closest = selector => selector.startsWith('a[') ? trigger : null;
 const click=(options={})=>{
  let prevented=false;
  events.click({target:trigger,button:0,preventDefault(){prevented=true;},...options});
  return prevented;
 };
 return {dialog,content,status,close,trigger,click,route,paths,saved:()=>savedCallback};
}
for (const owner of [true,false]) {
 const scope=owner?'owner':'member';
 test(scope+' opens settings in the current page, reads only preferences, and cancel restores focus',async()=>{
  const ui=settingsHarness(owner);
  assert.equal(ui.click({ctrlKey:true}),false);
  assert.equal(ui.click(),true);
  assert.equal(ui.dialog.open,true);
  assert.equal(ui.close.focused,true);
  await flush();
  await flush();
  assert.deepEqual(ui.paths,[['GET',ui.route]]);
  const form=ui.content.children[0];
  assert.ok(form);
  assert.equal(items(form).some(node=>node.name==='price_cap_yen'),false);
  assert.equal(items(form).some(node=>node.name==='exit_endpoint'),false);
  assert.equal(items(form).some(node=>node.textContent==='プッシュ通知'),false);
  const shown=items(form).map(node=>node.name);
  for (const key of ['theme','font_size','page_size']) assert.equal(shown.includes(key),owner);
  assert.equal(shown.includes('trial_preset'),false);
  const cancel=items(form).find(node=>node.textContent==='キャンセル');
  cancel.events.click();
  assert.equal(ui.dialog.open,false);
  assert.equal(ui.trigger.focused,true);
  assert.deepEqual(ui.paths,[['GET',ui.route]]);
 });

 test(scope+' saves its editable fields while preserving hidden fields and never requesting quotes or push',async()=>{
  const ui=settingsHarness(owner);
  ui.click();
  await flush();
  await flush();
  const form=ui.content.children[0];
  items(form).find(node=>node.name===(owner?'theme':'cost_percent')).value=owner?'light':'2';
  await form.events.submit({preventDefault(){}});
  if (owner) {
   assert.deepEqual(JSON.parse(JSON.stringify(ui.saved()?.state.viewPreferences)),{...view_preferences,theme:'light'});
   assert.equal(ui.saved()?.trialChanged,false);
  } else {
   assert.equal(ui.saved()?.state.preferences.cost_percent,2);
   assert.deepEqual(ui.saved()?.state.view_preferences,view_preferences);
  }
  assert.deepEqual(ui.paths,owner?[['GET',ui.route],['PUT',ui.route]]:[['GET',ui.route],['PUT',ui.route],['GET',ui.route]]);
  assert.match(ui.status.textContent,/設定を保存しました/);
 });
}
test('the replacement owner UI does not mount notifications or the push registration script',()=>{
 assert.doesNotMatch(source('owner-loader.js'),/AOwnerNotifications|owner-notifications\.js|weak-early-beta-push\.js/);
 assert.doesNotMatch(readFileSync(path.join(assets,'../settings-body.html'),'utf8'),/プッシュ通知|new-a-notification-settings/);
});

test('owner access reset clears an open modal and its direct fallback form',()=>{
 const loader=source('owner-loader.js');
 const reset=loader.slice(loader.indexOf(' function unavailable(){'),loader.indexOf(' async function start(){'));
 assert.match(reset,/CloudSettingsDialog\?\.close\(true\)/);
 assert.match(reset,/['"]cloud-settings-direct['"]/);
 assert.match(reset,/node\.replaceChildren\(\);node\.hidden=true/);
});
