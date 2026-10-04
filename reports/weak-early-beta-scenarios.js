/* Public presentation calculations. Inputs are verified audience-visible
 * history attributes, never canonical ledger or private source receipts. */
const CloudScenario = (() => {
  const number = value => value === '' || value === null || value === undefined ? null :
    Number.isFinite(Number(value)) ? Number(value) : null;
  const sum = values => values.reduce((a, b) => a + b, 0);
  const median = values => { const a = [...values].sort((a,b) => a-b), n = a.length;
    return n ? (a[Math.floor((n-1)/2)] + a[Math.floor(n/2)]) / 2 : null; };
  const pct = (v, signed=false) => v === null || !Number.isFinite(v) ? '—' : `${signed && v>0?'+':''}${v.toFixed(2)}%`;
  const yen = (v, signed=false) => v === null || !Number.isFinite(v) ? '—' : `${signed && v>0?'+':''}${Math.round(v).toLocaleString('ja-JP')}円`;
  const text = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function validate(shares = 100, cost = 0) {
    shares = number(shares); cost = number(cost);
    if (!Number.isInteger(shares) || shares < 100 || shares > 1000000 || shares % 100) throw new Error('株数は100〜1,000,000株の範囲で、100株ずつ入力してください。');
    if (cost === null || cost < 0 || cost > 10 || !/^\d+(?:\.\d{1,2})?$/.test(String(cost))) throw new Error('売買手数料は0〜10%の範囲で、小数点以下2桁まで入力してください。');
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
    const visible=datasets.filter(d => d.masked!=='true' && (!years||years.includes(Number(d.date.slice(0,4)))) &&
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
  const table=(headers,rows,detail=false)=>`<table class="scenario-table${detail?' analytics-detail-table':''}"${detail?` style="--detail-width:${headers.length*160+120}px"`:''} ${rows.length>20?'data-paginated-table':''}>${detail?'<colgroup><col style="width:160px"><col style="width:280px">'+headers.slice(2).map(()=>'<col style="width:160px">').join('')+'</colgroup>':''}<thead><tr>${headers.map(h=>`<th>${text(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((v,i)=>`<td data-label="${text(headers[i])}">${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  function line(data, field='curve', allocations=['unique','stacked'], domainAllocations=allocations) {
    const all=domainAllocations.flatMap(k=>data.strategies[k][field]);
    if(!all.length)return '<p class="scenario-empty">結果がまだありません。</p>';
    const W=900,H=320,L=115,R=35,T=30,B=60,dates=all.map(p=>Date.parse(p.date)),minX=Math.min(...dates),maxX=Math.max(...dates),values=all.map(p=>p.value);
    let lo=Math.min(...values),hi=Math.max(...values),pad=Math.max((hi-lo)*.08,1000);lo-=pad;hi+=pad;
    const x=d=>L+(Date.parse(d)-minX)/(maxX-minX||1)*(W-L-R),y=v=>H-B-(v-lo)/(hi-lo)*(H-T-B);
    const grid=Array.from({length:4},(_,i)=>{const value=lo+(hi-lo)*i/3,Y=y(value);return `<line x1="${L}" x2="${W-R}" y1="${Y}" y2="${Y}" class="grid-line"/><text x="${L-12}" y="${Y+6}" text-anchor="end" class="axis-label">${(value/10000).toFixed(1)}</text>`;}).join('');
    const paths=allocations.map(k=>{const points=data.strategies[k][field],color=k==='stacked'?'var(--violet)':'var(--blue)';
      // Each cubic stays in the rectangle of its two actual endpoints. Its
      // controls preserve every observation and cannot introduce an extremum.
      const d=points.map((p,j)=>{const X=x(p.date),Y=y(p.value);if(!j)return `M${X.toFixed(2)} ${Y.toFixed(2)}`;const a=points[j-1],A=x(a.date),B=y(a.value),dx=(X-A)/3;return `C${(A+dx).toFixed(2)} ${B.toFixed(2)} ${(X-dx).toFixed(2)} ${Y.toFixed(2)} ${X.toFixed(2)} ${Y.toFixed(2)}`;}).join(' ');
      if(!points.length)return '';
      return `<defs><linearGradient id="cloud-equity-fill-${k}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="var(--cyan)" stop-opacity="0"/></linearGradient></defs><path class="cloud-equity-area" d="${d} L${x(points.at(-1).date).toFixed(2)} ${H-B} L${x(points[0].date).toFixed(2)} ${H-B} Z" fill="url(#cloud-equity-fill-${k})"/><path data-cloud-allocation="${k}" d="${d}" class="equity-line" style="stroke:${color}"/>`;}).join('');
    const unit=field==='equityCurve'?'資産（万円）':'損益（万円）';
    return `<svg class="scenario-chart cloud-equity-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${unit}と売却日の推移" data-domain-min="${lo}" data-domain-max="${hi}"><title>${unit}・確定した売却日で変化</title><text x="${L}" y="20" class="axis-label">${unit}</text>${grid}${paths}<text x="${L}" y="${H-22}" class="axis-label">${new Date(minX).toISOString().slice(0,10)}</text>${minX===maxX?'':`<text x="${W-R}" y="${H-22}" text-anchor="end" class="axis-label">${new Date(maxX).toISOString().slice(0,10)}</text>`}<text x="${(L+W-R)/2}" y="${H-2}" text-anchor="middle" class="axis-label">売却日</text></svg>`;
  }
  function bars(rows,keys,labels,unit){
    const max=Math.max(1,...rows.flatMap(r=>keys.map(k=>Math.abs(r[k]??0))));
    return `<div class="cloud-horizontal-bars">${rows.map(r=>`<div class="cloud-bar-row" data-year="${text(r.label)}"><strong>${text(r.label)}</strong>${keys.map((k,i)=>`<div class="cloud-bar-item" data-bar-value="${r[k]??0}" data-method="${k}"><span class="cloud-bar-track"><i style="width:${Math.abs(r[k]??0)/max*100}%;background:${r[k]<0?'#df6670':k==='stacked'?'var(--violet)':'var(--blue)'}"></i></span><b>${r[k]===null?'—':unit==='円'?yen(r[k],true):unit==='%'?pct(r[k],true):r[k]}</b><small>${text(labels[i])}</small></div>`).join('')}</div>`).join('')}</div>`;
  }
  function render(data,prefs,view,payload){
    const profit=v=>`<span class="${v>0?'positive':v<0?'negative':''}">${yen(v,true)}</span>`;
    const home=payload.page==='home',analytics=payload.page==='analytics',mode=!home&&!analytics;
    const allocations=view.allocation==='all'?['unique','stacked']:[view.allocation];
    const labels={unique:`各銘柄を同じ株数で試算する（${prefs.baseShares.toLocaleString()}株）`,stacked:`一致した条件数に応じて株数を増やす（基本${prefs.baseShares.toLocaleString()}株）`},u=data.strategies.unique;
    const stat=(label,value)=>`<div><dt>${text(label)}</dt><dd>${value}</dd></div>`,kpi=(label,value,compact=false)=>`<div class="kpi"><small>${text(label)}</small><b${compact?' class="period-range"':''}>${value}</b></div>`;
    const dates=data.trades.map(t=>t.signal).sort(),period=dates.length?`${text(dates[0])}<br><span>〜${text(payload.generated.slice(0,10))}</span>`:'—',scope=payload.scopes[view.yearScope]?.label||'記録期間すべて';
    const title=home?'天底極致 -Cloud- ダッシュボード':analytics?'天底極致 -Cloud- アナリティクス':payload.modeNames[payload.page]||'Cloudモード';
    const context=typeof document==='undefined'?null:document.getElementById('cloud-mode-context');
    const lead=home?'条件に該当した銘柄を新しい順に確認し、5つのモード別ページへ進めます。':analytics?'5つのモードを合わせた成績と資産推移です。検出銘柄はダッシュボード、各モードの内訳は専用ページで確認できます。':context?.dataset.feature||'このモードの成績と検出銘柄を確認できます。';
    const conditions=`${scope} / 検出日終値 ${prefs.priceCapYen===null?'上限なし':prefs.priceCapYen.toLocaleString()+'円以下'} / ${prefs.exitKey==='d5_close'?'5営業日後 終値':'6営業日後 始値'} / 基本${prefs.baseShares}株 / 片道手数料${prefs.costPercent}%`;
    const hero=`<section class="hero"><div class="panel hero-main"><span class="eyebrow">${mode?'CLOUD MODE':'TEN-TEI-KYOKUCHI / CLOUD'}</span><h1>${text(title)}</h1><p class="lead">${text(lead)}</p>${mode?`<p>${text(context?.dataset.selection||'')}</p>`:''}<p class="note">${text(conditions)}</p><p class="note">取得が難しい参考記録${data.referenceCount}件は、成績に含めません。過去の結果は将来の利益を保証しません。</p></div><aside class="panel"><div class="kpis">${kpi('結果が出た銘柄',u.n+'件')}${kpi('保有中・価格未取得',u.pending+'件')}${kpi('記録期間',period,true)}${kpi('最終検出日',text(dates.at(-1)||'—'))}</div></aside></section>`;
    if(home)return hero;
    const compare=rows=>table(['指標',...allocations.map(k=>labels[k])],rows.map(([label,key,f])=>[text(label),...allocations.map(k=>f(data.strategies[k][key]))]));
    const strategy=allocations.map(k=>{const v=data.strategies[k];return `<article class="chart-card research-strategy" data-cloud-allocation="${k}"><h3><i class="research-swatch ${k}"></i>${text(labels[k])}</h3><p class="note allocation-explanation">${text(k==='unique'?`該当モード数にかかわらず、同じ日・同じ銘柄を${prefs.baseShares.toLocaleString('ja-JP')}株だけ買ったものとして集計します。`:`同じ銘柄が複数モードに該当した場合、モードごとに${prefs.baseShares.toLocaleString('ja-JP')}株ずつ買ったものとして集計します（例: 3モード該当なら合計${(prefs.baseShares*3).toLocaleString('ja-JP')}株）。`)}</p>${line(data,'equityCurve',[k],[k])}<div class="chart-stats"><div><small>累積損益</small><b class="${v.cash_pl_100_yen>0?'positive':v.cash_pl_100_yen<0?'negative':''}">${yen(v.cash_pl_100_yen,true)}</b></div><div><small>必要な資金（目安）</small><b>${yen(v.required_capital_yen)}</b></div><div><small>資金増加率</small><b>${pct(v.capital_return_pct,true)}</b></div><div><small>勝率</small><b>${pct(v.win_pct)}</b></div></div><dl class="scenario-stats">${stat('結果が出た取引',v.n+'回')}${stat('平均の騰落率',pct(v.mean_pct,true))}${stat('中央値',pct(v.median_pct,true))}${stat('年あたり（単純換算）',pct(v.simple_annualized_pct,true))}</dl></article>`;}).join('');
    const payoffSummaries=allocations.map(k=>{const v=data.strategies[k],loss=Math.abs(v.average_loss_pct??0),gain=v.average_win_pct??0,max=Math.max(1,loss,gain);return `<article data-cloud-allocation="${k}"><div class="payoff-heading"><h3>${text(labels[k])}</h3><span class="payoff-ratio">平均利益幅 ÷ 平均損失幅 ${v.payoff_ratio===null?'—':v.payoff_ratio.toFixed(2)+'倍'}</span></div><dl class="payoff-kpis"><div class="payoff-kpi"><strong>${pct(v.win_pct)}</strong><small>勝率</small></div><div class="payoff-kpi loss"><strong>${pct(v.average_loss_pct,true)}</strong><small>平均負け</small></div><div class="payoff-kpi win"><strong>${pct(v.average_win_pct,true)}</strong><small>平均勝ち</small></div></dl><div class="payoff-track" role="img" aria-label="平均負け ${pct(v.average_loss_pct,true)}、平均勝ち ${pct(v.average_win_pct,true)}" data-average-loss="${v.average_loss_pct}" data-average-win="${v.average_win_pct}"><span class="payoff-bar loss" style="width:${loss/max*45}%"></span><span class="payoff-zero"></span><span class="payoff-bar win" style="width:${gain/max*45}%"></span></div><div class="payoff-axis"><span class="loss">${pct(v.average_loss_pct,true)} 平均負け</span><span class="win">${pct(v.average_win_pct,true)} 平均勝ち</span></div><p class="note">左は損失、右は利益。中央が0%、左右は同じ尺度です。</p></article>`;}).join('');
    const annual=bars([...data.annual].reverse().map(r=>({label:r.period+'年',unique:r.unique.cash_pl_100_yen,stacked:r.stacked.cash_pl_100_yen})),allocations,allocations.map(k=>labels[k]),'円');
    const annualLegend=`<div class="research-legend">${allocations.map(k=>`<span><i class="research-swatch ${k}"></i>${text(labels[k])}</span>`).join('')}<span><i class="research-swatch negative"></i>損失</span></div>`;
    const pagination='<div class="table-pagination"><button class="table-load-more" type="button">次の20件</button><button class="table-collapse" type="button" hidden>最初の20件へ</button><output class="table-result-count"></output></div>';
    const periodDetails=(rows,title)=>`<details class="scenario-details"><summary>${title}</summary><div class="table-wrap">${table(['期間','株数の配分','取引数','損益','必要資金','平均','勝率'],rows.flatMap(r=>allocations.map(k=>[text(r.period),text(labels[k]),String(r[k].n),profit(r[k].cash_pl_100_yen),yen(r[k].required_capital_yen),pct(r[k].mean_pct,true),pct(r[k].win_pct)])))}</div>${rows.length*allocations.length>20?pagination:''}</details>`;
    const payoffTable=compare([['利益の合計','total_win_yen',v=>profit(v)],['損失の合計','total_loss_yen',v=>profit(v)],['勝ったときの平均損益','average_win_yen',v=>profit(v)],['負けたときの平均損益','average_loss_yen',v=>profit(v)],['平均の上昇率','average_win_pct',v=>pct(v,true)],['平均の下落率','average_loss_pct',v=>pct(v,true)]]);
    const risk=compare([['必要な資金（取得額の最大）','required_capital_yen',yen],['売却代金を再利用した場合の開始資金','minimum_initial_cash_yen',yen],['累積損益の最大の落ち込み','max_drawdown_yen',yen],['最も大きい1取引の損失','worst_pl_yen',v=>profit(v)],['利益上位3取引を除いた損益','profit_excluding_best3_yen',v=>profit(v)]]);
    const overall=compare([['累積損益','cash_pl_100_yen',v=>profit(v)],['確定取引数','n',String],['未確定取引数','pending',String],['必要な資金','required_capital_yen',yen],['資金増加率','capital_return_pct',v=>pct(v,true)],['平均の騰落率','mean_pct',v=>pct(v,true)],['中央値','median_pct',v=>pct(v,true)],['勝率','win_pct',pct],['+10%以上','plus10_pct',pct],['+20%以上','plus20_pct',pct],['-10%以下','minus10_pct',pct],['-20%以下','minus20_pct',pct],['最大上昇率','max_up_pct',v=>pct(v,true)],['最大下落率','max_down_pct',v=>pct(v,true)],['上位3取引を除く平均','top3_ex_mean_pct',v=>pct(v,true)]]);
    const metricColumns=[['取引数','n',String],['価格待ち','pending',String],['損益','cash_pl_100_yen',profit],['必要資金','required_capital_yen',yen],['資金増加率','capital_return_pct',v=>pct(v,true)],['1年あたり（単純換算）','simple_annualized_pct',v=>pct(v,true)],['平均の騰落率','mean_pct',v=>pct(v,true)],['中央値','median_pct',v=>pct(v,true)],['勝率','win_pct',pct],['+10%以上','plus10_pct',pct],['+20%以上','plus20_pct',pct],['-10%以下','minus10_pct',pct],['-20%以下','minus20_pct',pct],['最大上昇率','max_up_pct',v=>pct(v,true)],['最大下落率','max_down_pct',v=>pct(v,true)],['利益上位3件を除いた平均','top3_ex_mean_pct',v=>pct(v,true)]];
    const detailPeriods=(rows,title=null)=>{
      const markup='<div class="table-wrap analytics-detail-table-wrap" tabindex="0" role="region" aria-label="成績の詳細表。横にスクロールできます">'+table(['期間','株数の配分',...metricColumns.map(c=>c[0])],rows.flatMap(r=>allocations.map(k=>[text(r.period)+`<small class="detail-method-mobile">${text(k==='unique'?'一律':'条件数比例')}</small>`,text(labels[k]),...metricColumns.map(([,key,f])=>f(r[k][key]))])),true)+'</div>';
      return title?`<details class="scenario-details"><summary>${title}</summary>${markup}${rows.length*allocations.length>20?pagination:''}</details>`:markup;
    };
    const detailedOverall=analytics?detailPeriods([{period:'全期間',...data.strategies}]):overall;
    const detailedAnnual=analytics?detailPeriods(data.annual,'年別の詳しい成績'):periodDetails(data.annual,'年別の詳しい成績');
    const detailedMonthly=analytics?detailPeriods(data.monthly,'月別の詳しい成績'):periodDetails(data.monthly,'月別の詳しい成績');
    const overlap=table(['一致した条件','結果あり','平均','勝率',view.allocation==='stacked'?'損益（条件数比例）':'損益（一律）'],data.overlap.map(r=>[r.count+'個',r.n+'件',pct(r.mean_pct,true),pct(r.win_pct),r.n?profit(r.cash_pl_100_yen*(view.allocation==='stacked'?r.count:1)):'—']));
    const reference=table(['比較','損益'],[['同じ株数で試算',profit(data.strategies.unique.cash_pl_100_yen)],['条件数に応じた株数で試算',profit(data.strategies.stacked.cash_pl_100_yen)],['総取得株数をそろえた参考値',data.strategies.stacked.n?profit(data.strategies.stacked.cash_pl_100_yen*u.n/data.strategies.stacked.n):'—']]);
    return hero+`<section class="panel" id="strategy-comparison"><h2>${mode?text(title)+' の資産推移':'取得株数による比較'}</h2>${mode?'<p class="note">このモードに該当した銘柄を集計しています。</p>':''}<p class="note">利益と必要資金を並べて比較します。必要資金に売却後の損益を加えた試算です。売却日の記録をつないだ線で、途中の値動きは表しません。</p><div class="${allocations.length>1?'chart-grid':''}">${strategy}</div></section><div class="insight-grid"><section class="panel" id="payoff-structure"><h2>利益構造</h2><div class="${allocations.length>1?'payoff-comparison':''}">${payoffSummaries}</div></section><section class="panel" id="annual-pl"><h2>年別損益</h2>${annualLegend}<p class="note">金額（円）。表示中の年は、両方式で同じ長さの目盛りです。</p><div id="annual-year-bars">${annual}</div><button id="annual-older-toggle" class="settings-secondary" type="button" aria-expanded="false" aria-controls="annual-year-bars" hidden>過去の年を表示</button></section></div><section class="panel" id="detailed-performance"><h2>詳しい成績</h2><p class="note">グラフと同じ取引から計算しています。売買手数料を含み、配当・税金は含みません。</p><h3>全期間の成績</h3>${analytics?'<p class="note">表は横にスクロールできます。全期間・年別・月別は同じ並びです。</p>':''}${detailedOverall}${detailedAnnual}${detailedMonthly}<details class="scenario-details"><summary>利益構造の詳しい数字</summary>${payoffTable}</details><details class="scenario-details" id="capital-risk"><summary>資金と損失の詳しい数字</summary>${risk}<p class="note">結果が出た取引の試算です。同日の取得資金を先に用意します。</p></details>${analytics?`<details class="scenario-details"><summary>条件の重なり</summary>${overlap}</details><details class="scenario-details"><summary>取得株数の影響を金額をそろえて比較</summary>${reference}<p class="note">取得株数の比率で縮小した参考値です。同じ資金で実際に買えた結果ではありません。</p></details>`:''}</section>`;
  }
  const csvMetrics=(data,prefs,view)=>['全期間',...data.annual.map(r=>r.period),...data.monthly.map(r=>r.period)].flatMap(period=>{
    const source=period==='全期間'?data.strategies:[...data.annual,...data.monthly].find(r=>r.period===period);
    return ['unique','stacked'].filter(k=>view.allocation==='all'||view.allocation===k).map(k=>{const v=source[k];return {
      '期間':period,'株数の配分':k==='unique'?'同じ株数':'条件数に応じた株数','基本株数':prefs.baseShares,'片道手数料%':prefs.costPercent,
      '検出日終値の上限':prefs.priceCapYen??'上限なし','売却価格の選択':prefs.exitKey==='d5_close'?'5営業日後 終値':'6営業日後 始値',
      '結果ありの取引数':v.n,'価格待ちの取引数':v.pending,'損益円':v.cash_pl_100_yen,'平均の騰落率%':v.mean_pct,'中央値%':v.median_pct,'勝率%':v.win_pct,
      '必要資金円':v.required_capital_yen,'開始資金円':v.minimum_initial_cash_yen,'資金増加率%':v.capital_return_pct,'単純年率%':v.simple_annualized_pct,
      '+10%の割合':v.plus10_pct,'+20%の割合':v.plus20_pct,'-10%の割合':v.minus10_pct,'-20%の割合':v.minus20_pct,
      '最大上昇率%':v.max_up_pct,'最大下落率%':v.max_down_pct,'利益上位3取引を除く平均%':v.top3_ex_mean_pct,'最大の落ち込み円':v.max_drawdown_yen,
      '平均利益円':v.average_win_yen,'平均損失円':v.average_loss_yen,'平均利益と平均損失の幅の比':v.payoff_ratio};});});
  return {number,validate,trade,risk,summarize,calculate,render,csvMetrics,pct,yen};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=CloudScenario;
