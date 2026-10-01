'use strict';
const data = JSON.parse(document.getElementById('data').textContent);
const featureName = {all45:'既存45特徴量',price_market:'価格・市場39特徴量',augmented:'因果特徴を追加した53項目'};
const featureShort = {all45:'既存45',price_market:'価格・市場39',augmented:'拡張53'};
const objectiveName = {top025:'当日の上位0.25%',win:'コスト0.2%を超える利益',return:'収益回帰'};
const rankName = {score:'予測順位',volume:'低出来高倍率',body:'低実体',blend:'両者の順位平均',fusion:'両者の一致'};
const num = v => v == null ? '—' : Number(v).toFixed(2);
const pct = v => v == null ? '—' : `${num(v)}%`;
const capName = n => n ? `${n.toLocaleString()}円以下` : '上限なし';
const endpoint = s => s ? `検出${s.split('_')[0].slice(1)}営業日後${s.endsWith('open')?'始値':'終値'}` : '—';
const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function setting(c){return `${c.learner.toUpperCase()} ${c.size} · ${capName(c.cap)}<br>${featureName[c.features]}<br>${objectiveName[c.objective]}／教師${c.horizon}日`;}
function policy(p){return `${rankName[p.rank]}、予測CDF≥${p.gate}、市場5日中央値${p.market==null?'制約なし':`≤${pct(p.market*100)}`}、銘柄10日騰落${p.retmax==null?'制約なし':`≤${pct(p.retmax*100)}`}、市場1日中央値${p.medmin==null?'制約なし':`≥${pct(p.medmin*100)}`}、最低出来高${p.vol}倍、同銘柄休止${p.cooldown}営業日`;}
function render(){
  const stage=document.getElementById('stage').value, cap=document.getElementById('cap').value, sort=document.getElementById('sort').value;
  const subset=data.records.filter(r=>r.stage===stage&&(cap==='all'||String(r.config.cap)===cap));
  const rows=[...subset].sort((a,b)=>(b.best?.metrics[sort]??-Infinity)-(a.best?.metrics[sort]??-Infinity));
  document.getElementById('scope').textContent=`比較完了 ${subset.length}設定 ／ 品質通過候補あり ${subset.filter(r=>r.best).length}設定。未計算の設定は含みません。`;
  document.getElementById('results').innerHTML=rows.map(r=>{
    const b=r.best,m=b?.metrics;
    if(!b)return `<tr><td class="setting">${setting(r.config)}</td><td colspan="9">品質基準を通過する政策・出口なし</td></tr>`;
    return `<tr><td class="setting">${setting(r.config)}<details><summary>検出条件を見る</summary>${esc(policy(b.policy))}<br>品質通過 ${r.qualifying}通り ／ 2023年${m.n2023}件・2024年${m.n2024}件</details></td><td>${endpoint(b.endpoint)}</td><td>${m.n}</td><td>${pct(m.win_pct)}</td><td>${pct(m.mean_pct)}</td><td>${pct(m.median_pct)}</td><td>${pct(m.loss10_pct)}</td><td>${pct(m.top3_ex_mean_pct)}</td><td>${Math.round(m.required_capital_yen).toLocaleString()}円</td><td>${num(m.utility)}</td></tr>`;
  }).join('')||'<tr><td colspan="10">この段階・価格上限の比較は未完了です。</td></tr>';
  const qualified=rows.filter(r=>r.best).slice(0,8), scale=Math.max(1,...qualified.map(r=>Math.max(Math.abs(r.best.metrics.mean_pct),Math.abs(r.best.metrics.top3_ex_mean_pct))));
  document.getElementById('chart').innerHTML=qualified.map(r=>{
    const m=r.best.metrics,c=r.config;
    return ['mean_pct','top3_ex_mean_pct'].map((key,i)=>`<div class="barrow"><small>${c.learner.toUpperCase()}・${capName(c.cap)}・${featureShort[c.features]}／${i?'上位3除外':'平均'}</small><div class="track"><div class="fill ${m[key]<0?'negative':''}" style="width:${Math.abs(m[key])/scale*100}%"></div></div><span class="value">${pct(m[key])}</span></div>`).join('');
  }).join('')||'<p>品質基準を通過した候補がまだありません。</p>';
}
for(const id of ['stage','cap','sort'])document.getElementById(id).addEventListener('change',render);
render();
if(!data.final){document.getElementById('validation').innerHTML='<p>候補を固定する前のため未計算です。2025年の成績を見て、同年に有利な条件へ選び直しません。</p>';}
else{
  const rows=data.final.candidates;
  document.getElementById('validation').innerHTML=`<p>2025年は固定後の検証、2026年は閲覧済みの参考評価。採用は未確認です。</p><div class="scroll"><table><thead><tr><th>固定候補</th><th>年</th><th>出口</th><th>件数</th><th>勝率</th><th>平均</th><th>中央値</th><th>大敗率</th><th>上位3除外</th><th>現行同入力</th><th>公開参考水準</th></tr></thead><tbody>${rows.map(m=>`<tr><td>候補${m.candidate+1}</td><td>${m.year}</td><td>${endpoint(m.endpoint)}</td><td>${m.n}</td><td>${pct(m.win_pct)}</td><td>${pct(m.mean_pct)}</td><td>${pct(m.median_pct)}</td><td>${pct(m.loss10_pct)}</td><td>${pct(m.top3_ex_mean_pct)}</td><td>${m.comparable_baseline_pass?'通過':'未達'}</td><td>${m.published_reference_screen_pass?'通過':'未達'}</td></tr>`).join('')}</tbody></table></div>`;
}
