/* Public presentation calculations. Inputs are verified audience-visible
 * history attributes, never canonical ledger or private source receipts. */
const CloudScenario = (() => {
  const number = value => value === '' || value === null || value === undefined ? null :
    Number.isFinite(Number(value)) ? Number(value) : null;
  const sum = values => values.reduce((a, b) => a + b, 0);
  const median = values => { const a = [...values].sort((a,b) => a-b), n = a.length;
    return n ? (a[Math.floor((n-1)/2)] + a[Math.floor(n/2)]) / 2 : null; };
  const pct = v => v === null || !Number.isFinite(v) ? '—' : `${v.toFixed(2)}%`;
  const yen = v => v === null || !Number.isFinite(v) ? '—' : `${Math.round(v).toLocaleString('ja-JP')}円`;
  const text = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function validate(shares = 100, cost = 0) {
    shares = number(shares); cost = number(cost);
    if (!Number.isInteger(shares) || shares < 100 || shares > 1000000 || shares % 100) throw new Error('株数は100〜1,000,000株の範囲で、100株ずつ入力してください。');
    if (cost === null || cost < 0 || cost > 10 || !/^\d+(?:\.\d{1,2})?$/.test(String(cost))) throw new Error('売買コストは0〜10%の範囲で、小数点以下2桁まで入力してください。');
    return {baseShares: shares, costPercent: cost};
  }
  function trade(dataset, preferences) {
    const d6 = preferences.exitKey === 'd6_open', factor = preferences.baseShares / 100,
      rate = preferences.costPercent / 100;
    const c = number(d6 ? dataset.d6EntryCost : dataset.entryCost),
      p = number(d6 ? dataset.d6Proceeds : dataset.d5Proceeds),
      receiptReturn = number(d6 ? dataset.d6Return : dataset.d5Return);
    const cost = c !== null && c > 0 ? c * factor * (1 + rate) : null;
    const proceeds = p !== null && p > 0 && receiptReturn !== null ? p * factor * (1 - rate) : null;
    const pl = cost !== null && proceeds !== null ? proceeds - cost : null;
    return {signal: dataset.date, symbol: dataset.symbol, name: dataset.name,
      selectors: (dataset.selectors || '').split(' ').filter(Boolean),
      historical: dataset.historical === 'true', reference: dataset.reference === 'true',
      entry: (d6 ? dataset.d6EntryDate : dataset.entryDate) || '',
      exit: (d6 ? dataset.d6Date : dataset.d5Date) || '',
      entryOpen: number(d6 ? dataset.d6EntryOpen : dataset.entryOpen),
      exitPrice: number(d6 ? dataset.d6Open : dataset.d5Close),
      signalClose: number(dataset.signalActualClose), grossCost: c === null ? null : c * factor,
      grossProceeds: p === null || receiptReturn === null ? null : p * factor,
      entryFee: c === null ? null : c * factor * rate,
      exitFee: p === null || receiptReturn === null ? null : p * factor * rate,
      exitShares: number(d6 ? dataset.d6ExitShares : dataset.d5ExitShares) === null ? null :
        number(d6 ? dataset.d6ExitShares : dataset.d5ExitShares) * factor,
      cost, proceeds, pl, returnPct: pl === null ? null : pl / cost * 100};
  }
  function risk(trades) {
    if (!trades.length) return {capital: null, initialCash: null, maxLots: 0, maxSymbols: 0};
    if (trades.some(t => !t.entry || !t.exit || t.cost === null || t.proceeds === null))
      return {capital:null, initialCash:null, maxLots:null, maxSymbols:null};
    const events = new Map();
    const at = day => { if (!events.has(day)) events.set(day, {buy:[],sell:[]}); return events.get(day); };
    trades.forEach(t => { at(t.entry).buy.push(t); at(t.exit).sell.push(t); });
    let principal=0,capital=0,cash=0,minimum=0,lots=0,maxLots=0,maxSymbols=0;
    const active = new Map();
    for (const day of [...events.keys()].sort()) {
      const event=events.get(day);
      // Purchases precede sale receipts, including D6's same-day opening auctions.
      for (const t of event.buy) { principal+=t.cost;cash-=t.cost;lots++;active.set(t.symbol,(active.get(t.symbol)||0)+1); }
      capital=Math.max(capital,principal);minimum=Math.min(minimum,cash);
      maxLots=Math.max(maxLots,lots);maxSymbols=Math.max(maxSymbols,active.size);
      for (const t of event.sell) { principal-=t.cost;cash+=t.proceeds;lots--;const n=active.get(t.symbol)-1;n?active.set(t.symbol,n):active.delete(t.symbol); }
      minimum=Math.min(minimum,cash);
    }
    return {capital,initialCash:-minimum,maxLots,maxSymbols};
  }
  function summarize(trades, generated) {
    const done = trades.filter(t => t.pl !== null), returns=done.map(t=>t.returnPct), pls=done.map(t=>t.pl),
      wins=done.filter(t=>t.pl>0), losses=done.filter(t=>t.pl<0), n=done.length;
    const average = values => values.length ? sum(values)/values.length : null;
    const total = sum(pls), r=risk(done), days = new Map();
    done.forEach(t => days.set(t.exit,(days.get(t.exit)||0)+t.pl));
    let realised=0,peak=0,drawdown=0;
    const curve=[];
    if (done.length) { const first=[...days.keys()].sort()[0], earliest=done.map(t=>t.entry).sort()[0];
      const baseline=earliest<first?earliest:new Date(Date.parse(first+'T00:00:00Z')-86400000).toISOString().slice(0,10);
      curve.push({date:baseline,value:0}); }
    for(const day of [...days.keys()].sort()){realised+=days.get(day);peak=Math.max(peak,realised);drawdown=Math.max(drawdown,peak-realised);curve.push({date:day,value:realised});}
    const dates=trades.map(t=>t.signal).filter(Boolean).sort(), exits=trades.map(t=>t.exit).filter(Boolean).sort();
    const observed=dates.length ? [dates.at(-1),exits.at(-1)||dates.at(-1)].sort().at(-1) : null;
    const end=observed ? [observed,generated.slice(0,10)].sort()[0] : null;
    const years=dates.length ? Math.max((Date.parse(end)-Date.parse(dates[0]))/86400000/365.2425,1/365.2425) : null;
    const capitalReturn = r.capital ? total/r.capital*100 : null;
    return {n,pending:trades.length-n,cash_pl_100_yen:total,mean_pct:average(returns),median_pct:median(returns),
      win_pct:n?wins.length/n*100:null,average_win_pct:average(wins.map(t=>t.returnPct)),average_loss_pct:average(losses.map(t=>t.returnPct)),
      average_win_yen:average(wins.map(t=>t.pl)),average_loss_yen:average(losses.map(t=>t.pl)),
      total_win_yen:sum(wins.map(t=>t.pl)),total_loss_yen:sum(losses.map(t=>t.pl)),
      payoff_ratio:wins.length&&losses.length?average(wins.map(t=>t.returnPct))/Math.abs(average(losses.map(t=>t.returnPct))):null,
      required_capital_yen:r.capital,minimum_initial_cash_yen:r.initialCash,max_lots:r.maxLots,max_symbols:r.maxSymbols,
      max_drawdown_yen:n?drawdown:null,worst_pl_yen:n?Math.min(...pls):null,
      profit_excluding_best3_yen:n?total-sum([...pls].sort((a,b)=>b-a).slice(0,3)):null,
      top3_ex_mean_pct:n>3?average([...returns].sort((a,b)=>b-a).slice(3)):null,
      max_up_pct:n?Math.max(...returns):null,max_down_pct:n?Math.min(...returns):null,
      plus10_pct:n?returns.filter(v=>v>=10).length/n*100:null,plus20_pct:n?returns.filter(v=>v>=20).length/n*100:null,
      minus10_pct:n?returns.filter(v=>v<=-10).length/n*100:null,minus20_pct:n?returns.filter(v=>v<=-20).length/n*100:null,
      capital_return_pct:capitalReturn,simple_annualized_pct:capitalReturn===null?null:capitalReturn/years,
      total_entry_cost_yen:sum(done.map(t=>t.cost)),curve,
      equityCurve:r.capital===null?[]:curve.map(p=>({date:p.date,value:r.capital+p.value}))};
  }
  function calculate(datasets, prefs, view, payload) {
    validate(prefs.baseShares,prefs.costPercent);
    const years=view.yearScope==='all'?null:payload.scopes[view.yearScope].years;
    const visible=datasets.filter(d => (!years||years.includes(Number(d.date.slice(0,4)))) &&
      (prefs.priceCapYen===null || d.signalPriceVerified==='true'&&number(d.signalActualClose)!==null&&number(d.signalActualClose)<=prefs.priceCapYen));
    const trades=visible.map(d=>trade(d,prefs)), eligible=trades.filter(t=>!t.reference), stacked=eligible.flatMap(t=>t.selectors.map(()=>t));
    const strategies={unique:summarize(eligible,payload.generated),stacked:summarize(stacked,payload.generated)};
    const groups=(key, list)=> [...new Set(list.map(t=>t.signal.slice(0,key==='year'?4:7)))].sort().map(period=>({period,
      unique:summarize(list.filter(t=>t.signal.startsWith(period)),payload.generated),
      stacked:summarize(list.filter(t=>t.signal.startsWith(period)).flatMap(t=>t.selectors.map(()=>t)),payload.generated)}));
    const yearsData=groups('year',eligible), monthly=groups('month',eligible);
    const overlap=Array.from({length:5},(_,index)=>{const count=index+1,items=eligible.filter(t=>t.selectors.length===count);return {count,...summarize(items,payload.generated)};});
    return {trades,eligible,strategies,annual:yearsData,monthly,overlap,referenceCount:trades.length-eligible.length};
  }
  const table=(headers,rows)=>`<table class="scenario-table" ${rows.length>20?'data-paginated-table':''}><thead><tr>${headers.map(h=>`<th>${text(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(v=>`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  function line(data, field='curve', allocations=['unique','stacked']) {
    const all=allocations.flatMap(k=>data.strategies[k][field]);
    if (!all.length) return '<p class="scenario-empty">価格を取得した結果がまだありません。</p>';
    const W=900,H=300,pad=55,dates=all.map(p=>Date.parse(p.date)),minX=Math.min(...dates),maxX=Math.max(...dates),
      values=[0,...all.map(p=>p.value)],lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1,
      x=d=>pad+(Date.parse(d)-minX)/(maxX-minX||1)*(W-2*pad),y=v=>H-pad-(v-lo)/span*(H-2*pad);
    // Step changes reflect only realised cash flows; no invented daily interpolation.
    const paths=allocations.map(k=>{const points=data.strategies[k][field];
      const d=points.map((p,j)=>`${j?'H':'M'}${x(p.date).toFixed(2)}${j?` V${y(p.value).toFixed(2)}`:` ${y(p.value).toFixed(2)}`}`).join(' ');
      return `<path data-cloud-allocation="${k}" d="${d}" fill="none" stroke="${k==='stacked'?'#7959df':'#0ba9a7'}" stroke-width="3"/>`;}).join('');
    return `<svg class="scenario-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="売却日ごとの累積損益"><title>売却日ごとの累積損益</title><line x1="${pad}" x2="${W-pad}" y1="${y(0)}" y2="${y(0)}" stroke="currentColor" opacity=".2"/>${paths}<text x="${pad}" y="38" fill="currentColor" font-size="13">${text(yen(hi))}</text><text x="${pad}" y="${H-18}" fill="currentColor" font-size="13">${text(new Date(minX).toISOString().slice(0,10))}</text><text x="${W-pad}" y="${H-18}" text-anchor="end" fill="currentColor" font-size="13">${text(new Date(maxX).toISOString().slice(0,10))}</text></svg>`;
  }
  function bars(rows, keys, labels, unit) {
    const values=[0,...rows.flatMap(r=>keys.map(k=>r[k])).filter(v=>v!==null)], lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1,W=900,H=290,pad=50;
    const y=v=>H-pad-(v-lo)/span*(H-pad-25),group=(W-2*pad)/Math.max(1,rows.length),width=Math.min(50,group*.65/keys.length);
    const items=rows.map((r,i)=>keys.map((k,j)=>r[k]===null?`<text x="${pad+group*(i+.5)}" y="${y(0)-8}" text-anchor="middle" fill="currentColor">—</text>`:
      `<rect x="${pad+group*(i+.5)+(j-keys.length/2)*width}" y="${Math.min(y(0),y(r[k]))}" width="${width-3}" height="${Math.abs(y(r[k])-y(0))}" fill="${r[k]<0?'#dc6177':k==='stacked'?'#7959df':'#0ba9a7'}"><title>${text(labels[j])}: ${text(unit==='円'?yen(r[k]):unit==='%'?pct(r[k]):r[k])}</title></rect>`).join('')+`<text x="${pad+group*(i+.5)}" y="${H-20}" text-anchor="middle" fill="currentColor" font-size="14">${text(r.label)}</text>`).join('');
    return `<svg class="scenario-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${text(labels.join('・'))}"><line x1="${pad}" x2="${W-pad}" y1="${y(0)}" y2="${y(0)}" stroke="currentColor" opacity=".2"/>${items}</svg>`;
  }
  function render(data,prefs,view,payload) {
    const labels={unique:`一律${prefs.baseShares.toLocaleString()}株`,stacked:`条件数×${prefs.baseShares.toLocaleString()}株`},u=data.strategies.unique,s=data.strategies.stacked;
    const allocations=view.allocation==='unique'||view.allocation==='stacked'?[view.allocation]:['unique','stacked'];
    const stat=(label,value)=>`<div><dt>${text(label)}</dt><dd>${value}</dd></div>`;
    const pair=allocations.map(k=>{const v=data.strategies[k];return `<article class="research-strategy" data-cloud-allocation="${k}"><h3><i class="research-swatch ${k}"></i>${text(labels[k])}</h3><div class="scenario-profit ${v.cash_pl_100_yen>=0?'positive':'negative'}">${yen(v.cash_pl_100_yen)}</div><dl class="scenario-stats">${stat('結果が出た銘柄',`${u.n}件`)}${stat('売却した取引',`${v.n}回`)}${stat('勝率',pct(v.win_pct))}${stat('平均の騰落率',pct(v.mean_pct))}${stat('中央値',pct(v.median_pct))}${stat('必要な資金',yen(v.required_capital_yen))}${stat('資金の増加率',pct(v.capital_return_pct))}${stat('年あたり（単純換算）',pct(v.simple_annualized_pct))}</dl></article>`;}).join('');
    const compare=(rows)=>table(['指標',...allocations.map(k=>labels[k])],rows.map(([label,key,format])=>[text(label),...allocations.map(k=>format(data.strategies[k][key]))]));
    const payoff=compare([['利益の合計','total_win_yen',yen],['損失の合計','total_loss_yen',yen],['勝ったときの平均損益','average_win_yen',yen],['負けたときの平均損益','average_loss_yen',yen],['平均の上昇率','average_win_pct',pct],['平均の下落率','average_loss_pct',pct],['平均利益 ÷ 平均損失の幅','payoff_ratio',v=>v===null?'—':`${v.toFixed(2)}倍`]]);
    const riskTable=compare([['必要な資金（買付額の最大）','required_capital_yen',yen],['売却代金を再利用した場合の開始資金','minimum_initial_cash_yen',yen],['累積損益の最大の落ち込み','max_drawdown_yen',yen],['最も大きい1取引の損失','worst_pl_yen',yen],['同時に保有した取引の最大数','max_lots',v=>v===null?'—':`${v}回`],['同時に保有した銘柄の最大数','max_symbols',v=>v===null?'—':`${v}銘柄`],['利益上位3取引を除いた損益','profit_excluding_best3_yen',yen]]);
    const payoffSummaries=allocations.map(k=>{const v=data.strategies[k];return `<article data-cloud-allocation="${k}"><h3>${text(labels[k])}</h3><dl class="scenario-stats">${stat('勝率',pct(v.win_pct))}${stat('平均の下落率',pct(v.average_loss_pct))}${stat('平均の上昇率',pct(v.average_win_pct))}</dl>${bars([{label:'平均損失',value:v.average_loss_pct},{label:'平均利益',value:v.average_win_pct}],['value'],[`${labels[k]}の騰落率`],'%')}</article>`;}).join('');
    const pagination='<div class="table-pagination"><button class="table-load-more" type="button">次の20件</button><button class="table-collapse" type="button" hidden>最初の20件へ</button><output class="table-result-count"></output></div>';
    const periodDetails=(rows,title)=>`<details class="scenario-details"><summary>${title}</summary><div class="table-wrap">${table(['期間','買付方法','取引数','損益','必要資金','平均','勝率'],rows.flatMap(r=>['unique','stacked'].filter(k=>view.allocation==='all'||view.allocation===k).map(k=>[text(r.period),text(labels[k]),`${r[k].n}`,yen(r[k].cash_pl_100_yen),yen(r[k].required_capital_yen),pct(r[k].mean_pct),pct(r[k].win_pct)])))}</div>${rows.length*(view.allocation==='all'?2:1)>20?pagination:''}</details>`;
    const historical=data.trades.filter(t=>t.historical).length, forward=data.trades.length-historical;
    const selectedDates=data.trades.map(t=>t.signal).sort(),period=selectedDates.length?`${selectedDates[0]}〜${payload.generated.slice(0,10)}`:'—';
    const scope=payload.scopes[view.yearScope]?.label||'記録期間すべて',title=payload.page==='analytics'?'アナリティクス':payload.page==='home'?'検出銘柄を確認':payload.modeNames[payload.page]||'モードの成績';
    if(payload.page==='home') {
      const dates=data.trades.map(t=>t.signal).sort(),latest=dates.at(-1)||'—';
      return `<section class="panel"><div class="research-heading"><h1>検出銘柄を確認</h1><a class="button-link" href="#history">銘柄を探す ↓</a></div><dl class="scenario-stats">${stat('表示中の銘柄',`${data.trades.length}件`)}${stat('最終検出日',text(latest))}${stat('結果が出た銘柄',`${u.n}件`)}${stat('保有中・価格待ち',`${u.pending}件`)}</dl><p class="note">価格待ちの銘柄は、売却価格を取得すると結果が表示されます。参考扱い${data.referenceCount}件は成績から除外します。</p><details class="scenario-details"><summary>過去データについて</summary><p>過去データによる試算 ${historical}件 / 運用開始後の記録 ${forward}件。2026年の過去データも、結果が分かった期間の試算です。</p></details></section>`;
    }
    const annualBars=bars(data.annual.map(r=>({label:r.period,unique:r.unique.cash_pl_100_yen,stacked:r.stacked.cash_pl_100_yen})),allocations,allocations.map(k=>labels[k]),'円');
    const overlapTable=table(['一致した条件','結果あり','平均','勝率',view.allocation==='stacked'?'損益（条件数に応じた株数）':'損益（同じ株数）'],data.overlap.map(r=>[`${r.count}個`,`${r.n}件`,pct(r.mean_pct),pct(r.win_pct),r.n?yen(r.cash_pl_100_yen*(view.allocation==='stacked'?r.count:1)):'—']));
    let html=`<div class="cloud-research-page"><div class="research-heading"><h1>${text(title)}</h1><span>${text(scope)} · ${text(period)}</span></div><p class="research-notice">表示中 ${data.trades.length}銘柄 · 結果あり ${u.n}件 · 保有中・価格待ち ${u.pending}件 · 参考扱い ${data.referenceCount}件（成績に含めません）</p><p class="note">過去データによる試算 ${historical}件 / 運用開始後の記録 ${forward}件。2026年の過去データも、結果が分かった期間の試算です。</p><section class="panel research-card" id="strategy-comparison"><h2>買付株数による比較</h2><div class="${allocations.length>1?'scenario-pair':''}">${pair}</div><h3>累積損益</h3>${line(data,'curve',allocations)}<p class="note">売却価格が取得できた取引の損益だけを加えています。保有中の値動きは含みません。</p></section>`;
    if(payload.page!=='home') html+=`<section class="panel research-card" id="payoff-structure"><h2>損小利大の構造</h2><div class="${allocations.length>1?'scenario-pair':''}">${payoffSummaries}</div>${payoff}<p class="note">勝率だけでなく、勝ったときの利益と負けたときの損失の幅を比べます。売買コストを含みます。</p></section><section class="panel research-card" id="annual-pl"><h2>年ごとの損益</h2>${annualBars}${periodDetails(data.annual,'年ごとの詳しい数字')}${periodDetails(data.monthly,'月ごとの詳しい数字')}</section><section class="panel research-card" id="capital-risk"><h2>必要な資金と損失の大きさ</h2>${riskTable}<p class="note">結果が出た取引を使った試算です。同日の買付資金を先に用意する計算です。保有中の損益・税金は含みません。</p></section><section class="panel research-card"><h2>条件の重なり</h2>${bars(data.overlap.map(r=>({label:`${r.count}個`,count:r.n})),['count'],['結果が出た銘柄数'],'件')}${bars(data.overlap.map(r=>({label:`${r.count}個`,average:r.mean_pct})),['average'],['平均の騰落率'],'%')}${overlapTable}</section><section class="panel research-card"><h2>株数を増やした影響</h2>${table(['比較','損益'],[['同じ株数で買付',yen(u.cash_pl_100_yen)],['条件の数だけ買付',yen(s.cash_pl_100_yen)],['総買付株数をそろえた参考値',s.n?yen(s.cash_pl_100_yen*u.n/s.n):'—'],['総買付金額をそろえた参考値',s.total_entry_cost_yen?yen(s.cash_pl_100_yen*u.total_entry_cost_yen/s.total_entry_cost_yen):'—']])}<p class="note">総株数や総金額の比率で縮小した参考比較です。同じ資金で実際に買えた結果ではありません。</p></section>`;
    if(payload.page!=='home')html+=`<section class="panel research-card" id="growth"><details class="scenario-details"><summary>必要資金から見た資産の推移</summary>${line(data,'equityCurve',allocations)}<p class="note">必要資金に売却後の損益を加えた試算です。保有中の値動きは含みません。</p></details></section>`;
    return html+'</div>';
  }
  const csvMetrics=(data,prefs,view)=>['全期間',...data.annual.map(r=>r.period),...data.monthly.map(r=>r.period)].flatMap(period=>{
    const source=period==='全期間'?data.strategies:[...data.annual,...data.monthly].find(r=>r.period===period);
    return ['unique','stacked'].filter(k=>view.allocation==='all'||view.allocation===k).map(k=>{const v=source[k];return {
      '期間':period,'買付方法':k==='unique'?'同じ株数':'条件数に応じた株数','基本株数':prefs.baseShares,'片道コスト%':prefs.costPercent,
      '検出日終値の上限':prefs.priceCapYen??'上限なし','売却価格の選択':prefs.exitKey==='d5_close'?'検出から5営業日後 終値':'検出から6営業日後 始値',
      '結果ありの取引数':v.n,'価格待ちの取引数':v.pending,'損益円':v.cash_pl_100_yen,'平均騰落率%':v.mean_pct,'中央値%':v.median_pct,'勝率%':v.win_pct,
      '必要資金円':v.required_capital_yen,'開始資金円':v.minimum_initial_cash_yen,'資金増加率%':v.capital_return_pct,'単純年率%':v.simple_annualized_pct,
      '+10%の割合':v.plus10_pct,'+20%の割合':v.plus20_pct,'-10%の割合':v.minus10_pct,'-20%の割合':v.minus20_pct,
      '最大上昇率%':v.max_up_pct,'最大下落率%':v.max_down_pct,'利益上位3取引を除く平均%':v.top3_ex_mean_pct,'最大の落ち込み円':v.max_drawdown_yen,
      '平均利益円':v.average_win_yen,'平均損失円':v.average_loss_yen,'平均利益と平均損失の幅の比':v.payoff_ratio};});});
  return {number,validate,trade,risk,summarize,calculate,render,csvMetrics,pct,yen};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=CloudScenario;
