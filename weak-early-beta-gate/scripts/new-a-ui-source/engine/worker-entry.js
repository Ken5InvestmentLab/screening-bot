let runtime=null;
let dashboardCloses=null;

function initialize(manifest,records){
 const quoteMap=new Map(records.map(([symbol,day,quote])=>[
  symbol+'|'+day,
  quote===null?null:Object.fromEntries(manifest.quote_fields.map((field,index)=>[field,quote[index]])),
 ]));
 if(quoteMap.size!==manifest.expected_quote_keys)throw Error('quote_key_count');
 const asOf=manifest.as_of;
 const closes={};
 if(typeof asOf==='string'&&asOf===manifest.input.calendar.at(-1)&&asOf===manifest.input.limits?.completeThrough){
  for(const [symbol,day] of records){
   if(day!==asOf||!/^[0-9][0-9A-Z]{3}$/.test(symbol))continue;
   const quote=quoteMap.get(symbol+'|'+day);
   if(AFiniteEngine.valid(quote,true))closes[symbol]={date:day,price:quote.actual_close};
  }
 }
 dashboardCloses={date:asOf,prices:closes};
 runtime=AFiniteDataset.createDatasetRuntime(manifest.input,{get(symbol,day){
  const key=symbol+'|'+day;
  if(!quoteMap.has(key))throw Error('unprepared_quote_key');
  return quoteMap.get(key);
 }});
}

function simulation(message){
 const {id,request_id,preferences,exit_policy}=message;
 const trialPreset=message.trial_preset??null;
 const options={exitPolicy:exit_policy,trialPreset};
 const result=runtime.simulate(preferences,options);
 const response={id,request_id,preferences,source_version:runtime.source_version,view_kind:result.view_kind,result};
 if(message.dashboard_prices===true&&dashboardCloses?.date)response.dashboard_closes=dashboardCloses;
 if(trialPreset){
  response.trial_preset=trialPreset;
  if(message.dashboard_prices!==true)response.model_result=runtime.simulate(preferences,{exitPolicy:exit_policy});
 }
 if(message.recent_analytics===true&&!result.resolved){
  const recent=runtime.simulateLatestYear(preferences,options);
  if(recent)response.latest_year={period:recent.period,daily:recent.daily,metrics:recent.metrics,
   resolved:recent.resolved,first_unresolved_date:recent.unresolved[0]?.date??null};
 }
 if(message.dashboard_prices===true&&!result.resolved){
  const current=runtime.currentPortfolio(preferences,dashboardCloses?.date,{...options,fullResult:result});
  if(current?.basis==='LATEST_YEAR_STANDALONE')response.dashboard_year=current.result;
 }
 return response;
}

onmessage=event=>{
 const message=event.data,{id,kind}=message;
 try{
  if(kind==='initialize'){
   initialize(message.manifest,message.records);
   postMessage({id,ready:true,source_version:runtime.source_version});
  }else if(kind==='source_version'||kind==='simulate'){
   if(!runtime)throw Error('input_not_ready');
   postMessage(kind==='simulate'?simulation(message):{id,source_version:runtime.source_version});
  }else throw Error('request_kind');
 }catch(error){
  postMessage({id,error:error.message==='unprepared_quote_key'?'incomplete_source':'simulation_unavailable'});
 }
};
