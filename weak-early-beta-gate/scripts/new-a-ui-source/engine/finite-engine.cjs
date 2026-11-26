// 凍結済み監視結果からの資金配分。価格や認証を取得せず、検証済み入力だけを受け取る。
'use strict';
const EPS=1e-7;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const near=(a,b)=>Math.abs(a-b)<=1e-12+1e-9*Math.abs(b);
// Keep the saved d6_open key; only model entries from this session use D5 OPEN.
const OPEN_EXIT_POLICY_VERSION='A_OPEN_EXIT_V2';
function validateExitPolicy(value){
 if(value===null||value===undefined)return null;
 if(typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==4||value.version!==OPEN_EXIT_POLICY_VERSION||!/^\d{4}-\d{2}-\d{2}$/.test(value.first_d5_entry_session)||value.legacy_endpoint!=='d6_open'||value.new_endpoint!=='d5_open')throw Error('exit_policy_invalid');
 return {...value};
}
function exitTerms(endpoint,entryDate,policy=null){
 if(endpoint==='d6_open'){const fresh=policy&&entryDate>=policy.first_d5_entry_session;return {sessions:fresh?5:6,timing:'OPEN',endpoint:fresh?'d5_open':'d6_open'};}
 return {sessions:endpoint==='d5_close'?5:20,timing:'CLOSE',endpoint};
}
const TRIAL_PRESETS=Object.freeze({defensive:Object.freeze({id:'defensive',exit_sessions:5,daily_fill_cap:3}),balanced:Object.freeze({id:'balanced',exit_sessions:5,daily_fill_cap:null}),profit:Object.freeze({id:'profit',exit_sessions:8,daily_fill_cap:3})});
function trialTerms(id){if(id===null||id===undefined)return null;if(typeof id!=='string'||!Object.hasOwn(TRIAL_PRESETS,id))throw Error('trial_preset_invalid');return {...TRIAL_PRESETS[id]};}
function valid(r,volume=false){return !!r&&['open','high','low','close','actual_close'].every(k=>finite(r[k])&&r[k]>0)&&[true,1,'true','1'].includes(r.source_usable)&&r.low<=Math.min(r.open,r.close)&&Math.max(r.open,r.close)<=r.high&&(!volume||(r.volume>0&&r.actual_volume>0));}
function validatePreferences(p){
 if(!p||typeof p!=='object'||Array.isArray(p))throw Error('preferences_object_required');
 const keys=['initial_cash_yen','max_positions','per_order_cap_yen','base_shares','cost_percent','price_cap_yen','exit_endpoint','year_scope','allocation'];
 if(Object.keys(p).some(k=>!keys.includes(k))||keys.some(k=>!(k in p)))throw Error('preferences_fields');
 for(const k of ['initial_cash_yen','per_order_cap_yen'])if(!Number.isSafeInteger(p[k])||p[k]<=0||p[k]>1e12)throw Error(k);
 if(!Number.isSafeInteger(p.max_positions)||p.max_positions<1||p.max_positions>1000)throw Error('max_positions');
 if(!Number.isSafeInteger(p.base_shares)||p.base_shares<100||p.base_shares>1e6||p.base_shares%100)throw Error('base_shares');
 if(!finite(p.cost_percent)||p.cost_percent<0||p.cost_percent>10||!/^\d+(?:\.\d{1,2})?$/.test(String(p.cost_percent)))throw Error('cost_percent');
 if(p.price_cap_yen!==null&&(!finite(p.price_cap_yen)||p.price_cap_yen<=0||p.price_cap_yen>1e9||!/^\d+(?:\.\d{1,2})?$/.test(String(p.price_cap_yen))))throw Error('price_cap_yen');
 if(!['d5_close','d6_open','a20_close'].includes(p.exit_endpoint))throw Error('exit_endpoint');
 if(!['all','2023','2024','2025','2026'].includes(p.year_scope))throw Error('year_scope');
 if(!['all','unique','stacked'].includes(p.allocation))throw Error('allocation');
 return {...p};
}
function compare(a,b){return a.candidate_date.localeCompare(b.candidate_date)||b.priority_score-a.priority_score||a.symbol.localeCompare(b.symbol,'en')||a.episode_id-b.episode_id;}
function summarize(result,cash0){
 const {daily,orders,trades,open_positions,unresolved}=result;
 const last=daily.at(-1),resolved=!unresolved.length&&(!last||!last.unresolved&&finite(last.equity_diagnostic));
 const counts={};for(const o of orders)counts[o.status]=(counts[o.status]||0)+1;
 let peak=cash0,dd=0;
 for(const d of daily){
  if(d.unresolved||!finite(d.equity_diagnostic))continue;
  peak=Math.max(peak,d.equity_diagnostic);dd=Math.min(dd,d.equity_diagnostic/peak-1);
 }
 const end=last?.equity_diagnostic??cash0,realized=trades.reduce((s,t)=>s+t.profit,0),wins=trades.filter(t=>t.profit>0),losses=trades.filter(t=>t.profit<0),returns=trades.map(t=>t.return*100).sort((a,b)=>a-b);
 const sum=(a,k)=>a.reduce((s,t)=>s+t[k],0),average=(a,k)=>a.length?sum(a,k)/a.length:null;
 let previous=cash0;const yearly=[];
 for(const year of [...new Set(daily.map(d=>d.date.slice(0,4)))]){
  const lastDay=daily.filter(d=>d.date.startsWith(year)).at(-1);
  const last=lastDay.unresolved?null:lastDay.equity_diagnostic;
  yearly.push({year:Number(year),markedNetProfit:resolved&&finite(last)&&finite(previous)?last-previous:null,fills:orders.filter(o=>o.status==='FILLED'&&o.order_date.startsWith(year)).length});previous=last;
 }
 return {resolved,counts,yearly,metrics:{initialCash:cash0,endEquity:resolved?end:null,netProfit:resolved?end-cash0:null,realizedProfit:resolved?realized:null,unrealizedProfit:resolved?end-cash0-realized:null,maxDrawdown:resolved?dd:null,requiredCash:resolved?result.required_cash:null,fills:counts.FILLED||0,closed:trades.length,open:Object.keys(open_positions).length,unresolvedCount:unresolved.length,winRate:resolved&&trades.length?wins.length/trades.length:null,meanReturnPct:resolved?average(trades,'return')===null?null:average(trades,'return')*100:null,medianReturnPct:resolved&&returns.length?(returns[Math.floor((returns.length-1)/2)]+returns[Math.floor(returns.length/2)])/2:null,averageWinYen:resolved?average(wins,'profit'):null,averageLossYen:resolved?average(losses,'profit'):null,totalWinYen:resolved?sum(wins,'profit'):null,totalLossYen:resolved?sum(losses,'profit'):null}};
}
function replay({calendar,intents,quotes,restrictionExits=[]},preferences,{variableShares=false,exitPolicy=null,trialPreset=null}={}){
 const prefs=validatePreferences(preferences),policy=validateExitPolicy(exitPolicy),trial=trialTerms(trialPreset),timing=trial?'OPEN':prefs.exit_endpoint==='d6_open'?'OPEN':'CLOSE';
 if(!Array.isArray(calendar)||!calendar.length||new Set(calendar).size!==calendar.length||calendar.some((d,i)=>!/^\d{4}-\d{2}-\d{2}$/.test(d)||(i&&d<=calendar[i-1])))throw Error('calendar_invalid');
 if(!Array.isArray(restrictionExits)||restrictionExits.some(r=>!r||!/^[0-9A-Z]{4}$/.test(r.symbol)||!/^\d{4}-\d{2}-\d{2}$/.test(r.confirmed_on)||!/^\d{4}-\d{2}-\d{2}$/.test(r.exit_date)||r.exit_date<=r.confirmed_on||!['整理銘柄入り','上場廃止決定'].includes(r.reason)))throw Error('restriction_exit_invalid');
 const forcedRules=restrictionExits.slice().sort((a,b)=>a.confirmed_on.localeCompare(b.confirmed_on));
 const byday=new Map(),index=new Map(calendar.map((d,i)=>[d,i]));
 for(const e of intents){if(!e.symbol||!finite(e.priority_score)||!Number.isSafeInteger(e.episode_id)||!index.has(e.trigger_date)||!index.has(e.candidate_date)||e.candidate_date>e.trigger_date)throw Error('intent_invalid');const ti=index.get(e.trigger_date)+1;if(ti<calendar.length){if(!byday.has(ti))byday.set(ti,[]);byday.get(ti).push(e);}}
 let cash=prefs.initial_cash_yen,minimum=cash;const positions=new Map(),daily=[],orders=[],trades=[],unresolved=[];
 const trouble=(date,symbol,reason)=>unresolved.push({date,symbol,reason});
 const scheduledExits=new Map();
 const supportsLateExit=trial!==null&&typeof quotes.scheduledExit==='function';
 const supportsSkippedMark=trial!==null&&typeof quotes.decisionSkipped==='function';
 function retainLateExit(symbol,date){
  if(!supportsLateExit)return;
  const receipt=quotes.scheduledExit(symbol,date);
  if(receipt&&finite(receipt.open)&&receipt.open>0&&finite(receipt.factor)&&receipt.factor>0
    &&typeof receipt.observed_after==='string'&&receipt.observed_after>date&&index.has(receipt.observed_after)){
   scheduledExits.set(symbol,{open:receipt.open,factor:receipt.factor,observed_after:receipt.observed_after});
  }
 }
 function updateShares(symbol,position,factor,date){
  const ratio=factor/position.factor;
  if(!near(ratio,1)){
   const quantity=position.shares*ratio;
   position.actions++;
   if(Math.abs(quantity-Math.round(quantity))>1e-6)trouble(date,symbol,'FRACTIONAL_ACTION_NO_SETTLEMENT');
   position.shares=quantity;
  }
  position.factor=factor;
 }
 function settle(symbol,position,price,details={}){
  const date=calendar[position.exit_i];
  const proceeds=position.shares*price*(1-prefs.cost_percent/100);
  cash+=proceeds;
  trades.push({symbol,...position,scheduled_exit_date:date,actual_exit_timing:position.forced_exit_reason?'OPEN':timing,delay_market_sessions:0,exit_price_nominal:price,exit_date:date,proceeds,profit:proceeds-position.entry_cost,return:proceeds/position.entry_cost-1,odd_lot_exit:Math.abs(position.shares/100-Math.round(position.shares/100))>1e-8,...details});
  positions.delete(symbol);
 }
 function handleScheduledExit(symbol,position,date,quote){
  if(valid(quote,true)&&quote.high!==quote.low){
   const price=(position.forced_exit_reason||timing==='OPEN')?quote.open*quote.actual_close/quote.close:quote.actual_close;
   settle(symbol,position,price);
   return true;
  }
  trouble(date,symbol,'UNRESOLVED_SCHEDULED_EXIT');
  retainLateExit(symbol,date);
  return false;
 }
 function resolveObservedExits(date){
  for(const [symbol,receipt] of scheduledExits){
   if(receipt.observed_after!==date)continue;
   scheduledExits.delete(symbol);
   const position=positions.get(symbol);
   const scheduledDate=calendar[position.exit_i];
   const ratio=receipt.factor/position.factor;
   const quantity=near(ratio,1)?position.shares:position.shares*ratio;
   if(!finite(quantity)||quantity<=0||Math.abs(quantity-Math.round(quantity))>1e-6){
    trouble(scheduledDate,symbol,'FRACTIONAL_ACTION_NO_SETTLEMENT');
    continue;
   }
   updateShares(symbol,position,receipt.factor,scheduledDate);
   settle(symbol,position,receipt.open,{settlement_observed_after:date});
   for(let at=unresolved.length-1;at>=0;at--){
    const issue=unresolved[at];
    if(issue.date===scheduledDate&&issue.symbol===symbol
       &&['MISSING_HELD_QUOTE','UNRESOLVED_SCHEDULED_EXIT'].includes(issue.reason))unresolved.splice(at,1);
   }
  }
 }
 function recordUnresolvedDay(date){
  daily.push({date,cash:null,holdings_value:null,equity_diagnostic:null,positions:positions.size,unresolved:true,stale_marks:null,cash_fraction:null});
 }
 for(let i=0;i<calendar.length;i++){
  const dt=calendar[i],pending=[...(byday.get(i)||[])].sort(compare),admitted=[],free=prefs.max_positions-positions.size;
  for(const e of pending){
   const row={...e,order_date:dt,arm:'watch',status:null,entry_cost:null};delete row.trigger_date;
   if(forcedRules.some(r=>r.symbol===e.symbol&&dt>r.confirmed_on))row.status='VERIFIED_RESTRICTED';
   else if(unresolved.length)row.status='HALTED_UNRESOLVED';
   else if(prefs.price_cap_yen!==null&&!valid(quotes.get(e.symbol,e.candidate_date)))row.status='SIGNAL_PRICE_UNVERIFIED';
   else if(prefs.price_cap_yen!==null&&quotes.get(e.symbol,e.candidate_date).actual_close>prefs.price_cap_yen)row.status='PRICE_CAP';
   else if(positions.has(e.symbol))row.status='DUPLICATE_HELD';
   else if(admitted.length>=free)row.status='CAPACITY';else admitted.push(row);
   if(row.status)orders.push(row);
  }
  if(trial&&unresolved.length){
   if(scheduledExits.size){
    // Orders for this session already used the state known at its open.
    // Existing positions still have their own fixed settlement dates.
    for(const [symbol,position] of positions){
     if(i!==position.exit_i)continue;
     const quote=quotes.get(symbol,dt);
     if(valid(quote)){
      updateShares(symbol,position,quote.close/quote.actual_close,dt);
      position.last_mark=position.shares*quote.actual_close;
     }else trouble(dt,symbol,'MISSING_HELD_QUOTE');
     handleScheduledExit(symbol,position,dt,quote);
    }
    resolveObservedExits(dt);
   }
   if(unresolved.length){recordUnresolvedDay(dt);continue;}
  }
  let budget=cash,filledToday=0;
  for(const row of admitted){
   if(trial&&trial.daily_fill_cap!==null&&filledToday>=trial.daily_fill_cap){row.status='DAILY_FILLED_CAP';orders.push(row);continue;}
   const s=row.symbol,r=quotes.get(s,dt);let price;
   if(valid(r))price=r.open*r.actual_close/r.close;else{const prev=i?quotes.get(s,calendar[i-1]):null;price=valid(prev)?prev.actual_close:Infinity;}
   const qty=variableShares&&Number.isFinite(price)?Math.floor(prefs.per_order_cap_yen/(price*100))*100:prefs.base_shares;
   if(!qty||(!variableShares&&qty*price>prefs.per_order_cap_yen+EPS)){row.status='LOT_EXCEEDS_ALLOCATION';orders.push(row);continue;}
   const cost=qty*price*(1+prefs.cost_percent/100);row.entry_cost=Number.isFinite(cost)?cost:null;
   if(cost>budget+EPS)row.status='CASH_INSUFFICIENT';
   else{
    budget-=cost;
    if(!valid(r,true))row.status='UNFILLED';else if(r.high===r.low)row.status='UNFILLED_UNCERTAIN_ONE_PRICE';
    else{row.status='FILLED';filledToday++;cash-=cost;minimum=Math.min(minimum,cash);const exit=trial?{sessions:trial.exit_sessions,timing:'OPEN',endpoint:'trial_open'}:exitTerms(prefs.exit_endpoint,dt,policy),position={shares:qty,factor:r.close/r.actual_close,entry_cost:cost,entry_date:dt,entry_price_nominal:price,entry_i:i,exit_i:i+exit.sessions-1,candidate_date:row.candidate_date,episode_id:row.episode_id,actions:0,last_mark:cost};if(!trial&&prefs.exit_endpoint==='d6_open'&&exit.endpoint==='d5_open')Object.assign(position,{exit_endpoint:'d5_open',exit_policy_version:OPEN_EXIT_POLICY_VERSION});positions.set(s,position);}
   }
   orders.push(row);
  }
  for(const [symbol,position] of positions){
   const rule=forcedRules.find(r=>r.symbol===symbol&&r.confirmed_on<=dt&&r.confirmed_on>=position.entry_date);
   if(!rule)continue;
   const due=index.get(rule.confirmed_on)+1;
   if(index.has(rule.confirmed_on)&&due<=position.exit_i){
    if(due<calendar.length&&calendar[due]!==rule.exit_date)throw Error('restriction_exit_calendar_mismatch');
    position.exit_i=due;position.exit_reason='RESTRICTED_FORCED_EXIT';position.forced_exit_reason=rule.reason;position.restriction_confirmed_on=rule.confirmed_on;
   }
  }
  let holdings=0,stale=0,skippedMark=false;
  for(const [s,p]of [...positions]){
   const r=quotes.get(s,dt);
   if(valid(r)){
    updateShares(s,p,r.close/r.actual_close,dt);
    p.last_mark=p.shares*r.actual_close;
   }else{
    if(supportsSkippedMark&&r===null&&i<p.exit_i&&quotes.decisionSkipped(s,dt)===true)skippedMark=true;
    else trouble(dt,s,'MISSING_HELD_QUOTE');
    stale++;
   }
   if(i===p.exit_i&&handleScheduledExit(s,p,dt,r))continue;
   holdings+=p.last_mark;
  }
  if(cash< -1e-6||positions.size>prefs.max_positions)throw Error('account_invariant');
  if(skippedMark||scheduledExits.size){recordUnresolvedDay(dt);continue;}
  const equity=cash+holdings;daily.push({date:dt,cash,holdings_value:holdings,equity_diagnostic:equity,positions:positions.size,unresolved:!!unresolved.length,stale_marks:stale,cash_fraction:equity?cash/equity:null});
 }
 const result={daily,orders,trades,unresolved,open_positions:Object.fromEntries(positions),required_cash:prefs.initial_cash_yen-minimum},output={...result,...summarize(result,prefs.initial_cash_yen)};if(trial)output.trial_policy={...trial,purchase_day_is_one:true,timing:'OPEN',execution_status:'ANALYTICS_SIMULATION_ONLY'};else if(prefs.exit_endpoint==='d6_open'&&policy)output.exit_policy=policy;return output;
}
module.exports={valid,validatePreferences,compare,replay,summarize,exitTerms,validateExitPolicy,OPEN_EXIT_POLICY_VERSION,trialTerms,TRIAL_PRESETS};
