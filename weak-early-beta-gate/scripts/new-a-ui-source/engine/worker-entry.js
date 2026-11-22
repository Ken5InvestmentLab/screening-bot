let runtime=null;
let dashboardCloses=null;

function initialize(manifest,quoteChunks){
 runtime=null;
 dashboardCloses=null;
 if(!Array.isArray(quoteChunks)||quoteChunks.length!==manifest.quotes.length)throw Error('quote_chunk_count');
 const quoteMap=new Map(),decoder=new TextDecoder();
 const asOf=manifest.as_of;
 const quoteDecoder=AFiniteDataset.createQuoteDecoder(manifest.quote_fields,manifest.input.calendar,asOf);
 const closes={};
 const hasLatestPrices=typeof asOf==='string'&&asOf===manifest.input.calendar.at(-1)&&asOf===manifest.input.limits?.completeThrough;
 for(const [index,chunk] of quoteChunks.entries()){
  const descriptor=manifest.quotes[index];
  if(chunk.byteLength!==descriptor.bytes)throw Error('quote_chunk_bytes');
  const rows=JSON.parse(decoder.decode(chunk));
  if(!Array.isArray(rows)||rows.length!==descriptor.rows)throw Error('quote_chunk_rows');
  for(const [symbol,day,record] of rows){
   const key=symbol+'|'+day;
   if(quoteMap.has(key))throw Error('quote_duplicate_key');
   const quote=quoteDecoder.normal(symbol,day,record);
   quoteMap.set(key,quote);
   if(hasLatestPrices&&day===asOf&&/^[0-9][0-9A-Z]{3}$/.test(symbol)&&AFiniteEngine.valid(quote,true))closes[symbol]={date:day,price:quote.actual_close};
  }
 }
 if(quoteMap.size!==manifest.expected_quote_keys)throw Error('quote_key_count');
 dashboardCloses={date:asOf,prices:closes};
 runtime=AFiniteDataset.createDatasetRuntime(manifest.input,{get(symbol,day){
  const key=symbol+'|'+day;
  if(!quoteMap.has(key))throw Error('unprepared_quote_key');
  return quoteMap.get(key);
 },scheduledExit:quoteDecoder.scheduledExit,decisionSkipped:quoteDecoder.decisionSkipped});
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
   initialize(message.manifest,message.quoteChunks);
   postMessage({id,ready:true,source_version:runtime.source_version});
  }else if(kind==='source_version'||kind==='simulate'){
   if(!runtime)throw Error('input_not_ready');
   postMessage(kind==='simulate'?simulation(message):{id,source_version:runtime.source_version});
  }else throw Error('request_kind');
 }catch(error){
  postMessage({id,error:error.message==='unprepared_quote_key'?'incomplete_source':'simulation_unavailable'});
 }
};
