// 凍結済み監視結果からの資金配分。価格や認証を取得せず、検証済み入力だけを受け取る。
'use strict';
const EPS=1e-7;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const near=(a,b)=>Math.abs(a-b)<=1e-12+1e-9*Math.abs(b);
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
 const {daily,orders,trades,open_positions,unresolved}=result,resolved=!unresolved.length;
 const counts={};for(const o of orders)counts[o.status]=(counts[o.status]||0)+1;
 let peak=cash0,dd=0;for(const d of daily){peak=Math.max(peak,d.equity_diagnostic);dd=Math.min(dd,d.equity_diagnostic/peak-1);}
 const end=daily.at(-1)?.equity_diagnostic??cash0,realized=trades.reduce((s,t)=>s+t.profit,0),wins=trades.filter(t=>t.profit>0),losses=trades.filter(t=>t.profit<0),returns=trades.map(t=>t.return*100).sort((a,b)=>a-b);
 const sum=(a,k)=>a.reduce((s,t)=>s+t[k],0),average=(a,k)=>a.length?sum(a,k)/a.length:null;
 let previous=cash0;const yearly=[];
 for(const year of [...new Set(daily.map(d=>d.date.slice(0,4)))]){const days=daily.filter(d=>d.date.startsWith(year)),last=days.at(-1).equity_diagnostic;yearly.push({year:Number(year),markedNetProfit:resolved?last-previous:null,fills:orders.filter(o=>o.status==='FILLED'&&o.order_date.startsWith(year)).length});previous=last;}
 return {resolved,counts,yearly,metrics:{initialCash:cash0,endEquity:resolved?end:null,netProfit:resolved?end-cash0:null,realizedProfit:resolved?realized:null,unrealizedProfit:resolved?end-cash0-realized:null,maxDrawdown:resolved?dd:null,requiredCash:resolved?result.required_cash:null,fills:counts.FILLED||0,closed:trades.length,open:Object.keys(open_positions).length,unresolvedCount:unresolved.length,winRate:resolved&&trades.length?wins.length/trades.length:null,meanReturnPct:resolved?average(trades,'return')===null?null:average(trades,'return')*100:null,medianReturnPct:resolved&&returns.length?(returns[Math.floor((returns.length-1)/2)]+returns[Math.floor(returns.length/2)])/2:null,averageWinYen:resolved?average(wins,'profit'):null,averageLossYen:resolved?average(losses,'profit'):null,totalWinYen:resolved?sum(wins,'profit'):null,totalLossYen:resolved?sum(losses,'profit'):null}};
}
function replay({calendar,intents,quotes},preferences,{variableShares=false}={}){
 const prefs=validatePreferences(preferences),hold=prefs.exit_endpoint==='a20_close'?20:prefs.exit_endpoint==='d5_close'?5:6,timing=prefs.exit_endpoint==='d6_open'?'OPEN':'CLOSE';
 if(!Array.isArray(calendar)||!calendar.length||new Set(calendar).size!==calendar.length||calendar.some((d,i)=>!/^\d{4}-\d{2}-\d{2}$/.test(d)||(i&&d<=calendar[i-1])))throw Error('calendar_invalid');
 const byday=new Map(),index=new Map(calendar.map((d,i)=>[d,i]));
 for(const e of intents){if(!e.symbol||!finite(e.priority_score)||!Number.isSafeInteger(e.episode_id)||!index.has(e.trigger_date)||!index.has(e.candidate_date)||e.candidate_date>e.trigger_date)throw Error('intent_invalid');const ti=index.get(e.trigger_date)+1;if(ti<calendar.length){if(!byday.has(ti))byday.set(ti,[]);byday.get(ti).push(e);}}
 let cash=prefs.initial_cash_yen,minimum=cash;const positions=new Map(),daily=[],orders=[],trades=[],unresolved=[];
 const trouble=(date,symbol,reason)=>unresolved.push({date,symbol,reason});
 for(let i=0;i<calendar.length;i++){
  const dt=calendar[i],pending=[...(byday.get(i)||[])].sort(compare),admitted=[],free=prefs.max_positions-positions.size;
  for(const e of pending){
   const row={...e,order_date:dt,arm:'watch',status:null,entry_cost:null};delete row.trigger_date;
   if(unresolved.length)row.status='HALTED_UNRESOLVED';
   else if(prefs.price_cap_yen!==null&&!valid(quotes.get(e.symbol,e.candidate_date)))row.status='SIGNAL_PRICE_UNVERIFIED';
   else if(prefs.price_cap_yen!==null&&quotes.get(e.symbol,e.candidate_date).actual_close>prefs.price_cap_yen)row.status='PRICE_CAP';
   else if(positions.has(e.symbol))row.status='DUPLICATE_HELD';
   else if(admitted.length>=free)row.status='CAPACITY';else admitted.push(row);
   if(row.status)orders.push(row);
  }
  let budget=cash;
  for(const row of admitted){
   const s=row.symbol,r=quotes.get(s,dt);let price;
   if(valid(r))price=r.open*r.actual_close/r.close;else{const prev=i?quotes.get(s,calendar[i-1]):null;price=valid(prev)?prev.actual_close:Infinity;}
   const qty=variableShares&&Number.isFinite(price)?Math.floor(prefs.per_order_cap_yen/(price*100))*100:prefs.base_shares;
   if(!qty||(!variableShares&&qty*price>prefs.per_order_cap_yen+EPS)){row.status='LOT_EXCEEDS_ALLOCATION';orders.push(row);continue;}
   const cost=qty*price*(1+prefs.cost_percent/100);row.entry_cost=Number.isFinite(cost)?cost:null;
   if(cost>budget+EPS)row.status='CASH_INSUFFICIENT';
   else{
    budget-=cost;
    if(!valid(r,true))row.status='UNFILLED';else if(r.high===r.low)row.status='UNFILLED_UNCERTAIN_ONE_PRICE';
    else{row.status='FILLED';cash-=cost;minimum=Math.min(minimum,cash);positions.set(s,{shares:qty,factor:r.close/r.actual_close,entry_cost:cost,entry_date:dt,entry_price_nominal:price,entry_i:i,exit_i:i+hold-1,candidate_date:row.candidate_date,episode_id:row.episode_id,actions:0,last_mark:cost});}
   }
   orders.push(row);
  }
  let holdings=0,stale=0;
  for(const [s,p]of [...positions]){
   const r=quotes.get(s,dt);
   if(!valid(r))trouble(dt,s,'MISSING_HELD_QUOTE');else{const factor=r.close/r.actual_close,ratio=factor/p.factor;if(!near(ratio,1)){const qty=p.shares*ratio;p.actions++;if(Math.abs(qty-Math.round(qty))>1e-6)trouble(dt,s,'FRACTIONAL_ACTION_NO_SETTLEMENT');p.shares=qty;}p.factor=factor;}
   if(valid(r))p.last_mark=p.shares*r.actual_close;else stale++;
   if(i===p.exit_i){
    if(valid(r,true)&&r.high!==r.low){const price=timing==='OPEN'?r.open*r.actual_close/r.close:r.actual_close,proceeds=p.shares*price*(1-prefs.cost_percent/100);cash+=proceeds;trades.push({symbol:s,...p,scheduled_exit_date:calendar[p.exit_i],actual_exit_timing:timing,delay_market_sessions:0,exit_price_nominal:price,exit_date:dt,proceeds,profit:proceeds-p.entry_cost,return:proceeds/p.entry_cost-1,odd_lot_exit:Math.abs(p.shares/100-Math.round(p.shares/100))>1e-8});positions.delete(s);continue;}
    else trouble(dt,s,'UNRESOLVED_SCHEDULED_EXIT');
   }
   holdings+=p.last_mark;
  }
  if(cash< -1e-6||positions.size>prefs.max_positions)throw Error('account_invariant');
  const equity=cash+holdings;daily.push({date:dt,cash,holdings_value:holdings,equity_diagnostic:equity,positions:positions.size,unresolved:!!unresolved.length,stale_marks:stale,cash_fraction:equity?cash/equity:null});
 }
 const result={daily,orders,trades,unresolved,open_positions:Object.fromEntries(positions),required_cash:prefs.initial_cash_yen-minimum};return {...result,...summarize(result,prefs.initial_cash_yen)};
}
module.exports={valid,validatePreferences,compare,replay,summarize};
