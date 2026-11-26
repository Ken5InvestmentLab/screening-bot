/* Only the owner-gated, version-pinned private API supplies presentation data. */
(function(global){'use strict';
 const kinds=['episodes','intents','watches','presentation','current_daily'];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const hash=async(bytes,c=global.crypto)=>Array.from(new Uint8Array(await c.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
 async function assembleCurrent(records,crypto=global.crypto){
  if(!records.length)return[];
  if(records.length===1&&['NEW_A_OWNER_DAILY_DISPLAY_V1','NEW_A_OWNER_DAILY_SNAPSHOT_V1'].includes(records[0]?.schema))return records;
  const first=records[0];if(first?.schema!=='NEW_A_CURRENT_JSON_FRAGMENT_V1'||!Number.isSafeInteger(first.count)||first.count<1||first.count>256||records.length!==first.count||!Number.isSafeInteger(first.bytes_total)||first.bytes_total<2||first.bytes_total>8*1024*1024||!/^[a-f0-9]{64}$/.test(first.display_sha256))throw Error('current_fragment_bounds');
  const parts=[];let total=0;
  for(let index=0;index<records.length;index++){const r=records[index];if(r.schema!=='NEW_A_CURRENT_JSON_FRAGMENT_V1'||r.index!==index||r.count!==first.count||r.bytes_total!==first.bytes_total||r.display_sha256!==first.display_sha256||typeof r.payload_base64!=='string'||r.payload_base64.length>43692||!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(r.payload_base64))throw Error('current_fragment_order');const raw=global.atob(r.payload_base64),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));if(!bytes.length||bytes.length>32768)throw Error('current_fragment_size');total+=bytes.length;if(total>first.bytes_total)throw Error('current_fragment_size');parts.push(bytes);}
  if(total!==first.bytes_total)throw Error('current_fragment_total');const bytes=new Uint8Array(total);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}if(await hash(bytes,crypto)!==first.display_sha256)throw Error('current_fragment_hash');const display=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));if(display?.schema!=='NEW_A_OWNER_DAILY_DISPLAY_V1')throw Error('current_fragment_schema');return[display];
 }
 function validateManifest(m){if(!m||m.schema!=='A_BROWSER_PRIVATE_INPUT_V1'||m.audience!=='EXISTING_CLOUD_OWNER_ONLY'||!/^a-[a-f0-9]{20,64}$/.test(m.dataset_id)||!m.input_header||m.input_header.source_version!==m.source_version||!m.collections||kinds.some(k=>!Array.isArray(m.collections[k])))throw Error('private_manifest');const all=[...Object.values(m.collections).flat(),...m.quotes];if(all.length>512||new Set(all.map(d=>d.name)).size!==all.length||all.some(d=>!/^(episodes|intents|watches|presentation|current_daily|quotes)-\d{3}\.json$/.test(d.name)||d.dataset_id!==undefined&&!/^a-[a-f0-9]{20,64}$/.test(d.dataset_id)||!Number.isSafeInteger(d.bytes)||d.bytes<2||d.bytes>196608||!Number.isSafeInteger(d.rows)||d.rows<0||!/^[a-f0-9]{64}$/.test(d.sha256)))throw Error('private_manifest_bounds');return m;}
 async function readManifest(network){
  const r=await network('/api/cloud/new-a-finite/input/manifest.json',{credentials:'same-origin',cache:'no-store'});
  if(!r.ok)throw Error(r.status===401||r.status===403?'authorization_required':'private_unavailable');
  return validateManifest(await r.json());
 }
 async function readCurrent(network,crypto){
  const manifest=await readManifest(network);
  const reads=new Map();
  function readPart(d){
   const previous=reads.get(d.name);
   if(previous)return previous;
   const reading=(async()=>{
    const part=await network('/api/cloud/new-a-finite/input/'+(d.dataset_id||manifest.dataset_id)+'/'+d.name,{credentials:'same-origin',cache:'no-store'});
    if(!part.ok)throw Error(part.status===401||part.status===403?'authorization_required':'private_unavailable');
    const bytes=await part.arrayBuffer();
    if(bytes.byteLength!==d.bytes||await hash(bytes,crypto)!==d.sha256)throw Error('private_integrity');
    const rows=JSON.parse(new TextDecoder().decode(bytes));
    if(!Array.isArray(rows)||rows.length!==d.rows)throw Error('private_rows');
    return rows;
   })().catch(error=>{reads.delete(d.name);throw error;});
   reads.set(d.name,reading);
   return reading;
  }
  async function readParts(descriptors){
   let next=0;
   const loaded=new Array(descriptors.length);
   async function load(){
    while(next<descriptors.length){
     const index=next++;
     loaded[index]=await readPart(descriptors[index]);
    }
   }
   await Promise.all(Array.from({length:Math.min(4,descriptors.length)},load));
   return loaded.flat();
  }
  const current=await assembleCurrent(await readParts(manifest.collections.current_daily),crypto);
  if(current[0]?.schema==='NEW_A_OWNER_DAILY_DISPLAY_V1'&&(!/^[a-f0-9]{64}$/.test(manifest.daily_snapshot_sha256)||current[0].source_snapshot_sha256!==manifest.daily_snapshot_sha256))throw Error('daily_snapshot_mismatch');
  const presentation=manifest.collections.presentation;
  async function readDashboardRows(episodes,identities){
   // The bundle and its fundamental update retain the same sorted episode order.
   // Even for an older bundle, each display row must match the requested identity.
   if(episodes.length!==presentation.reduce((total,part)=>total+part.rows,0))return [];
   const wanted=new Set();
   let offset=0;
   for(const part of presentation){
    const end=offset+part.rows;
    for(let index=offset;index<end;index++){
     if(identities.has(episodeKey(episodes[index]))){wanted.add(part);break;}
    }
    offset=end;
   }
   return (await readParts([...wanted])).filter(row=>identities.has(row.identity));
  }
  async function readHistory(){
   const active=await readManifest(network);
   if(active.dataset_id!==manifest.dataset_id||active.source_version!==manifest.source_version)throw Error('source_version_changed');
   return readParts(presentation);
  }
  return {manifest,current,readDashboardRows,readHistory};
 }
 function inputFor(rows,manifest){return {schema:'A_LEGACY_UI_INPUT_V1',status:'ready',scopeLabel:'監視開始',asOfDate:manifest.input_header.limits?.completeThrough,accountRegimes:[],measurement:{kind:'A_SIGNAL_LEGACY_D5_D6',anchorBasis:'candidateDate',entryBasis:'EXPLICIT_VERIFIED_ENTRY'},rows};}
 function presentationMarkup(rows,manifest,adapter){adapter.validateInput(inputFor(rows,manifest));const ordered=[...rows].sort((a,b)=>b.signalDate.localeCompare(a.signalDate)||a.symbol.localeCompare(b.symbol)||a.identity.localeCompare(b.identity));return ordered.map((r,i)=>adapter.lightweightRowHtml(r,i)).join('');}
 const episodeKey=entry=>entry?.symbol&&entry?.candidate_date&&entry?.episode_id!=null
  ?[entry.symbol,entry.candidate_date,entry.episode_id].join('|'):null;
 function dashboardIdentities(snapshot,model,episodes){
  const keys=new Set([
   ...(snapshot.events??[]).filter(event=>event.session===snapshot.as_of).map(episodeKey),
   ...Object.values(snapshot.monitor_state?.watches??{}).map(watch=>episodeKey(watch.episode)),
   ...(snapshot.monitor_state?.pending_references??[]).filter(ref=>ref.reference_entry_date===snapshot.as_of).map(episodeKey),
   ...(model?.trades??[]).filter(trade=>trade.entry_date===snapshot.as_of||trade.exit_date===snapshot.as_of).map(episodeKey),
   ...Object.entries(model?.open_positions??{}).map(([symbol,position])=>episodeKey({...position,symbol})),
  ]);
  const held=new Set(Object.keys(snapshot.held_symbols??{}));
  for(let index=episodes.length-1;index>=0&&held.size;index--){
   const episode=episodes[index];
   if(held.delete(episode.symbol))keys.add(episodeKey(episode));
  }
  keys.delete(null);
  return keys;
 }
 const watchPreviewSize=8;
 const transitions={
  WATCH_STARTED:{label:'監視開始',tone:'watch-start'},
  WATCH_TERMINAL:{label:'監視終了',tone:'watch-end'},
  HOLD_STARTED:{label:'仮想保有開始',tone:'hold-start'},
  HOLD_ENDED:{label:'仮想保有終了',tone:'hold-end'},
  FORCED_EXIT:{label:'強制決済',tone:'forced-exit'},
 };
 const reasons={UP_ESCAPED:'上方離脱',DOWN_INVALIDATED:'下方無効',EXPIRED:'期限',TRIGGERED:'支持反発'};
 function dailyChanges(snapshot,model){
  const changes=new Map();
  const date=snapshot.as_of;
  function add(entry,kind,reason){
   const key=episodeKey(entry);
   if(!key)return;
   if(!changes.has(key))changes.set(key,{entry,labels:new Map()});
   const change=changes.get(key);
   if(!change.labels.has(kind)||reason)change.labels.set(kind,reason);
   if(kind==='HOLD_ENDED'||kind==='FORCED_EXIT')change.settlement=entry;
  }
  for(const event of snapshot.events??[]){
   if(event.session!==date)continue;
   if(event.kind==='WATCH_STARTED'||event.kind==='WATCH_TERMINAL')add(event,event.kind,reasons[event.reason]);
  }
  const holdingReady=model?.resolved===true&&model.period?.[1]===date;
  if(holdingReady){
   for(const trade of model.trades){
    if(trade.entry_date===date)add(trade,'HOLD_STARTED');
    if(trade.exit_date===date)add(trade,trade.forced_exit_reason?'FORCED_EXIT':'HOLD_ENDED',trade.forced_exit_reason);
   }
   for(const [symbol,position] of Object.entries(model.open_positions??{})){
    if(position.entry_date===date)add({...position,symbol},'HOLD_STARTED');
   }
  }
  return {changes,holdingReady};
 }
 const validPrice=price=>Number.isFinite(price)&&price>0;
 const money=price=>esc(price.toLocaleString('ja-JP',{maximumFractionDigits:2}))+'円';
 const percentage=value=>esc((value*100).toLocaleString('ja-JP',{maximumFractionDigits:2}))+'%';
 const chartAvailable=(row,symbol,adapter)=>row&&row.chartAllowed!==false&&!adapter?.identityHold(row)&&/^[0-9][0-9A-Z]{3}$/.test(symbol);
 function settledProfit(trade){
  return trade&&Number.isFinite(trade.profit)&&Number.isFinite(trade.return)?{yen:trade.profit,rate:trade.return}:null;
 }
 function profitMarkup(profit){
  if(!profit)return '<span class="cloud-pnl">未確認</span>';
  const sign=profit.yen>0?'+':'',tone=profit.yen>0?' positive':profit.yen<0?' negative':'';
  return '<span class="cloud-pnl'+tone+'">'+sign+money(profit.yen)+' <small>（'+sign+percentage(profit.rate)+'）</small></span>';
 }
 function confirmedClose(snapshot,symbol,preparedCloses){
  const prepared=preparedCloses?.date===snapshot.as_of?preparedCloses.prices?.[symbol]:null;
  const latest=snapshot.latest_closes?.[symbol]??prepared;
  return latest?.date===snapshot.as_of&&validPrice(latest.price)&&!Object.hasOwn(snapshot.held_symbols??{},symbol)?latest:null;
 }
 function positionProfit(close,position){
  if(!close||!validPrice(position.entry_cost)||!validPrice(position.shares))return null;
  const yen=close.price*position.shares-position.entry_cost, rate=yen/position.entry_cost;
  return Number.isFinite(yen)&&Number.isFinite(rate)?{yen,rate}:null;
 }
 function holdingPerformance(snapshot,rows,adapter,preparedCloses){
  const byEpisode=new Map(rows.map(row=>[row.identity,row]));
  return (position,symbol)=>{
   const row=byEpisode.get(episodeKey({...position,symbol}));
   const close=chartAvailable(row,symbol,adapter)?confirmedClose(snapshot,symbol,preparedCloses):null;
   return profitMarkup(positionProfit(close,position));
  };
 }
 function stockDetails(snapshot,rows,adapter,model,preparedCloses,dashboardYear){
  const byEpisode=new Map(rows.map(row=>[row.identity,row]));
  const trades=new Map((model?.trades??[]).map(trade=>[episodeKey(trade),trade]));
  const open=model?.resolved===false?{}:model?.open_positions??{};
  return (entry,{showEntryPrice=true}={})=>{
   const identity=episodeKey(entry);
   const row=byEpisode.get(identity);
   if(!row)return '';
   const symbol=entry.symbol;
   const chartAllowed=chartAvailable(row,symbol,adapter);
   const latest=chartAllowed?confirmedClose(snapshot,symbol,preparedCloses):null;
   const trade=trades.get(identity);
   const position=open[symbol];
   const stillOpen=position&&episodeKey({...position,symbol})===identity;
   const datePrice=(caption,observation)=>observation&&validPrice(observation.price)
    ?'<div><dt>'+caption+'</dt><dd>'+money(observation.price)+' <small>'+esc(observation.date)+'</small></dd></div>':'';
   const actual=latest?datePrice('対象日終値',latest):'<div><dt>対象日終値</dt><dd>未確認</dd></div>';
   const signal=row.signalClose?.status==='verified'?datePrice('検出日終値',row.signalClose):'';
   const started=trade||(stillOpen?position:null);
   const entryPrice=!chartAllowed||!showEntryPrice?'':started
    ?datePrice('仮想開始価格',{date:started.entry_date,price:started.entry_price_nominal})
    :row.entry?.status==='verified'?datePrice('開始価格（参考）',row.entry):'';
   let outcome='<div><dt>個別成績</dt><dd>未確定</dd></div>';
   const settled=chartAllowed?settledProfit(trade):null;
   if(settled){
    outcome='<div><dt>仮想決済 成績</dt><dd>'+money(settled.yen)+'（'+percentage(settled.rate)+'） <small>'+esc(trade.exit_date)+'</small></dd></div>';
   }else if(chartAllowed&&stillOpen){
    const profit=positionProfit(latest,position);
    if(profit)outcome='<div><dt>仮想保有 評価損益</dt><dd>'+money(profit.yen)+'（'+percentage(profit.rate)+'）</dd></div>';
    else outcome='<div><dt>個別成績</dt><dd>仮想保有中・評価未確認</dd></div>';
   }
   const chart=chartAllowed?'<a class="button-link cloud-stock-action" href="https://jp.tradingview.com/chart/?symbol=TSE%3A'+encodeURIComponent(symbol)+'" target="_blank" rel="noopener noreferrer">チャート</a>':'';
   const analysis=chartAllowed&&adapter?adapter.fundamentalMarkup(row):'';
   const basis=dashboardYear&&(trade||stillOpen)?'<p class="note">'+esc(dashboardYear.period[0].slice(0,4))+'年の独立試算</p>':'';
   return '<details class="cloud-table-details cloud-stock-detail"><summary>銘柄の詳細</summary><dl class="scenario-stats">'+actual+signal+entryPrice+outcome+'</dl>'+basis+'<div class="actions">'+analysis+chart+(analysis?'':'<small class="note">ファンダ分析 未確認</small>')+'</div></details>';
  };
 }

 function currentMarkup(snapshots,rows=[],{adapter,model,watchSelection,preparedCloses,dashboardYear,modelPending=false}={}){
  if(!snapshots.length)return '<section class="panel"><h2>最新の監視状況</h2><p>監視状況を確認できません。</p></section>';
  if(snapshots.length!==1)throw Error('current_snapshot_count');
  const s=snapshots[0];
  if(!['NEW_A_OWNER_DAILY_SNAPSHOT_V1','NEW_A_OWNER_DAILY_DISPLAY_V1'].includes(s.schema)||!['EXISTING_CLOUD_OWNER_ONLY','OWNER_ONLY'].includes(s.audience))throw Error('current_snapshot_schema');
  const eligible=Array.isArray(watchSelection)?new Set(watchSelection
   .filter(watch=>watch.watch_status==='WATCHING'&&watch.selection_reason===null)
   .map(episodeKey)):null;
  const watches=eligible?Object.values(s.monitor_state?.watches??{}).filter(watch=>eligible.has(episodeKey(watch.episode)))
   .sort((a,b)=>b.episode.candidate_date.localeCompare(a.episode.candidate_date)||a.episode.symbol.localeCompare(b.episode.symbol)):[];
  const events=s.events??[],held=s.held_symbols??{};
  const detailFor=stockDetails(s,rows,adapter,model,preparedCloses,dashboardYear);
  const names=new Map();
  for(const row of rows){
   if(row.identityStatus==='PRELISTING_HISTORY_MAPPING_UNVERIFIED')continue;
   const existing=names.get(row.symbol);
   if(!existing||existing.signalDate<row.signalDate)names.set(row.symbol,row);
  }
  const stock=symbol=>{
   const name=names.get(symbol)?.companyName;
   return name?'<span class="cloud-stock"><strong>'+esc(name)+'</strong><small>'+esc(symbol)+'</small></span>':esc(symbol||'—');
  };
  const heldReason={MISSING_SOURCE:'取得未確認',VERIFIED_DELISTED:'上場廃止',SOURCE_QUARANTINED:'価格照合',VERIFIED_RESTRICTED:'取引制限'};
  const {changes,holdingReady}=dailyChanges(s,model);
  const performanceFor=holdingPerformance(s,rows,adapter,preparedCloses);
  const byEpisode=new Map(rows.map(row=>[row.identity,row]));
  const counts=Object.fromEntries(Object.keys(transitions).map(kind=>[kind,0]));
  const transitionBadge=(kind,text)=>'<span class="cloud-transition cloud-transition--'+transitions[kind].tone+'">'+text+'</span>';
  const observed=typeof s.observed_at==='string'&&Number.isFinite(Date.parse(s.observed_at))?new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(s.observed_at)):'';
  const live=s.observation_kind==='LIVE_OBSERVATION',delayed=s.observation_kind==='DELAYED_SCHEDULED_OBSERVATION';
  const newCount=new Set(events.filter(e=>e.kind==='WATCH_STARTED'&&e.session===s.as_of&&(live&&e.is_new_live_signal||delayed&&e.is_delayed_scheduled_signal)).map(e=>e.symbol)).size;
  const eventCards=[...changes.values()].map(({entry,labels,settlement})=>{
   const badges=Object.entries(transitions).filter(([kind])=>labels.has(kind)).map(([kind,{label}])=>{
    counts[kind]++;
    const reason=labels.get(kind);
    return '<div class="cloud-transition-row">'+transitionBadge(kind,label)+(reason?'<small>'+esc(reason)+'</small>':'')+'</div>';
   }).join('');
   const identity=episodeKey(entry);
   const position=holdingReady?model.open_positions?.[entry.symbol]:null;
   let profit='';
   if(settlement){
    const confirmed=chartAvailable(byEpisode.get(identity),entry.symbol,adapter)?settledProfit(settlement):null;
    profit='<div class="cloud-card-pnl"><small>確定損益</small>'+profitMarkup(confirmed)+'</div>';
   }else if(position&&episodeKey({...position,symbol:entry.symbol})===identity){
    profit='<div class="cloud-card-pnl"><small>評価損益</small>'+performanceFor(position,entry.symbol)+'</div>';
   }
   return {primary:(labels.has('HOLD_ENDED')||labels.has('FORCED_EXIT')),markup:'<article data-daily-change="'+esc(identity)
    +'" data-reference-kind="'+(labels.has('FORCED_EXIT')?'FORCED_EXIT':labels.has('HOLD_ENDED')?'HOLD_ENDED':'OTHER')+'" data-reference-symbol="'+esc(entry.symbol)
    +'" data-reference-name="'+esc(names.get(entry.symbol)?.companyName||entry.symbol)+'">'
    +stock(entry.symbol)+'<div class="cloud-transition-list">'+badges+'</div>'+profit+detailFor(entry)+'</article>'};
  });
  const totals=Object.entries(transitions).filter(([kind])=>kind!=='FORCED_EXIT'||model?.source_limits?.restrictionExitActions?.length).map(([kind,{label}])=>{
   const total=kind.startsWith('HOLD_')&&!holdingReady?(modelPending?'計算中':'未確定'):counts[kind]+'件';
   return '<li>'+transitionBadge(kind,label+' <b>'+total+'</b>')+'</li>';
  }).join('');
  const referenceLabels={ENTRY_CANDIDATE:'仮想保有開始候補',MONITOR_RESET:'監視条件リセット'};
  const references=events.filter(e=>e.session===s.as_of&&Object.hasOwn(referenceLabels,e.kind))
   .sort((a,b)=>(a.kind==='ENTRY_CANDIDATE'?0:1)-(b.kind==='ENTRY_CANDIDATE'?0:1)||a.symbol.localeCompare(b.symbol));
  const referenceRows=references.map(e=>{
   const close=confirmedClose(s,e.symbol,preparedCloses);
   const candidate=e.kind==='ENTRY_CANDIDATE';
   const limit=candidate?'<p class="note">開始条件：次の営業日の始値で100株50万円以内</p>'
    +(close&&close.price>5000?'<span class="badge">現在の株価では注文上限超過</span>':''):'';
   return {primary:candidate,markup:'<article data-reference-kind="'+esc(e.kind)+'" data-reference-symbol="'+esc(e.symbol)
    +'" data-reference-name="'+esc(names.get(e.symbol)?.companyName||e.symbol)+'">'+stock(e.symbol)
    +'<span class="badge">'+referenceLabels[e.kind]+'</span>'
    +(reasons[e.reason]?'<small>'+esc(reasons[e.reason])+'</small>':'')+limit+detailFor(e)+'</article>'};
  });
  const allCards=[...referenceRows,...eventCards];
  const primaryCards=allCards.filter(card=>card.primary),otherCards=allCards.filter(card=>!card.primary);
  const referenceCards='<div class="cloud-reference-events"><h3>仮想保有開始候補・終了銘柄</h3>'
   +'<div class="cloud-card-sort" role="group" aria-label="記録の並び順">'
   +[['kind','候補を先に'],['symbol','コード順'],['name','銘柄名順']].map(([value,label])=>'<button type="button" data-reference-sort="'+value+'" aria-pressed="'+(value==='kind')+'">'+label+'</button>').join('')
   +'</div><div class="cloud-stock-grid" data-reference-cards>'+(primaryCards.map(card=>card.markup).join('')
    ||'<p class="cloud-empty">対象の候補・終了銘柄はありません</p>')+'</div>'
   +(otherCards.length?'<details class="cloud-table-details cloud-other-events"><summary>その他の動き・記録（'+otherCards.length+'件）</summary>'
    +'<div class="cloud-stock-grid" data-reference-cards>'+otherCards.map(card=>card.markup).join('')+'</div></details>':'')+'</div>';
  const watchRows=watches.map((w,i)=>{
   const symbol=w.episode?.symbol, hold=held[symbol], detail=hold?heldReason[hold.reason]||'確認待ち':'';
   return '<tr data-current-watch'+(i>=watchPreviewSize?' hidden':'')+'><td>'+stock(symbol)+'</td><td>'+esc(w.episode?.candidate_date||'—')+'</td><td>'+(detail?'<span class="badge cloud-status-held">データ保留</span><small class="cloud-table-meta"> '+esc(detail)+'</small>':'')+detailFor(w.episode)+'</td></tr>';
  }).join('');
  const watchStatus=eligible?watches.length+'銘柄':modelPending?'計算中':'未確認';
  const noWatches=eligible?'監視中の銘柄なし':modelPending?'監視対象を計算しています。':'監視対象を確認できません。';
  const heldRows=Object.entries(held).sort(([a],[b])=>a.localeCompare(b)).map(([symbol,item])=>'<tr><td>'+stock(symbol)+'</td><td>'+esc(heldReason[item.reason]||'確認待ち')+'</td><td>'+esc(item.day||'—')+'</td></tr>').join('');
  const table=(head,body)=>'<div class="table-wrap"><table class="scenario-table"><thead><tr>'+head.map(h=>'<th scope="col">'+h+'</th>').join('')+'</tr></thead><tbody>'+body+'</tbody></table></div>';
  return '<section class="panel" id="new-a-current" aria-labelledby="new-a-events-heading"><div class="cloud-section-head"><h2 id="new-a-events-heading">対象日の動き</h2><div class="cloud-meta"><span class="badge">対象 '+esc(s.as_of||'—')+'</span>'+(observed?'<span class="badge">観測 '+esc(observed)+' JST</span>':'')+(s.observation_kind==='DELAYED_SCHEDULED_OBSERVATION'?'<span class="badge">遅延実行</span>':'')+'</div></div><ul class="cloud-transition-summary" aria-label="対象日の件数">'+totals+'</ul><div class="cloud-meta">'+(live||delayed?'<span class="badge">新規検出 '+newCount+'銘柄</span>':'<span class="badge">照合</span>')+'<span class="badge">データ保留 '+Object.keys(held).length+'銘柄</span></div>'+referenceCards+'</section>'+
   '<section class="panel" aria-labelledby="new-a-watch-heading"><div class="cloud-section-head"><h2 id="new-a-watch-heading">現在の監視</h2><span class="badge">'+watchStatus+'</span></div>'+(watchRows?table(['銘柄','監視開始日','詳細'],watchRows):'<p class="cloud-empty">'+noWatches+'</p>')+(watches.length>watchPreviewSize?'<button class="settings-secondary" type="button" id="new-a-current-more">残り '+(watches.length-watchPreviewSize)+'銘柄を表示</button>':'')+(heldRows?'<details class="cloud-table-details"><summary>データ保留 '+Object.keys(held).length+'銘柄</summary>'+table(['銘柄','理由','対象日'],heldRows)+'</details>':'')+'</section>';
 }
 function openFundamental(button){
  const dialog=button.nextElementSibling;
  if(!dialog?.matches('dialog.fundamental-detail')||dialog.open)return;
  const dismiss=event=>{
   if(event.target===dialog||event.target.closest?.('.fundamental-close'))dialog.close();
  };
  dialog.addEventListener('click',dismiss);
  dialog.addEventListener('close',()=>{
   dialog.removeEventListener('click',dismiss);
   button.setAttribute('aria-expanded','false');
   if(button.isConnected)button.focus({preventScroll:true});
  },{once:true});
  dialog.showModal();
  button.setAttribute('aria-expanded','true');
 }
 const api={validateManifest,assembleCurrent,readCurrent,inputFor,presentationMarkup,dashboardIdentities,currentMarkup,stockDetails,holdingPerformance,openFundamental};
 if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
 global.AOwnerPresentation=api;
 if(typeof document==='undefined')return;
 const scriptAt=path=>new Promise((resolve,reject)=>{
  const node=document.createElement('script');
  node.src=path;
  node.onload=resolve;
  node.onerror=()=>reject(Error('asset_unavailable'));
  document.head.append(node);
 });
 const script=name=>scriptAt('/new-a-assets/'+name);
 const closeSettings=()=>global.CloudSettingsDialog?.close(true);
 document.addEventListener('visibilitychange',closeSettings);
 global.addEventListener('pagehide',closeSettings);
 global.addEventListener('pageshow',event=>{if(event.persisted)closeSettings();});
 document.addEventListener('click',event=>{
  const fundamental=event.target.closest?.('[data-owner-fundamental]');
  if(fundamental&&!global.AFiniteRevoked)openFundamental(fundamental);
 });
 function showLoadStatus(message,retry){
  const panel=document.getElementById('new-a-load-panel');
  if(!panel)return;
  panel.hidden=!message;
  document.getElementById('new-a-load-progress').hidden=!message||Boolean(retry);
  document.getElementById('new-a-load-message').textContent=message||'';
  const button=document.getElementById('new-a-load-retry');
  button.hidden=!retry;
  button.onclick=retry||null;
 }
 global.AOwnerLoadStatus=showLoadStatus;
 const pageLoad=new AbortController();
 function unavailable(){
  pageLoad.abort();
  global.CloudSettingsDialog?.close(true);
  global.AOwnerSavedSettings=null;
  global.AFiniteBrowser?.clear();
  global.AFiniteRevoked=true;
  global.AOwnerPageData=null;
  for(const id of ['new-a-dashboard','new-a-model-holdings','cloud-analytics-content','history','cloud-settings-direct']){
   const node=document.getElementById(id);
   if(node){node.replaceChildren();node.hidden=true;}
  }
  showLoadStatus('データを読み込めませんでした。',()=>global.location.reload());
 }

 async function start(){
  global.AFiniteUI=true;
  const network=(url,options={})=>global.fetch(url,{...options,signal:options.signal??pageLoad.signal});
  const page=document.body.dataset.page;

  let data={manifest:null,rows:[],current:[]};
  const dashboard=document.getElementById('new-a-dashboard');
  const preload=[script('browser-transport.js'),script('finite-controller.js')];
  let settingsAssets;
  function openSettings(target,status,context) {
   settingsAssets ??= Promise.all([...preload,script('member-settings.js'),script('owner-settings.js')])
    .catch(error=>{settingsAssets=undefined;throw error;});
   return settingsAssets.then(()=>{
    if(!context.active()||global.AFiniteRevoked)return;
    let localBrowser;
    context.signal?.addEventListener('abort',()=>localBrowser?.clear(),{once:true});
    const transport=(url,options)=>{
     if(url!=='/api/cloud/new-a-finite/simulate')return network(url,{...options,signal:context.signal});
     const browser=global.AFiniteBrowser??(localBrowser??=makeBrowser(null));
     return browser.transport(url,options);
    };
    return global.mountOwnerSettings(target,status,{...context,transport,dashboardPrices:page==='home',recentAnalytics:page==='analytics',
     onRevoked:unavailable,
     onSaved(state){
      if(global.AFiniteUIController){
       void global.AFiniteUIController.load();
      }else{
       global.AOwnerSavedSettings=state;
      }
     },
    });
   });
  }
  global.CloudSettingsDialog?.connect(openSettings,()=>!global.AFiniteRevoked);
  if(page==='settings'){
   const target=document.getElementById('cloud-settings-direct'),status=document.getElementById('cloud-settings-status');
   function confirmLeave(event){event.preventDefault();event.returnValue=true;}
   function setBusy(saving){
    if(saving)global.addEventListener('beforeunload',confirmLeave);
    else global.removeEventListener('beforeunload',confirmLeave);
   }
   const load=()=>{
    showLoadStatus('');
    openSettings(target,status,{active:()=>!pageLoad.signal.aborted,signal:pageLoad.signal,setBusy}).catch(()=>{
     if(!pageLoad.signal.aborted)showLoadStatus('設定を読み込めませんでした。',load);
    });
   };
   load();
   return;
  }
  function makeBrowser(manifest){
   const browser=global.AFiniteBrowserTransport.create({
    fetch:network,pinnedManifest:manifest,createWorker:()=>new Worker('/new-a-assets/new-a-finite-worker.generated.js'),
    onSimulationPhase:phase=>{
     const task=page==='home'?'監視対象・仮想保有':'過去成績';
     showLoadStatus(phase==='prices'?'株価データを読み込んでいます。':task+'を計算しています。');
    },
   });
   return browser;
  }
  function configureTransport(manifest){
   const browser=makeBrowser(manifest);
   global.AFiniteBrowser=browser;
   global.AFiniteTransport=browser.transport;
   return browser;
  }
  if(page==='home'){
   let watchesExpanded=false;
   const cardDetails='.cloud-stock-grid > [data-daily-change] > .cloud-stock-detail';
   function showAllWatches(){
    const hidden=dashboard.querySelectorAll('[data-current-watch][hidden]');
    for(const row of hidden)row.hidden=false;
    const more=dashboard.querySelector('#new-a-current-more');
    if(more)more.hidden=true;
    return hidden[0];
   }
   function renderDashboard(snapshots,rows,options){
    if(global.AFiniteRevoked)throw Error('authorization_reset');
    const openCards=new Set(Array.from(dashboard.querySelectorAll(cardDetails+'[open]'),
     details=>details.parentElement.dataset.dailyChange));
    const focusedCard=document.activeElement?.matches(cardDetails+' > summary')?
     document.activeElement.parentElement.parentElement.dataset.dailyChange:null;
    dashboard.innerHTML=currentMarkup(snapshots,rows,options);
    for(const details of dashboard.querySelectorAll(cardDetails)){
     const identity=details.parentElement.dataset.dailyChange;
     details.open=openCards.has(identity);
     if(identity===focusedCard)details.querySelector('summary').focus({preventScroll:true});
    }
    if(watchesExpanded)showAllWatches();
   }
   dashboard.addEventListener('click',event=>{
    const summary=event.target.closest?.(cardDetails+' > summary');
    if(summary){
     event.preventDefault();
     const pressed=summary.parentElement;
     const top=pressed.parentElement.getBoundingClientRect().top;
     const open=!pressed.open;
     // Measure the row before toggling any card and moving the following rows.
     const row=Array.from(dashboard.querySelectorAll(cardDetails)).filter(
      details=>Math.abs(details.parentElement.getBoundingClientRect().top-top)<1);
     for(const details of row)details.open=open;
     return;
    }
    if(!event.target.closest?.('#new-a-current-more'))return;
    watchesExpanded=true;
    showAllWatches()?.querySelector('summary,td')?.focus();
   });
   const reading=readCurrent(network,global.crypto).then(result=>{
    renderDashboard(result.current,[],{modelPending:true});
    showLoadStatus('株価データを読み込んでいます。');
    preload[0].then(()=>{
     if(pageLoad.signal.aborted||global.AFiniteBrowser)return;
     return configureTransport(result.manifest).preload();
    }).catch(error=>{if(error.status===401||error.status===403)unavailable();});
    return result;
   });
   [data]=await Promise.all([reading,script('presentation-adapter.generated.js'),...preload]);
   if(pageLoad.signal.aborted)return;
   const adapter=global.ANewPresentation;
   data.rows=[];
   data.dashboardRows=[];
   data.renderDashboard=options=>renderDashboard(data.current,data.rows.length?data.rows:data.dashboardRows,{adapter,...options});
   data.historyMarkup=async()=> {
    const rows=await data.readHistory();
    if(global.AFiniteRevoked)throw Error('authorization_reset');
    const markup=presentationMarkup(rows,data.manifest,adapter);
    data.rows=rows;
    return markup;
   };
   data.loadDashboardRows=async(snapshot,model)=>{
    const episodes=global.AFiniteBrowser.episodeOrder();
    return data.readDashboardRows(episodes,dashboardIdentities(snapshot,model,episodes));
   };
   data.onReadError=error=>{
    if(error.message==='authorization_required')unavailable();
   };
  }else await Promise.all(preload);
  global.AOwnerPageData=data;
  const payload=document.createElement('script');
  payload.type='application/json';
  payload.id='cloud-analytics-data';
  const years=[...new Set((data.manifest?.input_header?.calendar??[]).map(day=>Number(day.slice(0,4))))].sort(),scopes={all:{label:'全期間',years}};
  for(const y of years)scopes[String(y)]={label:y+'年',years:[y]};
  payload.textContent=JSON.stringify({version:2,page,scopes,variants:{},modeNames:{A_BASE:'監視開始'},generated:data.manifest?.input_header?.limits?.completeThrough||'',aInputStatus:'ready'});
  document.body.append(payload);
  if(!global.AFiniteBrowser)configureTransport(data.manifest);
  await script('new-a-legacy-interactions.generated.js');
  if(pageLoad.signal.aborted)return;
  await script('member-presentation.js');
  await script('finite-dom.js');
 }
 start().catch(unavailable);
})(typeof globalThis!=='undefined'?globalThis:this);

/* Code-only owner UI: an ordinary same-origin read behind the existing access gate. */
(function () {
  'use strict';
  if (typeof location === 'undefined' || typeof document === 'undefined' || location.pathname !== '/weak_early_beta_latest.html') return;
  const button = document.getElementById('new-a-owner-access-check');
  const output = document.getElementById('new-a-owner-access-status');
  if (!button || !output) return;
  let pending = false;
  const tell = (status, text) => {
    output.dataset.state = status;
    output.textContent = text;
  };
  button.addEventListener('click', async () => {
    if (pending) return;
    pending = true;
    button.disabled = true;
    tell('checking', '本人アクセスを確認しています。');
    try {
      const response = await fetch('/api/cloud/new-a-finite/access', {
        method: 'GET', mode: 'same-origin', credentials: 'same-origin',
        cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(5000)
      });
      if (response.status !== 200 || !response.headers.get('content-type')?.toLowerCase().startsWith('application/json')) {
        tell('denied', '本人アクセスを確認できません。');
        return;
      }
      const raw = await response.text();
      if (raw.length > 256) throw Error('access_contract');
      const body = JSON.parse(raw);
      if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).length !== 2 || body.authorized !== true || body.strategy !== 'A_BASE') {
        tell('denied', '本人アクセスを確認できません。');
        return;
      }
      tell('verified', '本人アクセスを確認しました。日次処理の完了を示すものではありません。');
    } catch {
      tell('unavailable', '確認に失敗しました。時間をおいて再度お試しください。');
    } finally {
      pending = false;
      button.disabled = false;
    }
  });
})();
