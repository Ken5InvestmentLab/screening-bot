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
function metrics(m){return '<div class="kpis">'+[['純損益',m?.net_profit,'円'],['最大下落率',m?.max_drawdown_pct,'%'],['勝率',m?.win_rate_pct,'%'],['決済件数',m?.trade_count,'件']].map(([k,v,u])=>'<div class="kpi"><span>'+k+'</span><b>'+number(v)+(v==null?'':u)+'</b></div>').join('')+'</div>';}
function chart(rows){
 if(!Array.isArray(rows)||!rows.length)return '<p class="note">日次推移はまだありません。</p>';
 const valid=rows.filter(r=>typeof r.equity_yen==='number'&&Number.isFinite(r.equity_yen));if(!valid.length)return '<p class="note">日次推移は未確定です。</p>';
 const min=Math.min(...valid.map(r=>r.equity_yen)),max=Math.max(...valid.map(r=>r.equity_yen)),span=Math.max(max-min,1);let segments=[],points=[];
 rows.forEach((r,i)=>{if(r.equity_yen==null){if(points.length)segments.push(points);points=[];return;}points.push((48+ i/Math.max(rows.length-1,1)*844).toFixed(2)+','+(220-(r.equity_yen-min)/span*180).toFixed(2));});if(points.length)segments.push(points);
 return '<div class="research-chart"><svg role="img" aria-label="仮想資金の日次推移。欠測区間は線を結びません" viewBox="0 0 940 275" style="width:100%;height:auto"><text x="48" y="22" fill="currentColor">'+esc(number(max))+'円</text><text x="48" y="252" fill="currentColor">'+esc(rows[0].date)+'</text><text text-anchor="end" x="892" y="252" fill="currentColor">'+esc(rows.at(-1).date)+'</text>'+segments.map(p=>'<polyline fill="none" stroke="var(--blue)" stroke-width="3" points="'+p.join(' ')+'"/>').join('')+'</svg></div>';
}
function history(rows){return '<div class="history-table-wrap"><table id="detection-table"><thead><tr><th>検出日</th><th>銘柄</th><th>状態</th><th>詳細</th></tr></thead><tbody>'+rows.map(r=>'<tr><td data-label="検出日">'+esc(r.date)+'</td><th scope="row">'+esc(r.symbol)+'</th><td data-label="状態">'+esc(states[r.state]??r.state)+'</td><td><details><summary>確認</summary><p>検出日 '+esc(r.date)+'<br>銘柄 '+esc(r.symbol)+'<br>状態 '+esc(states[r.state]??r.state)+'</p><p class="note">共通の検出情報です。本人の保有・注文ではありません。</p></details></td></tr>').join('')+'</tbody></table></div>';}
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
function currentWatch(rows) {
  if (!rows.length) return '<p class="cloud-empty">監視中の銘柄なし</p>';
  return '<div class="table-wrap"><table class="scenario-table"><thead><tr><th scope="col">銘柄</th>'
    + '<th scope="col">監視開始日</th><th scope="col">状況</th></tr></thead><tbody>'
    + rows.map(({symbol, date, state}) => '<tr><td data-label="銘柄">' + esc(symbol) + '</td>'
      + '<td data-label="監視開始日"><time datetime="' + esc(date) + '">' + esc(date) + '</time></td>'
      + '<td data-label="状況">' + movementBadge(state) + '</td></tr>').join('') + '</tbody></table></div>';
}
function dashboardLevel(selected) {
  return '<fieldset id="member-preset" class="member-level"><legend>運用レベル</legend><div class="member-level-options">'
    + Object.entries(names).map(([value, label]) => '<label><input type="radio" name="new-a-dashboard-level" value="'
      + value + '"' + (value === selected ? ' checked' : '') + '><span>' + label + '</span></label>').join('')
    + '</div></fieldset>';
}
function premiumHome({asOf, selected, rows, chartRows, dashboard}, current) {
  if (!Array.isArray(dashboard?.today) || !Array.isArray(dashboard?.watching)) throw Error('dashboard_unavailable');
  const latest = chartRows?.at(-1);
  const holdingCount = current.resolved && latest?.date === asOf
    && Number.isSafeInteger(latest.holding_count) && latest.holding_count >= 0 ? latest.holding_count : null;
  const m = current.resolved ? current.metrics : null;
  const summary = dashboardKpis([['純損益',m?.net_profit,'円'],['最大DD',m?.max_drawdown_pct,'%'],
    ['勝率',m?.win_rate_pct,'%'],['保有件数',holdingCount,'件']]);
  return '<section class="panel today-summary" aria-labelledby="member-today-title">'
    + '<div class="cloud-section-head"><h1 id="member-today-title">ダッシュボード</h1>'
    + dashboardLevel(selected) + '</div>' + summary + '</section>'
    + '<section class="panel" id="new-a-current" aria-labelledby="member-activity-heading"><div class="cloud-section-head">'
    + '<h2 id="member-activity-heading">対象日の動き</h2><div class="cloud-meta"><span class="badge">対象 '
    + '<time datetime="' + esc(asOf) + '">' + esc(asOf) + '</time></span></div></div>'
    + movementSummary(dashboard.today) + movementCards(dashboard.today) + '</section>'
    + '<section class="panel" aria-labelledby="member-watching-heading"><div class="cloud-section-head">'
    + '<h2 id="member-watching-heading">現在の監視</h2><span class="badge">' + dashboard.watching.length + '銘柄</span></div>'
    + currentWatch(dashboard.watching) + '</section>'
    + '<section class="panel"><h2>日次資金推移</h2>' + chart(chartRows) + '</section>'
    + '<section class="panel"><h2>検出履歴</h2>' + history(rows) + '</section>';
}
function freeHome(rows = null) {
  return heading('home') + '<section class="panel member-locked"><h2>今日の動きと監視状況</h2>'
    + '<p>今日の検出と監視中の銘柄はPremium会員限定です。</p>' + purchase + '</section>'
    + (rows === null ? '' : '<section class="panel"><h2>終了済みの検出履歴</h2>'
      + (rows.length ? history(rows) : '<p class="note">表示できる検出履歴はありません。</p>') + '</section>');
}
function view({mode,access,asOf,presets,selected,rows,chartRows,personal,dashboard}){
 if(access==='free')return mode==='home'?freeHome(rows):lockedPage(mode);
 if(access!=='premium')throw Error('access_unavailable');
 const current=presets.find(x=>x.preset===selected);if(!current)throw Error('preset_unavailable');
 if(mode==='home')return premiumHome({asOf,selected,rows,chartRows,dashboard},current);
 return heading(mode, asOf)+'<section class="panel"><label>見方を変える <select id="member-preset">'+presets.map(x=>'<option value="'+esc(x.preset)+'"'+(x.preset===selected?' selected':'')+'>'+esc(names[x.preset]??x.preset)+'</option>').join('')+'</select></label><p class="note">共通条件による仮想試算です。売買や通知の設定は変更しません。</p>'+metrics(current.resolved?current.metrics:null)+'</section><section class="panel"><h2>日次資金推移</h2>'+chart(chartRows)+'</section>'+(mode==='analytics'?'<section class="panel"><h2>あなたの保存条件による試算</h2>'+(personal?metrics(personal):'<p role="status">現在のデータ・保存条件に一致する結果を準備中、または未確定です。以前の結果では代用しません。</p>')+'</section><section class="panel"><h2>3つの見方の比較</h2>'+presets.map(x=>'<h3>'+esc(names[x.preset]??x.preset)+'</h3>'+metrics(x.resolved?x.metrics:null)).join('')+'</section>':'<section class="panel"><h2>検出履歴</h2>'+history(rows)+'</section>');
}
g.NewAMemberPresentation={metrics,chart,history,view,lockedPage,freeHome};
if(typeof module!=='undefined')module.exports=g.NewAMemberPresentation;
})(globalThis);
