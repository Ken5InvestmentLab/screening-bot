/* Isolated extension. Quotes and allocation are supplied only by the owner-gated API. */
(function (global) {
 'use strict';
 const BASE={price_cap_yen:1000,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,year_scope:'all',allocation:'all',initial_cash_yen:10000000,max_positions:20,per_order_cap_yen:500000};
 const TRIAL_PRESETS=Object.freeze({defensive:'守り',balanced:'中間',profit:'利益優先'});
 const validTrial=id=>id===null||typeof id==='string'&&Object.hasOwn(TRIAL_PRESETS,id);
 const trialLabel=policy=>`${TRIAL_PRESETS[policy.id]}｜${policy.exit_sessions}営業日目 寄付／1日新規 ${policy.daily_fill_cap===null?'上限なし':policy.daily_fill_cap+'件'}`;
 const copy=v=>JSON.parse(JSON.stringify(v));
 const canonical=v=>JSON.stringify(Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])));
 function validate(p){
  if(!p||Object.keys(p).length!==Object.keys(BASE).length||Object.keys(BASE).some(k=>!(k in p)))throw Error('設定の項目を確認してください。');
  for(const k of ['initial_cash_yen','per_order_cap_yen'])if(!Number.isSafeInteger(p[k])||p[k]<=0||p[k]>1e12)throw Error('資金は1～1兆円の整数で入力してください。');
  if(!Number.isSafeInteger(p.max_positions)||p.max_positions<1||p.max_positions>1000)throw Error('保有上限は1～1,000銘柄です。');
  if(!Number.isSafeInteger(p.base_shares)||p.base_shares<100||p.base_shares>1e6||p.base_shares%100)throw Error('株数は100株単位で入力してください。');
  const decimal=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max&&/^\d+(?:\.\d{1,2})?$/.test(String(v));
  if(!decimal(p.cost_percent,0,10)||p.price_cap_yen!==null&&!decimal(p.price_cap_yen,.01,1e9))throw Error('株価上限・費用を確認してください。');
  if(!['d5_close','d6_open','a20_close'].includes(p.exit_endpoint)||!['all','2023','2024','2025','2026'].includes(p.year_scope)||!['all','unique','stacked'].includes(p.allocation))throw Error('試算条件を確認してください。');
  return copy(p);
 }
 const key=r=>`${r.symbol}|${r.candidate_date}|${r.episode_id}`;
 const validSaveBinding=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
 function validateView(view){
  if(view==null)return null;
  if(!validTrial(view.trial_preset)||!['dark','light','system'].includes(view.theme)||!['small','standard','large'].includes(view.font_size)||![20,50,100].includes(view.page_size))throw Error('保存した表示設定を確認できません。');
  return {trial_preset:view.trial_preset,theme:view.theme,font_size:view.font_size,page_size:view.page_size};
 }
 function createController({transport,onChange=()=>{},localPreferences=null,localViewPreferences=null,calculateOnLoad=true,trialPreset=null,useTrialPreset=true}){
  if(!validTrial(trialPreset))throw Error('trial_preset_invalid');
  const s={trialPreset,viewPreferences:null,phase:'loading',presence:'unknown',revision:null,applied:null,draft:copy(BASE),accepted:null,dirty:false,edit:0,request:0,message:'設定を読み込んでいます。',defaultProposalVerified:false};
  let committed=null,saveBinding=null;
  const emit=()=>onChange(copy(s));
  async function api(path,method,body){
   const response=await transport(path,{method,credentials:'same-origin',cache:'no-store',headers:{'content-type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
   let data;
   try{data=await response.json();}catch(_){throw Error('応答を確認できません。');}
   if(!response.ok){
    const e=Error(data?.error==='settings_session_changed'?'ログイン状態が変わりました。':response.status===409?'別の画面で設定が更新されました。再読み込みして確認してください。':response.status===401||response.status===403?'認証を確認してください。':method==='PUT'?'設定を保存できませんでした。':'読み込めませんでした。');
    e.status=response.status;e.data=data;throw e;
   }
   return data;
  }
  async function simulation(p,id,selected){
   const d=await api('/api/cloud/new-a-finite/simulate','POST',{preferences:p,request_id:id,...(selected?{trial_preset:selected}:{})});
   if((d.trial_preset??null)!==selected||selected&&(!d.model_result||!Array.isArray(d.model_result.trades)||!Array.isArray(d.model_result.orders)||!Array.isArray(d.model_result.watches)||!d.result?.trial_policy||d.result.trial_policy.id!==selected))throw Error('試算結果を確認できませんでした。');
   if(d.request_id!==id||canonical(validate(d.preferences))!==canonical(p)||typeof d.source_version!=='string'||!d.source_version||typeof d.view_kind!=='string'||!d.result||typeof d.result.resolved!=='boolean'||!Array.isArray(d.result.orders)||!Array.isArray(d.result.trades)||!Array.isArray(d.result.daily)||!Array.isArray(d.result.yearly)||!Array.isArray(d.result.watches))throw Error('試算結果を確認できませんでした。');
   return d;
  }
  function remember(preferences,result,preset,view){
   s.applied=copy(preferences);s.accepted=result;s.trialPreset=preset;s.viewPreferences=view;
   committed={preferences:s.applied,result,preset,view};
  }
  function failed(e){
   s.phase=e.data?.error==='settings_session_changed'?'session-changed':e.status===401||e.status===403?'denied':'error';s.message=e.message;
   if(s.phase==='denied'||s.phase==='session-changed'){
    saveBinding=null;
    s.accepted=null;s.applied=null;s.viewPreferences=null;s.revision=null;s.draft=copy(BASE);s.trialPreset=trialPreset;s.dirty=false;committed=null;
   }
   emit();return false;
  }
  async function load(){
   const token=++s.request;
   s.phase='loading';s.message='設定を読み込んでいます。';emit();
   try{
    const d=await api('/api/cloud/new-a-finite/preferences','GET');
    if(token!==s.request)return false;
    if(d.schema_version!==1||typeof d.has_saved_preferences!=='boolean'||typeof d.has_saved_finite_preferences!=='boolean'||!Number.isSafeInteger(d.revision)||d.revision<0||d.default_proposal_verified!==false||d.has_saved_finite_preferences&&(!d.has_saved_preferences||d.revision===0)||!d.has_saved_finite_preferences&&d.revision!==0)throw Error('保存状態を確認できません。');
    if(!d.has_saved_finite_preferences&&(localPreferences==='unknown'||localViewPreferences==='unknown'))throw Error('以前の設定を確認できません。');
    let p=validate(d.preferences);
    if(!d.has_saved_preferences&&localPreferences)p=validate(localPreferences);
    else if(!d.has_saved_finite_preferences&&localViewPreferences)p=validate({...p,...localViewPreferences});
    const view=validateView(d.view_preferences);
    if(d.save_binding!==undefined&&!validSaveBinding(d.save_binding))throw Error('設定の読み込みを確認できません。');
    const preset=view?view.trial_preset:trialPreset;
    const result=calculateOnLoad?await simulation(p,'load-'+token,useTrialPreset?preset:null):null;
    if(token!==s.request)return false;
    s.presence=d.has_saved_preferences?'saved':'absent';s.revision=d.revision;
    saveBinding=d.save_binding??null;
    remember(p,result,preset,view);
    s.draft=copy(p);s.dirty=false;s.phase='ready';s.message='';
    emit();return true;
   }catch(e){return token===s.request?failed(e):false;}
  }
  function edit(p){s.draft=validate(p);s.edit++;s.dirty=true;s.message='未保存の変更';emit();}
  function reset(){s.draft=copy(BASE);s.edit++;s.dirty=true;s.message='初期値（未保存）';emit();}
  function cancel(){
   if(!committed||s.phase==='denied')return;
   s.draft=copy(committed.preferences);s.accepted=committed.result;s.trialPreset=committed.preset;s.viewPreferences=committed.view;
   s.edit++;s.dirty=false;s.phase='ready';s.message='';emit();
  }
  async function run(save,viewPreferences){
   if(s.revision===null||s.phase==='loading'||s.phase==='saving'||s.phase==='calculating')return false;
   const p=validate(save?s.draft:s.applied),view=validateView(viewPreferences),preset=view?view.trial_preset:s.trialPreset;
   if(save&&view&&!validSaveBinding(saveBinding))return failed(Error('設定を保存できませんでした。再読み込みして確認してください。'));
   const token=++s.request,id=(save?'save-':'preview-')+token;
   s.phase=save?'saving':'calculating';s.message=save?'設定を保存しています。':'試算しています。';emit();
   try{
    const displayOnly=save&&view&&committed&&preset===committed.preset&&canonical(p)===canonical(committed.preferences);
    const d=displayOnly?committed.result:await simulation(p,id,preset);
    if(token!==s.request)return false;
    if(save){
     const receipt=await api('/api/cloud/new-a-finite/preferences','PUT',{preferences:p,expected_revision:s.revision,request_id:id,...(view?{view_preferences:view,save_binding:saveBinding}:{})});
     if(token!==s.request)return false;
     if(receipt.request_id!==id||receipt.schema_version!==1||receipt.has_saved_preferences!==true||receipt.has_saved_finite_preferences!==true||receipt.default_proposal_verified!==false||receipt.revision!==s.revision+1||canonical(validate(receipt.preferences))!==canonical(p)||view&&(!validSaveBinding(receipt.save_binding)||!validateView(receipt.view_preferences)||canonical(validateView(receipt.view_preferences))!==canonical(view)))throw Error('保存結果を確認できません。再読み込みして確認してください。');
     s.revision=receipt.revision;s.presence='saved';
     if(view)saveBinding=receipt.save_binding;
     remember(p,d,preset,view||s.viewPreferences);
     s.dirty=false;s.message='設定を保存しました。';
    }else{
     s.accepted=d;s.message='未保存の変更';
    }
    s.phase='ready';emit();return true;
   }catch(e){return token===s.request?failed(e):false;}
  }
  function setTrialPreset(id){
   if(!validTrial(id))throw Error('trial_preset_invalid');
   if(s.phase==='saving'||s.phase==='calculating')return false;
   s.trialPreset=id;s.dirty=true;s.message='未保存の変更';emit();return true;
  }
  return {load,edit,reset,cancel,setTrialPreset,save:view=>run(true,view),recalculate:()=>run(false),state:()=>copy(s)};
 }
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=v=>v===null||v===undefined?'未確定':Number(v).toLocaleString('ja-JP',{maximumFractionDigits:2});
 const yen=v=>v===null||v===undefined?'未確定':number(v)+'円';
 const pct=v=>v===null||v===undefined?'未確定':number(v*100)+'%';
 const status=v=>({DAILY_FILLED_CAP:'1日新規上限',FILLED:'約定',CAPACITY:'保有上限',LOT_EXCEEDS_ALLOCATION:'注文上限超過',CASH_INSUFFICIENT:'資金不足',DUPLICATE_HELD:'保有中',PRICE_CAP:'株価上限',SIGNAL_PRICE_UNVERIFIED:'株価未確認',UNFILLED:'未約定',UNFILLED_UNCERTAIN_ONE_PRICE:'一値・約定未確認',HALTED_UNRESOLVED:'未解決で停止',IDENTITY_UNVERIFIED:'銘柄対応未確認',TRIGGERED:'支持反発確認',EXPIRED:'監視期限',UP_ESCAPED:'上方離脱',DOWN_INVALIDATED:'下方無効',WATCHING:'監視中'})[v]||v||'未確認';
 function table(columns,rows,id){return `<div class="table-wrap"><table class="scenario-table" data-finite-table="${id}"><thead><tr>${columns.map(c=>`<th>${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>'<tr>'+columns.map(c=>`<td data-label="${esc(c[1])}">${esc(c[2]?c[2](r[c[0]]):r[c[0]])}</td>`).join('')+'</tr>').join('')}</tbody></table></div>`;}
 function exitLabel(endpoint,position,policy){if(endpoint==='a20_close')return '20営業日目 引け';if(endpoint==='d5_close')return '5営業日目 引け';if(!policy?.first_d5_entry_session)return '6営業日目 寄付';if(position?.entry_date)return position.entry_date>=policy.first_d5_entry_session?'5営業日目 寄付':'6営業日目 寄付';return `寄付（${policy.first_d5_entry_session}買付から5営業日目・以前は6営業日目）`;}
 function annualBars(rows){
  const values=rows.filter(r=>Number.isFinite(r.markedNetProfit));
  if(!values.length)return '';
  const max=Math.max(1,...values.map(r=>Math.abs(r.markedNetProfit)));
  return '<ul class="cloud-annual-bars" aria-label="年別の純損益">'+values.map(r=>{
   const v=r.markedNetProfit,width=Math.abs(v)/max*50,left=v<0?50-width:50;
   return '<li><span>'+esc(r.year)+'年</span><span class="cloud-annual-track" aria-hidden="true"><span class="cloud-annual-bar'+(v<0?' loss':'')+'" style="width:'+width+'%;left:'+left+'%"></span></span><strong>'+yen(v)+'</strong></li>';
  }).join('')+'</ul>';
 }
 function render(d){
  if(!d)return '';
  const r=d.result,m=r.metrics,p=d.preferences;
  const cards=[['純損益',yen(m.netProfit)],['勝率',pct(m.winRate)],['最大下落率',pct(m.maxDrawdown)],['決済済み',number(m.closed)+'件']];
  const details=[['元本',yen(m.initialCash)],['期末純資産',yen(m.endEquity)],['必要資金',yen(m.requiredCash)],['確定損益',yen(m.realizedProfit)],['評価損益',yen(m.unrealizedProfit)],['仮想買付',number(m.fills)+'件'],['仮想保有',number(m.open)+'件'],['監視開始',number(r.watches.length)+'件'],['支持反発',number(r.watches.filter(w=>w.trigger_date).length)+'件'],['平均騰落率',m.meanReturnPct==null?'未確定':number(m.meanReturnPct)+'%'],['中央値',m.medianReturnPct==null?'未確定':number(m.medianReturnPct)+'%'],['平均利益',yen(m.averageWinYen)],['平均損失',yen(m.averageLossYen)],['利益合計',yen(m.totalWinYen)],['損失合計',yen(m.totalLossYen)],['未解決',number(m.unresolvedCount)+'件']];
  const stats=details.map(([label,value])=>'<div><dt>'+esc(label)+'</dt><dd>'+value+'</dd></div>').join('');
  const trial=r.trial_policy?trialLabel(r.trial_policy):exitLabel(p.exit_endpoint,null,r.exit_policy);
  const unresolved=!r.resolved?'<p role="status" class="note">試算保留'+(r.unresolved[0]?' · '+esc(r.unresolved[0].date)+'以降の資金推移は未計算':'')+'</p>':'';
  const applied='<dl class="scenario-stats" id="cloud-applied-summary"><div><dt>決済方法</dt><dd>'+esc(trial)+'</dd></div><div><dt>株価上限</dt><dd>'+(p.price_cap_yen===null?'上限なし':yen(p.price_cap_yen))+'</dd></div><div><dt>株数・手数料</dt><dd>'+number(p.base_shares)+'株・片道 '+number(p.cost_percent)+'%</dd></div><div><dt>保有・注文上限</dt><dd>'+number(p.max_positions)+'銘柄・'+yen(p.per_order_cap_yen)+'</dd></div></dl>';
  const badges=Object.entries(r.counts).filter(([,v])=>v).map(([k,v])=>'<span class="badge">'+esc(status(k))+' '+number(v)+'</span>').join(' ');
  return '<section class="panel" aria-labelledby="analytics-overview"><div class="cloud-section-head"><h2 id="analytics-overview">過去成績</h2><div class="cloud-meta"><span class="badge">仮想試算</span><span class="badge">'+esc(r.period?.join(' 〜 ')||'期間未確認')+'</span></div></div>'+
   '<p class="note" id="new-a-trial-summary">'+esc(trial)+'</p>'+unresolved+
   '<div class="kpis">'+cards.map(([label,value])=>'<div class="kpi"><small>'+label+'</small><b>'+value+'</b></div>').join('')+'</div>'+
   '<details class="cloud-kpi-detail"><summary>成績の内訳</summary><dl class="scenario-stats">'+stats+'</dl><div class="cloud-meta">'+badges+'</div></details>'+
   '<details class="cloud-kpi-detail"><summary>適用中の設定</summary>'+applied+'<a href="./weak_early_beta_settings.html">設定を開く</a></details>'+
   '</section><section class="panel" aria-labelledby="analytics-equity"><h2 id="analytics-equity">日次資金推移</h2><div class="cloud-chart" id="new-a-daily-chart"></div><details class="cloud-table-details"><summary>日次表</summary><div id="new-a-daily-table"></div><button id="new-a-daily-more" class="settings-secondary" type="button">次の50営業日</button></details></section>'+
   '<section class="panel" aria-labelledby="analytics-yearly"><h2 id="analytics-yearly">年別純損益</h2>'+annualBars(r.yearly)+'<details class="cloud-table-details"><summary>年次表</summary>'+table([['year','年'],['markedNetProfit','純損益',yen],['fills','仮想買付件数',number]],r.yearly,'yearly')+'</details></section>'+
   '<section class="panel" aria-labelledby="analytics-export"><h2 id="analytics-export">CSV</h2><div class="cloud-meta"><button id="new-a-export-summary" class="settings-secondary" type="button">集計</button><button id="new-a-export-trades" class="settings-secondary" type="button">明細</button><button id="new-a-export-daily" class="settings-secondary" type="button">日次</button></div></section>';
 }
 function renderHoldings(d,{rows=[],calendar=[]}={}){
  const model=d.model_result||d.result,byIdentity=new Map(rows.map(r=>[r.identity,r]));
  const holdings=Object.entries(model.open_positions||{}).sort(([a],[b])=>a.localeCompare(b));
  const display=holdings.map(([symbol,p])=>{
   const row=byIdentity.get(key({...p,symbol})),endpoint=p.exit_endpoint==='d5_open'?'d5_close':d.preferences.exit_endpoint;
   const offset=calendar.indexOf(model.period?.[0]);
   const scheduled=(offset<0?null:calendar[offset+p.exit_i])||(row?.entry?.date===p.entry_date?row.endpoints?.[endpoint]?.date:null);
   return {stock:row?.companyName?row.companyName+' ('+symbol+')':symbol,entry:p.entry_date,exit:scheduled||'未確認'};
  });
  return '<section class="panel" id="new-a-model-holdings"><details class="cloud-table-details"><summary>仮想保有 '+holdings.length+'銘柄</summary><p class="note">モデル決済 · '+esc(model.period?.[1]||'対象日未確認')+'</p>'+(display.length?table([['stock','銘柄'],['entry','仮想買付日'],['exit','仮想決済予定日']],display,'holdings'):'<p>仮想保有なし</p>')+'</details></section>';
 }
 function csv(records){const keys=[...new Set(records.flatMap(Object.keys))];const cell=v=>{const s=v===null||v===undefined?'':typeof v==='object'?JSON.stringify(v):String(v);return '"'+(/^[=+@\-\t\r]/.test(s)&&typeof v!=='number'?"'":'')+s.replaceAll('"','""')+'"';};return '\ufeff'+[keys.map(cell).join(','),...records.map(r=>keys.map(k=>cell(r[k])).join(','))].join('\r\n')+'\r\n';}
 function exportsFor(d,kind,keys=null){if(!d)throw Error('適用済み結果がありません。');const prefix={request_id:d.request_id,source_version:d.source_version,view_kind:d.view_kind,measurement:'過去検証',resolved:d.result.resolved,...d.preferences,...(d.result.exit_policy?{exit_policy:d.result.exit_policy}:{}),...(d.result.trial_policy?{trial_preset:d.trial_preset,trial_policy:d.result.trial_policy}:{})};const orders=new Map(d.result.orders.map(r=>[key(r),r])),trades=new Map(d.result.trades.map(r=>[key(r),r]));let rows=kind==='daily'?d.result.daily:kind==='summary'?[d.result.metrics]:d.result.watches.map(w=>({...w,...orders.get(key(w)),...trades.get(key(w))}));if(keys&&kind==='trades')rows=rows.filter(r=>keys.has(key(r)));return csv(rows.map(r=>({...prefix,...r})));}
 const api={BASE,validate,canonical,key,createController,render,exportsFor,table,esc,number,yen,pct,status,exitLabel,TRIAL_PRESETS,trialLabel,renderHoldings};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;global.AFinite=api;
})(typeof globalThis!=='undefined'?globalThis:this);
