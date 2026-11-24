/* Display the exact dashboard projections returned by the Worker. */
(function(g){'use strict';
const fundamentalText = require('../fundamental-text.cjs');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=(v, maximumFractionDigits=2)=>typeof v==='number'&&Number.isFinite(v)
  ? v.toLocaleString('ja-JP',{maximumFractionDigits}) : '未確定';
const wholeYen=v=>number(typeof v==='number' && Math.abs(v)<0.5 ? 0 : v, 0);
const names={defensive:'守り',medium:'中間',return_priority:'利益優先'};
const states={
 WATCHING:'監視中',TRIGGERED:'検出',EXPIRED:'期限終了',UP_ESCAPED:'上抜け',DOWN_INVALIDATED:'下抜け',REFERENCE_ONLY:'参考',
 WATCH_STARTED:'監視開始',ENTRY_CANDIDATE:'仮想買付候補',WATCH_TERMINAL:'監視終了',HOLD_STARTED:'仮想保有開始',HOLD_ENDED:'仮想保有終了',
 DATA_GAP:'価格未確認',BASIS_CHANGED:'価格基準変更',IDENTITY_CHANGED:'銘柄情報変更',
};
function metrics(m, annualized) {
 const items=[['純損益',m?.net_profit,'円'],['最大下落率',m?.max_drawdown_pct,'%'],
  ['勝率',m?.win_rate_pct,'%'],['決済件数',m?.trade_count,'件']];
 if(annualized!==undefined)items.splice(1,0,['年率換算損益率',annualized,'%','累積損益率を経過年数で割った値']);
 return '<div class="kpis">'+items.map(([label,value,unit,hint])=>'<div class="kpi"><span'
  +(hint?' title="'+hint+'"':'')+'>'+label+'</span><b>'+(unit==='円'?wholeYen(value):number(value))+(value==null?'':unit)
  +'</b></div>').join('')+'</div>';
}
function chart(rows){
 if(!Array.isArray(rows)||!rows.length)return '<p class="note">日次推移はまだありません。</p>';
 const valid=rows.filter(r=>typeof r.equity_yen==='number'&&Number.isFinite(r.equity_yen));if(!valid.length)return '<p class="note">日次推移は未確定です。</p>';
 const min=Math.min(...valid.map(r=>r.equity_yen)),max=Math.max(...valid.map(r=>r.equity_yen)),span=Math.max(max-min,1);let segments=[],points=[];
 rows.forEach((r,i)=>{if(r.equity_yen==null){if(points.length)segments.push(points);points=[];return;}points.push((48+ i/Math.max(rows.length-1,1)*844).toFixed(2)+','+(220-(r.equity_yen-min)/span*180).toFixed(2));});if(points.length)segments.push(points);
 return '<div class="research-chart"><svg role="img" aria-label="仮想資金の日次推移。欠測区間は線を結びません" viewBox="0 0 940 275" style="width:100%;height:auto"><text x="48" y="22" fill="currentColor">'+wholeYen(max)+'円</text><text x="48" y="252" fill="currentColor">'+esc(rows[0].date)+'</text><text text-anchor="end" x="892" y="252" fill="currentColor">'+esc(rows.at(-1).date)+'</text>'+segments.map(p=>'<polyline fill="none" stroke="var(--blue)" stroke-width="3" points="'+p.join(' ')+'"/>').join('')+'</svg></div>';
}
const fundamentalLabels = ['材料インパクト','事業概要','足元材料','ファンダ要点','注意点','開示リンク','Sources'];
const day = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && Number.isFinite(Date.parse(value + 'T00:00:00Z'))
  && new Date(value + 'T00:00:00Z').toISOString().slice(0,10) === value;
// The chart and summary represent the same selected preset and data generation.
function annualizedProfitPct(current, rows) {
 if(current.resolved!==true||!Array.isArray(rows)||!day(current.from)||!day(current.through)
   ||current.through<=current.from)return null;
 const first=rows[0],last=rows.at(-1);
 if(first?.date!==current.from||last?.date!==current.through)return null;
 const start=first.equity_yen,end=last.equity_yen,profit=current.metrics?.net_profit;
 // The projection rounds each money amount independently to two decimal places.
 if(!Number.isFinite(start)||start<=0||!Number.isFinite(end)||end<0||!Number.isFinite(profit)
   ||Math.abs(end-start-profit)>0.02)return null;
 const elapsed=Date.parse(current.through+'T00:00:00Z')-Date.parse(current.from+'T00:00:00Z');
 const years=elapsed/(365.2425*86_400_000);
 const annualized=profit/start*100/years;
 return Number.isFinite(annualized)?annualized:null;
}
const exactKeys = (value, keys) => value !== null && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value,key));
function referencePayload(value, item) {
  const keys = ['as_of','generation','markup'];
  const hasItem = exactKeys(value,[...keys,'item']) && value.item === item;
  const maxMarkup = 512 * 1024;
  return (hasItem || exactKeys(value,keys)) && day(value.as_of)
    && typeof value.generation === 'string' && /^[a-f0-9]{64}$/.test(value.generation)
    && typeof value.markup === 'string' && value.markup.trim().length !== 0
    && value.markup.length <= maxMarkup
    && new TextEncoder().encode(value.markup).byteLength <= maxMarkup;
}
function fundamentalItem(page, row) {
  return Number.isSafeInteger(page) && page >= 1 && page <= 200 && row?.has_fundamental === true
    && day(row.date) && typeof row.symbol === 'string' && /^[0-9A-Z]{4}$/.test(row.symbol)
    ? [page,row.date,row.symbol].join('.') : null;
}
function fundamentalSelector(item) {
  const match = typeof item === 'string' && /^([1-9]\d{0,2})\.(\d{4}-\d{2}-\d{2})\.([0-9A-Z]{4})$/.exec(item);
  return match && Number(match[1]) <= 200 && day(match[2]) ? { date: match[2], symbol: match[3] } : null;
}
const historyStates = {
  ...states, TRIGGERED:'支持反発確認', EXPIRED:'監視期限', UP_ESCAPED:'上方離脱', DOWN_INVALIDATED:'下方無効',
  DAILY_FILLED_CAP:'1日新規上限', FILLED:'約定', CAPACITY:'保有上限', LOT_EXCEEDS_ALLOCATION:'注文上限超過',
  CASH_INSUFFICIENT:'資金不足', DUPLICATE_HELD:'保有中', PRICE_CAP:'株価上限', SIGNAL_PRICE_UNVERIFIED:'株価未確認',
  UNFILLED:'未約定', UNFILLED_UNCERTAIN_ONE_PRICE:'一値・約定未確認', HALTED_UNRESOLVED:'未解決で停止',
  IDENTITY_UNVERIFIED:'銘柄対応未確認',
};
const positive = value => Number.isFinite(value) && value > 0;
const tuple = (value, length) => Array.isArray(value) && value.length === length;
function referenceHistory(markup, page, asOf, basicRows, fromIndex = false) {
  let result;
  try { result = JSON.parse(markup); } catch { return null; }
  if (!exactKeys(result,['page','rows']) || result.page !== page || !Array.isArray(result.rows) || !Array.isArray(basicRows)
    || result.rows.length > 100 || result.rows.length !== basicRows.length) return null;
  const keys = ['date','symbol','companyName','chartAllowed','signalClose','d5','d6','levels'];
  const encoder = new TextEncoder();
  const valid = result.rows.every((row,index) => {
    const basic = basicRows[index];
    const hasItem = exactKeys(row,[...keys,'item']);
    if ((!hasItem && !exactKeys(row,keys)) || !day(row.date) || row.date > asOf || row.date !== basic?.date
      || typeof row.symbol !== 'string' || !/^[0-9A-Z]{4}$/.test(row.symbol) || row.symbol !== basic?.symbol
      || typeof row.chartAllowed !== 'boolean' || (row.signalClose !== null && !positive(row.signalClose))
      || (row.companyName !== null && (typeof row.companyName !== 'string' || !row.companyName.trim()
        || row.companyName.length > 256 || encoder.encode(row.companyName).length > 256))
      || (fromIndex && row.companyName !== basic.companyName)
      || (hasItem && (!row.chartAllowed || typeof row.item !== 'string'
        || row.item !== fundamentalItem(page,fromIndex ? { ...basic, has_fundamental:true } : basic)))
      || !tuple(row.levels,3)) return false;
    const validDate = date => day(date) && date >= row.date && date <= asOf;
    const validPoint = point => point === null || (tuple(point,3) && validDate(point[0])
      && positive(point[1]) && typeof point[2] === 'boolean');
    if (!validPoint(row.d5) || !validPoint(row.d6)) return false;
    return row.levels.every(level => {
      if (!tuple(level,4)) return false;
      const [state,selected,entry,exit] = level;
      return typeof state === 'string' && Object.hasOwn(historyStates,state) && typeof selected === 'boolean'
        && (entry === null || (tuple(entry,4) && validDate(entry[0]) && entry.slice(1).every(positive)))
        && (exit === null || (entry !== null && tuple(exit,4) && validDate(exit[0]) && exit[0] >= entry[0]
          && positive(exit[1]) && Number.isFinite(exit[2]) && Number.isFinite(exit[3])));
    });
  });
  return valid ? result.rows : null;
}
function referenceHistoryIndex(markup, asOf, pageCount) {
  let index;
  try { index = JSON.parse(markup); } catch { return null; }
  if (!exactKeys(index,['names','rows']) || !Array.isArray(index.names) || !Array.isArray(index.rows)
    || index.rows.length > 20000 || index.names.length > index.rows.length
    || Math.max(1,Math.ceil(index.rows.length / 100)) !== pageCount) return null;
  const encoder = new TextEncoder();
  if (!index.names.every(name => typeof name === 'string' && name.trim() && name.length <= 256
    && encoder.encode(name).length <= 256)) return null;
  const identities = new Set();
  for (const row of index.rows) {
    if (!tuple(row,3) || !day(row[0]) || row[0] > asOf || typeof row[1] !== 'string' || !/^[0-9A-Z]{4}$/.test(row[1])
      || (row[2] !== null && (!Number.isSafeInteger(row[2]) || row[2] < 0 || row[2] >= index.names.length))) return null;
    const identity = row[0] + '.' + row[1];
    if (identities.has(identity)) return null;
    identities.add(identity);
  }
  return index;
}
function matchingHistory(index, { symbol, from, through, order }) {
  const query = symbol.normalize('NFKC').trim().toLowerCase();
  const matches = index.rows.flatMap(([date,code,name], offset) =>
    ((!from || date >= from) && (!through || date <= through)
      && (!query || code.toLowerCase().includes(query) || (name !== null
        && index.names[name].normalize('NFKC').toLowerCase().includes(query)))) ? [offset] : []);
  if (order === 'oldest') matches.sort((left,right) => index.rows[left][0].localeCompare(index.rows[right][0]));
  if (order === 'symbol') matches.sort((left,right) => index.rows[left][1].localeCompare(index.rows[right][1]));
  return matches;
}
function sortReferenceCards(cards, order) {
  const compare=(a,b)=>String(a??'').localeCompare(String(b??''),'ja',{numeric:true});
  return [...cards].sort((a,b)=>{
    const left=a.dataset,right=b.dataset;
    const primary=order==='name'?compare(left.referenceName,right.referenceName)
      :order==='symbol'?0:(left.referenceKind==='ENTRY_CANDIDATE'?0:1)-(right.referenceKind==='ENTRY_CANDIDATE'?0:1);
    return primary||compare(left.referenceSymbol,right.referenceSymbol)||compare(left.referenceKind,right.referenceKind);
  });
}
function fundamentalImpactClass(fields) {
  const impact = fields.find(field => field?.label === '材料インパクト')?.text;
  if (typeof impact !== 'string') return '';
  const category = impact.trim().split(/[\s:：。、「」]/u, 1)[0];
  if (/^(?:ポジティブ(?:材料)?|positive)$/iu.test(category)) return ' impact-positive';
  if (/^(?:ネガティブ(?:材料)?|negative)$/iu.test(category)) return ' impact-negative';
  if (/^(?:様子見|中立|混在(?:[/・]要確認)?|要確認|watch|neutral|mixed)$/iu.test(category)) return ' impact-watch';
  return '';
}
function fundamentalMarkup(report, {date,symbol,asOf,generation}) {
  const encoder = new TextEncoder();
  const boundedText = (value, limit) => typeof value === 'string' && value.trim().length > 0
    && value.length <= limit && encoder.encode(value).length <= limit;
  if (!exactKeys(report,['as_of','generation','date','symbol','company_name','analysis_cutoff','fields'])
    || report.generation !== generation || report.as_of !== asOf || report.date !== date || report.symbol !== symbol
    || (report.company_name !== null && !boundedText(report.company_name,256))
    || typeof report.analysis_cutoff !== 'string' || report.analysis_cutoff.length > 40
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(report.analysis_cutoff)
    || !day(report.analysis_cutoff.slice(0,10)) || !Number.isFinite(Date.parse(report.analysis_cutoff))
    || !Array.isArray(report.fields) || report.fields.length !== fundamentalLabels.length
    || !report.fields.every((field,index) => exactKeys(field,['label','text'])
      && field.label === fundamentalLabels[index] && boundedText(field.text,8192))
    || encoder.encode(JSON.stringify(report)).length > 16384) return null;
  const heading = report.company_name === null ? symbol : report.company_name + '(' + symbol + ')';
  const fields = report.fields.map(field => '<dt>' + esc(field.label) + '</dt><dd>'
    + fundamentalText(field) + '</dd>').join('');
  return '<button class="fundamental-close" type="button" aria-label="ファンダ分析を閉じる" autofocus>×</button>'
    + '<div class="discord-message"><article class="discord-embed'
    + fundamentalImpactClass(report.fields) + '"><h4>' + esc(heading) + '</h4>'
    + '<p>検出日 ' + esc(date) + '</p><p>分析時点 ' + esc(report.analysis_cutoff) + '</p>'
    + '<dl>' + fields + '</dl></article></div>';
}
function fundamentalButton(item) {
  return item ? '<button class="fundamental-toggle cloud-stock-action" type="button" aria-haspopup="dialog" aria-expanded="false" data-member-fundamental="'
    + esc(item) + '">ファンダ</button>' : '';
}
function history(rows, premiumPage) {
  return '<div class="history-table-wrap"><table id="detection-table"><thead><tr><th>検出日</th><th>銘柄</th>'
    + '<th>状態</th><th>詳細</th></tr></thead><tbody>' + rows.map(row => {
      const item = fundamentalItem(premiumPage,row);
      const action = item ? '<div class="actions">' + fundamentalButton(item) + '</div>' : '';
      const state = esc(Object.hasOwn(states,row.state) ? states[row.state] : row.state);
      return '<tr><td data-label="検出日">' + esc(row.date) + action + '</td><th scope="row">' + esc(row.symbol)
        + '</th><td data-label="状態">' + state + '</td><td><details><summary>確認</summary><p>検出日 ' + esc(row.date)
        + '<br>銘柄 ' + esc(row.symbol) + '<br>状態 ' + state + '</p>'
        + '<p class="note">共通の検出情報です。本人の保有・注文ではありません。</p></details></td></tr>';
    }).join('') + '</tbody></table></div>';
}
const historyColumns = [
  '検出日','銘柄','試算条件','状況','試算開始日・始値','5営業日後 終値','6営業日後 始値','試算損益',
];
function historyReferenceCell(point) {
  if (point === null) return '—';
  const [date, price, priceOnly] = point;
  return esc(date) + '<small>' + number(price) + '円 · ' + (priceOnly ? '価格のみ参照' : '参照') + '</small>';
}
function referenceHistoryTable(rows, preset) {
  if (rows.length === 0) return '<p class="note">該当する銘柄がありません。</p>';
  const level = Object.keys(names).indexOf(preset);
  const headers = historyColumns.map((label,index) => '<div' + (index === 7 ? ' class="number"' : '') + '>'
    + label + (index === 5 || index === 6 ? '<small>参照</small>' : '') + '</div>').join('');
  const records = rows.map(row => {
    const [state, selected, entry, exit] = row.levels[level];
    const status = state === 'FILLED' ? (exit ? '仮想決済済' : '仮想保有中') : historyStates[state];
    const trial = selected ? (entry ? number(entry[2]) + '株で試算' : '試算対象') : '—';
    const details = entry ? esc(entry[0]) + '<small>寄付 ' + number(entry[1]) + '円</small><small>'
      + number(entry[2]) + '株 · ' + number(entry[3]) + '円</small>' : '—';
    const result = exit ? '<strong>' + number(exit[2]) + '円</strong><small>' + number(exit[3]*100) + '%</small>'
      + '<div class="cloud-exit-details"><small>決済 ' + esc(exit[0]) + ' · ' + number(exit[1]) + '円</small></div>'
      : entry ? '<strong>仮想保有中</strong>' : '—';
    const close = row.signalClose === null ? '未確認' : number(row.signalClose) + '円';
    const identification = row.chartAllowed ? '' : '<small>当時の銘柄名を確認中</small>';
    const chart = row.chartAllowed
      ? '<a class="button-link cloud-stock-action" href="https://jp.tradingview.com/chart/?symbol=TSE%3A'
        + encodeURIComponent(row.symbol) + '" target="_blank" rel="noopener noreferrer">チャート</a>'
      : '<span class="button-link" aria-disabled="true">チャート保留</span>';
    return '<tr><td colspan="8" class="history-record"><div class="history-visible-grid">'
      + '<div class="history-date" data-label="検出日"><div class="history-date-value">' + esc(row.date)
      + '</div><div class="actions history-date-actions">' + fundamentalButton(row.item) + chart + '</div></div>'
      + '<div class="history-company"><strong><span class="symbol">' + esc(row.symbol) + '</span>'
      + (row.companyName === null ? '' : ' ' + esc(row.companyName)) + '</strong><small>検出日終値 ' + close + '</small>'
      + identification + '</div><div data-label="試算条件"><small>' + trial + '</small></div>'
      + '<div data-label="状況"><span class="status pending">' + status + '</span></div>'
      + '<div data-label="試算開始日・始値">' + details + '</div>'
      + '<div data-label="5営業日後 終値">' + historyReferenceCell(row.d5) + '</div>'
      + '<div data-label="6営業日後 始値">' + historyReferenceCell(row.d6) + '</div>'
      + '<div data-label="成績" class="number cloud-history-result">' + result + '</div></div>'
      + '<button type="button" class="history-mobile-toggle" data-member-history-details aria-expanded="false">詳細を見る</button></td></tr>';
  }).join('');
  return '<div class="history-details"><div class="table-wrap history-table-wrap"><table id="detection-table">'
    + '<thead><tr><th colspan="8"><div class="history-visible-grid">' + headers + '</div></th></tr></thead>'
    + '<tbody>' + records + '</tbody></table></div></div>';
}
function historyFilters() {
  return '<div class="filters" id="member-history-filters" role="group" aria-label="検出履歴の絞り込み">'
    + '<label class="filter-field"><span>銘柄</span><input type="search" data-history-filter="symbol" '
    + 'autocomplete="off" placeholder="証券コード・銘柄名で検索"></label>'
    + '<label class="filter-field"><span>開始日</span><input type="date" data-history-filter="from"></label>'
    + '<label class="filter-field"><span>終了日</span><input type="date" data-history-filter="through"></label>'
    + '<label class="filter-field"><span>並び順</span><select data-history-filter="order"><option value="newest">新しい順</option>'
    + '<option value="oldest">古い順</option><option value="symbol">証券コード順</option></select></label>'
    + '<button class="clear-search" type="button" data-history-clear>検索をクリア</button>'
    + '<output class="result-count" id="member-history-filter-status" aria-live="polite"></output></div>';
}
const purchase = '<a class="member-purchase" href="/purchase">Premiumアクセス権を購入する</a>';
const titleFor = mode => mode === 'analytics' ? 'アナリティクス' : mode === 'settings' ? '設定' : 'ダッシュボード';
function heading(mode, asOf) {
  return '<div class="page-heading"><h1>' + titleFor(mode) + '</h1>'
    + (asOf ? '<span>対象日 ' + esc(asOf) + '</span>' : '') + '</div>';
}
function lockedPage(mode) {
  return heading(mode) + '<section class="panel member-locked"><p>' + titleFor(mode)
    + 'はPremium会員限定です。</p>' + purchase + '</section>';
}
const movementTone = {
  WATCH_STARTED: 'watch-start', WATCH_TERMINAL: 'watch-end', HOLD_STARTED: 'hold-start', HOLD_ENDED: 'hold-end',
};
function movementBadge(state) {
  return '<span class="cloud-transition cloud-transition--' + movementTone[state] + '">'
    + states[state] + '</span>';
}
function movementSummary(rows) {
  const totals = Object.fromEntries(Object.keys(movementTone).map(state => [state, 0]));
  for (const {state} of rows) if (Object.hasOwn(totals, state)) totals[state]++;
  const holdingKnown = totals.HOLD_STARTED > 0 || totals.HOLD_ENDED > 0;
  return '<ul class="cloud-transition-summary" aria-label="対象日の件数">'
    + Object.entries(movementTone).map(([state, tone]) => '<li><span class="cloud-transition cloud-transition--'
      + tone + '">' + states[state] + ' <b>' + (state.startsWith('HOLD_') && !holdingKnown ? '未確定' : totals[state] + '件')
      + '</b></span></li>').join('') + '</ul>';
}
function movementCards(rows) {
  const stocks = new Map();
  for (const {symbol, state} of rows) {
    if (!Object.hasOwn(movementTone, state)) continue;
    if (!stocks.has(symbol)) stocks.set(symbol, []);
    stocks.get(symbol).push(state);
  }
  const cards = [...stocks].map(([symbol, changes]) => '<article><strong>' + esc(symbol) + '</strong>'
    + '<div class="cloud-transition-list">' + changes.map(state => '<div class="cloud-transition-row">'
      + movementBadge(state) + '</div>').join('') + '</div></article>').join('');
  return '<div class="cloud-stock-grid">' + (cards || '<p class="cloud-empty">確認済みの開始・終了はありません</p>') + '</div>';
}
function entryCandidates(rows) {
  const symbols = rows.filter(({state}) => state === 'ENTRY_CANDIDATE').map(({symbol}) => symbol);
  if (!symbols.length) return '';
  return '<details class="cloud-table-details cloud-reference-events"><summary>仮想買付候補</summary>'
    + '<ul class="cloud-transition-summary">' + symbols.map(symbol => '<li><span class="badge">' + esc(symbol)
      + '</span></li>').join('') + '</ul></details>';
}
function watchTable(rows, label) {
  return '<div class="table-wrap"><table class="scenario-table" aria-label="' + label + '">'
    + '<thead><tr><th scope="col">銘柄</th><th scope="col">監視開始日</th></tr></thead><tbody>'
    + rows.map(({symbol, date}) => '<tr><td data-label="銘柄">' + esc(symbol) + '</td>'
      + '<td data-label="監視開始日"><time datetime="' + esc(date) + '">' + esc(date) + '</time></td></tr>')
      .join('') + '</tbody></table></div>';
}
function currentWatch(rows) {
  if (!rows.length) return '<p class="cloud-empty">監視中の銘柄なし</p>';
  const visible = 8;
  const rest = rows.slice(visible);
  return watchTable(rows.slice(0, visible), '直近の監視銘柄')
    + (rest.length ? '<details class="cloud-table-details"><summary>残り' + rest.length + '銘柄</summary>'
      + watchTable(rest, '残りの監視銘柄') + '</details>' : '');
}
function operatingLevel(selected) {
  return '<fieldset id="member-preset" class="member-level"><legend>運用レベル</legend><div class="member-level-options">'
    + Object.entries(names).map(([value, label]) => '<label><input type="radio" name="new-a-dashboard-level" value="'
      + value + '"' + (value === selected ? ' checked' : '') + '><span>' + label + '</span></label>').join('')
    + '</div></fieldset>';
}
function premiumHeading(mode, asOf, selected) {
  return '<div class="page-heading"><div><p class="note">データ更新日 <time datetime="'
    + esc(asOf) + '">' + esc(asOf) + '</time></p><h1>' + titleFor(mode) + '</h1></div>'
    + operatingLevel(selected) + '</div>';
}
function historyContent(rows, historyPage, referenceRows, selected) {
  return referenceRows
    ? historyFilters() + '<div id="member-history-results">' + referenceHistoryTable(referenceRows, selected) + '</div>'
    : history(rows, historyPage);
}
function historyPanel(rows, historyPage, referenceRows, selected, deferHistory) {
  return '<section class="panel" id="history" tabindex="-1" aria-labelledby="member-history-heading">'
    + '<h2 id="member-history-heading">検出履歴</h2>'
    + (deferHistory
      ? '<p id="member-history-state" role="status"></p>'
        + '<button type="button" class="settings-secondary" id="member-history-open">検出履歴を表示</button>'
        + '<div id="member-history-content"></div>'
      : historyContent(rows, historyPage, referenceRows, selected)) + '</section>';
}
function premiumHome({asOf, selected, rows, chartRows, dashboard, historyPage, referenceHistoryRows, deferHistory}, current) {
  if (!Array.isArray(dashboard?.today) || !Array.isArray(dashboard?.watching)) throw Error('dashboard_unavailable');
  const latest = chartRows?.at(-1);
  const holdingCount = current.resolved && latest?.date === asOf
    && Number.isSafeInteger(latest.holding_count) && latest.holding_count >= 0 ? latest.holding_count : null;
  const holdings = holdingCount === null ? '未確定' : number(holdingCount) + '銘柄';
  return premiumHeading('home',asOf,selected)
    + '<section class="panel" id="new-a-current" aria-labelledby="member-activity-heading"><div class="cloud-section-head">'
    + '<h2 id="member-activity-heading">対象日の動き</h2></div>'
    + movementSummary(dashboard.today) + movementCards(dashboard.today) + entryCandidates(dashboard.today) + '</section>'
    + '<section class="panel" aria-labelledby="member-holdings-heading"><div class="cloud-section-head">'
    + '<h2 id="member-holdings-heading">現在の仮想保有</h2><span class="badge">' + holdings + '</span></div></section>'
    + '<section class="panel" aria-labelledby="member-watching-heading"><div class="cloud-section-head">'
    + '<h2 id="member-watching-heading">現在の監視</h2><span class="badge">' + dashboard.watching.length + '銘柄</span></div>'
    + currentWatch(dashboard.watching) + '</section>'
    + historyPanel(rows, historyPage, referenceHistoryRows, selected, deferHistory);
}
function lockedStockPanels() {
  const sections = [
    ['activity', '対象日の動き'], ['holdings', '現在の仮想保有'], ['watching', '現在の監視'],
  ];
  return sections.map(([key, label]) => {
    const id = 'member-locked-' + key;
    return '<section class="panel" aria-labelledby="' + id + '"><div class="cloud-section-head"><h2 id="' + id
      + '">' + label + '</h2></div><details class="member-locked-row"><summary aria-label="' + label
      + 'の詳細を見る"><span class="member-locked-message">銘柄・詳細はPremium限定</span>'
      + '<span class="member-locked-action">詳細を見る</span></summary><div class="member-locked-upgrade">'
      + purchase + '</div></details></section>';
  }).join('');
}
function freeHistoryRows(rows) {
  const closed = rows.filter(row => row.state === 'HOLD_ENDED');
  return closed.length ? history(closed) : '<p class="note">このページに仮想保有終了銘柄はありません。</p>';
}
function freeHome(rows = null) {
  return heading('home') + lockedStockPanels()
    + '<section class="panel" id="history" aria-labelledby="member-history-heading"><h2 id="member-history-heading">検出履歴</h2>'
    + '<p class="note">仮想保有が終了した銘柄を表示しています。</p><div id="member-free-history">'
    + (rows === null ? '' : freeHistoryRows(rows)) + '</div></section>';
}
function view({mode,access,asOf,presets,selected,rows,chartRows,personal,dashboard,historyPage,reference,referenceHistoryRows,deferHistory}){
 if(access==='free'){
  if(mode==='home')return freeHome(rows);
  if(mode!=='analytics'||reference!==true)return lockedPage(mode);
 }else if(access!=='premium')throw Error('access_unavailable');
 if(reference===true)return premiumHeading(mode,asOf,selected)+'<div id="member-reference-content"></div>'
  +(mode==='home'?historyPanel(rows,historyPage,referenceHistoryRows,selected,deferHistory):'');
 const current=presets.find(x=>x.preset===selected);if(!current)throw Error('preset_unavailable');
 if(mode==='home')return premiumHome({asOf,selected,rows,chartRows,dashboard,historyPage,referenceHistoryRows,deferHistory},current);
 return premiumHeading(mode,asOf,selected)+'<section class="panel">'+metrics(current.resolved?current.metrics:null,annualizedProfitPct(current,chartRows))
  +'</section><section class="panel"><h2>日次資金推移</h2>'+chart(chartRows)+'</section><section class="panel"><h2>あなたの保存条件による試算</h2>'
  +(personal?metrics(personal):'<p role="status">保存した条件による試算結果を準備中です。</p>')+'</section>';
}
g.NewAMemberPresentation={metrics,chart,history,view,lockedPage,freeHome,freeHistoryRows,operatingLevel,wholeYen,referencePayload,referenceHistory,
  referenceHistoryIndex,matchingHistory,referenceHistoryTable,historyContent,sortReferenceCards,
  fundamentalItem,fundamentalSelector,fundamentalMarkup};
if(typeof module!=='undefined')module.exports=g.NewAMemberPresentation;
})(globalThis);
