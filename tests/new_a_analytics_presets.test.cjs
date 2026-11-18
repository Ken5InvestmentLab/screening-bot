'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const source=path.join(__dirname,'../weak-early-beta-gate/scripts/new-a-ui-source');
const engine=require(path.join(source,'engine/finite-engine.cjs')),dataset=require(path.join(source,'engine/dataset-runtime.cjs'));
const prefs={initial_cash_yen:10000000,max_positions:20,per_order_cap_yen:500000,base_shares:100,cost_percent:0,price_cap_yen:null,exit_endpoint:'d6_open',year_scope:'all',allocation:'all'};
const policy={version:'A_OPEN_EXIT_V2',first_d5_entry_session:'2026-11-17',legacy_endpoint:'d6_open',new_endpoint:'d5_open'};
const calendar=['09','10','11','12','13','16','17','18','19','20','24','25','26','27','30'].map(d=>'2026-11-'+d);
const quote=(s,d)=>{const n=calendar.indexOf(d),price=100+n;return {open:price,high:price+2,low:price-2,close:price+1,actual_close:price+1,volume:100,actual_volume:100,source_usable:1,split_factor:1};};
const intents=(n=5)=>Array.from({length:n},(_,i)=>({symbol:String(1100+i),candidate_date:'2026-11-16',trigger_date:'2026-11-16',episode_id:1,priority_score:n-i}));
function input(){const selected=intents();return {source_version:'synthetic-input',calendar,limits:{identityUnverifiedBefore:{}},episodes:selected.map(e=>({...e})),intents:selected,watches:selected.map(e=>({...e,watch_status:'TRIGGERED'}))};}
function workerFixture(){
 const data=input(),fields=Object.keys(quote('1100',calendar[0])),records=intents().flatMap(e=>calendar.map(d=>[e.symbol,d,fields.map(k=>quote(e.symbol,d)[k])])),messages=[];
 const ctx={AFiniteDataset:dataset,postMessage:m=>messages.push(structuredClone(m))};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'engine/worker-entry.js'),'utf8'),ctx);
 ctx.onmessage({data:{id:1,kind:'initialize',manifest:{quote_fields:fields,expected_quote_keys:records.length,input:data},records}});assert.equal(messages.pop().ready,true);
 return {simulate:(preset=null)=>{ctx.onmessage({data:{id:2,kind:'simulate',preferences:prefs,exit_policy:policy,...(preset?{trial_preset:preset}:{}),request_id:'synthetic-request'}});return messages.pop();}};
}
function controllerFactory(){const ctx={module:{exports:{}}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/finite-controller.js'),'utf8'),ctx);return ctx.module.exports;}

test('preset day counts include purchase day and skip the holiday; model remains grandfathered',()=>{
 const runtime=dataset.createDatasetRuntime(input(),{get:quote}),model=runtime.simulate(prefs,{exitPolicy:policy});
 assert.equal(model.trades[0].exit_date,'2026-11-24');
 for(const [preset,days,date] of [['defensive',5,'2026-11-24'],['balanced',5,'2026-11-24'],['profit',8,'2026-11-27']]){
  const trial=runtime.simulate(prefs,{exitPolicy:policy,trialPreset:preset});assert(trial.trades.every(t=>t.exit_date===date&&t.exit_i-t.entry_i===days-1&&t.actual_exit_timing==='OPEN'));assert.equal(trial.metrics.fills,preset==='balanced'?5:3);
 }
 assert.deepEqual(runtime.simulate(prefs,{exitPolicy:policy}),model);
 const oldIntent={...intents(1)[0],candidate_date:'2026-11-13',trigger_date:'2026-11-13'};
 const old=engine.replay({calendar,intents:[oldIntent],quotes:{get:quote}},prefs,{exitPolicy:policy});assert.equal(old.trades[0].exit_i-old.trades[0].entry_i,5);
});

test('three-fill cap counts successful new fills, retaining lot and portfolio constraints',()=>{
 const q=(s,d)=>s==='1100'?{...quote(s,d),open:100,high:100,low:100,close:100,actual_close:100}:quote(s,d);
 const r=engine.replay({calendar,intents:intents(),quotes:{get:q}},prefs,{trialPreset:'defensive'});
 assert.equal(r.counts.UNFILLED_UNCERTAIN_ONE_PRICE,1);assert.equal(r.counts.FILLED,3);assert.equal(r.counts.DAILY_FILLED_CAP,1);assert(r.trades.every(t=>t.shares===100));
 const expensive=()=>({...quote(),open:6000,high:6100,low:5900,close:6000,actual_close:6000});
 const cap=engine.replay({calendar,intents:intents(1),quotes:{get:expensive}},prefs,{trialPreset:'balanced'});assert.equal(cap.counts.LOT_EXCEEDS_ALLOCATION,1);
 const held=engine.replay({calendar,intents:intents(),quotes:{get:quote}},{...prefs,max_positions:2},{trialPreset:'balanced'});assert.equal(held.counts.FILLED,2);assert.equal(held.counts.CAPACITY,3);
});

test('invalid presets fail closed and missing preset exit prices do not delay settlement',()=>{
 for(const id of ['unknown','__proto__',{},0])assert.throws(()=>engine.trialTerms(id),/trial_preset_invalid/);
 const r=engine.replay({calendar,intents:intents(1),quotes:{get:(s,d)=>d==='2026-11-27'?null:quote(s,d)}},prefs,{trialPreset:'profit'});
 assert.equal(r.resolved,false);assert.equal(r.metrics.netProfit,null);assert.equal(r.trades.length,0);assert(r.unresolved.some(x=>x.reason==='UNRESOLVED_SCHEDULED_EXIT'));
});

test('unresolved trial stops its account timeline without querying beyond prepared prices or inventing equity',()=>{
 const queried=[];const q=(s,d)=>{queried.push(d);if(d>'2026-11-27')throw Error('unprepared_quote_key');return d==='2026-11-27'?null:quote(s,d);};
 const r=engine.replay({calendar,intents:intents(1),quotes:{get:q}},prefs,{trialPreset:'profit'});
 assert.equal(r.resolved,false);assert.equal(r.metrics.netProfit,null);assert.equal(r.daily.at(-1).equity_diagnostic,null);assert.equal(r.daily.at(-1).cash,null);assert(!queried.includes('2026-11-30'));
});

test('actual worker supplies separate model history and each independently calculated trial',()=>{
 const worker=workerFixture(),baseline=worker.simulate();assert.equal(baseline.trial_preset,undefined);
 for(const id of ['defensive','balanced','profit']){
  const r=worker.simulate(id);assert.equal(r.trial_preset,id);assert.deepEqual(r.model_result,baseline.result);assert.equal(r.result.trial_policy.execution_status,'ANALYTICS_SIMULATION_ONLY');assert.equal(r.result.trial_policy.id,id);
  if(id==='balanced')assert.deepEqual(r.result.daily,baseline.result.daily);else assert.notDeepEqual(r.result.daily,baseline.result.daily);assert.deepEqual(r.preferences,prefs);
 }
 assert.deepEqual(worker.simulate(),baseline);
});

test('controller selects and recalculates presets without changing the nine saved preference fields',async()=>{
 const F=controllerFactory(),worker=workerFixture(),writes=[];let revision=1;
 const transport=async(url,options)=>{
  if(options.method==='GET')return {ok:true,json:async()=>({schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,revision,default_proposal_verified:false,preferences:prefs})};
  const body=JSON.parse(options.body);
  if(options.method==='PUT'){writes.push(body);revision++;return {ok:true,json:async()=>({request_id:body.request_id,schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,default_proposal_verified:false,revision,preferences:body.preferences})};}
  const value=worker.simulate(body.trial_preset??null);value.request_id=body.request_id;value.preferences=body.preferences;return {ok:true,json:async()=>value};
 };
 const c=F.createController({transport,trialPreset:'balanced'});assert(await c.load());assert.equal(c.state().trialPreset,'balanced');assert.equal(c.state().accepted.result.trial_policy.exit_sessions,5);
 assert(c.setTrialPreset('profit'));assert(await c.recalculate());assert.equal(writes.length,0);assert.equal(c.state().accepted.result.trial_policy.exit_sessions,8);assert.equal(c.state().accepted.model_result.trades[0].exit_date,'2026-11-24');
 assert(await c.save());assert.equal(writes.length,1);assert.deepEqual(writes[0].preferences,prefs);assert.equal(Object.keys(writes[0].preferences).length,9);assert.equal(writes[0].trial_preset,undefined);
 assert(F.render(c.state().accepted).includes('利益優先'));assert(F.exportsFor(c.state().accepted,'daily').includes('ANALYTICS_SIMULATION_ONLY'));
 assert(c.setTrialPreset(null));assert(await c.recalculate());assert.equal(c.state().accepted.trial_preset,undefined);assert.equal(c.state().accepted.result.exit_policy.version,policy.version);
});

test('preset result mismatch is rejected before it can replace accepted metrics',async()=>{
 const F=controllerFactory(),worker=workerFixture();
 const transport=async(url,options)=>({ok:true,json:async()=>options.method==='GET'?{schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,revision:1,default_proposal_verified:false,preferences:prefs}:{...worker.simulate('profit'),request_id:JSON.parse(options.body).request_id}});
 const c=F.createController({transport,trialPreset:'balanced'});assert.equal(await c.load(),false);assert.equal(c.state().accepted,null);assert.equal(c.state().phase,'error');
});

test('warm browser broker rechecks owner access before another preset and clears on denial',async()=>{
 const ctx={module:{exports:{}},Response,TextDecoder,Uint8Array,crypto:webcrypto};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/browser-transport.js'),'utf8'),ctx);
 const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),source_version:'synthetic-input',input_header:{...input()},collections:{episodes:[],intents:[],watches:[]},quotes:[],quote_fields:[],expected_quote_keys:0};
 let allowed=true,checks=0,terminated=0;const posts=[];
 const broker=ctx.module.exports.create({pinnedManifest:manifest,fetch:async()=>{checks++;return new Response(JSON.stringify({exit_policy:policy}),{status:allowed?200:401});},createWorker:()=>({postMessage(m){posts.push(m);queueMicrotask(()=>this.onmessage({data:{id:m.id,request_id:m.request_id,source_version:'synthetic-input',ready:true}}));},terminate(){terminated++;}})});
 const body=JSON.stringify({preferences:prefs,trial_preset:'balanced',request_id:'synthetic'});
 assert.equal((await broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body})).status,200);assert.equal(posts.at(-1).trial_preset,'balanced');allowed=false;
 assert.equal((await broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body})).status,401);assert.equal(checks,2);assert.equal(terminated,1);
});

test('dashboard virtual holdings use model dates relative to the selected period',()=>{
 const F=controllerFactory(),d=workerFixture().simulate('profit');
 const row={symbol:'1100',identity:'1100|2026-11-16|1',companyName:'<script>synthetic</script>',entry:{date:'different'}};
 const pos={candidate_date:'2026-11-16',episode_id:1,entry_date:'2026-11-17',exit_i:3};
 d.model_result={...d.model_result,period:['2026-11-16','2026-11-18'],open_positions:{'1100':pos}};
 const html=F.renderHoldings(d,{rows:[row],calendar});
 assert.match(html,/仮想決済予定日/);
 assert.match(html,/2026-11-19/);
 assert.match(html,/&lt;script&gt;/);
 assert.doesNotMatch(html,/<script>synthetic/);
 d.model_result.open_positions['1100'].exit_i=99;
 assert.match(F.renderHoldings(d,{rows:[row],calendar}),/未確認/);
});

test('unresolved analytics shows the actual stop date and incomplete metrics',()=>{
 const F=controllerFactory(),d=workerFixture().simulate('profit');
 d.result={...d.result,resolved:false,metrics:{...d.result.metrics,netProfit:null,maxDrawdown:null,winRate:null},unresolved:[{date:'2026-11-27',symbol:'1100',reason:'UNRESOLVED_SCHEDULED_EXIT'}]};
 const html=F.render(d);
 assert.match(html,/2026-11-27以降の資金推移は未計算/);
 assert.equal((html.match(/<b>未確定<\/b>/g)||[]).length,3);
 assert.doesNotMatch(html,/検出履歴/);
});
