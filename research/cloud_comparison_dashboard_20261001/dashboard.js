(() => {
  'use strict';
  const D = JSON.parse(document.getElementById('research-data').textContent);
  const $ = id => document.getElementById(id);
  const records = (cols, rows) => rows.map(row => Object.fromEntries(cols.map((key, i) => [key, row[i]])));
  const exits = records(D.exitColumns, D.exits), caps = records(D.capColumns, D.caps);
  const exitMap = new Map(exits.map(r => [[r.arm, r.mode, r.period, r.endpoint].join('|'), r]));
  const state = { period: 'ALL_DESCRIPTIVE', mode: 'all_conditions_unique', metric: 'mean', arm: 'cap1000', endpoint: 'd5_close', capPeriod: 'ALL' };
  const metricNames = { mean: '平均リターン', win: '勝率', median: '中央値', loss: '−10%以下の割合', top3: '上位3件除外平均' };
  const periodNames = { ALL_DESCRIPTIVE: '全期間・事後比較', DEV_2023_2024: '2023〜2024年・選択期間', '2023': '2023年', '2024': '2024年', '2025': '2025年', '2026': '2026年・9月まで' };
  const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const armName = arm => arm === 'nocap' ? '上限なし' : Number(arm.slice(3)).toLocaleString('ja-JP') + '円以下';
  const shortArm = arm => arm === 'nocap' ? '上限なし' : Number(arm.slice(3)).toLocaleString('ja-JP') + '円';
  const endpointName = endpoint => Number(endpoint.split('_')[0].slice(1)) + '営業日後' + (endpoint.endsWith('open') ? '始値' : '終値');
  const pct = (n, signed = true, digits = 2) => n == null || !Number.isFinite(Number(n)) ? '—' : (signed && Number(n) > 0 ? '+' : '') + Number(n).toFixed(digits) + '%';
  const fmt = n => n == null ? '—' : Math.round(Number(n)).toLocaleString('ja-JP');
  const yen = n => n == null ? '—' : fmt(n) + '円';
  const moneyShort = n => n == null ? '—' : (Number(n) / 10000).toFixed(Number(n) >= 1000000 ? 0 : 1) + '万円';
  const signClass = n => Number(n) < 0 ? 'negative' : 'positive';
  const metricPct = (n, digits = 2) => pct(n, !['win', 'loss'].includes(state.metric), digits);
  const get = (arm, endpoint, period = state.period) => exitMap.get([arm, state.mode, period, endpoint].join('|'));
  const joint = period => D.joint.find(r => r.selector === state.mode && r.period === period);
  const currentRows = () => exits.filter(r => r.mode === state.mode && r.period === state.period);
  const bestRow = () => [...currentRows()].sort((a, b) => (state.metric === 'loss' ? a.loss - b.loss : b[state.metric] - a[state.metric]) || D.arms.indexOf(a.arm) - D.arms.indexOf(b.arm) || D.endpoints.indexOf(a.endpoint) - D.endpoints.indexOf(b.endpoint))[0];
  const fixedRow = () => { const j = joint(state.period); return get(j.dev_fixed_arm, j.dev_fixed_endpoint); };
  const setSelection = (arm, endpoint) => { state.arm = arm; state.endpoint = endpoint; render(); };

  $('mode').innerHTML = Object.entries(D.modes).map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
  function renderProduction() {
    const period = ['ALL_DESCRIPTIVE', 'DEV_2023_2024'].includes(state.period) ? 'ALL' : state.period;
    const p = D.production.metrics.find(r => r.mode === state.mode && r.period === period);
    const r = caps.find(r => r.arm === 'cap1000' && r.mode === state.mode && r.period === period);
    $('production-context').textContent = D.modes[state.mode] + ' / ' + (period === 'ALL' ? '全期間（2023〜2026年）' : period + '年') + ' / 1,000円以下・5営業日後終値。' + D.production.public_updated_label + 'の固定参照値。';
    const rows = [['本番Cloud・保存済み履歴', p.n, p.mean_pct, p.win_pct, p.median_pct], ['研究・補正後に再計算', r.n, r.mean, r.win, r.median]];
    $('production-table').innerHTML = rows.map(([label, n, mean, win, median]) => `<tr><td>${label}</td><td>${fmt(n)}</td><td>${pct(mean)}</td><td>${pct(win, false)}</td><td>${pct(median)}</td></tr>`).join('');
    const ids = D.production.completed_unique_identities;
    $('production-overlap').textContent = `全期間・銘柄均等の照合：共通 ${ids.shared}件 / 本番のみ ${ids.production_only}件 / 研究のみ ${ids.research_only}件。共通取引の騰落率は全件一致しました。`;
  }
  function renderInsights() {
    const best = bestRow(), fixed = fixedRow();
    $('best-condition').textContent = armName(best.arm) + ' / ' + endpointName(best.endpoint);
    $('best-value').textContent = metricPct(best[state.metric]);
    $('best-meta').textContent = metricNames[state.metric] + ' · ' + best.n + '件';
    $('fixed-condition').textContent = armName(fixed.arm) + ' / ' + endpointName(fixed.endpoint);
    $('fixed-value').textContent = pct(fixed.mean);
    $('fixed-meta').textContent = 'この期間の平均 · ' + fixed.n + '件';
    $('mode-note').textContent = state.mode === 'all_conditions_stacked' ? 'モード別積上げ：同じ日・銘柄が複数モードに出た場合、モードごとに100株を購入した集計です。' : state.mode === 'all_conditions_unique' ? '銘柄均等：5モードをまとめ、同じ日・銘柄は1回の100株購入として集計します。' : D.modes[state.mode] + 'で検出した銘柄だけの集計です。';
  }
  function renderHeatmaps() {
    const values = currentRows().map(r => r[state.metric]).filter(v => v != null);
    const min = Math.min(...values), max = Math.max(...values);
    $('heatmaps').innerHTML = ['open', 'close'].map(side => {
      let cells = '<div></div>' + Array.from({length: 10}, (_, i) => `<div class="heat-day">${i + 1}日後</div>`).join('');
      for (const arm of D.arms) {
        cells += `<div class="heat-label">${shortArm(arm)}</div>`;
        for (let day = 1; day <= 10; day++) {
          const endpoint = `d${day}_${side}`, r = get(arm, endpoint), value = r[state.metric];
          const fraction = value == null || max === min ? 0 : (value - min) / (max - min);
          const intensity = state.metric === 'loss' ? 1 - fraction : fraction;
          const dark = document.body.classList.contains('dark');
          const bg = dark ? `hsl(165 28% ${18 + 30 * intensity}%)` : `hsl(165 ${18 + 22 * intensity}% ${96 - 47 * intensity}%)`;
          const fg = dark ? '#e9fff9' : '#173c35';
          const selected = arm === state.arm && endpoint === state.endpoint;
          const label = `${armName(arm)} ${endpointName(endpoint)} ${metricNames[state.metric]} ${metricPct(value)}`;
          cells += `<button class="heat-cell${selected ? ' selected' : ''}${endpoint === 'd1_open' ? ' control' : ''}" data-arm="${arm}" data-endpoint="${endpoint}" aria-pressed="${selected}" aria-label="${esc(label)}" title="${esc(label)}" style="background:${bg};color:${fg}">${value == null ? '—' : Number(value).toFixed(1)}</button>`;
        }
      }
      return `<div class="heat-block ${side}"><h4>${side === 'open' ? '始値で売却' : '終値で売却'} <span class="caption">単位：%</span></h4><div class="heat-scroll"><div class="heat-grid">${cells}</div></div></div>`;
    }).join('');
  }
  function renderSelected() {
    const r = get(state.arm, state.endpoint);
    $('selected-title').textContent = armName(state.arm) + ' / ' + endpointName(state.endpoint);
    $('selected-context').textContent = periodNames[state.period] + ' · ' + D.modes[state.mode];
    const baseline = get('cap1000', 'd5_close');
    const difference = r.mean - baseline.mean;
    const cards = [
      ['平均リターン', pct(r.mean), `研究基準比 ${difference > 0 ? '+' : ''}${difference.toFixed(2)}pt`, signClass(r.mean)],
      ['勝率', pct(r.win, false), `プラスの取引 / ${fmt(r.n)}件`, ''],
      ['中央値', pct(r.median), '半数の取引がこの値以下', signClass(r.median)],
      ['−10%以下の割合', pct(r.loss, false), '売却時点の大幅損失', '']
    ];
    $('kpis').innerHTML = cards.map(([label, value, note, cls]) => `<article class="kpi"><span class="label">${label}</span><strong class="${cls}">${value}</strong><small>${note}</small></article>`).join('');
    const rows = [['確定件数', fmt(r.n) + '件'], ['上位3件除外平均', pct(r.top3)], ['最悪1件の損失', pct(r.worst)],
                  ['100株損益合計', yen(r.cash)], ['購入原価の延べ合計', moneyShort(r.entryTotal)], ['0%取引', fmt(r.flat) + '件']];
    $('details').innerHTML = rows.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join('');
  }
  function renderCurve() {
    const rows = D.endpoints.map(endpoint => get(state.arm, endpoint));
    const values = rows.map(r => r[state.metric]).filter(v => v != null);
    const rawMin = Math.min(0, ...values), rawMax = Math.max(0, ...values), span = rawMax - rawMin || 1;
    const low = rawMin - span * .13, high = rawMax + span * .13;
    const left = 52, right = 620, top = 25, bottom = 244;
    const x = day => left + (day - 1) * (right - left) / 9, y = value => bottom - (value - low) * (bottom - top) / (high - low);
    let svg = `<svg class="chart-svg" viewBox="0 0 660 280" role="group" aria-label="${esc(armName(state.arm) + 'の' + metricNames[state.metric] + '推移')}">`;
    for (let i = 0; i <= 4; i++) {
      const value = low + (high - low) * i / 4, yy = y(value);
      svg += `<line class="grid-line" x1="${left}" x2="${right}" y1="${yy}" y2="${yy}"/><text x="${left - 8}" y="${yy + 4}" text-anchor="end">${value.toFixed(1)}%</text>`;
    }
    svg += `<line class="chart-zero" x1="${left}" x2="${right}" y1="${y(0)}" y2="${y(0)}"/><line class="base-line" x1="${x(5)}" x2="${x(5)}" y1="${top}" y2="${bottom}"/>`;
    for (let day = 1; day <= 10; day++) svg += `<text x="${x(day)}" y="267" text-anchor="middle">${day}日</text>`;
    for (const side of ['open', 'close']) {
      const color = side === 'open' ? 'var(--accent)' : 'var(--blue)';
      const lineRows = rows.filter(r => r.endpoint.endsWith(side));
      let segment = [];
      const segments = [];
      for (const r of lineRows) {
        if (r[state.metric] == null) { if (segment.length) segments.push(segment); segment = []; }
        else segment.push(`${x(Number(r.endpoint.split('_')[0].slice(1)))},${y(r[state.metric])}`);
      }
      if (segment.length) segments.push(segment);
      svg += segments.map(points => `<polyline points="${points.join(' ')}" fill="none" stroke="${color}" stroke-width="2.3"/>`).join('');
      for (const r of lineRows) {
        if (r[state.metric] == null) continue;
        const selected = r.endpoint === state.endpoint, day = Number(r.endpoint.split('_')[0].slice(1));
        const label = `${endpointName(r.endpoint)} ${metricNames[state.metric]} ${metricPct(r[state.metric])}`;
        svg += `<g class="chart-point" role="button" tabindex="0" data-endpoint="${r.endpoint}" aria-label="${esc(label)}"><title>${esc(label)}</title><circle cx="${x(day)}" cy="${y(r[state.metric])}" r="${selected ? 6 : 4}" fill="var(--surface)" stroke="${color}" stroke-width="${selected ? 3 : 2}"/><circle cx="${x(day)}" cy="${y(r[state.metric])}" r="13" fill="transparent"/></g>`;
      }
    }
    $('curve').innerHTML = svg + '</svg>';
    $('curve-title').textContent = armName(state.arm) + ' / ' + metricNames[state.metric];
    $('endpoint-table').innerHTML = rows.map(r => `<tr class="${r.endpoint === state.endpoint ? 'active' : ''}"><td><button class="text-button" data-endpoint="${r.endpoint}">${endpointName(r.endpoint)}</button></td><td>${fmt(r.n)}</td><td class="${signClass(r.mean)}">${pct(r.mean)}</td><td>${pct(r.win, false)}</td><td>${pct(r.median)}</td><td>${pct(r.loss, false)}</td><td>${pct(r.top3)}</td><td>${pct(r.worst)}</td><td>${yen(r.cash)}</td></tr>`).join('');
  }
  function renderValidation() {
    const policy = joint('DEV_2023_2024');
    $('validation-policy').textContent = D.modes[state.mode] + '：120組から選んだ「' + armName(policy.dev_fixed_arm) + ' / ' + endpointName(policy.dev_fixed_endpoint) + '」を固定。選択期間は' + policy.dev_selection_n + '件です。';
    $('year-cards').innerHTML = ['DEV_2023_2024', '2025', '2026'].map(period => {
      const j = joint(period), cls = signClass(j.fixed_mean_pct);
      const label = period === 'DEV_2023_2024' ? '2023〜2024年' : period + '年';
      const badge = period === 'DEV_2023_2024' ? '選択期間' : period === '2025' ? '固定して検証' : '固定して検証・9月まで';
      const dl = [['件数', fmt(j.fixed_n) + '件'], ['勝率', pct(j.fixed_win_pct, false)], ['中央値', pct(j.fixed_median_pct)],
                  ['−10%以下', pct(j.fixed_loss10_pct, false)], ['上位3件除外', pct(j.fixed_top3_ex_mean_pct)],
                  ['研究基準比', (Number(j.fixed_minus_cap1000_d5_close_mean_pt) > 0 ? '+' : '') + Number(j.fixed_minus_cap1000_d5_close_mean_pt).toFixed(2) + 'pt']];
      return `<article class="year-card"><h3>${label}<span class="pill">${badge}</span></h3><span class="year-label">固定条件の平均</span><div class="year-mean ${cls}">${pct(j.fixed_mean_pct)}</div><dl>${dl.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl><p class="year-foot">同期間の事後最高：${armName(j.posthoc_best_arm)} / ${endpointName(j.posthoc_best_endpoint)}<br>平均 ${pct(j.posthoc_best_mean_pct)} · 固定条件より ${Number(j.posthoc_advantage_over_dev_fixed_pt).toFixed(2)}pt高い</p></article>`;
    }).join('');
  }
  function renderCapital() {
    const rows = D.arms.map(arm => caps.find(r => r.arm === arm && r.mode === state.mode && r.period === state.capPeriod));
    const max = Math.max(...rows.map(r => Math.abs(r.mean)), 1);
    $('capital-note').textContent = D.modes[state.mode] + ' / ' + (state.capPeriod === 'ALL' ? '全期間' : state.capPeriod + '年') + ' / 翌営業日始値購入 → 5営業日後終値売却。価格上限は検出前営業日の終値で判定します。';
    $('cap-bars').innerHTML = rows.map(r => `<div class="cap-bar"><label>${armName(r.arm)}</label><strong class="${signClass(r.mean)}">${pct(r.mean)}</strong><div class="bar-track"><span style="width:${Math.abs(r.mean) / max * 100}%;background:var(--${r.mean < 0 ? 'negative' : 'accent'})"></span></div><small>${fmt(r.n)}件 · 必要資金 ${moneyShort(r.capital)}</small></div>`).join('');
    $('cap-table').innerHTML = rows.map(r => `<tr class="${r.arm === 'cap1000' ? 'active' : ''}"><td>${armName(r.arm)}${r.arm === 'cap1000' ? ' · 研究基準' : ''}</td><td>${fmt(r.n)}</td><td class="${signClass(r.mean)}">${pct(r.mean)}</td><td>${pct(r.win, false)}</td><td>${pct(r.median)}</td><td>${pct(r.loss, false)}</td><td>${pct(r.top3)}</td><td>${yen(r.capital)}</td><td>${yen(r.cash)}</td></tr>`).join('');
  }
  function render() { renderProduction(); renderInsights(); renderHeatmaps(); renderSelected(); renderCurve(); renderValidation(); renderCapital(); }
  for (const [id, key] of [['period', 'period'], ['mode', 'mode'], ['metric', 'metric'], ['cap-period', 'capPeriod']]) {
    $(id).addEventListener('change', event => { state[key] = event.target.value; if (id === 'period' && state.period !== 'DEV_2023_2024') { state.capPeriod = state.period === 'ALL_DESCRIPTIVE' ? 'ALL' : state.period; $('cap-period').value = state.capPeriod; } render(); });
  }
  $('heatmaps').addEventListener('click', event => { const b = event.target.closest('button[data-arm]'); if (b) setSelection(b.dataset.arm, b.dataset.endpoint); });
  $('curve').addEventListener('click', event => { const b = event.target.closest('[data-endpoint]'); if (b) setSelection(state.arm, b.dataset.endpoint); });
  $('curve').addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { const b = event.target.closest('[data-endpoint]'); if (b) { event.preventDefault(); setSelection(state.arm, b.dataset.endpoint); } } });
  $('endpoint-table').addEventListener('click', event => { const b = event.target.closest('button[data-endpoint]'); if (b) setSelection(state.arm, b.dataset.endpoint); });
  $('select-best').addEventListener('click', () => { const r = bestRow(); setSelection(r.arm, r.endpoint); });
  $('select-fixed').addEventListener('click', () => { const r = fixedRow(); setSelection(r.arm, r.endpoint); });
  $('reset').addEventListener('click', () => setSelection('cap1000', 'd5_close'));
  function theme(dark) { document.body.classList.toggle('dark', dark); $('theme').setAttribute('aria-label', dark ? 'ライトモードに切り替え' : 'ダークモードに切り替え'); renderHeatmaps(); }
  try { theme(localStorage.getItem('cloud-research-theme') === 'dark'); } catch { theme(false); }
  $('theme').addEventListener('click', () => { const dark = !document.body.classList.contains('dark'); theme(dark); try { localStorage.setItem('cloud-research-theme', dark ? 'dark' : 'light'); } catch { /* Offline file permissions vary by browser. */ } });
  $('download').addEventListener('click', () => {
    const cols = ['arm', 'mode', 'period', 'endpoint', 'n', 'mean', 'win', 'median', 'loss', 'top3', 'worst', 'cash', 'entryTotal'];
    const rows = D.endpoints.map(ep => get(state.arm, ep));
    const csv = '\ufeff' + [cols.join(','), ...rows.map(r => cols.map(k => r[k] == null ? '' : r[k]).join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
    const a = document.createElement('a'); a.href = url; a.download = `cloud_${state.arm}_${state.mode}_${state.period}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $('provenance').innerHTML = `<div class="hash"><p>価格入力 SHA-256: ${esc(D.dailySha256)}</p><p>企業行動 SHA-256: ${esc(D.actionsSha256)}</p><p>以下の集計入力は改行をLFへ正規化したSHA-256です。</p>${D.sources.map(s => `<p>${esc(s.path)}<br>${esc(s.sha256)}</p>`).join('')}</div>`;
  render();
})();
