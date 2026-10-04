const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {webcrypto,createHash}=require('node:crypto');
const source=fs.readFileSync(require.resolve('../reports/weak-early-beta-push.js'),'utf8');
const ownId='11111111-1111-4111-8111-111111111111';
async function page({registered=false,permission='granted'}={}) {
 const elements=new Map();
 const element=()=>({children:[],hidden:false,disabled:false,textContent:'',listeners:{},append(...items){this.children.push(...items);},prepend(...items){this.children.unshift(...items);},setAttribute(){},addEventListener(name,fn){this.listeners[name]=fn;}});
 const host=element(),controls=element();host.append(controls);
 const document={getElementById:()=>host,createElement:()=>{const e=element();Object.defineProperty(e,'id',{set(id){elements.set(id,e);}});return e;}};
 const state={browser:registered,server:registered,permission,serverFailure:false,browserFailure:false,browserNoEffect:false,readFailure:false,saveFailure:false,readAfterSaveFailure:false,requests:[],permissions:0,subscriptions:0,otherDevice:true,contract:'paid',role:'allowed',notifications:false};
 const endpoint='https://push.example.invalid/fixture-device';
 const subscription={endpoint,toJSON:()=>({endpoint,keys:{p256dh:'fixture',auth:'fixture'}}),unsubscribe:async()=>{if(state.browserFailure)throw Error('browser-failure');if(!state.browserNoEffect)state.browser=false;return !state.browserNoEffect;}};
 const worker={pushManager:{getSubscription:async()=>state.browser?subscription:null,subscribe:async()=>{state.subscriptions++;state.browser=true;return subscription;}}};
 const Notification={get permission(){return state.permission;},requestPermission:async()=>{state.permissions++;return state.permission;}};
 const config=()=>({ok:true,registration_available:true,public_key:'BA',allowed_origins:['https://push.example.invalid'],personal_test_available:true,personal_test_subscription_id:ownId,devices:state.server?[{subscription_id:ownId,endpoint_hash:createHash('sha256').update(endpoint).digest('hex')}]:[]});
 const fetch=async(path,init)=>{
   state.requests.push({path,method:init.method,body:init.body});
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
 vm.runInNewContext(source,{document,window:{isSecureContext:true,PushManager:{},Notification},Notification,navigator:{serviceWorker:{getRegistration:async()=>worker,register:async()=>worker,ready:Promise.resolve(worker)}},fetch,Response,URL,crypto:webcrypto,TextEncoder,Uint8Array,atob});
 for(let i=0;i<100&&elements.get('cloud-device-status').textContent==='端末へのプッシュ通知は現在利用できません。';i++)await new Promise(resolve=>setImmediate(resolve));
 return {state,host,controls,get:id=>elements.get(id),click:async id=>elements.get(id).listeners.click()};
}
test('unregistered has receive at top and exactly one current-device revoke control at bottom',async()=>{
 const p=await page();assert.equal(p.host.children[0].children[0],p.get('cloud-device-register'));assert.equal(p.host.children[1],p.controls);
 assert.equal(p.host.children.at(-1).children.at(-1),p.get('cloud-device-revoke'));
 assert.equal(p.get('cloud-device-register').textContent,'この端末で通知を受け取る');assert.equal(p.get('cloud-device-register').disabled,false);assert.equal(p.get('cloud-device-revoke').hidden,false);assert.equal(p.get('cloud-device-revoke').disabled,true);
 assert.equal(p.state.permissions,0);assert.equal(p.state.subscriptions,0);
});
test('registered and notifications OFF keep registration in the same position',async()=>{
 const p=await page({registered:true});assert.equal(p.get('cloud-device-register').textContent,'登録済み');assert.equal(p.get('cloud-device-register').disabled,true);
 assert.match(p.get('cloud-device-status').textContent,/OFFでも登録は残ります/);assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.equal(p.state.requests.some(r=>r.method==='DELETE'),false);
});
test('denied browser permission is distinct from registered state and causes no save',async()=>{
 const p=await page({permission:'denied'});assert.equal(p.get('cloud-device-register').disabled,true);assert.match(p.get('cloud-device-permission').textContent,/拒否/);
 await p.click('cloud-device-register');assert.equal(p.state.server,false);assert.equal(p.state.subscriptions,0);assert.doesNotMatch(p.get('cloud-device-status').textContent,/解除しました|登録済み/);
 const registered=await page({registered:true,permission:'denied'});assert.equal(registered.get('cloud-device-register').textContent,'登録済み');assert.match(registered.get('cloud-device-permission').textContent,/拒否/);assert.equal(registered.get('cloud-device-test').hidden,true);
});
test('server revoke failure preserves browser registration and never displays completion',async()=>{
 const p=await page({registered:true});p.state.serverFailure=true;await p.click('cloud-device-revoke');assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.match(p.get('cloud-device-status').textContent,/完了していません/);
 assert.equal(p.get('cloud-device-revoke').hidden,false);assert.equal(p.state.otherDevice,true);
});
for(const failure of ['browserFailure','browserNoEffect'])test('partial browser revoke '+failure+' stays incomplete and allows browser-only retry',async()=>{
 const p=await page({registered:true});p.state[failure]=true;await p.click('cloud-device-revoke');assert.equal(p.state.server,false);assert.equal(p.state.browser,true);assert.match(p.get('cloud-device-status').textContent,/未完了/);assert.equal(p.get('cloud-device-register').textContent,'この端末で通知を受け取る');
 p.state[failure]=false;await p.click('cloud-device-revoke');assert.equal(p.state.browser,false);assert.match(p.get('cloud-device-status').textContent,/この端末の通知登録を解除しました/);assert.equal(p.state.requests.filter(r=>r.method==='DELETE').length,1);
});
test('successful revoke preserves permission, membership, role, other device and opt-in; re-register works',async()=>{
 const p=await page({registered:true});await p.click('cloud-device-revoke');assert.equal(p.state.server,false);assert.equal(p.state.browser,false);assert.equal(p.state.permission,'granted');assert.equal(p.state.otherDevice,true);assert.equal(p.state.contract,'paid');assert.equal(p.state.role,'allowed');assert.equal(p.state.notifications,false);
 assert.equal(p.get('cloud-device-register').textContent,'この端末で通知を受け取る');await p.click('cloud-device-register');assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.equal(p.state.notifications,false);assert.equal(p.get('cloud-device-register').textContent,'登録済み');
});
test('registration save or post-revoke read failure never reports completion',async()=>{
 const p=await page();p.state.saveFailure=true;await p.click('cloud-device-register');assert.equal(p.state.server,false);assert.equal(p.state.browser,true);assert.match(p.get('cloud-device-status').textContent,/登録できませんでした/);assert.notEqual(p.get('cloud-device-register').textContent,'登録済み');
 p.state.saveFailure=false;await p.click('cloud-device-register');assert.equal(p.state.server,true);assert.equal(p.state.subscriptions,1);assert.equal(p.get('cloud-device-register').textContent,'登録済み');
 const r=await page({registered:true});r.state.readFailure=true;await r.click('cloud-device-revoke');assert.doesNotMatch(r.get('cloud-device-status').textContent,/解除しました/);assert.match(r.get('cloud-device-status').textContent,/完了していません/);
});
test('lost registration confirmation retains paired endpoint and does not display registered completion',async()=>{
 const p=await page();p.state.readAfterSaveFailure=true;await p.click('cloud-device-register');assert.equal(p.state.server,true);assert.equal(p.state.browser,true);assert.notEqual(p.get('cloud-device-register').textContent,'登録済み');assert.match(p.get('cloud-device-status').textContent,/登録できませんでした/);assert.equal(p.get('cloud-device-revoke').hidden,false);
});
