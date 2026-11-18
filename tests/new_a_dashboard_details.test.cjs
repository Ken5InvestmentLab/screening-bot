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
const { currentMarkup, stockDetails } = loadBrowserScript('owner-loader.js');
const { renderHoldings } = loadBrowserScript('finite-controller.js');
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

test('dashboard details use exact episode, verified quote and individual model result', () => {
  const html = currentMarkup([snapshot], [row], { adapter, model: { trades: [closed] } });
  assert.match(html, /銘柄の詳細/);
  assert.match(html, /TradingView|tradingview\.com\/chart/);
  assert.match(html, /対象日終値<\/dt><dd>1,100円/);
  assert.match(html, /仮想決済 成績<\/dt><dd>9,320円（9.32%）/);
  assert.match(html, /ファンダ分析/);
  assert.match(html, /&lt;strong&gt;素材&lt;\/strong&gt;/);
  assert.doesNotMatch(html, /<strong>素材<\/strong>/);
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
