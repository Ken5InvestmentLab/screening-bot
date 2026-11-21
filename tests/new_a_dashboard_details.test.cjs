const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.resolve(__dirname, '../weak-early-beta-gate/scripts/new-a-ui-source/assets');
function loadBrowserScript(file) {
  const context = vm.createContext({ module: { exports: {} } });
  vm.runInContext(fs.readFileSync(path.join(assets, file), 'utf8'), context);
  return context.module.exports;
}
const { currentMarkup, stockDetails, holdingPerformance, openFundamental } = loadBrowserScript('owner-loader.js');
const { renderHoldings, historyRecords } = loadBrowserScript('finite-controller.js');
const adapter = require('../weak-early-beta-gate/scripts/new-a-ui-source/presentation-adapter.cjs');

const key = { symbol: '1234', candidate_date: '2026-11-17', episode_id: 1 };
const date = '2026-11-18';
const cutoff = '2026-11-17T08:20:00Z';
const row = {
  identity: '1234|2026-11-17|1', symbol: '1234', companyName: '銘柄 A',
  signalDate: key.candidate_date, candidateDate: key.candidate_date,
  chartAllowed: true, analysisCutoff: cutoff,
  signalClose: { status: 'verified', date: key.candidate_date, price: 1000 },
  fundamental: {
    identity: '2026-11-17|1234', symbol: '1234', signalDate: key.candidate_date,
    auditStatus: 'pass', analysisCutoff: cutoff, fields: [{ label: '業績', text: '<strong>素材</strong>' }],
  },
};
const snapshot = {
  schema: 'NEW_A_OWNER_DAILY_DISPLAY_V1', audience: 'EXISTING_CLOUD_OWNER_ONLY', as_of: date,
  observation_kind: 'LIVE_OBSERVATION', held_symbols: {},
  latest_closes: { 1234: { date, price: 1100 } },
  events: [{ ...key, session: date, kind: 'REFERENCE_OPEN' }],
  monitor_state: { watches: { a: { episode: key } } },
};
const closed = { ...key, entry_date: '2026-11-17', entry_price_nominal: 1000,
  exit_date: date, profit: 9320, return: 0.0932 };

test('owner monitoring previews the eight most recent watches and retains every watch', () => {
  const watchSelection = Array.from({ length: 10 }, (_, i) => ({
    symbol: String(1800 + i), candidate_date: '2026-11-' + String(i + 1).padStart(2, '0'),
    episode_id: i + 1, watch_status: 'WATCHING', selection_reason: null,
  }));
  const html = currentMarkup([{
    ...snapshot, events: [],
    monitor_state: { watches: Object.fromEntries(watchSelection.map(watch => [watch.symbol, { episode: watch }])) },
  }], [], { watchSelection });
  assert.equal([...html.matchAll(/<tr data-current-watch>/g)].length, 8);
  assert.deepEqual([...html.matchAll(/<tr data-current-watch hidden><td>(\d{4})/g)].map(match => match[1]), ['1801', '1800']);
  assert.match(html, /残り 2銘柄を表示/);
});

test('dashboard details use exact episode, verified quote and individual model result', () => {
  const daily = { ...snapshot, events: [{ ...key, session: date, kind: 'WATCH_STARTED' }] };
  const html = currentMarkup([daily], [row], { adapter, model: { trades: [closed] } });
  assert.match(html, /銘柄の詳細/);
  assert.match(html, /TradingView|tradingview\.com\/chart/);
  assert.match(html, /対象日終値<\/dt><dd>1,100円/);
  assert.match(html, /仮想決済 成績<\/dt><dd>9,320円（9.32%）/);
  assert.match(html, /data-owner-fundamental aria-haspopup="dialog" aria-expanded="false">ファンダ<\/button>/);
  assert.match(html, /<dialog class="fundamental-detail" aria-label="ファンダ分析の詳細">/);
  assert.match(html, /class="button-link cloud-stock-action"[^>]*>チャート<\/a>/);
  assert.match(html, /class="fundamental-toggle cloud-stock-action"/);
  assert.match(html, /<dl><dt>業績<\/dt><dd>/);
  assert.doesNotMatch(html, /<details class="cloud-fundamental"/);
  assert.match(html, /&lt;strong&gt;素材&lt;\/strong&gt;/);
  assert.doesNotMatch(html, /<strong>素材<\/strong>/);
});

test('owner popup uses the verified impact category without treating caution prose as an impact', () => {
  const fields = [
    { label: '材料インパクト', text: 'ポジティブ材料：材料確認済み。' },
    { label: '注意点', text: 'ネガティブ材料も要確認。<script>alert(1)</script>' },
  ];
  const reportRow = { ...row, fundamental: { ...row.fundamental, fields } };
  const rendered = adapter.fundamentalMarkup(reportRow);
  assert.match(rendered, /class="discord-embed impact-positive"/);
  assert.match(rendered, /<dt>注意点<\/dt><dd>ネガティブ材料も要確認。&lt;script&gt;/);
  assert.doesNotMatch(rendered, /<script/);
  assert.doesNotMatch(adapter.fundamentalMarkup({ ...reportRow, analysisCutoff: date }), /impact-/);
  const unknown = { ...reportRow, fundamental: { ...reportRow.fundamental,
    fields: [{ label: '材料インパクト', text: '分類未記載。ポジティブ材料を後日確認。' }, fields[1]] } };
  assert.match(adapter.fundamentalMarkup(unknown), /class="discord-embed"/);
});

test('the dynamically rendered owner history button opens a modal and restores its focus after dismissal', () => {
  class Dialog extends EventTarget {
    open = false;
    matches(selector) { return selector === 'dialog.fundamental-detail'; }
    showModal() { this.open = true; }
    close() {
      this.open = false;
      this.dispatchEvent(new Event('close'));
    }
    addEventListener(type, listener, options) {
      if (type !== 'click') return super.addEventListener(type, listener, options);
      this.clickListener = listener;
    }
    removeEventListener(type, listener) {
      if (type === 'click' && this.clickListener === listener) this.clickListener = null;
      else super.removeEventListener(type, listener);
    }
    click(target) { this.clickListener({ target }); }
  }
  const dialog = new Dialog();
  const button = {
    nextElementSibling: dialog, isConnected: true, expanded: 'false', focusCount: 0,
    setAttribute(name, value) { assert.equal(name, 'aria-expanded'); this.expanded = value; },
    focus() { this.focusCount++; },
  };
  openFundamental(button);
  assert.equal(dialog.open, true);
  assert.equal(button.expanded, 'true');
  dialog.click({ closest: () => null });
  assert.equal(dialog.open, true);
  dialog.click(dialog);
  assert.equal(dialog.open, false);
  assert.equal(button.expanded, 'false');
  assert.equal(button.focusCount, 1);
  openFundamental(button);
  dialog.click({ closest: (selector) => selector === '.fundamental-close' });
  assert.equal(dialog.open, false);
  assert.equal(button.expanded, 'false');
  assert.equal(button.focusCount, 2);
});

test('missing latest quote, held quote and a different episode cannot be used as a substitute', () => {
  const held = { ...snapshot, held_symbols: { 1234: { reason: 'MISSING_SOURCE' } } };
  const html = stockDetails(held, [row], adapter, { trades: [{ ...closed, episode_id: 9 }] })(key);
  assert.match(html, /対象日終値<\/dt><dd>未確認/);
  assert.match(html, /個別成績<\/dt><dd>未確定/);
  assert.doesNotMatch(html, /1,100円|9,320円/);
  assert.equal(stockDetails(snapshot, [row], adapter, null)({ ...key, episode_id: 2 }), '');
});

test('older daily snapshots show only the matching date from verified prepared quote input', () => {
  const older = { ...snapshot, latest_closes: undefined };
  const prepared = { date, prices: snapshot.latest_closes };
  assert.match(stockDetails(older, [row], adapter, null, prepared)(key), /対象日終値<\/dt><dd>1,100円/);
  assert.match(stockDetails(older, [row], adapter, null, { ...prepared, date: key.candidate_date })(key), /対象日終値<\/dt><dd>未確認/);
  assert.match(stockDetails({ ...older, held_symbols: { 1234: {} } }, [row], adapter, null, prepared)(key), /対象日終値<\/dt><dd>未確認/);
});

test('identity hold suppresses TradingView and fundamentals; unresolved portfolio is not labelled current', () => {
  const unsafe = { ...row, identityStatus: 'PRELISTING_HISTORY_MAPPING_UNVERIFIED', chartAllowed: false };
  const html = stockDetails(snapshot, [unsafe], adapter, null)(key);
  assert.doesNotMatch(html, /tradingview\.com|素材/);
  const holdings = renderHoldings({ result: { resolved: false, open_positions: { 1234: key } } });
  assert.match(holdings, /現在の仮想保有は確定していません/);
  assert.doesNotMatch(holdings, /1234|仮想保有 1銘柄/);
});

test('target-day transitions have separate labels, totals and one card per episode', () => {
  const another = { ...key, episode_id: 2 };
  const opening = { symbol: '5678', candidate_date: date, episode_id: 1, entry_date: date };
  const daily = { ...snapshot, events: [
    { ...key, session: date, kind: 'WATCH_TERMINAL', reason: 'TRIGGERED' },
    { ...key, session: date, kind: 'ENTRY_CANDIDATE', reason: 'TRIGGERED' },
    { ...key, session: date, kind: 'MONITOR_RESET', reason: 'TRIGGERED' },
    { ...key, session: date, kind: 'WATCH_TERMINAL' },
    { ...another, session: date, kind: 'WATCH_STARTED' },
    { ...opening, session: key.candidate_date, kind: 'WATCH_STARTED' },
  ] };
  const model = { resolved: true, period: [key.candidate_date, date],
    trades: [{ ...closed, entry_date: date }], open_positions: { 5678: opening } };
  const html = currentMarkup([daily], [row], { adapter, model });
  assert.match(html, /cloud-transition--watch-start">監視開始 <b>1件/);
  assert.match(html, /cloud-transition--watch-end">監視終了 <b>1件/);
  assert.match(html, /cloud-transition--hold-start">仮想保有開始 <b>2件/);
  assert.match(html, /cloud-transition--hold-end">仮想保有終了 <b>1件/);
  assert.match(html, /監視終了<\/span><small>支持反発/);
  assert.match(html, /買付候補・その他の記録/);
  const cards = [...html.matchAll(/<article data-daily-change="([^"]+)">/g)].map(match => match[1]);
  assert.deepEqual(cards, ['1234|2026-11-17|1', '1234|2026-11-17|2', '5678|2026-11-18|1']);
});

test('candidate, reset and exit schedule do not count as target-day transitions', () => {
  const daily = { ...snapshot, events: [
    { ...key, session: date, kind: 'ENTRY_CANDIDATE', reason: 'TRIGGERED' },
    { ...key, session: date, kind: 'MONITOR_RESET', reason: 'UP_ESCAPED' },
    { ...key, session: key.candidate_date, kind: 'WATCH_TERMINAL', reason: 'UP_ESCAPED' },
  ] };
  const result = { resolved: true, period: [key.candidate_date, date], trades: [],
    open_positions: { 1234: { ...key, entry_date: key.candidate_date, scheduled_exit_date: date } } };
  const html = currentMarkup([daily], [row], { model: result });
  assert.match(html, /監視終了 <b>0件/);
  assert.match(html, /仮想保有開始 <b>0件/);
  assert.match(html, /仮想保有終了 <b>0件/);
  assert.doesNotMatch(html, /<article data-daily-change=/);
  const stale = { ...result, period: [key.candidate_date, key.candidate_date] };
  for (const model of [null, stale, { ...result, resolved: false }]) {
    assert.match(currentMarkup([daily], [row], { model }), /仮想保有終了 <b>未確定/);
  }
  assert.match(renderHoldings({ result: stale }, { asOf: date }), /対象日時点の仮想保有は未確定/);
});

test('data on hold is distinct from watching and virtual holding', () => {
  const watchSelection = [{ ...key, watch_status: 'WATCHING', selection_reason: null }];
  const html = currentMarkup([{ ...snapshot, held_symbols: { 1234: { reason: 'MISSING_SOURCE' } } }], [row], { watchSelection });
  assert.match(html, /<tr data-current-watch>.*?<span class="badge cloud-status-held">データ保留/);
  assert.doesNotMatch(html, /<span class="badge">監視中<\/span>/);
});

test('confirmed holding gains, losses, and flat returns appear outside details', () => {
  const position = { ...key, entry_date: date, entry_cost: 100000, shares: 100 };
  const performance = holdingPerformance(snapshot, [row], adapter);
  const cases = [[position, /positive">\+10,000円 <small>（\+10%）/],
    [{ ...position, entry_cost: 125000 }, /negative">-15,000円 <small>（-12%）/],
    [{ ...position, entry_cost: 110000 }, /cloud-pnl">0円 <small>（0%）/]];
  for (const [held, value] of cases) assert.match(performance(held, key.symbol), value);
  assert.match(performance({ ...position, episode_id: 2 }, key.symbol), /未確認/);
  assert.match(holdingPerformance({ ...snapshot, held_symbols: { 1234: {} } }, [row], adapter)(position, key.symbol), /未確認/);
  assert.match(holdingPerformance({ ...snapshot, as_of: key.candidate_date }, [row], adapter)(position, key.symbol), /未確認/);

  const model = { resolved: true, period: [key.candidate_date, date], trades: [], open_positions: { 1234: position } };
  const holdings = renderHoldings({ result: model, preferences: { exit_endpoint: 'd5_open' } }, { rows: [row], performance, asOf: date });
  assert.match(holdings, /data-label="評価損益"><span class="cloud-pnl positive">\+10,000円/);
  assert.doesNotMatch(holdings, /<details/);
  const dashboard = currentMarkup([snapshot], [row], { adapter, model });
  assert.match(dashboard, /cloud-card-pnl"><small>評価損益<\/small><span class="cloud-pnl positive">\+10,000円/);
});

test('completed holdings show exact settled gains or losses before stock details', () => {
  const daily = { ...snapshot, latest_closes: {} };
  const period = [key.candidate_date, date];
  const scenarios = [
    [closed, /positive">\+9,320円 <small>（\+9\.32%）/],
    [{ ...closed, profit: -870, return: -0.0087 }, /negative">-870円 <small>（-0\.87%）/],
    [{ ...closed, profit: 0, return: 0 }, /cloud-pnl">0円 <small>（0%）/],
    [{ ...closed, profit: null, return: null }, /cloud-pnl">未確認/],
  ];
  for (const [trade, expected] of scenarios) {
    const html = currentMarkup([daily], [row], { adapter, model: { resolved: true, period, trades: [trade] } });
    const card = html.split(/<article data-daily-change="[^"]+">/)[1].split('<details')[0];
    assert.match(card, /仮想保有終了/);
    assert.match(card, /確定損益/);
    assert.match(card, expected);
    assert.doesNotMatch(card, /評価損益/);
  }
  const model = { resolved: true, period, trades: [closed],
    open_positions: { 1234: { ...key, episode_id: 2, entry_date: date, entry_cost: 1000, shares: 1 } } };
  const html = currentMarkup([daily], [{ ...row, identity: '1234|2026-11-17|2' }], { adapter, model });
  assert.match(html, /確定損益<\/small><span class="cloud-pnl">未確認/);
  assert.doesNotMatch(html, /9,320円/);
});

test('current watches match the saved cohort by episode, including unmatched stale episodes', () => {
  const sameSymbolOtherEpisode = { ...key, episode_id: 9 };
  const high = { symbol: '4321', candidate_date: date, episode_id: 1 };
  const olderYear = { symbol: '2222', candidate_date: '2025-12-30', episode_id: 1 };
  const daily = { ...snapshot, monitor_state: { watches: {
    active: { episode: key }, expensive: { episode: high }, past: { episode: olderYear },
  } } };
  const open = { watch_status: 'WATCHING', selection_reason: null };
  const selected = currentMarkup([daily], [row], { watchSelection: [
    { ...open, ...sameSymbolOtherEpisode },
    { ...open, ...key },
    { ...open, ...high, selection_reason: 'PRICE_CAP' },
  ] }).split('id="new-a-watch-heading"')[1];
  assert.match(selected, /1銘柄/);
  assert.match(selected, /1234/);
  assert.doesNotMatch(selected, /4321|2222/);

  const unmatched = currentMarkup([daily], [row], { watchSelection: [{ ...open, ...sameSymbolOtherEpisode }] });
  assert.match(unmatched, /現在の監視<\/h2><span class="badge">0銘柄/);
  assert.match(currentMarkup([daily], [row], { modelPending: true }), /現在の監視<\/h2><span class="badge">計算中/);
  assert.match(currentMarkup([daily], [row]), /現在の監視<\/h2><span class="badge">未確認/);
});

test('history keeps all presentation rows and only displays modeled results for the exact episode', () => {
  const earlier = { ...row, identity: '1234|2026-11-17|2' };
  const older = { ...row, identity: '1234|2025-11-17|1' };
  const held = { ...key, episode_id: 2 };
  const rows = [row, earlier, older];
  const index = historyRecords(rows, { resolved: true, orders: [], trades: [closed],
    watches: [key, held], open_positions: { 1234: held } });
  assert.equal(index.size, rows.length);
  assert.equal(index.get(row.identity).t, closed);
  assert.equal(index.get(row.identity).open, null);
  assert.equal(index.get(earlier.identity).t, undefined);
  assert.equal(index.get(earlier.identity).open, held);
  assert.equal(index.get(older.identity).source, older);
  assert.equal(index.get(older.identity).w, undefined);
  assert.equal(historyRecords(rows, null).size, rows.length);
});

test('the dashboard hides the opening table while retaining the original holding cards and verified detail', () => {
  const open = { ...key, session: date, kind: 'REFERENCE_OPEN',
    price_status: 'HISTORICAL_REFERENCE_ONLY', execution_status: 'NOT_EXECUTED', reference_open: 1012.5 };
  const candidate = { ...key, session: date, kind: 'ENTRY_CANDIDATE' };
  const today = { ...snapshot, events: [open, candidate] };
  const published = { ...row, entry: { status: 'verified', basis: 'NEXT_SESSION_OPEN_REFERENCE', date, price: 1012.5 } };
  const position = { ...key, entry_date: date, entry_price_nominal: 1012.5, entry_cost: 101250, shares: 100 };
  for (const model of [null, { resolved: true, period: [key.candidate_date, date], trades: [],
    open_positions: { 1234: position }, orders: [{ ...key, order_date: date, status: 'FILLED' }] }]) {
    const html = currentMarkup([today], [published], { adapter, model });
    assert.doesNotMatch(html, /日足始値と仮想保有の結果|new-a-daily-opening-heading|data-daily-opening/);
    assert.match(html, /買付候補・その他の記録|買付候補/);
    if (model) assert.match(html, /仮想保有開始/);
  }
});
