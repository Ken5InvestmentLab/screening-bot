// Data boundary for the preserved Cloud UI. Never imports old report data.
const html=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const day=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const equalMoney=(a,b)=>Math.abs(a-b)<=Math.max(1e-6,Math.abs(b)*1e-10);
const identityHold=row=>row.identityStatus==='PRELISTING_HISTORY_MAPPING_UNVERIFIED';
const missingInput={schema:'A_LEGACY_UI_INPUT_V1',status:'missing',scopeLabel:'A検出データ 接続待ち',rows:[],accountRegimes:[],measurement:{kind:'A_SIGNAL_LEGACY_D5_D6',anchorBasis:null,entryBasis:null}};
function validateInput(input){
 if(!input||input.schema!=='A_LEGACY_UI_INPUT_V1')throw Error('A UI input schema mismatch');
 if(!['missing','ready'].includes(input.status)||!Array.isArray(input.rows))throw Error('A UI input unavailable');
 if(input.measurement?.kind!=='A_SIGNAL_LEGACY_D5_D6')throw Error('A20 finite-account data cannot enter legacy measurement slots');
 if(input.status==='missing'){if(input.rows.length)throw Error('Missing input must not contain partially interpreted rows');return input;}
 if(!['candidateDate','triggerDate','entryDate'].includes(input.measurement.anchorBasis)||input.measurement.entryBasis!=='EXPLICIT_VERIFIED_ENTRY')throw Error('A measurement date/entry basis is unconfirmed');
 const identities=new Set();
 for(const row of input.rows){
  if(!row.identity||identities.has(row.identity))throw Error('A detection identity is missing or duplicated');identities.add(row.identity);
  if(!/^[0-9A-Z]{4,5}$/.test(row.symbol)||!row.companyName||!day(row.candidateDate)||!day(row.signalDate))throw Error('A identity fields unavailable');
  if(row.triggerDate!==null&&!day(row.triggerDate))throw Error('A trigger date unavailable');
  const anchor=input.measurement.anchorBasis==='entryDate'?row.entry?.date:row[input.measurement.anchorBasis];
  if((row.measurementAnchorDate??row.signalDate)!==anchor)throw Error('A measurement anchor mismatch');
  if(row.selectors?.length!==1||row.selectors[0]!=='A_BASE')throw Error('A must not be counted as five legacy selectors');
  const entry=row.entry;
  if(entry?.status==='verified'&&(!day(entry.date)||!finite(entry.price)||entry.price<=0||!finite(entry.cost100)||entry.cost100<=0||!equalMoney(entry.cost100,entry.price*100)))throw Error('A 100-share entry receipt unavailable or inconsistent');
  for(const key of ['d5_close','d6_open']){const endpoint=row.endpoints?.[key];if(endpoint?.status==='reference_price_only'){if(endpoint.measurementKind!=='A_SIGNAL_LEGACY_D5_D6'||endpoint.key!==key||endpoint.anchorDate!==(row.measurementAnchorDate??row.signalDate)||!day(endpoint.date)||!finite(endpoint.price)||endpoint.price<=0||!day(entry?.date)||endpoint.date<entry.date||endpoint.proceeds100!==null||endpoint.exitShares100!==null||endpoint.return!==null||endpoint.shareActionReceipt!=='REFERENCE_PRICE_ONLY_NOT_SETTLEMENT')throw Error('A price-only reference receipt mismatch');continue;}if(!endpoint||endpoint.status!=='verified')continue;
   if(endpoint.measurementKind!=='A_SIGNAL_LEGACY_D5_D6'||endpoint.key!==key||endpoint.anchorDate!==(row.measurementAnchorDate??row.signalDate)||!day(endpoint.date)||!finite(endpoint.price)||endpoint.price<=0||!finite(endpoint.proceeds100)||endpoint.proceeds100<=0||!Number.isSafeInteger(endpoint.exitShares100)||endpoint.exitShares100<=0||!finite(endpoint.return)||entry?.status!=='verified'||endpoint.date<entry.date||!equalMoney(endpoint.proceeds100,endpoint.price*endpoint.exitShares100))throw Error('A endpoint receipt/basis unavailable or inconsistent');
   const receipt=endpoint.shareActionReceipt;
   if(receipt?.status!=='verified'||receipt.symbol!==row.symbol||receipt.entryDate!==entry.date||receipt.exitDate!==endpoint.date||receipt.entryShares!==100||receipt.exitShares!==endpoint.exitShares100||receipt.cashInLieu!=='none'||!Array.isArray(receipt.actions))throw Error('A share-action receipt unavailable');
   let shares=100,previousActionDate=entry.date;
   for(const action of receipt.actions){if(!day(action.effectiveDate)||action.effectiveDate<=previousActionDate||action.effectiveDate>endpoint.date||!finite(action.factor)||action.factor<=0)throw Error('A share action dates/factor invalid or duplicate');shares*=action.factor;if(Math.abs(shares-Math.round(shares))>1e-8||!Number.isSafeInteger(Math.round(shares))||shares<=0)throw Error('A intermediate fractional shares require unresolved review');previousActionDate=action.effectiveDate;}
   if(Math.abs(shares-endpoint.exitShares100)>1e-8)throw Error('A share action quantity mismatch');
   const expected=(endpoint.proceeds100-entry.cost100)/entry.cost100;if(Math.abs(expected-endpoint.return)>1e-8)throw Error('A endpoint economics mismatch');
  }
  if(row.signalClose?.status==='verified'&&(row.signalClose.date!==row.signalDate||!finite(row.signalClose.price)||row.signalClose.price<=0))throw Error('A price-cap receipt/date mismatch');
 }
 return input;
}
function toDataset(row){
 const e=row.entry?.status==='verified'?row.entry:null,d5=row.endpoints?.d5_close?.status==='verified'?row.endpoints.d5_close:null,d6=row.endpoints?.d6_open?.status==='verified'?row.endpoints.d6_open:null,close=row.signalClose?.status==='verified'?row.signalClose:null;
 const ref5=row.endpoints?.d5_close?.status==='reference_price_only'?row.endpoints.d5_close:null,ref6=row.endpoints?.d6_open?.status==='reference_price_only'?row.endpoints.d6_open:null;
 const d={date:row.signalDate,symbol:row.symbol,name:row.companyName,search:`${row.symbol} ${row.companyName}`,selectors:'A_BASE',historical:'true',reference:String(identityHold(row)),aIdentity:row.identity,aIdentityStatus:row.identityStatus??'unconfirmed',aChartAllowed:String(!identityHold(row)),aNameStatus:row.nameStatus??'unverified',candidateDate:row.candidateDate,triggerDate:row.triggerDate??'',aEntryStatus:row.entry?.status??'missing',aEntryReason:row.entry?.reason??'',aEpisodeStatus:row.watchStatus??row.episodeStatus??row.status??'',aStatusLabel:statusLabel(row),aD5Status:row.endpoints?.d5_close?.status??'missing',aD6Status:row.endpoints?.d6_open?.status??'missing',aD5Reason:row.endpoints?.d5_close?.reason??'',aD6Reason:row.endpoints?.d6_open?.reason??'',signalActualClose:close?.price??'',signalPriceVerified:String(Boolean(close)),entryDate:e?.date??'',entryOpen:e?.price??'',entryCost:e?.cost100??'',entryShares:e?100:'',d5Date:d5?.date??ref5?.date??'',d5Close:d5?.price??ref5?.price??'',d5Return:d5?.return??'',d5Proceeds:d5?.proceeds100??'',d5ExitShares:d5?.exitShares100??'',d5Status:d5?'verified':'missing',d6Date:d6?.date??ref6?.date??'',d6Open:d6?.price??ref6?.price??'',d6Return:d6?.return??'',d6Proceeds:d6?.proceeds100??'',d6ExitShares:d6?.exitShares100??'',d6Status:d6?'verified':'missing',d6EntryDate:e?.date??'',d6EntryOpen:e?.price??'',d6EntryCost:e?.cost100??'',d6EntryShares:e?100:''};
 return Object.fromEntries(Object.entries(d).map(([k,v])=>[k,String(v)]));
}
function statusLabel(row){
 if(identityHold(row))return '同一性照合保留・参照のみ';
 if(!row.triggerDate)return({EXPIRED:'監視終了・期限',UP_ESCAPED:'監視終了・上抜け',DOWN_INVALIDATED:'監視終了・下抜け',WATCHING:'監視中'})[row.watchStatus??row.episodeStatus??row.status]??'反発未確認';
 if(row.entry?.status!=='verified')return row.entry?.status==='unfilled'?'未約定':['pending','pending_next_session'].includes(row.entry?.status)?'反発確認・開始価格待ち':'反発確認・開始未確認';
 return '開始価格確認・過去検証の参照';
}
function datasetAttributes(row){return Object.entries(toDataset(row)).map(([k,v])=>`data-${k.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())}="${html(v)}"`).join(' ');}
function endpointLabel(status){return({not_triggered:'未発動',pending_entry:'開始価格待ち',pending_exit:'出口価格待ち',unresolved:'未解決',missing:'未確認'})[status]??'未確認';}
function lightweightRowHtml(row,index){return `<tr ${datasetAttributes(row)} data-a-hydrate="pending"${index>=20?' hidden':''}><td colspan="8" class="history-record"></td></tr>`;}
function rowHtml(row,index){
 const d=toDataset(row),attrs=datasetAttributes(row),chart=`https://jp.tradingview.com/chart/?symbol=TSE%3A${encodeURIComponent(row.symbol)}`;
 // A missing analysis has its own exact symbol/day identity; no legacy cache lookup.
 const f=row.fundamental,exact=!identityHold(row)&&f?.auditStatus==='pass'&&f.symbol===row.symbol&&f.signalDate===row.signalDate&&typeof f.analysisCutoff==='string'&&f.analysisCutoff===row.analysisCutoff&&Number.isFinite(Date.parse(f.analysisCutoff))&&f.identity===`${row.signalDate}|${row.symbol}`;
 const analysis=exact?`<p>分析時点 ${html(f.analysisCutoff)}</p>${(f.fields||[]).map(field=>`<p><strong>${html(field.label)}</strong><br>${html(field.text)}</p>`).join('')}`:'<p>未作成</p>';
 const chartTitle=identityHold(row)?`${html(row.companyName)}(${html(row.symbol)}) 現在コード参照・当時対応未確認`:`<a href="${chart}" target="_blank" rel="noopener noreferrer">${html(row.companyName)}(${html(row.symbol)}) | TradingView チャート</a>`;
 const fundamental=`<button class="fundamental-toggle" data-fundamental-toggle type="button" aria-expanded="false">ファンダ分析</button><dialog class="fundamental-detail" aria-label="ファンダ分析の詳細"><button class="fundamental-close" type="button" aria-label="ファンダ分析を閉じる">×</button><div class="discord-message"><article class="discord-embed"><h4>${chartTitle}</h4><p>検出日 ${html(row.signalDate)}</p>${analysis}</article></div></dialog>`;
 const actions=fundamental+(identityHold(row)?'<span class="button-link" aria-disabled="true">チャート・照合保留</span>':`<a class="button-link" href="${chart}" target="_blank" rel="noopener noreferrer">チャート</a>`);
 const price=(v,status)=>v===''?endpointLabel(status):html(Number(v).toLocaleString('ja-JP',{maximumFractionDigits:12}))+'円';
 return `<tr ${attrs}${index>=20?' hidden':''}><td colspan="8" class="history-record"><div class="history-visible-grid"><div class="history-date" data-label="検出日"><div class="history-date-value">${html(row.signalDate)}</div><div class="actions history-date-actions">${actions}</div></div><div class="history-company"><strong><span class="symbol">${html(row.symbol)}</span> ${html(row.companyName)}</strong>${identityHold(row)?"<small>現在コード・現在名の参照／当時対応未確認</small>":""}<small>検出日 終値 ${price(d.signalActualClose)}</small><small>候補 ${html(row.candidateDate)} / 反発確認 ${html(row.triggerDate??'未確認')}</small></div><div data-label="該当モード"><span class="badge">A</span><small data-scenario-shares>100株で試算</small></div><div data-label="状況"><span class="status pending">${statusLabel(row)}</span></div><div data-label="試算開始日・始値">${html(d.entryDate||'未確認')}<small>${price(d.entryOpen)}</small><small data-scenario-cost></small></div><div data-label="5営業日後 終値">${html(d.d5Date)}<small>${price(d.d5Close,d.aD5Status)}</small></div><div data-label="6営業日後 始値">${html(d.d6Date)}<small>${price(d.d6Open,d.aD6Status)}</small></div><div data-label="成績" class="number"><small data-scenario-endpoint-label>6営業日後 始値</small><strong data-scenario-pl>未作成</strong><small data-scenario-return></small></div></div><button class="history-mobile-toggle" type="button" data-cloud-history-details aria-expanded="false">詳細を見る</button></td></tr>`;
}
function scopes(input){const years=[...new Set(input.rows.map(r=>Number(r.signalDate.slice(0,4))))].sort();return{all:{label:input.status==='missing'?'A検出 接続待ち':'A検出の記録期間',years:null},...Object.fromEntries(years.map(y=>[String(y),{label:`${y}年`,years:[y]}]))};}
// Staged default policy; no UI/server defaults are changed before a proposal is frozen.
function resolveInitialTrial({serverStatus,serverValues,localStatus,localValues,proposedDefaults,proposalVerified=false}){
 if(serverStatus==='present')return{source:'saved-server',values:structuredClone(serverValues),defaultsApplied:false};
 if(localStatus==='present')return{source:serverStatus==='absent'?'saved-local':'saved-local-server-unconfirmed',values:structuredClone(localValues),defaultsApplied:false};
 if(serverStatus!=='absent'||localStatus!=='absent')return{source:'unconfirmed',values:null,defaultsApplied:false};
 if(!proposalVerified||!proposedDefaults)return{source:'proposal-not-frozen',values:null,defaultsApplied:false};
 return{source:'new-user-default',values:structuredClone(proposedDefaults),defaultsApplied:true};
}
module.exports={validateInput,toDataset,rowHtml,lightweightRowHtml,datasetAttributes,statusLabel,endpointLabel,identityHold,scopes,missingInput,resolveInitialTrial};
