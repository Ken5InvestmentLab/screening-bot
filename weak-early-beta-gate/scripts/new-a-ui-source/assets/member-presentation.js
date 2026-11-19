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
function metrics(m){return '<div class="kpis">'+[['純損益',m?.net_profit,'円'],['最大下落率',m?.max_drawdown_pct,'%'],['勝率',m?.win_rate_pct,'%'],['決済件数',m?.trade_count,'件']].map(([k,v,u])=>'<div class="kpi"><span>'+k+'</span><b>'+number(v)+(v==null?'':u)+'</b></div>').join('')+'</div>';}
function chart(rows){
 if(!Array.isArray(rows)||!rows.length)return '<p class="note">日次推移はまだありません。</p>';
 const valid=rows.filter(r=>typeof r.equity_yen==='number'&&Number.isFinite(r.equity_yen));if(!valid.length)return '<p class="note">日次推移は未確定です。</p>';
 const min=Math.min(...valid.map(r=>r.equity_yen)),max=Math.max(...valid.map(r=>r.equity_yen)),span=Math.max(max-min,1);let segments=[],points=[];
 rows.forEach((r,i)=>{if(r.equity_yen==null){if(points.length)segments.push(points);points=[];return;}points.push((48+ i/Math.max(rows.length-1,1)*844).toFixed(2)+','+(220-(r.equity_yen-min)/span*180).toFixed(2));});if(points.length)segments.push(points);
 return '<div class="research-chart"><svg role="img" aria-label="仮想資金の日次推移。欠測区間は線を結びません" viewBox="0 0 940 275" style="width:100%;height:auto"><text x="48" y="22" fill="currentColor">'+esc(number(max))+'円</text><text x="48" y="252" fill="currentColor">'+esc(rows[0].date)+'</text><text text-anchor="end" x="892" y="252" fill="currentColor">'+esc(rows.at(-1).date)+'</text>'+segments.map(p=>'<polyline fill="none" stroke="var(--blue)" stroke-width="3" points="'+p.join(' ')+'"/>').join('')+'</svg></div>';
}
function history(rows){return '<div class="history-table-wrap"><table id="detection-table"><thead><tr><th>検出日</th><th>銘柄</th><th>状態</th><th>詳細</th></tr></thead><tbody>'+rows.map(r=>'<tr><td data-label="検出日">'+esc(r.date)+'</td><th scope="row">'+esc(r.symbol)+'</th><td data-label="状態">'+esc(states[r.state]??r.state)+'</td><td><details><summary>確認</summary><p>検出日 '+esc(r.date)+'<br>銘柄 '+esc(r.symbol)+'<br>状態 '+esc(states[r.state]??r.state)+'</p><p class="note">共通の検出情報です。本人の保有・注文ではありません。</p></details></td></tr>').join('')+'</tbody></table></div>';}
const purchase = '<a class="member-purchase" href="/purchase">Premiumのアクセス権を購入する</a>';
const titleFor = mode => mode === 'analytics' ? 'アナリティクス' : mode === 'settings' ? '設定' : 'ダッシュボード';
function heading(mode, asOf) {
  return '<div class="page-heading"><h1>' + titleFor(mode) + '</h1>'
    + (asOf ? '<span>対象日 ' + esc(asOf) + '</span>' : '') + '</div>';
}
function lockedPage(mode) {
  return heading(mode) + '<section class="panel member-locked"><p>' + titleFor(mode)
    + 'はPremium会員限定です。</p>' + purchase + '</section>';
}
function dashboardList(rows, empty) {
  if (!Array.isArray(rows)) throw Error('dashboard_unavailable');
  if (!rows.length) return '<p class="note">' + empty + '</p>';
  return '<ul class="member-detections">' + rows.map(row => '<li><b>' + esc(row.symbol) + '</b><span>'
    + esc(states[row.state] ?? row.state) + '</span><time datetime="' + esc(row.date) + '">'
    + esc(row.date) + '</time></li>').join('') + '</ul>';
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
 const activity=mode==='home'?'<div class="member-dashboard-panels"><section class="panel"><h2>今日の動き</h2>'
   +dashboardList(dashboard?.today,'検出はありません。')+'</section><section class="panel"><h2>最新の監視状況</h2>'
   +dashboardList(dashboard?.watching,'監視中の銘柄はありません。')+'</section></div>':'';
 return heading(mode, asOf)+activity+'<section class="panel"><label>見方を変える <select id="member-preset">'+presets.map(x=>'<option value="'+esc(x.preset)+'"'+(x.preset===selected?' selected':'')+'>'+esc(names[x.preset]??x.preset)+'</option>').join('')+'</select></label><p class="note">共通条件による仮想試算です。売買や通知の設定は変更しません。</p>'+metrics(current.resolved?current.metrics:null)+'</section><section class="panel"><h2>日次資金推移</h2>'+chart(chartRows)+'</section>'+(mode==='analytics'?'<section class="panel"><h2>あなたの保存条件による試算</h2>'+(personal?metrics(personal):'<p role="status">現在のデータ・保存条件に一致する結果を準備中、または未確定です。以前の結果では代用しません。</p>')+'</section><section class="panel"><h2>3つの見方の比較</h2>'+presets.map(x=>'<h3>'+esc(names[x.preset]??x.preset)+'</h3>'+metrics(x.resolved?x.metrics:null)).join('')+'</section>':'<section class="panel"><h2>検出履歴</h2>'+history(rows)+'</section>');
}
g.NewAMemberPresentation={metrics,chart,history,view,lockedPage,freeHome};
if(typeof module!=='undefined')module.exports=g.NewAMemberPresentation;
})(globalThis);
