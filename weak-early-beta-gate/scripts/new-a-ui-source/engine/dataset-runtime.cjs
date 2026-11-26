// 同一の検証済み入力を使う純粋なtrial wrapper。通信・ファイル・認証を持たない。
'use strict';
const {replay,valid,validatePreferences,validateExitPolicy,trialTerms}=require('./finite-engine.cjs');

function validDay(value) {
 if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
 const time = Date.parse(value + 'T00:00:00Z');
 return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

function createQuoteDecoder(fields, calendar, asOf) {
 if (!Array.isArray(fields) || !fields.every(field => typeof field === 'string')
     || new Set(fields).size !== fields.length) throw Error('Invalid canonical quote fields');
 const exitIndex = fields.indexOf('scheduled_exit');
 const skippedIndex = fields.indexOf('decision_skipped');
 const marketDays = exitIndex === -1 && skippedIndex === -1 ? null : new Set(calendar);
 const recoveries = new Map();
 const skipped = new Set();
 return {
  normal(symbol, day, values) {
   if (values === null) return null;
   if (!Array.isArray(values) || values.length !== fields.length) throw Error('Invalid canonical quote values');
   const exit = exitIndex === -1 ? null : values[exitIndex];
   const decisionSkipped = skippedIndex === -1 ? null : values[skippedIndex];
   if (decisionSkipped !== null && decisionSkipped !== true) throw Error('Invalid skipped quote decision');
   if (exit !== null || decisionSkipped === true) {
    if (typeof symbol !== 'string' || !/^[0-9A-Z]{4}$/.test(symbol)
        || !validDay(day) || !validDay(asOf) || !marketDays.has(day) || !marketDays.has(asOf) || day > asOf
        || values.some((value, index) => index !== exitIndex && index !== skippedIndex && value !== null)) {
     throw Error('Invalid missing quote metadata');
    }
    const key = symbol + '|' + day;
    if (exit !== null) {
     if (!exit || typeof exit !== 'object' || Array.isArray(exit) || Object.keys(exit).length !== 3
         || !Number.isFinite(exit.open) || exit.open <= 0 || !Number.isFinite(exit.factor) || exit.factor <= 0
         || !validDay(exit.observed_after) || !marketDays.has(exit.observed_after)
         || day >= exit.observed_after || exit.observed_after > asOf) {
      throw Error('Invalid scheduled exit quote');
     }
     recoveries.set(key, Object.freeze({ open: exit.open, factor: exit.factor, observed_after: exit.observed_after }));
    }
    if (decisionSkipped) skipped.add(key);
    return null;
   }
   if (marketDays && values.every(value => value === null)) return null;
   const quote = Object.create(null);
   for (let i = 0; i < fields.length; i++) {
    if (i !== exitIndex && i !== skippedIndex) quote[fields[i]] = values[i];
   }
   return quote;
  },
  scheduledExit(symbol, day) {
   return recoveries.get(symbol + '|' + day) ?? null;
  },
  decisionSkipped(symbol, day) {
   return skipped.has(symbol + '|' + day);
  },
 };
}

function createDatasetRuntime(input,quotes){
 const results=new Map();
 function calculate(preferences,{identityScreen=true,variableShares=false,exitPolicy=null,trialPreset=null}={},firstSession=null){
  preferences=validatePreferences(preferences);exitPolicy=validateExitPolicy(exitPolicy);const trial=trialTerms(trialPreset);
  const key=JSON.stringify([preferences,identityScreen,variableShares,exitPolicy,trialPreset,firstSession]);if(results.has(key))return structuredClone(results.get(key));
  const hold=trial?trial.exit_sessions:preferences.exit_endpoint==='a20_close'?20:preferences.exit_endpoint==='d5_close'?5:6;
  let calendar=input.calendar;
  if(firstSession!==null){
   calendar=input.calendar.slice(input.calendar.indexOf(firstSession));
  }else if(preferences.year_scope!=='all'){
   const last=input.calendar.findLastIndex(d=>d.startsWith(preferences.year_scope));
   if(last<0)throw Error('year_unavailable');
   calendar=input.calendar.filter((d,i)=>d.slice(0,4)>=preferences.year_scope&&i<=last+20+hold);
  }
  const selected=input.episodes.filter(e=>(preferences.year_scope==='all'||e.candidate_date.startsWith(preferences.year_scope))&&calendar.includes(e.candidate_date));
  const status=new Map(input.watches.map(w=>[`${w.symbol}|${w.candidate_date}|${w.episode_id}`,w]));
  const watches=selected.map(e=>{
   const w=status.get(`${e.symbol}|${e.candidate_date}|${e.episode_id}`),r=quotes.get(e.symbol,e.candidate_date);let reason=null;
   if(identityScreen&&input.limits.identityUnverifiedBefore[e.symbol]&&e.candidate_date<input.limits.identityUnverifiedBefore[e.symbol])reason='IDENTITY_UNVERIFIED';
   else if(preferences.price_cap_yen!==null&&!valid(r))reason='SIGNAL_PRICE_UNVERIFIED';
   else if(preferences.price_cap_yen!==null&&r.actual_close>preferences.price_cap_yen)reason='PRICE_CAP';
   return {...w,selection_reason:reason};
  });
  const identityKeys=new Set(watches.filter(w=>w.selection_reason==='IDENTITY_UNVERIFIED').map(w=>`${w.symbol}|${w.candidate_date}|${w.episode_id}`));
  const intents=input.intents.filter(e=>calendar.includes(e.candidate_date)&&calendar.includes(e.trigger_date)&&(preferences.year_scope==='all'||e.candidate_date.startsWith(preferences.year_scope))&&!identityKeys.has(`${e.symbol}|${e.candidate_date}|${e.episode_id}`));
  const result={...replay({calendar,intents,quotes,restrictionExits:input.limits.restrictionExitActions??[]},preferences,{variableShares,exitPolicy,trialPreset}),simulation:true,execution_status:'SIMULATED_NOT_ACTUAL_TRADES',watches,period:[calendar[0],calendar.at(-1)],source_limits:input.limits,pending_next_open:intents.filter(e=>e.trigger_date===calendar.at(-1)).length,view_kind:identityScreen?'A_FINITE_IDENTITY_SCREENED_TRIAL_V1':'FROZEN_ORIGINAL_COHORT_FINITE_PROFILE_COMPARISON'};
  results.set(key,result);if(results.size>4)results.delete(results.keys().next().value);return structuredClone(result);
 }
 function simulate(preferences,options){
  return calculate(preferences,options);
 }
 function simulateLatestYear(preferences,options){
  if(preferences.year_scope!=='all')return null;
  const year=input.calendar.at(-1)?.slice(0,4);
  const start=input.calendar.find(day=>day.startsWith(year));
  if(!start||start===input.calendar[0])return null;
  // Start a separate account with the same preferences. No position or missing
  // settlement from the interrupted full-period result enters this calculation.
  return calculate(preferences,options,start);
 }
 function currentPortfolio(preferences,asOf,{exitPolicy=null,trialPreset=null,fullResult=null}={}){
  if(typeof asOf!=='string'||asOf!==input.calendar.at(-1)||asOf!==input.limits?.completeThrough)return null;
  const options={exitPolicy,trialPreset};
  const full=fullResult??simulate(preferences,options);
  if(full.period?.[1]!==asOf)return null;
  if(full.resolved===true)return {result:full,basis:'SAVED_SCOPE'};
  if(full.resolved!==false||preferences.year_scope!=='all')return null;
  const current=simulateLatestYear(preferences,options);
  return current?.resolved===true&&current.period[1]===asOf
   ?{result:current,basis:'LATEST_YEAR_STANDALONE'}:null;
 }
 return {source_version:input.source_version,input,quotes,simulate,simulateLatestYear,currentPortfolio};
}
module.exports={createDatasetRuntime,createQuoteDecoder,validDay};
