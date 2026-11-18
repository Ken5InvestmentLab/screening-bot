const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {webcrypto,createHash}=require('node:crypto');
const source=fs.readFileSync(require.resolve('../reports/weak-early-beta-push.js'),'utf8');
const ownId='11111111-1111-4111-8111-111111111111';
async function page({registered=false,permission='granted',qualificationReason=null}={}) {
 const elements=new Map();
 const element=()=>({children:[],hidden:false,disabled:false,textContent:'',listeners:{},append(...items){this.children.push(...items);},prepend(...items){this.children.unshift(...items);},setAttribute(){},addEventListener(name,fn){this.listeners[name]=fn;}});
 const host=element(),controls=element();host.append(controls); const windowEvents=new Map();
 const document={getElementById:()=>host,createElement:()=>{const e=element();Object.defineProperty(e,'id',{set(id){elements.set(id,e);}});return e;}};
 const state={browser:registered,server:registered,permission,qualificationReason,membershipStatus:qualificationReason?'unavailable':'paid',serverFailure:false,browserFailure:false,browserNoEffect:false,readFailure:false,saveFailure:false,readAfterSaveFailure:false,requests:[],permissions:0,subscriptions:0,otherDevice:true,contract:'paid',role:'allowed',notifications:false};
 const endpoint='https://push.example.invalid/fixture-device';
 const subscription={endpoint,toJSON:()=>({endpoint,keys:{p256dh:'fixture',auth:'fixture'}}),unsubscribe:async()=>{if(state.browserFailure)throw Error('browser-failure');if(!state.browserNoEffect)state.browser=false;return !state.browserNoEffect;}};
 const worker={pushManager:{getSubscription:async()=>state.browser?subscription:null,subscribe:async()=>{state.subscriptions++;state.browser=true;return subscription;}}};
 const Notification={get permission(){return state.permission;},requestPermission:async()=>{state.permissions++;state.permission=state.permissionResult??(state.permission==='default'?'granted':state.permission);return state.permission;}};
 const config=()=>({ok:true,...(state.freeAudience?{notification_eligible:['paid','free'].includes(state.membershipStatus)}:{}),registration_available:state.membershipStatus==='paid'||(state.freeAudience&&state.membershipStatus==='free'),membership:{status:state.membershipStatus,reason:state.qualificationReason},purchase_url:state.membershipStatus==='free'?'https://whop.com/fixture-existing-plan/':undefined,public_key:'BA',allowed_origins:['https://push.example.invalid'],personal_test_available:true,personal_test_subscription_id:ownId,devices:state.server?[{subscription_id:ownId,endpoint_hash:createHash('sha256').update(endpoint).digest('hex')}]:[]});
 const fetch=async(path,init)=>{
   state.requests.push({path,method:init.method,body:init.body,permissions:state.permissions});
   if(path==='/api/cloud/push-config'){if(state.readFailure)return Response.json({ok:false},{status:503});return Response.json(config());}
   if(path==='/api/cloud/push-subscriptions/device'){
     assert.equal(init.method,'DELETE');assert.deepEqual(JSON.parse(init.body),{subscription_id:ownId});
     if(state.serverFailure)return Response.json({ok:false},{status:503});state.server=false;return Response.json({ok:true,device_revoked:true});
   }
   if(path==='/api/cloud/push-subscriptions'){
     assert.equal(init.method,'POST');if(state.saveFailure)return Response.json({ok:false},{status:503});state.server=true;if(state.readAfterSaveFailure)state.readFailure=true;return Response.json({ok:true,subscription_id:ownId});
   }
   throw Error('unexpected-route');
 };
 vm.runInNewContext(source,{document,window:{isSecureContext:true,PushManager:{},Notification,addEventListener:(name,fn)=>windowEvents.set(name,fn)},Notification,navigator:{serviceWorker:{getRegistration:async()=>worker,register:async()=>worker,ready:Promise.resolve(worker)}},fetch,Response,URL,crypto:webcrypto,TextEncoder,Uint8Array,atob});
 const deadline=Date.now()+5000;
 while(elements.get('cloud-device-status').textContent==='端末へのプッシュ通知は現在利用できません。'&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,5));
 assert.notEqual(elements.get('cloud-device-status').textContent,'端末へのプッシュ通知は現在利用できません。','Initial async device lookup must settle before an action.');
 return {state,host,controls,get:id=>elements.get(id),enable:()=>new Promise(resolve=>windowEvents.get('cloud-notification-enable')({detail:{complete:resolve}})),disable:()=>new Promise(resolve=>windowEvents.get('cloud-notification-disable')({detail:{complete:resolve}})),click:async id=>elements.get(id).listeners.click()};
}
test('unregistered has no receive/revoke buttons and load never asks permission',async()=>{
 const p=await page();assert.equal(p.host.children[0].children[0],p.get('cloud-device-registration'));assert.equal(p.host.children[1],p.controls);
 assert.equal(p.get('cloud-device-revoke'),undefined);
 assert.equal(p.get('cloud-device-registration').textContent,'');assert.equal(p.get('cloud-device-register'),undefined);assert.equal(p.get('cloud-device-revoke'),undefined);
 assert.equal(p.state.permissions,0);assert.equal(p.state.subscriptions,0);
});
test('failed fresh qualification keeps registration disabled and reports lookup failure distinctly',async()=>{
 const p=await page({qualificationReason:'fresh_managed_role_unavailable'});assert.equal(p.get('cloud-device-register'),undefined);assert.match(p.get('cloud-notification-eligibility-status').textContent,/通知を利用できません/);assert.doesNotMatch(p.get('cloud-device-status').textContent,/剥奪|登録済み/);assert.equal(p.state.permissions,0);assert.equal(p.state.subscriptions,0);
});
test('eligibility failure retries to confirmed free then paid without permission, registration or push',async()=>{
 const p=await page({qualificationReason:'fresh_managed_role_unavailable'});assert.equal(p.get('cloud-notification-eligibility-status').textContent,'通知を利用できません。再試行してください。');assert.equal(p.get('cloud-notification-purchase'),undefined);assert.equal(p.get('cloud-notification-retry').hidden,false);
 p.state.membershipStatus='free';p.state.qualificationReason='managed_role_revoked';await p.click('cloud-notification-retry');assert.equal(p.get('cloud-notification-eligibility-status').textContent,'通知を利用できません。再試行してください。');assert.equal(p.get('cloud-notification-purchase'),undefined);assert.equal(p.get('cloud-device-register'),undefined);
 p.state.readFailure=true;await p.click('cloud-notification-retry');assert.equal(p.get('cloud-notification-purchase'),undefined);assert.equal(p.get('cloud-notification-eligibility-status').textContent,'通知を利用できません。再試行してください。');
 p.state.readFailure=false;p.state.membershipStatus='paid';p.state.qualificationReason=null;await p.click('cloud-notification-retry');assert.equal(p.get('cloud-notification-eligibility').hidden,true);assert.equal(p.get('cloud-notification-purchase'),undefined);assert.equal(p.get('cloud-notification-retry').hidden,true);assert.equal(p.get('cloud-device-register'),undefined);
 assert.equal(p.state.permissions,0);assert.equal(p.state.subscriptions,0);assert.ok(p.state.requests.every(r=>r.path==='/api/cloud/push-config'));
});
test('registered and notifications OFF keep registration in the same position',async()=>{
 const p=await page({registered:true});assert.equal(p.get('cloud-device-registration').textContent,'登録済み');assert.equal(p.get('cloud-device-register'),undefined);
 assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.equal(p.state.requests.some(r=>r.method==='DELETE'),false);
});
test('denied browser permission is distinct from registered state and causes no save',async()=>{
 const p=await page({permission:'denied'});assert.equal(p.get('cloud-device-register'),undefined);assert.match(p.get('cloud-device-permission').textContent,/拒否/);
 await p.enable();assert.equal(p.state.server,false);assert.equal(p.state.subscriptions,0);assert.doesNotMatch(p.get('cloud-device-status').textContent,/解除しました|登録済み/);
 const registered=await page({registered:true,permission:'denied'});assert.equal(registered.get('cloud-device-registration').textContent,'登録済み');assert.match(registered.get('cloud-device-permission').textContent,/拒否/);assert.equal(registered.get('cloud-device-test').hidden,true);
});

test('switch enable asks permission before network and reports registration only after confirmation',async()=>{
 const p=await page({permission:'default'});assert.equal(await p.enable(),true);
 assert.equal(p.state.permissions,1);assert.equal(p.state.subscriptions,1);
 assert.equal(p.state.requests.filter(r=>r.path==='/api/cloud/push-config')[1].permissions,1);
 assert.equal(p.get('cloud-device-registration').textContent,'登録済み');
 assert.equal(p.get('cloud-device-permission').textContent,'');
 assert.equal(await p.enable(),true);assert.equal(p.state.subscriptions,1);
});

test('permission prompt refusal returns false without browser/server registration',async()=>{
 const p=await page({permission:'default'});p.state.permissionResult='denied';assert.equal(await p.enable(),false);
 assert.equal(p.state.permissions,1);assert.equal(p.state.server,false);assert.equal(p.state.browser,false);assert.equal(p.state.subscriptions,0);
 assert.notEqual(p.get('cloud-device-registration').textContent,'登録済み');
});
test('server revoke failure preserves browser registration and never displays completion',async()=>{
 const p=await page({registered:true});p.state.serverFailure=true;await p.disable();assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.match(p.get('cloud-device-status').textContent,/解除を確認できません/);
 assert.equal(p.get('cloud-device-revoke'),undefined);assert.equal(p.state.otherDevice,true);
});
for(const failure of ['browserFailure','browserNoEffect'])test('partial browser revoke '+failure+' stays incomplete and allows browser-only retry',async()=>{
 const p=await page({registered:true});p.state[failure]=true;await p.disable();assert.equal(p.state.server,false);assert.equal(p.state.browser,true);assert.match(p.get('cloud-device-status').textContent,/未完了/);assert.equal(p.get('cloud-device-registration').textContent,'');
 p.state[failure]=false;await p.disable();assert.equal(p.state.browser,false);assert.equal(p.get('cloud-device-status').textContent,'');assert.equal(p.state.requests.filter(r=>r.method==='DELETE').length,1);
});
test('successful revoke preserves permission, membership, role, other device and opt-in; re-register works',async()=>{
 const p=await page({registered:true});await p.disable();assert.equal(p.state.server,false);assert.equal(p.state.browser,false);assert.equal(p.state.permission,'granted');assert.equal(p.state.otherDevice,true);assert.equal(p.state.contract,'paid');assert.equal(p.state.role,'allowed');assert.equal(p.state.notifications,false);
 assert.equal(p.get('cloud-device-registration').textContent,'');await p.enable();assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.equal(p.state.notifications,false);assert.equal(p.get('cloud-device-registration').textContent,'登録済み');
});
test('registration save or post-revoke read failure never reports completion',async()=>{
 const p=await page();p.state.saveFailure=true;await p.enable();assert.equal(p.state.server,false);assert.equal(p.state.browser,true);assert.match(p.get('cloud-device-status').textContent,/登録できませんでした/);assert.notEqual(p.get('cloud-device-registration').textContent,'登録済み');
 p.state.saveFailure=false;await p.enable();assert.equal(p.state.server,true);assert.equal(p.state.subscriptions,1);assert.equal(p.get('cloud-device-registration').textContent,'登録済み');
 const r=await page({registered:true});r.state.readFailure=true;await r.disable();assert.doesNotMatch(r.get('cloud-device-status').textContent,/解除しました/);assert.match(r.get('cloud-device-status').textContent,/解除を確認できません/);
});
test('lost registration confirmation retains paired endpoint and does not display registered completion',async()=>{
 const p=await page();p.state.readAfterSaveFailure=true;await p.enable();assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.notEqual(p.get('cloud-device-registration').textContent,'登録済み');assert.match(p.get('cloud-device-status').textContent,/登録できませんでした/);assert.equal(p.get('cloud-device-revoke'),undefined);
});

test('approved free audience hides paid-only offer and enables registration, failure blocks again',async()=>{
 const p=await page();p.state.freeAudience=true;p.state.membershipStatus='free';
 await p.get('cloud-notification-retry').listeners.click();
 assert.equal(p.get('cloud-notification-eligibility').hidden,true);assert.equal(p.get('cloud-notification-purchase'),undefined);
 assert.equal(p.get('cloud-device-register'),undefined);assert.equal(p.state.permissions,0);assert.equal(p.state.subscriptions,0);
 p.state.membershipStatus='unavailable';await p.get('cloud-notification-retry').listeners.click();
 assert.equal(p.get('cloud-device-register'),undefined);assert.equal(p.get('cloud-notification-retry').hidden,false);
 assert.equal(p.get('cloud-notification-eligibility-status').textContent,'通知を利用できません。再試行してください。');
});

async function newASettings({available=true,originAllowed=true}={}){
 const app={exports:{}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-notifications.js'),'utf8'),{module:app});
 const {mount}=app.exports;
 const elements=new Map(),listeners=new Map(),writes=[];
 const state={permissions:0,subscriptionWrites:0,saved:{new_detection:false,reminder:false},registered:false,scriptLoads:0};
 const element=()=>({hidden:false,disabled:false,checked:false,children:[],listeners:{},textContent:'',
  set id(id){elements.set(id,this);},append(...nodes){this.children.push(...nodes);},prepend(...nodes){this.children.unshift(...nodes);},
  addEventListener(name,callback){this.listeners[name]=callback;},setAttribute(){},focus(){},remove(){elements.delete('cloud-device-test');}});
 for(const id of ['settings','device','register','opt-in','status','save','retry']) elements.set('new-a-notification-'+id,element());
 for(const id of ['detection','reminder']) elements.set('new-a-notify-'+id,element());
 const get=id=>elements.get(id),document={getElementById:get,createElement:element};
 class CustomEvent {constructor(type,{detail}){this.type=type;this.detail=detail;}}
 const window={CustomEvent,isSecureContext:true,PushManager:{},Notification:null,
  addEventListener:(name,callback)=>listeners.set(name,callback),
  dispatchEvent:event=>listeners.get(event.type)?.(event)};
 const Notification={permission:'default',async requestPermission(){state.permissions++;this.permission='granted';return 'granted';}};
 window.Notification=Notification;
 const endpoint='https://fixture-provider.invalid/private-token';
 const subscription={endpoint,toJSON:()=>({endpoint,keys:{p256dh:'synthetic',auth:'synthetic'}}),unsubscribe:async()=>true};
 let browserSubscription=null;
 const worker={pushManager:{getSubscription:async()=>browserSubscription,subscribe:async()=>browserSubscription=subscription}};
 const config=()=>({ok:true,notification_eligible:true,membership:{status:'paid'},registration_available:originAllowed,
  preparation_available:!originAllowed,public_key:'BA',allowed_origins:originAllowed?['https://fixture-provider.invalid']:[],
  personal_test_available:true,personal_test_subscription_id:ownId,
  devices:state.registered?[{subscription_id:ownId,endpoint_hash:createHash('sha256').update(endpoint).digest('hex')}]:[]});
 const fetch=async(path,init)=>{
  if(init.method!=='GET')writes.push([path,init.method,JSON.parse(init.body)]);
  if(path==='/api/cloud/new-a-finite/notification-preferences'){
   if(init.method==='PUT')state.saved=JSON.parse(init.body).notifications;
   return Response.json({ok:true,available,notifications:state.saved});
  }
  if(path==='/api/cloud/push-config') return Response.json(config());
  if(path==='/api/cloud/push-subscriptions'&&init.method==='POST'){
   state.registered=true;
   state.subscriptionWrites++;
   return Response.json({ok:true,subscription_id:ownId});
  }
  assert.fail('Unexpected request '+path);
 };
 const loadPush=async()=>{
  state.scriptLoads++;
  vm.runInNewContext(source,{document,window,CustomEvent,Notification,navigator:{
   serviceWorker:{getRegistration:async()=>worker,register:async()=>worker,ready:Promise.resolve(worker)}
  },fetch,Response,URL,crypto:webcrypto,TextEncoder,Uint8Array,atob});
 };
 await mount({document,window,fetch,loadPush});
 if(available){
  const deadline=Date.now()+1000,register=get('new-a-notification-register');
  while(register.disabled&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,5));
  assert.equal(register.disabled,false,'Initial push qualification must finish before enrollment.');
 }
 return {state,writes,get,click:async id=>get('new-a-notification-'+id).listeners.click(),
  change:(kind,checked)=>{get('new-a-notify-'+kind).checked=checked;get('new-a-notification-opt-in').listeners.change();}};
}

test('New A enrolls only after explicit registration and saves just the two scoped opt-ins',async()=>{
 const {state,writes,get,click,change}=await newASettings();
 assert.equal(state.permissions,0);
 assert.deepEqual(writes,[]);
 assert.equal(get('cloud-device-test'),undefined);
 change('detection',true);
 await click('save');
 assert.deepEqual(writes,[]);
 assert.equal(state.permissions,0);
 await click('register');
 assert.equal(state.permissions,1);
 assert.equal(state.subscriptionWrites,1);
 assert.equal(state.saved.new_detection,false);
 assert.equal(get('cloud-device-test'),undefined);
 await click('save');
 assert.deepEqual(writes.at(-1),['/api/cloud/new-a-finite/notification-preferences','PUT',{notifications:{new_detection:true,reminder:false}}]);
 assert.equal(state.saved.new_detection,true);
 change('detection',false);
 await click('save');
 assert.equal(state.saved.new_detection,false);
 assert.equal(state.registered,true);
 assert.equal(state.subscriptionWrites,1);
});

test('New A keeps unavailable modes read-only and reports only the unapproved provider origin',async()=>{
 const disabled=await newASettings({available:false});
 assert.equal(disabled.state.scriptLoads,0);
 assert.equal(disabled.get('new-a-notification-register').disabled,true);
 assert.equal(disabled.get('new-a-notification-opt-in').disabled,true);
 assert.deepEqual(disabled.writes,[]);
 const prepared=await newASettings({originAllowed:false});
 await prepared.click('register');
 assert.equal(prepared.state.permissions,1);
 assert.equal(prepared.state.registered,false);
 assert.equal(prepared.get('cloud-device-provider-origin').textContent,'通知サービスのorigin: https://fixture-provider.invalid');
 assert.deepEqual(prepared.writes,[]);
});
