/* Bind the owner-only frame to its calculation, history and account settings. */
(function(){
 'use strict';
 const page=document.body.dataset.page, isHome=page==='home', isAnalytics=page==='analytics';
 const app=globalThis.AFinite,legacy=globalThis.AFiniteLegacy;
 if(!app||!legacy)return;
 const byId=id=>document.getElementById(id);
 const content=byId('cloud-analytics-content');
 const settings=byId('cloud-settings-page');
 const settingsLinks=settings?[...document.querySelectorAll('.topbar .nav a[href]')]:[];
 const rows=Array.from(document.querySelectorAll('#detection-table tbody tr[data-date]'));
 const fields={initial_cash_yen:'new-a-initial-cash',max_positions:'new-a-max-positions',per_order_cap_yen:'new-a-per-order-cap',base_shares:'cloud-base-shares',cost_percent:'cloud-cost-percent',exit_endpoint:'cloud-exit-endpoint',year_scope:'cloud-year-scope',allocation:'cloud-allocation'};
 let drawn=null,displayKey,history=new Map(),dailyLimit=50,latest=null,settingsSaving=false;
 const busy=s=>['loading','saving','calculating'].includes(s.phase);
 const trial=()=>byId('new-a-trial-preset').value;
 const defaultPrefs=legacy.initialDisplay();
 function readTrial(){
  const values={};
  for(const [key,id] of Object.entries(fields)){
   const field=byId(id);
   if(!field.value)throw Error('空欄を入力してください。');
   values[key]=field.type==='number'?field.valueAsNumber:field.value;
  }
  const preset=byId('cloud-price-preset').value;
  values.price_cap_yen=preset==='unlimited'?null:preset==='custom'?byId('cloud-price-custom').valueAsNumber:Number(preset);
  return app.validate(values);
 }
 function readView(){
  return {trial_preset:trial()==='custom'?null:trial(),theme:byId('cloud-theme').value,font_size:byId('cloud-font-size').value,page_size:Number(byId('cloud-page-size').value)};
 }
 function syncPriceControl(){
  const custom=byId('cloud-price-preset').value==='custom';
  byId('cloud-price-custom-field').hidden=!custom;
  byId('cloud-price-custom').disabled=!custom;
 }
 function syncExitControl(){
  const active=trial()==='custom';
  const field=byId('cloud-exit-endpoint');
  field.closest('label').hidden=!active;
  field.disabled=!active;
 }
 function syncTrial(p,preset){
  for(const [key,id] of Object.entries(fields))byId(id).value=String(p[key]);
  const cap=p.price_cap_yen;
  byId('cloud-price-preset').value=cap===null?'unlimited':[1000,2000,3000,5000].includes(cap)?String(cap):'custom';
  byId('cloud-price-custom').value=cap===null?'':String(cap);
  byId('new-a-trial-preset').value=preset??'custom';
  syncPriceControl();
  syncExitControl();
 }
 function syncDisplay(v){
  byId('cloud-theme').value=v?.theme??defaultPrefs.theme;
  byId('cloud-font-size').value=v?.font_size??defaultPrefs.fontSize;
  byId('cloud-page-size').value=String(v?.page_size??defaultPrefs.pageSize);
 }
 function setSettingsStatus(text,error=false){
  const status=byId('cloud-settings-status');
  status.textContent=text;
  status.dataset.state=error?'error':'';
 }
 function confirmLeaveWhileSaving(event){
  event.preventDefault();
  event.returnValue=true;
 }
 function blockSettingsNavigation(event){
  if(settingsLinks.includes(event.target.closest?.('a[href]')))event.preventDefault();
 }
 function setSettingsSaving(saving){
  if(settingsSaving===saving)return;
  settingsSaving=saving;
  for(const link of settingsLinks){
   if(saving)link.setAttribute('aria-disabled','true');
   else link.removeAttribute('aria-disabled');
  }
  if(saving){
   document.addEventListener('click',blockSettingsNavigation,true);
   window.addEventListener('beforeunload',confirmLeaveWhileSaving);
   byId('cloud-settings-status').focus({preventScroll:true});
  }else{
   document.removeEventListener('click',blockSettingsNavigation,true);
   window.removeEventListener('beforeunload',confirmLeaveWhileSaving);
  }
 }
 function refCell(date,price,status){
  if(!date||!price)return '—';
  return app.esc(date)+'<small>'+app.yen(Number(price))+' · '+(status==='reference_price_only'?'価格のみ参照':'参照')+'</small>';
 }
 function rowMarkup(row,record){
  const d=row.dataset, {w,o,t,open,source}=record||{}, pos=t||open;
  const chartAllowed=d.aChartAllowed!=='false';
  const name=app.esc(d.name),code=app.esc(d.symbol);
  const url='https://jp.tradingview.com/chart/?symbol=TSE%3A'+encodeURIComponent(d.symbol);
  const chart=chartAllowed?'<a class="button-link cloud-stock-action" href="'+url+'" target="_blank" rel="noopener noreferrer">チャート</a>':'<span class="button-link" aria-disabled="true">チャート保留</span>';
  const fundamental=globalThis.ANewPresentation?.fundamentalMarkup(source);
  const entry=pos?app.esc(pos.entry_date)+'<small>寄付 '+app.yen(pos.entry_price_nominal)+'</small><small>'+app.number(pos.shares)+'株 · '+app.yen(pos.entry_cost)+'</small>':'—';
  const simulated=w&&w.selection_reason===null&&latest?.applied;
  const exit=simulated?(historyTrialPolicy?app.trialLabel(historyTrialPolicy):app.exitLabel(latest.applied.exit_endpoint,pos,historyExitPolicy)):'';
  const result=t?'<strong>'+app.yen(t.profit)+'</strong><small>'+app.pct(t.return)+'</small>':open?'<strong>仮想保有中</strong>':'—';
  const exitDetails=t?'<small>決済 '+app.esc(t.exit_date)+' · '+app.yen(t.exit_price_nominal)+'</small>':'';
  const close=d.signalActualClose?'<small>検出日終値 '+app.yen(Number(d.signalActualClose))+'</small>':'<small>検出日終値 未確認</small>';
  const state=w?.selection_reason||o?.status||w?.watch_status||d.aStatusLabel;
  return '<td colspan="8" class="history-record"><div class="history-visible-grid">'+
   '<div class="history-date" data-label="検出日"><div class="history-date-value">'+app.esc(d.date)+'</div><div class="actions history-date-actions">'+(fundamental||'')+chart+'</div></div>'+
   '<div class="history-company"><strong><span class="symbol">'+code+'</span> '+name+'</strong>'+close+(chartAllowed?'':'<small>当時の銘柄名を確認中</small>')+'</div>'+
   '<div data-label="状況"><span class="status pending">'+app.esc(state==='FILLED'?(t?'仮想決済済':'仮想保有中'):app.status(state))+'</span></div>'+
   '<div data-label="試算条件"><small>'+(simulated?app.number(pos?.shares??latest.applied.base_shares)+'株で試算':'—')+'</small></div>'+
   '<div data-label="試算開始日・始値">'+entry+'</div>'+
   '<div data-label="5営業日後 終値">'+refCell(d.d5Date,d.d5Close,d.aD5Status)+'</div>'+
   '<div data-label="6営業日後 始値">'+refCell(d.d6Date,d.d6Open,d.aD6Status)+'</div>'+
   '<div data-label="成績" class="number cloud-history-result">'+result+(exit?'<div class="cloud-exit-details"><small>'+app.esc(exit)+'</small>'+exitDetails+'</div>':'')+'</div></div>'+
   '<button type="button" class="history-mobile-toggle" data-cloud-history-details aria-expanded="false">詳細を見る</button></td>';
 }
 let historyExitPolicy=null,historyTrialPolicy=null;
 function rebuildHistory(model){
  historyExitPolicy=model?.exit_policy;
  historyTrialPolicy=model?.trial_policy;
  history=app.historyRecords(globalThis.AOwnerPageData.rows,model);
  for(const row of rows){row.dataset.finiteHydrate='pending';row.replaceChildren();}
  hydrateVisible();
 }
 function showHistory(){
  const tbody=document.querySelector('#detection-table tbody');
  if(tbody)tbody.hidden=false;
  const section=byId('history');
  section.hidden=false;
  byId('new-a-history-jump').hidden=false;
  if(location.hash==='#history')section.scrollIntoView();
 }
 function hydrateVisible(){
  for(const row of rows)if(!row.hidden&&row.dataset.finiteHydrate==='pending'){
   row.innerHTML=rowMarkup(row,history.get(row.dataset.aIdentity));
   row.dataset.finiteHydrate='done';
  }
 }
 function equityChart(list,resolved){
  const points=list.filter(d=>Number.isFinite(d.equity_diagnostic));
  if(!points.length)return '<p>日次値なし</p>';
  const values=points.map(d=>d.equity_diagnostic),lo=Math.min(...values),hi=Math.max(...values);
  const x=i=>132+i/Math.max(1,points.length-1)*694,y=v=>hi===lo?145:240-(v-lo)/(hi-lo)*190;
  const line=points.map((d,i)=>(i?'L':'M')+x(i).toFixed(2)+' '+y(d.equity_diagnostic).toFixed(2)).join(' ');
  const label=resolved?'純資産（円）':'純資産の診断値（円）';
  const ticks=hi===lo?'<text x="122" y="151" text-anchor="end" class="axis-label">'+app.number(hi)+'</text>':'<text x="122" y="55" text-anchor="end" class="axis-label">'+app.number(hi)+'</text><text x="122" y="246" text-anchor="end" class="axis-label">'+app.number(lo)+'</text>';
  return '<svg class="scenario-chart cloud-equity-chart" viewBox="0 0 870 308" role="img" aria-label="'+label+'の日次推移"><title>'+label+'の日次推移</title>'+
   '<text x="132" y="25" class="axis-label">'+label+'</text><path d="M132 49H826M132 242H826" fill="none" stroke="var(--line)"/>'+
   ticks+
   '<path class="equity-line" d="'+line+'" style="stroke:var(--blue)"/><circle cx="'+x(points.length-1)+'" cy="'+y(values.at(-1))+'" r="4" fill="var(--blue)"/>'+
   '<text x="132" y="284" class="axis-label">'+app.esc(points[0].date)+'</text><text x="826" y="284" text-anchor="end" class="axis-label">'+app.esc(points.at(-1).date)+'</text></svg>';
 }
 function drawDaily(result){
  const data=result.daily;
  byId('new-a-daily-table').innerHTML=app.table([['date','日付'],['cash','現金',app.yen],['holdings_value','保有評価',app.yen],['equity_diagnostic',result.resolved?'純資産':'純資産（診断値）',app.yen],['positions','保有数',app.number],['unresolved','状態',v=>v?'保留':'確定']],data.slice(0,dailyLimit),'daily');
  byId('new-a-daily-more').hidden=dailyLimit>=data.length;
 }
 function clearPrivateDisplay(){
  globalThis.AFiniteRevoked=true;
  globalThis.AOwnerPageData=null;
  globalThis.AFiniteBrowser?.clear();
  history.clear();
  if(isHome)byId('new-a-history-jump').hidden=true;
  legacy.clearHistory();
  rows.length=0;
  for(const id of ['new-a-dashboard','new-a-model-holdings','cloud-analytics-content','history','cloud-settings-page','new-a-notification-settings']){
   const node=byId(id);
   if(node){node.replaceChildren();node.hidden=true;}
  }
 }
 function update(state){
  latest=state;
  const working=busy(state);
  const key=JSON.stringify(state.viewPreferences);
  if(state.revision!==null&&key!==displayKey){
   legacy.applyAccountDisplay(state.viewPreferences);
   displayKey=key;
  }
  if(settings){
   for(const control of settings.querySelectorAll('select,input,button'))control.disabled=working||state.revision===null;
   if(!working&&state.revision!==null){
    if(!state.dirty){syncTrial(state.draft,state.trialPreset);syncDisplay(state.viewPreferences);}
    syncPriceControl();syncExitControl();
   }
   setSettingsStatus(state.message,state.phase==='error'||state.phase==='denied');
   setSettingsSaving(state.phase==='saving');
  }
  content?.setAttribute('aria-busy',String(working));
  if(state.phase==='denied'||state.phase==='session-changed'){
   clearPrivateDisplay();
   const message=state.phase==='session-changed'?'ログイン状態が変わりました。':'認証を確認できませんでした。';
   globalThis.AOwnerLoadStatus?.(message,()=>location.reload());
   return;
  }
  if(state.phase==='error'){
   if(content&&!state.accepted)content.hidden=true;
   if(isHome&&!state.accepted)globalThis.AOwnerPageData?.renderDashboard?.({});
   if(!settings||state.revision===null){
    const message=isAnalytics?(state.accepted?'過去成績を更新できませんでした。':'過去成績を読み込めませんでした。'):isHome?'監視対象と仮想保有を確認できませんでした。':'設定を読み込めませんでした。';
    globalThis.AOwnerLoadStatus?.(message,()=>{
     globalThis.AOwnerLoadStatus?.('読み込んでいます。');
     controller.load();
    });
   }
   return;
  }
  if(state.phase==='ready'){
   globalThis.AOwnerLoadStatus?.('');
   if(content)content.hidden=false;
  }
  if(!state.accepted||drawn===state.accepted.request_id)return;
  const simulation=state.accepted;
  drawn=simulation.request_id;
  if(isAnalytics){
   content.innerHTML=app.render(simulation);
   byId('new-a-daily-chart').innerHTML=equityChart(simulation.result.daily,simulation.result.resolved);
   const recentChart=byId('new-a-latest-year-chart');
   if(recentChart&&simulation.latest_year)recentChart.innerHTML=equityChart(simulation.latest_year.daily,simulation.latest_year.resolved);
   dailyLimit=50;
   drawDaily(simulation.result);
  }
  if(isHome){
   byId('new-a-model-holdings')?.remove();
   const data=globalThis.AOwnerPageData;
   const current=data.current?.[0];
   const asOf=current?.as_of;
   const sameDate=Boolean(asOf&&simulation.dashboard_closes?.date===asOf);
   const dashboardYear=sameDate&&simulation.dashboard_year?.period[1]===asOf?simulation.dashboard_year:null;
   const model=sameDate?(dashboardYear||simulation.result):null;
   const currentModel=model?.period?.[1]===asOf?model:null;
   const preparedCloses=simulation.dashboard_closes;
   const watchSelection=sameDate?simulation.result.watches:null;
   data.renderDashboard?.({model:currentModel,preparedCloses,dashboardYear,watchSelection});
   const presentation=globalThis.AOwnerPresentation;
   const details=current&&presentation.stockDetails(current,data.rows,globalThis.ANewPresentation,currentModel,preparedCloses,dashboardYear);
   const performance=current&&presentation.holdingPerformance(current,data.rows,globalThis.ANewPresentation,preparedCloses);
   const holdings=app.renderHoldings(simulation,{rows:data.rows,calendar:data.manifest.input_header.calendar,details,performance,model,asOf});
   const events=byId('new-a-current');
   if(events)events.insertAdjacentHTML('afterend',holdings);
   else byId('new-a-dashboard').insertAdjacentHTML('beforeend',holdings);
   rebuildHistory(simulation.result);
  }
 }
 const controller=app.createController({trialPreset:'balanced',recentAnalytics:isAnalytics,dashboardPrices:isHome,transport:globalThis.AFiniteTransport,onChange:update,calculateOnLoad:isAnalytics||isHome});
 globalThis.AFiniteUIController=controller;

 if(settings){
  const tabs=[...settings.querySelectorAll('[role="tab"]')];
  const switchTab=tab=>{
   for(const item of tabs){
    const selected=item===tab;
    item.tabIndex=selected?0:-1;
    item.setAttribute('aria-selected',String(selected));
    byId(item.getAttribute('aria-controls')).hidden=!selected;
   }
   byId('cloud-research-reset').textContent=tab.id==='settings-tab-display'?'表示をリセット':'試算方法をリセット';
  };
  for(const [i,tab] of tabs.entries()){
   tab.addEventListener('click',()=>switchTab(tab));
   tab.addEventListener('keydown',event=>{
    const offset={ArrowLeft:-1,ArrowRight:1}[event.key];
    const next=event.key==='Home'?tabs[0]:event.key==='End'?tabs.at(-1):offset?tabs[(i+offset+tabs.length)%tabs.length]:null;
    if(!next)return;
    event.preventDefault();
    switchTab(next);
    next.focus();
   });
  }
  const markChanged=()=>{
   syncPriceControl();
   try{controller.edit(readTrial());}catch(e){setSettingsStatus(e.message,true);}
  };
  settings.addEventListener('change',()=>{
   if(busy(latest))return;
   syncExitControl();
   markChanged();
  });
  byId('cloud-settings-cancel').addEventListener('click',()=>{
   if(busy(latest))return;
   controller.cancel();
   const state=controller.state();
   syncTrial(state.draft,state.trialPreset);
   syncDisplay(state.viewPreferences);
  });
  byId('cloud-research-reset').addEventListener('click',()=>{
   if(busy(latest))return;
   if(byId('settings-tab-display').getAttribute('aria-selected')==='true'){
    syncDisplay(null);
    markChanged();
    return;
   }
   controller.reset();
   controller.setTrialPreset('balanced');
   syncTrial(controller.state().draft,'balanced');
  });
  byId('cloud-settings-save').addEventListener('click',async()=>{
   if(busy(latest))return;
   try{
    const conditions=readTrial(),view=readView();
    controller.edit(conditions);
    await controller.save(view);
   }catch(e){setSettingsStatus(e.message,true);}
  });
 }
 document.addEventListener('click',event=>{
  const id=event.target.closest('button')?.id, snapshot=latest;
  if(!id||!snapshot)return;
  if(id==='new-a-daily-more'&&snapshot.accepted){
   dailyLimit+=50;drawDaily(snapshot.accepted.result);return;
  }
  const kind={'new-a-export-summary':'summary','new-a-export-trades':'trades','new-a-export-daily':'daily'}[id];
  if(!kind||busy(snapshot)||!snapshot.accepted)return;
  const data=snapshot.accepted;
  const matching=kind==='trades'?new Set(data.result.watches.filter(w=>!['PRICE_CAP','SIGNAL_PRICE_UNVERIFIED'].includes(w.selection_reason)).map(app.key)):null;
  const text=app.exportsFor(data,kind,matching);
  const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');
  link.href=url;link.download='Cloud2_A_'+kind+'.csv';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 const tbody=document.querySelector('#detection-table tbody');
 if(tbody)new MutationObserver(hydrateVisible).observe(tbody,{subtree:true,attributes:true,attributeFilter:['hidden']});
 if(isHome){rebuildHistory(null);showHistory();}
 controller.load();
})();
