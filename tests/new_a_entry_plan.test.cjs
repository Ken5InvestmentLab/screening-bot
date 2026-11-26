'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { replay, planNextEntries } = require('../weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs');
const prefs = {price_cap_yen:null,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,year_scope:'all',allocation:'all',initial_cash_yen:1000000,max_positions:2,per_order_cap_yen:500000};
const calendar=['2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06','2026-11-09','2026-11-10','2026-11-11','2026-11-12'];
const intent=(symbol,candidate_date,trigger_date)=>({symbol,candidate_date,trigger_date,priority_score:1,episode_id:1});
const intents=[intent('1111',calendar[0],calendar[0]),intent('2222',calendar[1],calendar[7]),intent('3333',calendar[2],calendar[7])];
const quote={open:100,high:101,low:99,close:100,actual_close:100,volume:10,actual_volume:10,source_usable:true};
const quotes={get:()=>quote};
function before(){const result=replay({calendar:calendar.slice(0,-1),intents,quotes},prefs,{trialPreset:'profit'});return {...result,period:[calendar[0],calendar[7]]};}
test('evening plan and actual replay share the same slot priority including same-open exits',()=>{
 const result=before();assert.equal(Object.keys(result.open_positions).length,1);
 const plan=planNextEntries({asOf:calendar[7],nextSession:calendar[8],intents,result,
  quotes:{get:(symbol,day)=>{assert.ok(day<=calendar[7],'future quote must never be read');return quote;}}},prefs);
 assert.deepEqual(plan.rows.map(r=>[r.symbol,r.status]),[['2222','PLANNED_CONDITIONAL'],['3333','CAPACITY']]);
 const actual=replay({calendar,intents,quotes},prefs,{trialPreset:'profit'});
 assert.deepEqual(actual.orders.filter(r=>r.order_date===calendar[8]).map(r=>[r.symbol,r.status]),[['3333','CAPACITY'],['2222','FILLED']]);
 assert.equal(actual.trades[0].exit_date,calendar[8]);
 assert.equal(Object.keys(actual.open_positions).length,1);
});
test('plans remain conditional on unknown opening prices and remaining cash',()=>{
 const result=before();result.daily.at(-1).cash=12345;
 const plan=planNextEntries({asOf:calendar[7],nextSession:calendar[8],intents,result,quotes},prefs);
 assert.equal(plan.rows[0].status,'PLANNED_CONDITIONAL');assert.equal(plan.rows[0].max_opening_yen,123.45);
 assert.equal(plan.rows[1].max_opening_yen,null);
});
test('unresolved or stale accounts do not produce an affirmative plan',()=>{
 for(const result of [{...before(),resolved:false},{...before(),period:[calendar[0],calendar[6]]}]){
  assert.deepEqual(planNextEntries({asOf:calendar[7],nextSession:calendar[8],intents,result,quotes},prefs),{available:false,rows:[]});
 }
});
test('daily cap is a conditional standby and duplicate holdings are explicitly excluded',()=>{
 const result={...before(),open_positions:{},daily:[{date:calendar[7],cash:1000000}]};
 const many=['2222','3333','4444','5555'].map(s=>intent(s,calendar[1],calendar[7]));
 const plan=planNextEntries({asOf:calendar[7],nextSession:calendar[8],intents:many,result,quotes},{...prefs,max_positions:10});
 assert.deepEqual(plan.rows.map(r=>r.status),['PLANNED_CONDITIONAL','PLANNED_CONDITIONAL','PLANNED_CONDITIONAL','DAILY_CAP_STANDBY']);
 result.open_positions={'2222':{}};
 assert.equal(planNextEntries({asOf:calendar[7],nextSession:calendar[8],intents:many,result,quotes},{...prefs,max_positions:10}).rows[0].status,'DUPLICATE_HELD');
});
