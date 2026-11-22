'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const source=path.join(__dirname,'../weak-early-beta-gate/scripts/new-a-ui-source');
const memberSource=path.join(source,'assets/member-presentation.js');
const memberContext={module:{exports:{}},require:require('node:module').createRequire(memberSource)};
vm.runInNewContext(fs.readFileSync(memberSource,'utf8'),memberContext);
const NewAMemberPresentation=memberContext.module.exports;
const engine=require(path.join(source,'engine/finite-engine.cjs')),dataset=require(path.join(source,'engine/dataset-runtime.cjs'));
const prefs={initial_cash_yen:10000000,max_positions:20,per_order_cap_yen:500000,base_shares:100,cost_percent:0,price_cap_yen:null,exit_endpoint:'d6_open',year_scope:'all',allocation:'all'};
const policy={version:'A_OPEN_EXIT_V2',first_d5_entry_session:'2026-11-17',legacy_endpoint:'d6_open',new_endpoint:'d5_open'};
const calendar=['09','10','11','12','13','16','17','18','19','20','24','25','26','27','30'].map(d=>'2026-11-'+d);
const quote=(s,d)=>{const n=calendar.indexOf(d),price=100+n;return {open:price,high:price+2,low:price-2,close:price+1,actual_close:price+1,volume:100,actual_volume:100,source_usable:1,split_factor:1};};
const intents=(n=5)=>Array.from({length:n},(_,i)=>({symbol:String(1100+i),candidate_date:'2026-11-16',trigger_date:'2026-11-16',episode_id:1,priority_score:n-i}));
function input(){const selected=intents();return {source_version:'synthetic-input',calendar,limits:{identityUnverifiedBefore:{}},episodes:selected.map(e=>({...e})),intents:selected,watches:selected.map(e=>({...e,watch_status:'TRIGGERED'}))};}
function workerInitialization(manifest,records){
 const chunk=new TextEncoder().encode(JSON.stringify(records)).buffer;
 return {id:1,kind:'initialize',manifest:{...manifest,expected_quote_keys:records.length,quotes:[{bytes:chunk.byteLength,rows:records.length}]},quoteChunks:[chunk]};
}
function workerFixture(){
 const data=input(),fields=Object.keys(quote('1100',calendar[0])),records=intents().flatMap(e=>calendar.map(d=>[e.symbol,d,fields.map(k=>quote(e.symbol,d)[k])])),messages=[];
 const ctx={AFiniteDataset:dataset,TextDecoder,postMessage:m=>messages.push(structuredClone(m))};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'engine/worker-entry.js'),'utf8'),ctx);
 ctx.onmessage({data:workerInitialization({quote_fields:fields,input:data},records)});assert.equal(messages.pop().ready,true);
 return {simulate:(preset=null)=>{ctx.onmessage({data:{id:2,kind:'simulate',preferences:prefs,exit_policy:policy,...(preset?{trial_preset:preset}:{}),request_id:'synthetic-request'}});return messages.pop();}};
}
function controllerFactory(){const ctx={module:{exports:{}}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/finite-controller.js'),'utf8'),ctx);return ctx.module.exports;}

test('owner Analytics removes CSV and keeps the full chart and daily table paging',()=>{
 const client=controllerFactory(), simulation=workerFixture().simulate('profit');
 simulation.result.daily=Array.from({length:51},(_,offset)=>({
  ...simulation.result.daily[0], date:new Date(Date.UTC(2026,0,offset+1)).toISOString().slice(0,10),
 }));
 let panelRemoved=false, click;
 const nodes={
  'cloud-analytics-content':{
   setAttribute(){},
   querySelector(selector){
    assert.equal(selector,'section[aria-labelledby="analytics-export"]');
    assert.match(this.innerHTML,/aria-labelledby="analytics-export"/);
    return {remove(){panelRemoved=true;}};
   },
  },
  'new-a-daily-chart':{},'new-a-daily-table':{},'new-a-daily-more':{},
 };
 const context={
  AFinite:{...client,createController({onChange}){
   return {load(){onChange({phase:'ready',revision:1,accepted:simulation});}};
  }},
  AFiniteLegacy:{applyAccountDisplay(){}},
  document:{body:{dataset:{page:'analytics'}},getElementById:id=>nodes[id],querySelector:()=>null,
   addEventListener(type,handler){if(type==='click')click=handler;}},
 };
 vm.runInNewContext(fs.readFileSync(path.join(source,'assets/finite-dom.js'),'utf8'),context);
 assert.equal(panelRemoved,true);
 assert.match(nodes['new-a-daily-chart'].innerHTML,/2026-02-20/);
 assert.doesNotMatch(nodes['new-a-daily-table'].innerHTML,/2026-02-20/);
 assert.equal(nodes['new-a-daily-more'].hidden,false);
 click({target:{closest:()=>({id:'new-a-daily-more'})}});
 assert.match(nodes['new-a-daily-table'].innerHTML,/2026-02-20/);
 assert.equal(nodes['new-a-daily-more'].hidden,true);
});

test('shared analytics displays whole yen in retained markup and additional daily rows',()=>{
 const daily=Array.from({length:51},(_,offset)=>[
  new Date(Date.UTC(2026,0,offset+1)).toISOString().slice(0,10),90.75,-10.5,null,1,false,
 ]);
 let panelRemoved=false, templateRemoved=false, click;
 const element=()=>({dataset:{},children:[],append(child){this.children.push(child);}});
 const tableBody={rows:daily.slice(0,50),append(fragment){this.rows.push(...fragment.children);}};
 const nodes={
  '#new-a-reference-daily-values':{content:{textContent:JSON.stringify({daily,summary:[['合計',100]]})},
   remove(){templateRemoved=true;}},
  '#new-a-daily-table table':{tBodies:[tableBody],tHead:{rows:[{cells:daily[0].map(()=>({textContent:'見出し'}))}]}},
  '#new-a-daily-more':{hidden:false,addEventListener(type,handler){if(type==='click')click=handler;}},
  'section[aria-labelledby="analytics-export"]':{remove(){panelRemoved=true;}},
 };
 const amounts = ['190,092.48円','-390,980.5円','保有・注文上限 20銘柄・3,000.61円','-0.49円','-15.21%','2件']
  .map(textContent=>({textContent}));
 const axes = ['1,200.77','-2.5','2026-02-20','純資産（円）'].map(textContent=>({textContent}));
 const context={NewAMemberPresentation,document:{createDocumentFragment:element,createElement:element}};
 vm.runInNewContext(fs.readFileSync(path.join(source,'assets/reference-analytics.js'),'utf8'),context);
 context.NewAReferenceAnalytics.mount({
  querySelector:selector=>nodes[selector],
  querySelectorAll:selector=>selector.startsWith('svg')?axes:amounts,
 });
 assert.deepEqual(amounts.map(label=>label.textContent),
  ['190,092円','-390,981円','保有・注文上限 20銘柄・3,001円','0円','-15.21%','2件']);
 assert.deepEqual(axes.map(label=>label.textContent), ['1,201','-3','2026-02-20','純資産（円）']);
 assert.equal(panelRemoved,true);
 assert.equal(templateRemoved,true);
 assert.equal(tableBody.rows.length,50);
 click();
 assert.equal(tableBody.rows.length,51);
 assert.deepEqual(tableBody.rows[50].children.map(cell=>cell.textContent),
  ['2026-02-20','91円','-11円','未確定','1','確定']);
 assert.deepEqual(daily[50].slice(1,4), [90.75,-10.5,null]);
 assert.equal(nodes['#new-a-daily-more'].hidden,true);
});

test('Premium Analytics fetches the daily table on open, can retry, and pages without another fetch',async()=>{
 const daily=Array.from({length:51},(_,offset)=>[
  new Date(Date.UTC(2026,0,offset+1)).toISOString().slice(0,10),90.4,10.6,100,1,false,
 ]);
 const element=()=>({dataset:{},children:[],listeners:{},append(...children){this.children.push(...children);},
  setAttribute(){},addEventListener(event,fn){this.listeners[event]=fn;},remove(){this.removed=true;}});
 const tableBody={rows:[],append(fragment){this.rows.push(...fragment.children);}};
 const details=element();
 const more=element();
 const table={closest:()=>details,tBodies:[tableBody],tHead:{rows:[{cells:daily[0].map(()=>({textContent:'見出し'}))}]}};
 const nodes={'#new-a-daily-table table':table,'#new-a-daily-more':more};
 const context={NewAMemberPresentation,document:{createDocumentFragment:element,createElement:element}};
 vm.runInNewContext(fs.readFileSync(path.join(source,'assets/reference-analytics.js'),'utf8'),context);
 let calls=0, settle;
 context.NewAReferenceAnalytics.mount({querySelector:selector=>nodes[selector],querySelectorAll:()=>[]},()=>{
  calls++;
  if(calls===1) return Promise.reject(Error('temporary_error'));
  return new Promise(resolve=>{settle=resolve;});
 });
 const [message,retry]=details.children;
 assert.equal(calls,0);
 assert.equal(tableBody.rows.length,0);
 assert.equal(more.hidden,true);
 details.open=true;
 await details.listeners.toggle();
 assert.equal(calls,1);
 assert.equal(retry.hidden,false);
 assert.match(message.textContent,/読み込めません/);
 const loading=retry.listeners.click();
 await details.listeners.toggle();
 assert.equal(calls,2);
 assert.equal(tableBody.rows.length,0);
 settle(JSON.stringify({daily}));
 await loading;
 assert.equal(tableBody.rows.length,50);
 assert.deepEqual(tableBody.rows[0].children.map(cell=>cell.textContent),
  ['2026-01-01','90円','11円','100円','1','確定']);
 assert.equal(more.hidden,false);
 assert.equal(message.removed,true);
 assert.equal(retry.removed,true);
 more.listeners.click();
 await details.listeners.toggle();
 assert.equal(calls,2);
 assert.equal(tableBody.rows.length,51);
 assert.equal(tableBody.rows[50].children[0].textContent,'2026-02-20');
 assert.equal(more.hidden,true);
});

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

test('late trial settlements use the original fifth or eighth session open and preserve intervening orders',()=>{
 const days=[...calendar,'2026-12-01','2026-12-02','2026-12-03'];
 for(const [preset,due,observed] of [
  ['defensive','2026-11-24','2026-11-26'],
  ['balanced','2026-11-24','2026-11-26'],
  ['profit','2026-11-27','2026-12-02'],
 ]){
  const dueIndex=days.indexOf(due), observedIndex=days.indexOf(observed);
  const first=intents(1)[0];
  const candidates=[due,days[observedIndex-1],observed].map((trigger_date,index)=>({
   ...first,symbol:String(1101+index),candidate_date:trigger_date,trigger_date,
  }));
  const scheduledQueries=[];
  const params={calendar:days,intents:[first,...candidates],quotes:{
   get:(symbol,date)=>symbol===first.symbol&&date===due?null:quote(symbol,date),
   scheduledExit(symbol,date){
    scheduledQueries.push([symbol,date]);
    return {open:63,factor:2,observed_after:observed};
   },
  }};
  const settings={...prefs,max_positions:1};
  const options={trialPreset:preset};
  const unresolved=engine.replay({...params,quotes:{get:params.quotes.get}},settings,options);
  const result=engine.replay(params,settings,options);
  assert.deepEqual(scheduledQueries,[[first.symbol,due]]);
  assert.deepEqual(result.orders.filter(order=>order.order_date<=observed),
   unresolved.orders.filter(order=>order.order_date<=observed));
  assert.equal(result.orders.find(order=>order.order_date===observed).status,'HALTED_UNRESOLVED');
  assert.equal(result.orders.find(order=>order.order_date===days[observedIndex+1]).status,'FILLED');
  const trade=result.trades[0];
  assert.equal(trade.exit_date,due);
  assert.equal(trade.scheduled_exit_date,due);
  assert.equal(trade.exit_i,dueIndex);
  assert.equal(trade.settlement_observed_after,observed);
  assert.equal(trade.actual_exit_timing,'OPEN');
  assert.equal(trade.exit_price_nominal,63);
  assert.equal(trade.shares,200);
  assert.equal(trade.proceeds,12600);
  assert.equal(trade.delay_market_sessions,0);
  assert.equal(result.resolved,true);
  assert.equal(result.daily[dueIndex].equity_diagnostic,null);
  assert.equal(result.daily[dueIndex+1].equity_diagnostic,null);
  assert(result.metrics.maxDrawdown>-1);
 }
});

test('overlapping held symbols keep separate scheduled settlement dates and observations',()=>{
 const first=intents(2),next={...first[0],symbol:'1102',candidate_date:'2026-11-17',trigger_date:'2026-11-17'};
 const lookup={
  '1100':{open:90,factor:1,observed_after:'2026-11-26'},
  '1101':{open:95,factor:1,observed_after:'2026-11-27'},
 };
 const requests=[];
 const quotes={
  get:(symbol,date)=>Object.hasOwn(lookup,symbol)&&date==='2026-11-24'?null:quote(symbol,date),
  scheduledExit(symbol,date){
   requests.push([symbol,date]);
   return lookup[symbol];
  },
 };
 const result=engine.replay({calendar,intents:[...first,next],quotes},prefs,{trialPreset:'balanced'});
 assert.deepEqual(requests,[['1100','2026-11-24'],['1101','2026-11-24']]);
 assert.deepEqual(result.trades.map(({symbol,exit_date,settlement_observed_after})=>[symbol,exit_date,settlement_observed_after]),[
  ['1102','2026-11-25',undefined],
  ['1100','2026-11-24','2026-11-26'],
  ['1101','2026-11-24','2026-11-27'],
 ]);
 assert.equal(result.daily.find(day=>day.date==='2026-11-26').unresolved,true);
 assert.equal(result.daily.find(day=>day.date==='2026-11-27').unresolved,false);
 assert.equal(result.metrics.open,0);
});

test('late exit evidence cannot revise a regular quote or clear a different price gap',()=>{
 const first=intents(1);
 const prices={calendar,intents:first,quotes:{
  get:(symbol,date)=>date==='2026-11-24'?null:quote(symbol,date),
  scheduledExit:()=>{throw Error('non-trial settlement evidence read');},
 }};
 assert.equal(engine.replay(prices,prefs,{exitPolicy:policy}).trades.length,0);
 assert.equal(engine.replay({...prices,quotes:{...prices.quotes,get:quote}},prefs,{trialPreset:'balanced'}).trades.length,1);
 for(const receipt of [
  {open:80,factor:1,observed_after:'2026-11-24'},
  {open:80,factor:1,observed_after:'2026-11-28'},
  {open:80,factor:0.004,observed_after:'2026-11-25'},
 ]){
  const result=engine.replay({...prices,quotes:{...prices.quotes,scheduledExit:()=>receipt}},prefs,{trialPreset:'balanced'});
  assert.equal(result.trades.length,0);
  assert.equal(result.resolved,false);
 }
 const gap=engine.replay({...prices,quotes:{
  get:(symbol,date)=>['2026-11-19','2026-11-24'].includes(date)?null:quote(symbol,date),
  scheduledExit:()=>{throw Error('past non-exit price gap cannot be resolved by this receipt');},
 }},prefs,{trialPreset:'balanced'});
 assert.deepEqual(gap.unresolved,[{date:'2026-11-19',symbol:'1100',reason:'MISSING_HELD_QUOTE'}]);
});

test('a frozen missing intermediate mark leaves only that day unknown and keeps later trial orders',()=>{
 const missingDay='2026-11-19';
 const first=intents(1)[0];
 const later={...first,symbol:'1101',candidate_date:missingDay,trigger_date:missingDay};
 const prices=(symbol,date)=>{
  const bar=quote(symbol,date);
  if(symbol!==first.symbol)return bar;
  if(date===missingDay)return null;
  return date>missingDay?{...bar,actual_close:bar.close/2}:bar;
 };
 const quotes={get:prices,decisionSkipped:(symbol,date)=>symbol===first.symbol&&date===missingDay};
 const params={calendar,intents:[first,later],quotes};
 const options={trialPreset:'balanced'};
 const result=engine.replay(params,prefs,options);
 assert.deepEqual(result.unresolved,[]);
 assert.equal(result.resolved,true);
 assert.equal(result.daily.find(day=>day.date===missingDay).equity_diagnostic,null);
 assert.equal(result.daily.find(day=>day.date===missingDay).cash,null);
 assert.equal(result.daily.find(day=>day.date===missingDay).unresolved,true);
 assert.equal(result.daily.find(day=>day.date==='2026-11-20').unresolved,false);
 assert.equal(result.orders.find(order=>order.symbol===later.symbol).status,'FILLED');
 assert.equal(result.trades.find(trade=>trade.symbol===first.symbol).shares,200);
 const toMissingDay={...params,calendar:calendar.slice(0,calendar.indexOf(missingDay)+1)};
 const partial=engine.replay(toMissingDay,prefs,options);
 assert.equal(partial.resolved,false);
 assert.equal(partial.metrics.endEquity,null);
 assert.deepEqual(partial.unresolved,[]);
 for(const blockedQuotes of [
  {get:prices},
  {...quotes,get:(symbol,date)=>prices(symbol,date)??{...quote(symbol,date),source_usable:false}},
 ]){
  const blocked=engine.replay({...params,quotes:blockedQuotes},prefs,options);
  assert.equal(blocked.orders.find(order=>order.symbol===later.symbol).status,'HALTED_UNRESOLVED');
  assert.deepEqual(blocked.unresolved,[{date:missingDay,symbol:first.symbol,reason:'MISSING_HELD_QUOTE'}]);
 }
 const legacy=engine.replay({...params,quotes:{...quotes,decisionSkipped:()=>{throw Error('old model inspected decision skip');}}},prefs,{exitPolicy:policy});
 assert(legacy.unresolved.some(issue=>issue.reason==='MISSING_HELD_QUOTE'));
 const due='2026-11-24';
 const scheduled=engine.replay({...params,quotes:{
  get:(symbol,date)=>date===due&&symbol===first.symbol?null:quote(symbol,date),
  decisionSkipped:()=>true,
 }},prefs,options);
 assert(scheduled.unresolved.some(issue=>issue.date===due&&issue.reason==='UNRESOLVED_SCHEDULED_EXIT'));
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

test('Analytics shows the newest verified year separately when an old one-price exit stops full-period results',async()=>{
 const days=['2024-02-19','2024-02-20','2024-02-21','2024-02-22','2024-02-26','2024-02-27','2024-02-28','2024-02-29','2024-03-01','2024-03-04',...calendar];
 const past={symbol:'4911',candidate_date:days[0],trigger_date:days[0],episode_id:1,priority_score:1};
 const current=intents(1)[0];
 const episodes=[past,current],data={source_version:'verified-fixture',calendar:days,limits:{identityUnverifiedBefore:{},completeThrough:days.at(-1)},
  episodes,intents:episodes,watches:episodes.map(e=>({...e,watch_status:'TRIGGERED'}))};
 const normalQuote={open:100,high:103,low:99,close:101,actual_close:101,volume:100,actual_volume:100,source_usable:1};
 const get=(symbol,day)=>symbol===past.symbol&&['2024-02-27','2024-02-28','2024-03-01'].includes(day)
  ?{...normalQuote,open:100,high:100,low:100,close:100,actual_close:100}:normalQuote;
 const fields=Object.keys(normalQuote),records=episodes.flatMap(e=>days.map(day=>[e.symbol,day,fields.map(f=>get(e.symbol,day)[f])]));
 const messages=[],ctx={AFiniteEngine:engine,AFiniteDataset:dataset,TextDecoder,postMessage:m=>messages.push(structuredClone(m))};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'engine/worker-entry.js'),'utf8'),ctx);
 ctx.onmessage({data:workerInitialization({as_of:days.at(-1),quote_fields:fields,input:data},records)});
 assert.equal(messages.pop().ready,true);
 const simulate=(preferences,options={})=>{
  ctx.onmessage({data:{id:2,kind:'simulate',request_id:'load-1',preferences,exit_policy:policy,trial_preset:'balanced',...options}});
  return messages.pop();
 };
 const full=simulate(prefs);
 assert.equal(full.latest_year,undefined);
 assert.equal(full.result.resolved,false);
 assert.equal(full.result.unresolved[0].reason,'UNRESOLVED_SCHEDULED_EXIT');
 assert.equal(full.result.metrics.netProfit,null);
 const newer=simulate(prefs,{recent_analytics:true});
 assert.deepEqual(newer.result,full.result);
 assert.equal(newer.latest_year.resolved,true);
 assert.deepEqual(newer.latest_year.period,[calendar[0],calendar.at(-1)]);
 assert.equal(newer.latest_year.daily.at(-1).date,calendar.at(-1));
 assert(Number.isFinite(newer.latest_year.daily.at(-1).equity_diagnostic));
 assert.equal(newer.latest_year.metrics.fills,1);
 assert.equal(simulate({...prefs,year_scope:'2024'},{recent_analytics:true}).latest_year,undefined);
 const presetDashboard=simulate(prefs,{dashboard_prices:true});
 assert.equal(presetDashboard.dashboard_year.trial_policy.id,'balanced');
 assert.equal(presetDashboard.model_result,undefined);
 assert.deepEqual(presetDashboard.dashboard_year.daily,newer.latest_year.daily);
 const profitDashboard=simulate(prefs,{dashboard_prices:true,trial_preset:'profit'});
 assert.equal(profitDashboard.dashboard_year.trial_policy.id,'profit');
 assert.equal(profitDashboard.dashboard_year.trades[0].exit_date,'2026-11-27');
 assert.equal(simulate({...prefs,year_scope:'2024'},{dashboard_prices:true}).dashboard_year,undefined);
 const dashboard=simulate(prefs,{dashboard_prices:true,trial_preset:undefined});
 assert.equal(dashboard.result.resolved,false);
 assert.equal(dashboard.dashboard_year.resolved,true);
 assert.equal(dashboard.dashboard_year.trades[0].symbol,current.symbol);
 assert.deepEqual(dashboard.dashboard_closes.prices[current.symbol],{date:calendar.at(-1),price:101});
 ctx.onmessage({data:workerInitialization({as_of:days.at(-2),quote_fields:fields,input:data},records)});
 assert.equal(messages.pop().ready,true);
 assert.equal(simulate(prefs,{dashboard_prices:true,trial_preset:undefined}).dashboard_year,undefined);
 assert.equal(simulate(prefs,{dashboard_prices:true}).dashboard_year,undefined);
 const F=controllerFactory(),requests=[];
 const transport=async(url,options)=>{
  if(options.method==='GET')return Response.json({schema_version:1,has_saved_preferences:true,
   has_saved_finite_preferences:true,revision:1,default_proposal_verified:false,preferences:prefs});
  requests.push(JSON.parse(options.body));
  return Response.json(newer);
 };
 const controller=F.createController({transport,trialPreset:'balanced',recentAnalytics:true});
 assert.equal(await controller.load(),true);
 assert.equal(requests[0].recent_analytics,true);
 assert.deepEqual(requests[0].preferences,prefs);
 const html=F.render(controller.state().accepted);
 assert.match(html,/2024-02-27以降の資金推移は未計算/);
 assert.match(html,/2026年の成績/);
 assert.match(html,/2026-11-09 〜 2026-11-30/);
 assert.match(html,/全期間の資金・保有は引き継ぎません/);
 assert.match(html,/id="new-a-latest-year-chart"/);
 assert(html.indexOf('2026年の成績')<html.indexOf('全期間の成績'));
});

test('owner Analytics annualizes the period return using opening capital and elapsed calendar days',()=>{
 const F=controllerFactory(),d=workerFixture().simulate(),r=d.result;
 const period=['2025-01-02','2026-01-02'];
 const metrics={...r.metrics,initialCash:10_000_000,endEquity:11_400_000,netProfit:1_400_000};
 const report=(patch={},metricsPatch={})=>F.render({...d,result:{...r,period,...patch,metrics:{...metrics,...metricsPatch}}});
 const value=label=>new RegExp('年率換算損益率</small><b>'+label+'</b>');
 assert.match(report(),value('14\\.01%'));
 assert.match(report({period:['2025-01-02','2026-01-03']},{endEquity:9_000_000,netProfit:-1_000_000}),value('-9\\.98%'));
 assert.match(report({}, {endEquity:10_000_000,netProfit:0}),value('0%'));
 assert.match(report({}, {endEquity:0,netProfit:-10_000_000}),value('-100\\.07%'));
 for(const patch of [{resolved:false},{period:[]},{period:[period[0],period[0]]},{period:[period[1],period[0]]},
  {period:['2025-02-29',period[1]]},{period:['invalid',period[1]]}]){
  assert.match(report(patch),value('未確定'));
 }
 for(const metricsPatch of [{endEquity:null},{endEquity:-1},{initialCash:0},{initialCash:null}]){
  assert.match(report({},metricsPatch),value('未確定'));
 }
});

test('preset result mismatch is rejected before it can replace accepted metrics',async()=>{
 const F=controllerFactory(),worker=workerFixture();
 const transport=async(url,options)=>({ok:true,json:async()=>options.method==='GET'?{schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,revision:1,default_proposal_verified:false,preferences:prefs}:{...worker.simulate('profit'),request_id:JSON.parse(options.body).request_id}});
 const c=F.createController({transport,trialPreset:'balanced'});assert.equal(await c.load(),false);assert.equal(c.state().accepted,null);assert.equal(c.state().phase,'error');
});

test('warm browser broker rechecks owner access before another preset and clears on denial',async()=>{
 const ctx={module:{exports:{}},Response,TextDecoder,Uint8Array,AbortController,crypto:webcrypto};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/browser-transport.js'),'utf8'),ctx);
 const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),source_version:'synthetic-input',input_header:{...input()},collections:{episodes:[],intents:[],watches:[]},quotes:[],quote_fields:[],expected_quote_keys:0};
 let allowed=true,checks=0,terminated=0;const posts=[];
 const broker=ctx.module.exports.create({pinnedManifest:manifest,fetch:async()=>{checks++;return new Response(JSON.stringify({exit_policy:policy}),{status:allowed?200:401});},createWorker:()=>({postMessage(m){posts.push(m);queueMicrotask(()=>this.onmessage({data:{id:m.id,request_id:m.request_id,source_version:'synthetic-input',ready:true}}));},terminate(){terminated++;}})});
 const body=JSON.stringify({preferences:prefs,trial_preset:'balanced',request_id:'synthetic'});
 assert.equal((await broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body})).status,200);assert.equal(posts.at(-1).trial_preset,'balanced');allowed=false;
 assert.equal((await broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body})).status,401);assert.equal(checks,2);assert.equal(terminated,1);
});

test('preloading model data transfers the original verified quote buffers exactly once',async()=>{
 const ctx={module:{exports:{}},Response,TextDecoder,Uint8Array,AbortController,crypto:webcrypto};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/browser-transport.js'),'utf8'),ctx);
 const quoteText=JSON.stringify([['1100',calendar[0],[100,102,98,101]]]);
 const bytes=new TextEncoder().encode(quoteText);
 const descriptor={name:'quotes-000.json',bytes:bytes.length,rows:1,
  sha256:Buffer.from(await webcrypto.subtle.digest('SHA-256',bytes)).toString('hex')};
 const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),
  source_version:'synthetic-input',input_header:input(),collections:{episodes:[],intents:[],watches:[]},quotes:[descriptor]};
 const entered=Promise.withResolvers(),release=Promise.withResolvers();
 let quoteRequests=0,authChecks=0,workerStarts=0;
 const broker=ctx.module.exports.create({
  pinnedManifest:manifest,
  async fetch(url,options){
   assert.equal(options.cache,'no-store');
   if(url.endsWith('/preferences')){authChecks++;return Response.json({exit_policy:policy});}
   assert(url.endsWith(descriptor.name));quoteRequests++;entered.resolve();await release.promise;
   return new Response(quoteText);
  },
  createWorker(){
   workerStarts++;
   return {
    postMessage(message,transfer){
     if(message.kind==='initialize'){
      assert.equal(transfer.length,1);
      assert.equal(transfer[0],message.quoteChunks[0]);
      assert.equal(new TextDecoder().decode(transfer[0]),quoteText);
      const copied=structuredClone(message,{transfer});
      assert.equal(transfer[0].byteLength,0);
      assert.equal(copied.quoteChunks[0].byteLength,descriptor.bytes);
     }
     queueMicrotask(()=>this.onmessage({data:{id:message.id,ready:true}}));
    },
    terminate(){},
   };
  },
 });
 const preparing=broker.preload();assert.equal(broker.preload(),preparing);
 await entered.promise;
 assert.equal(authChecks,0);
 const result=broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body:JSON.stringify({preferences:prefs})});
 release.resolve();
 await preparing;assert.equal((await result).status,200);
 assert.equal(quoteRequests,1);assert.equal(workerStarts,1);assert.equal(authChecks,1);
});

test('owner price preload admits eight concurrent private part reads and queues the ninth', { timeout:5000 }, async t=>{
 const ctx={module:{exports:{}},Response,TextDecoder,Uint8Array,AbortController,crypto:webcrypto};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/browser-transport.js'),'utf8'),ctx);
 const raw='[]';
 const sha256=Buffer.from(await webcrypto.subtle.digest('SHA-256',new TextEncoder().encode(raw))).toString('hex');
 const quotes=Array.from({length:9},(_,index)=>({name:`quotes-00${index}.json`,bytes:raw.length,rows:0,sha256}));
 const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),
  source_version:'synthetic-input',input_header:input(),collections:{episodes:[],intents:[],watches:[]},quotes};
 const entered=Promise.withResolvers(), ninth=Promise.withResolvers(), first=Promise.withResolvers(), rest=Promise.withResolvers();
 const requests=[];
 const broker=ctx.module.exports.create({
  pinnedManifest:manifest,
  async fetch(url,{cache,credentials}){
   assert.equal(cache,'no-store');
   assert.equal(credentials,'same-origin');
   const index=requests.length;
   requests.push(url);
   if(requests.length===8)entered.resolve();
   if(requests.length===9)ninth.resolve();
   await (index===0?first.promise:rest.promise);
   return new Response(raw);
  },
  createWorker:()=>({postMessage(m){queueMicrotask(()=>this.onmessage({data:{id:m.id,ready:true}}));},terminate(){}}),
 });
 t.after(()=>{first.resolve();rest.resolve();});
 const loaded=broker.preload();
 await entered.promise;
 assert.equal(requests.length,8);
 first.resolve();
 await ninth.promise;
 rest.resolve();
 await loaded;
 assert.deepEqual(requests,quotes.map(d=>`/api/cloud/new-a-finite/input/${manifest.dataset_id}/${d.name}`));
});

test('a failed preload is surfaced without a silent retry and its other part reads are aborted',async()=>{
 const ctx={module:{exports:{}},Response,TextDecoder,Uint8Array,AbortController,crypto:webcrypto};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/browser-transport.js'),'utf8'),ctx);
 const descriptor=name=>({name,bytes:2,rows:0,sha256:'1'.repeat(64)});
 const manifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),
  source_version:'synthetic-input',input_header:input(),collections:{episodes:[],intents:[],watches:[]},
  quotes:[descriptor('quotes-000.json'),descriptor('quotes-001.json')]};
 for(const status of [401,503]){
  const blocked=Promise.withResolvers(),ready=Promise.withResolvers(),cancelled=Promise.withResolvers();
  let loads=0;
  const broker=ctx.module.exports.create({
   pinnedManifest:manifest,
   async fetch(url,{signal}){
    if(url.endsWith('/preferences'))return Response.json({exit_policy:policy});
    loads++;
    if(url.endsWith('000.json')){await blocked.promise;return new Response(null,{status});}
    return new Promise((resolve,reject)=>{
     signal.addEventListener('abort',()=>{cancelled.resolve();reject(signal.reason);},{once:true});
     ready.resolve();
    });
   },
   createWorker:()=>assert.fail('unverified inputs must not reach the worker'),
  });
  const result=assert.rejects(broker.preload(),error=>error.status===status);
  await ready.promise;blocked.resolve();
  await result;await cancelled.promise;
  const simulation=await broker.transport('/api/cloud/new-a-finite/simulate',{method:'POST',body:'{}'});
  assert.equal(simulation.status,status);
  assert.equal(loads,2);
 }
});

test('a same-length price change is rejected before any buffers reach a worker',async()=>{
 const ctx={module:{exports:{}},Response,TextDecoder,Uint8Array,AbortController,crypto:webcrypto};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'assets/browser-transport.js'),'utf8'),ctx);
 const original='[["1100","2026-11-09",[100]]]';
 const sha256=Buffer.from(await webcrypto.subtle.digest('SHA-256',new TextEncoder().encode(original))).toString('hex');
 const pinnedManifest={schema:'A_BROWSER_PRIVATE_INPUT_V1',audience:'EXISTING_CLOUD_OWNER_ONLY',dataset_id:'a-'+'1'.repeat(24),
  source_version:'synthetic-input',input_header:input(),collections:{episodes:[],intents:[],watches:[]},
  quotes:[{name:'quotes-000.json',bytes:original.length,rows:1,sha256}]};
 const broker=ctx.module.exports.create({
  pinnedManifest,fetch:async()=>new Response(original.replace('[100]', '[101]')),
  createWorker:()=>assert.fail('tampered quote bytes reached the worker'),
 });
 await assert.rejects(broker.preload(),/chunk_hash/);
});

test('model initialization rejects missing, truncated and duplicate quote chunks',()=>{
 const ctx={AFiniteDataset:dataset,TextDecoder,postMessage:null};
 let reply;ctx.postMessage=value=>{reply=value;};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(source,'engine/worker-entry.js'),'utf8'),ctx);
 const record=['1100',calendar[0],[100]];
 const prepare=records=>workerInitialization({quote_fields:['open'],input:input()},records);
 const missing=prepare([record]);missing.quoteChunks=[];
 const truncated=prepare([record]);truncated.manifest.quotes[0].rows=2;
 for(const message of [missing,truncated,prepare([record,record])]){
  ctx.onmessage({data:message});
  assert.equal(reply.error,'simulation_unavailable');
  assert.equal(reply.ready,undefined);
 }
});

test('dashboard virtual holdings use model dates relative to the selected period',()=>{
 const F=controllerFactory(),d=workerFixture().simulate('profit');
 const row={symbol:'1100',identity:'1100|2026-11-16|1',companyName:'<script>synthetic</script>',entry:{date:'2026-11-17'},endpoints:{d6_open:{date:'wrong-D6-date'}}};
 const pos={candidate_date:'2026-11-16',episode_id:1,entry_date:'2026-11-17',exit_i:3};
 d.result={...d.result,period:['2026-11-16','2026-11-18'],open_positions:{'1100':pos}};
 const html=F.renderHoldings(d,{rows:[row],calendar});
 assert.match(html,/仮想決済予定日/);
 assert.match(html,/2026-11-19/);
 assert.match(html,/&lt;script&gt;/);
 assert.doesNotMatch(html,/<script>synthetic/);
 assert.match(html,/8営業日目 寄付/);
 d.result.open_positions['1100'].exit_i=99;
 const unknown=F.renderHoldings(d,{rows:[row],calendar});
 assert.match(unknown,/未確認/);
 assert.doesNotMatch(unknown,/wrong-D6-date/);
});

test('unresolved analytics shows the actual stop date and incomplete metrics',()=>{
 const F=controllerFactory(),d=workerFixture().simulate('profit');
 d.result={...d.result,resolved:false,metrics:{...d.result.metrics,netProfit:null,maxDrawdown:null,winRate:null},unresolved:[{date:'2026-11-27',symbol:'1100',reason:'UNRESOLVED_SCHEDULED_EXIT'}]};
 const html=F.render(d);
 assert.match(html,/2026-11-27以降の資金推移は未計算/);
 assert.equal((html.match(/<b>未確定<\/b>/g)||[]).length,4);
 assert.doesNotMatch(html,/検出履歴/);
});

test('account view save uses the loaded binding and adopts only a matching receipt',async()=>{
 const F=controllerFactory(),worker=workerFixture(),writes=[];
 const binding='a'.repeat(64),next='b'.repeat(64);
 const view={trial_preset:'profit',theme:'light',font_size:'large',page_size:50};
 const base={schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,revision:1,default_proposal_verified:false,preferences:prefs,save_binding:binding,view_preferences:null};
 let changed=false;
 const transport=async(url,options)=>{
  if(options.method==='GET')return Response.json(base);
  const body=JSON.parse(options.body);
  if(options.method==='PUT'){
   writes.push(body);
   if(changed)return Response.json({error:'settings_session_changed'},{status:409});
   return Response.json({...base,preferences:body.preferences,revision:2,save_binding:next,view_preferences:view,request_id:body.request_id});
  }
  const value=worker.simulate(body.trial_preset??null);value.request_id=body.request_id;value.preferences=body.preferences;
  return Response.json(value);
 };
 const c=F.createController({transport,calculateOnLoad:false,trialPreset:'balanced'});
 assert(await c.load());
 assert.equal(c.state().viewPreferences,null);
 assert(await c.save(view));
 assert.equal(writes[0].save_binding,binding);
 assert.equal(c.state().viewPreferences.trial_preset,'profit');
 assert.equal(c.state().revision,2);
 changed=true;
 assert.equal(await c.save(view),false);
 assert.equal(writes[1].save_binding,next);
 assert.equal(c.state().phase,'session-changed');
 assert.equal(c.state().viewPreferences,null);
 assert.equal(c.state().applied,null);
 assert.equal(c.state().accepted,null);
});

test('display only saves without quote data, but changing the trial still requires simulation',async()=>{
 const F=controllerFactory(),writes=[];
 const binding='a'.repeat(64),next='b'.repeat(64);
 const view={trial_preset:'balanced',theme:'light',font_size:'large',page_size:50};
 const base={schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,revision:1,default_proposal_verified:false,preferences:prefs,save_binding:binding,view_preferences:null};
 let simulations=0;
 const transport=async(url,options)=>{
  if(options.method==='GET')return Response.json(base);
  const body=JSON.parse(options.body);
  if(options.method==='PUT'){
   writes.push(body);
   return Response.json({...base,preferences:body.preferences,revision:2,save_binding:next,view_preferences:view,request_id:body.request_id});
  }
  simulations++;
  return Response.json({error:'offline_quotes'},{status:503});
 };
 const c=F.createController({transport,calculateOnLoad:false,trialPreset:'balanced'});
 assert(await c.load());
 assert(await c.save(view));
 assert.equal(simulations,0);
 assert.equal(writes.length,1);
 assert.equal(c.state().viewPreferences.theme,'light');
 c.edit({...prefs,initial_cash_yen:20000000});
 assert.equal(await c.save(view),false);
 assert.equal(simulations,1);
 assert.equal(writes.length,1);
 assert.equal(c.state().applied.initial_cash_yen,prefs.initial_cash_yen);
 assert.equal(c.state().draft.initial_cash_yen,20000000);
});

test('pending account save holds the submitted draft until a verified receipt or a retryable error',async()=>{
 const F=controllerFactory(),worker=workerFixture(),writes=[];
 const binding='a'.repeat(64),view={trial_preset:'profit',theme:'light',font_size:'large',page_size:50};
 const base={schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,revision:1,default_proposal_verified:false,preferences:prefs,save_binding:binding};
 const draft={...prefs,max_positions:7};
 let simulation=Promise.withResolvers(),write=Promise.withResolvers(),writing=Promise.withResolvers();
 const transport=async(url,options)=>{
  if(options.method==='GET')return Response.json(base);
  const body=JSON.parse(options.body);
  if(options.method==='PUT'){
   writes.push(body);writing.resolve();
   return write.promise;
  }
  await simulation.promise;
  const data=worker.simulate(body.trial_preset);
  return Response.json({...data,request_id:body.request_id,preferences:body.preferences});
 };
 const c=F.createController({transport,calculateOnLoad:false,trialPreset:'balanced'});
 assert(await c.load());
 c.edit(draft);
 const pending=c.save(view);
 assert.equal(c.state().phase,'saving');
 assert.equal(await c.save(view),false);
 assert.equal(await c.load(),false);
 c.reset();c.cancel();c.edit({...draft,max_positions:5});
 assert.equal(c.state().draft.max_positions,7);
 assert.equal(writes.length,0);
 simulation.resolve();await writing.promise;
 assert.equal(c.state().phase,'saving');
 assert.equal(c.state().revision,1);
 write.resolve(Response.json({error:'temporarily_unavailable'},{status:503}));
 assert.equal(await pending,false);
 assert.equal(c.state().phase,'error');
 assert.equal(c.state().dirty,true);
 assert.equal(c.state().draft.max_positions,7);
 assert.equal(c.state().revision,1);
 assert.notEqual(c.state().message,'設定を保存しました。');

 write=Promise.withResolvers();writing=Promise.withResolvers();
 const retry=c.save(view);
 await writing.promise;
 assert.equal(c.state().phase,'saving');
 assert.equal(writes.length,2);
 const put=writes[1];
 assert.deepEqual(put.preferences,draft);
 assert.deepEqual(put.view_preferences,view);
 assert.equal(put.expected_revision,1);
 assert.equal(put.save_binding,binding);
 write.resolve(Response.json({...base,preferences:draft,view_preferences:view,revision:2,request_id:put.request_id,save_binding:'b'.repeat(64)}));
 assert.equal(await retry,true);
 assert.equal(c.state().phase,'ready');
 assert.equal(c.state().revision,2);
 assert.equal(c.state().dirty,false);
 assert.equal(c.state().message,'設定を保存しました。');
});
