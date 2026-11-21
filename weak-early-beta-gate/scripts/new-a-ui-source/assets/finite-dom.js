/* Bind the owner-only frame to its calculation and history. */
(function(){
 'use strict';
 const page=document.body.dataset.page, isHome=page==='home', isAnalytics=page==='analytics';
 const app=globalThis.AFinite,legacy=globalThis.AFiniteLegacy;
 if(!app||!legacy)return;
 const byId=id=>document.getElementById(id);
 const content=byId('cloud-analytics-content');
 let rows=[];
 let drawn=null,displayKey,history=new Map(),dailyLimit=50,latest=null;
 const busy=s=>['loading','saving','calculating'].includes(s.phase);
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
 let historyExitPolicy=null,historyTrialPolicy=null,historyLoad=null,historyLoaded=false,historyChanged=false;
 function rebuildHistory(model){
  historyExitPolicy=model?.exit_policy;
  historyTrialPolicy=model?.trial_policy;
  history=app.historyRecords(globalThis.AOwnerPageData.rows,model);
  for(const row of rows){row.dataset.finiteHydrate='pending';row.replaceChildren();}
  hydrateVisible();
 }
 function openHistory(){
  if(historyLoaded||historyLoad||globalThis.AFiniteRevoked)return;
  if(historyChanged){location.reload();return;}
  const data=globalThis.AOwnerPageData;
  const trigger=byId('new-a-history-open'),status=byId('new-a-history-status'),content=byId('new-a-history-content');
  const tbody=document.querySelector('#detection-table tbody');
  trigger.setAttribute('aria-expanded','true');
  trigger.disabled=true;
  status.textContent='検出履歴を読み込んでいます。';
  status.hidden=false;
  content.setAttribute('aria-busy','true');
  historyLoad=data.historyMarkup().then(markup=>{
   if(globalThis.AFiniteRevoked||globalThis.AOwnerPageData!==data)return;
   tbody.innerHTML=markup;
   rows=Array.from(tbody.querySelectorAll('tr[data-date]'));
   legacy.replaceHistoryRows(rows);
   historyLoaded=true;
   rebuildHistory(latest?.accepted?.result??null);
   if(latest?.accepted&&!data.dashboardRows.length)renderHome(latest.accepted);
   content.hidden=false;
   status.hidden=true;
   trigger.hidden=true;
   if(document.activeElement===trigger){
    byId('new-a-history-heading').focus({preventScroll:true});
   }
   if(location.hash==='#history')byId('history').scrollIntoView();
  }).catch(error=>{
   data.onReadError(error);
   if(globalThis.AFiniteRevoked)return;
   trigger.setAttribute('aria-expanded','false');
   historyChanged=error.message==='source_version_changed';
   trigger.textContent=historyChanged?'ページを再読み込み':'再試行';
   status.textContent=historyChanged?'検出データが更新されました。':'検出履歴を読み込めませんでした。';
  }).finally(()=>{
   historyLoad=null;
   trigger.disabled=false;
   content.setAttribute('aria-busy','false');
  });
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
  globalThis.CloudSettingsDialog?.close(true);
  globalThis.AOwnerSavedSettings=null;
  globalThis.AOwnerPageData=null;
  globalThis.AFiniteBrowser?.clear();
  history.clear();
  legacy.clearHistory();
  rows.length=0;
  for(const id of ['new-a-dashboard','new-a-model-holdings','cloud-analytics-content','history']){
   const node=byId(id);
   if(node){node.replaceChildren();node.hidden=true;}
  }
 }
 function renderHome(simulation){
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
  const displayRows=data.rows.length?data.rows:data.dashboardRows;
  const details=current&&presentation.stockDetails(current,displayRows,globalThis.ANewPresentation,currentModel,preparedCloses,dashboardYear);
  const performance=current&&presentation.holdingPerformance(current,displayRows,globalThis.ANewPresentation,preparedCloses);
  const holdings=app.renderHoldings(simulation,{rows:displayRows,calendar:data.manifest.input_header.calendar,details,performance,model,asOf});
  const events=byId('new-a-current');
  if(events)events.insertAdjacentHTML('afterend',holdings);
  else byId('new-a-dashboard').insertAdjacentHTML('beforeend',holdings);
  return currentModel;
 }
 function update(state){
  const saved=globalThis.AOwnerSavedSettings;
  if(saved&&state.phase!=='denied'&&state.phase!=='session-changed'&&state.revision<=saved.revision){
   state=saved.accepted?saved:{...state,viewPreferences:saved.viewPreferences};
  }
  latest=state;
  const working=busy(state);
  for(const input of level?.querySelectorAll('input[name="new-a-dashboard-level"]')??[]){
   input.disabled=working||state.revision===null;
   input.checked=presetOptions[input.value]===state.trialPreset;
  }
  const key=JSON.stringify(state.viewPreferences);
  if((state.revision!==null||state.viewPreferences)&&key!==displayKey){
   legacy.applyAccountDisplay(state.viewPreferences);
   displayKey=key;
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
   const message=isAnalytics?(state.accepted?'過去成績を更新できませんでした。':'過去成績を読み込めませんでした。'):isHome?'監視対象と仮想保有を確認できませんでした。':'設定を読み込めませんでした。';
   globalThis.AOwnerLoadStatus?.(message,()=>{
    globalThis.AOwnerLoadStatus?.('読み込んでいます。');
    controller.load();
   });
   return;
  }
  if(state.phase==='ready'){
   globalThis.AOwnerLoadStatus?.('');
   if(content)content.hidden=false;
  }
  if(!state.accepted||drawn===state.accepted)return;
  const simulation=state.accepted;
  drawn=simulation;
  if(isAnalytics){
   content.innerHTML=app.render(simulation);
   content.querySelector('section[aria-labelledby="analytics-export"]')?.remove();
   byId('new-a-daily-chart').innerHTML=equityChart(simulation.result.daily,simulation.result.resolved);
   const recentChart=byId('new-a-latest-year-chart');
   if(recentChart&&simulation.latest_year)recentChart.innerHTML=equityChart(simulation.latest_year.daily,simulation.latest_year.resolved);
   dailyLimit=50;
   drawDaily(simulation.result);
  }
  if(isHome){
   const data=globalThis.AOwnerPageData;
   const currentModel=renderHome(simulation);
   if(historyLoaded)rebuildHistory(simulation.result);
   if(data.current[0]&&!data.rows.length){
    data.loadDashboardRows(data.current[0],currentModel).then(displayRows=>{
     if(globalThis.AFiniteRevoked||latest?.accepted?.request_id!==simulation.request_id||!displayRows.length||data.rows.length)return;
     data.dashboardRows=displayRows;
     renderHome(simulation);
    }).catch(data.onReadError);
   }
  }
 }
 const level=byId('new-a-operating-level');
 const presetOptions={defensive:'defensive',medium:'balanced',return_priority:'profit'};
 let selected='return_priority';
 try{
  const stored=sessionStorage.getItem('cloud-owner-operating-level');
  if(Object.hasOwn(presetOptions,stored))selected=stored;
 }catch{
  // The current page still works without browser storage.
 }
 if(level)level.innerHTML=globalThis.NewAMemberPresentation.operatingLevel(selected);
 const controller=app.createController({trialPreset:presetOptions[selected],useSavedTrialPreset:false,
  recentAnalytics:isAnalytics,dashboardPrices:isHome,transport:globalThis.AFiniteTransport,
  onChange:update,calculateOnLoad:isAnalytics||isHome});
 globalThis.AFiniteUIController=controller;
 level?.addEventListener('change',async event=>{
  const choice=event.target.value;
  if(!event.target.matches('input[name="new-a-dashboard-level"]')||!Object.hasOwn(presetOptions,choice))return;
  const previous=controller.state().trialPreset;
  if(!controller.setTrialPreset(presetOptions[choice]))return;
  if(await controller.recalculate()){
   try{sessionStorage.setItem('cloud-owner-operating-level',choice);}catch{/* The current page does not need storage. */}
  }else if(controller.state().revision!==null){
   controller.setTrialPreset(previous);
  }
 });

 globalThis.AFiniteApplySavedSettings=()=>{if(latest)update(latest);};
 document.addEventListener('click',event=>{
  const simulation=latest?.accepted;
  if(event.target.closest('button')?.id!=='new-a-daily-more'||!simulation)return;
  dailyLimit+=50;
  drawDaily(simulation.result);
 });
 const tbody=document.querySelector('#detection-table tbody');
 if(tbody)new MutationObserver(hydrateVisible).observe(tbody,{subtree:true,attributes:true,attributeFilter:['hidden']});
 if(isHome){
  const historySection=byId('history');
  historySection.hidden=false;
  byId('new-a-history-open').addEventListener('click',openHistory);
  const openLinkedHistory=()=>{if(location.hash==='#history')openHistory();};
  window.addEventListener('hashchange',openLinkedHistory);
  if(new URLSearchParams(location.search).get('q'))openHistory();
  openLinkedHistory();
 }
 controller.load();
})();
