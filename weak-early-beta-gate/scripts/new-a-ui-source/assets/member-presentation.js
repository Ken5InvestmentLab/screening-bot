/* Display the exact dashboard projections returned by the Worker. */
(function(g){'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=v=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('ja-JP',{maximumFractionDigits:2}):'未確定';
const names={defensive:'守り',medium:'中間',return_priority:'利益優先'};
const states={
 WATCHING:'監視中',TRIGGERED:'検出',EXPIRED:'期限終了',UP_ESCAPED:'上抜け',DOWN_INVALIDATED:'下抜け',REFERENCE_ONLY:'参考',
 WATCH_STARTED:'監視開始',ENTRY_CANDIDATE:'仮想買付候補',WATCH_TERMINAL:'監視終了',HOLD_STARTED:'仮想保有開始',HOLD_ENDED:'仮想保有終了',
 DATA_GAP:'価格未確認',BASIS_CHANGED:'価格基準変更',IDENTITY_CHANGED:'銘柄情報変更',
};
function dashboardKpis(entries) {
 return '<div class="kpis today-kpis">' + entries.map(([label, value, unit]) =>
  '<div class="kpi"><small>' + label + '</small><b>' + number(value) + (value == null ? '' : unit)
   + '</b></div>').join('') + '</div>';
}
function metrics(m, annualized) {
 const items=[['純損益',m?.net_profit,'円'],['最大下落率',m?.max_drawdown_pct,'%'],
  ['勝率',m?.win_rate_pct,'%'],['決済件数',m?.trade_count,'件']];
 if(annualized!==undefined)items.splice(1,0,['年率換算損益率',annualized,'%','累積損益率を経過年数で割った値']);
 return '<div class="kpis">'+items.map(([label,value,unit,hint])=>'<div class="kpi"><span'
  +(hint?' title="'+hint+'"':'')+'>'+label+'</span><b>'+number(value)+(value==null?'':unit)
  +'</b></div>').join('')+'</div>';
}
function chart(rows){
 if(!Array.isArray(rows)||!rows.length)return '<p class="note">日次推移はまだありません。</p>';
 const valid=rows.filter(r=>typeof r.equity_yen==='number'&&Number.isFinite(r.equity_yen));if(!valid.length)return '<p class="note">日次推移は未確定です。</p>';
 const min=Math.min(...valid.map(r=>r.equity_yen)),max=Math.max(...valid.map(r=>r.equity_yen)),span=Math.max(max-min,1);let segments=[],points=[];
 rows.forEach((r,i)=>{if(r.equity_yen==null){if(points.length)segments.push(points);points=[];return;}points.push((48+ i/Math.max(rows.length-1,1)*844).toFixed(2)+','+(220-(r.equity_yen-min)/span*180).toFixed(2));});if(points.length)segments.push(points);
 return '<div class="research-chart"><svg role="img" aria-label="仮想資金の日次推移。欠測区間は線を結びません" viewBox="0 0 940 275" style="width:100%;height:auto"><text x="48" y="22" fill="currentColor">'+esc(number(max))+'円</text><text x="48" y="252" fill="currentColor">'+esc(rows[0].date)+'</text><text text-anchor="end" x="892" y="252" fill="currentColor">'+esc(rows.at(-1).date)+'</text>'+segments.map(p=>'<polyline fill="none" stroke="var(--blue)" stroke-width="3" points="'+p.join(' ')+'"/>').join('')+'</svg></div>';
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
function fundamentalItem(page, row) {
  return Number.isSafeInteger(page) && page >= 1 && page <= 999999 && row?.has_fundamental === true
    && day(row.date) && typeof row.symbol === 'string' && /^[0-9A-Z]{4}$/.test(row.symbol)
    ? [page,row.date,row.symbol].join('.') : null;
}
function fundamentalText({label,text}) {
  const references = label === '開示リンク' || label === 'Sources';
  return text.split(/\r\n?|\n/u).map(line => {
    if (!references) return esc(line);
    // The verified formatter emits one titled Markdown link per bullet.
    const link = /^[ \t]*(?:・[ \t]*)?\[((?:\\[\[\]]|[^\\[\]]|\\(?![\[\]]))+)\]\((https:\/\/[^\s()<>\\\x00-\x1f\x7f]+)\)[ \t]*$/u.exec(line);
    if (!link) return esc(line);
    const title = link[1].replace(/\\([\[\]])/gu,'$1').trim();
    if (!title || /^(?:https?:\/\/|www\.)/iu.test(title)) return esc(line);
    let address;
    try { address = new URL(link[2]); } catch { return esc(line); }
    if (address.protocol !== 'https:' || !address.hostname || address.username || address.password) return esc(line);
    return '・<a href="' + esc(address.href) + '" target="_blank" rel="noopener noreferrer">' + esc(title) + '</a>';
  }).join('<br>');
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
function history(rows, premiumPage) {
  return '<div class="history-table-wrap"><table id="detection-table"><thead><tr><th>検出日</th><th>銘柄</th>'
    + '<th>状態</th><th>詳細</th></tr></thead><tbody>' + rows.map(row => {
      const item = fundamentalItem(premiumPage,row);
      const action = item ? '<div class="actions"><button class="fundamental-toggle cloud-stock-action" type="button" aria-haspopup="dialog" aria-expanded="false" data-member-fundamental="'
        + esc(item) + '">ファンダ</button></div>' : '';
      const state = esc(Object.hasOwn(states,row.state) ? states[row.state] : row.state);
      return '<tr><td data-label="検出日">' + esc(row.date) + action + '</td><th scope="row">' + esc(row.symbol)
        + '</th><td data-label="状態">' + state + '</td><td><details><summary>確認</summary><p>検出日 ' + esc(row.date)
        + '<br>銘柄 ' + esc(row.symbol) + '<br>状態 ' + state + '</p>'
        + '<p class="note">共通の検出情報です。本人の保有・注文ではありません。</p></details></td></tr>';
    }).join('') + '</tbody></table></div>';
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
  const tone = Object.hasOwn(movementTone, state) ? movementTone[state] : null;
  const label = Object.hasOwn(states, state) ? states[state] : state;
  return '<span class="' + (tone ? 'cloud-transition cloud-transition--' + tone : 'badge') + '">'
    + esc(label) + '</span>';
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
    if (!stocks.has(symbol)) stocks.set(symbol, []);
    stocks.get(symbol).push(state);
  }
  const cards = [...stocks].map(([symbol, changes]) => '<article><strong>' + esc(symbol) + '</strong>'
    + '<div class="cloud-transition-list">' + changes.map(state => '<div class="cloud-transition-row">'
      + movementBadge(state) + '</div>').join('') + '</div></article>').join('');
  return '<div class="cloud-stock-grid">' + (cards || '<p class="cloud-empty">確認済みの開始・終了はありません</p>') + '</div>';
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
function dashboardLevel(selected) {
  return '<fieldset id="member-preset" class="member-level"><legend>運用レベル</legend><div class="member-level-options">'
    + Object.entries(names).map(([value, label]) => '<label><input type="radio" name="new-a-dashboard-level" value="'
      + value + '"' + (value === selected ? ' checked' : '') + '><span>' + label + '</span></label>').join('')
    + '</div></fieldset>';
}
function premiumHome({asOf, selected, rows, chartRows, dashboard, historyPage}, current) {
  if (!Array.isArray(dashboard?.today) || !Array.isArray(dashboard?.watching)) throw Error('dashboard_unavailable');
  const latest = chartRows?.at(-1);
  const holdingCount = current.resolved && latest?.date === asOf
    && Number.isSafeInteger(latest.holding_count) && latest.holding_count >= 0 ? latest.holding_count : null;
  const m = current.resolved ? current.metrics : null;
  const summary = dashboardKpis([['純損益',m?.net_profit,'円'],['最大DD',m?.max_drawdown_pct,'%'],
    ['勝率',m?.win_rate_pct,'%'],['保有件数',holdingCount,'件']]);
  return '<section class="panel today-summary" aria-labelledby="member-today-title">'
    + '<p class="note">データ更新日 <time datetime="' + esc(asOf) + '">' + esc(asOf) + '</time></p>'
    + '<div class="cloud-section-head"><h1 id="member-today-title">ダッシュボード</h1>'
    + dashboardLevel(selected) + '</div>' + summary + '</section>'
    + '<section class="panel" id="new-a-current" aria-labelledby="member-activity-heading"><div class="cloud-section-head">'
    + '<h2 id="member-activity-heading">対象日の動き</h2></div>'
    + movementSummary(dashboard.today) + movementCards(dashboard.today) + '</section>'
    + '<section class="panel" aria-labelledby="member-watching-heading"><div class="cloud-section-head">'
    + '<h2 id="member-watching-heading">現在の監視</h2><span class="badge">' + dashboard.watching.length + '銘柄</span></div>'
    + currentWatch(dashboard.watching) + '</section>'
    + '<section class="panel"><h2>検出履歴</h2>' + history(rows,historyPage) + '</section>';
}
function freeHome(rows = null) {
  const closed = rows?.filter(row => row.state === 'HOLD_ENDED');
  return heading('home') + '<section class="panel member-locked"><h2>今日の動きと監視状況</h2>'
    + '<p>今日の検出と監視中の銘柄はPremium会員限定です。</p>' + purchase + '</section>'
    + (closed === undefined ? '' : '<section class="panel"><h2>仮想保有終了銘柄</h2>'
      + (closed.length ? history(closed) : '<p class="note">このページに仮想保有終了銘柄はありません。</p>') + '</section>');
}
function view({mode,access,asOf,presets,selected,rows,chartRows,personal,dashboard,historyPage}){
 if(access==='free')return mode==='home'?freeHome(rows):lockedPage(mode);
 if(access!=='premium')throw Error('access_unavailable');
 const current=presets.find(x=>x.preset===selected);if(!current)throw Error('preset_unavailable');
 if(mode==='home')return premiumHome({asOf,selected,rows,chartRows,dashboard,historyPage},current);
 return heading(mode, asOf)+'<section class="panel"><label>見方を変える <select id="member-preset">'+presets.map(x=>'<option value="'+esc(x.preset)+'"'+(x.preset===selected?' selected':'')+'>'+esc(names[x.preset]??x.preset)+'</option>').join('')+'</select></label><p class="note">共通条件による仮想試算です。売買や通知の設定は変更しません。</p>'+metrics(current.resolved?current.metrics:null,mode==='analytics'?annualizedProfitPct(current,chartRows):undefined)+'</section><section class="panel"><h2>日次資金推移</h2>'+chart(chartRows)+'</section>'+(mode==='analytics'?'<section class="panel"><h2>あなたの保存条件による試算</h2>'+(personal?metrics(personal):'<p role="status">現在のデータ・保存条件に一致する結果を準備中、または未確定です。以前の結果では代用しません。</p>')+'</section><section class="panel"><h2>3つの見方の比較</h2>'+presets.map(x=>'<h3>'+esc(names[x.preset]??x.preset)+'</h3>'+metrics(x.resolved?x.metrics:null)).join('')+'</section>':'<section class="panel"><h2>検出履歴</h2>'+history(rows)+'</section>');
}
g.NewAMemberPresentation={metrics,chart,history,view,lockedPage,freeHome,fundamentalItem,fundamentalMarkup};
if(typeof module!=='undefined')module.exports=g.NewAMemberPresentation;
})(globalThis);
