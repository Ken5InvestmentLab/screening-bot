const test = require('node:test');
const assert = require('node:assert/strict');

const { parseSignalFeatureSnapshots } = require('../sheets');
const {
  applySignalSnapshot,
  buildSnapshotOnlyResult,
} = require('../signal_snapshot');

const options = {
  stableConditions: ['ema25', 'macdpos', 'stoch75', 'bb80', 'pre_down3', 'gap_up'],
  sniperConditions: ['vol12', 'atr3', 'hb20', 'rsi5070', 'ich_chikou', 'rci9_os'],
  sniperMaxScore: 6,
};

test('snapshot sheet parser accepts flexible headers and keeps the first final row', () => {
  const rows = [
    ['metadata'],
    [
      'alert_id', 'symbol_code', 'stable_star_score', 'modes_json',
      'features_json', 'stable_filters_json', 'status',
    ],
    [
      'A-1', 'TYO:7807', '★5', '[]',
      JSON.stringify({ ema25: true, macdpos: true, stoch75: true, bb80: true, pre_down3: false, gap_up: true, _atr: 2.4 }),
      JSON.stringify(['ema25', 'macdpos', 'stoch75', 'bb80', 'gap_up']),
      'FINAL',
    ],
    ['A-1', '7807', '6', '["sniper"]', '{}', '[]', 'FINAL'],
    ['A-2', '1234', '6', '["sniper"]', '{}', '[]', 'PENDING'],
  ];

  const snapshots = parseSignalFeatureSnapshots(rows);
  assert.equal(snapshots.size, 1);
  const snapshot = snapshots.get('A-1');
  assert.equal(snapshot.symbol, '7807');
  assert.equal(snapshot.stableScore, 5);
  assert.equal(snapshot.hasModes, true);
  assert.deepEqual([...snapshot.modes], []);
  assert.equal(snapshot.features.pre_down3, false);
});

test('final snapshot fixes Stable score, Sniper membership, volatility, and passed conditions', () => {
  const liveResult = {
    symbol: '7807',
    score: 6,
    maxScore: 6,
    filters: ['PM再計算の条件'],
    sniperScore: 6,
    sniperFilters: ['PM再計算のSniper条件'],
    sniperEnabled: true,
    atrPct: 3.1,
    indicators: { preDown3: true },
  };
  const snapshot = {
    stableScore: 5,
    modes: new Set(),
    hasModes: true,
    features: {
      ema25: true,
      macdpos: true,
      stoch75: true,
      bb80: true,
      pre_down3: false,
      gap_up: true,
      _atr: 2.4,
    },
    stableFilters: ['ema25', 'macdpos', 'stoch75', 'bb80', 'gap_up'],
    sniperFilters: [],
  };

  const result = applySignalSnapshot(liveResult, snapshot, options);
  assert.equal(result.score, 5);
  assert.equal(result.sniperEnabled, false);
  assert.equal(result.sniperScore, -1);
  assert.equal(result.atrPct, 2.4);
  assert.equal(result.filters.length, 5);
  assert.ok(result.filters.includes('終値が25日EMAより上'));
  assert.ok(!result.filters.includes('直近3日連続下落後'));
});

test('snapshot can publish a fixed result even when OHLCV is unavailable later', () => {
  const signal = {
    alertId: 'A-3',
    symbol: '7807',
    date: '2026/07/14',
    entry: 836,
    eval5bd: null,
    perf5bd: null,
  };
  const snapshot = {
    stableScore: 6,
    modes: new Set(['sniper', 'mega5_rebound']),
    hasModes: true,
    features: { _atr: 2.1, vol12: true, atr3: true },
    stableFilters: [],
    sniperFilters: ['vol12', 'atr3'],
  };

  const result = buildSnapshotOnlyResult(signal, snapshot, options);
  assert.equal(result.score, 6);
  assert.equal(result.sniperEnabled, true);
  assert.equal(result.sniperScore, 6);
  assert.equal(result.signalPrice, 836);
  assert.deepEqual(result.sniperFilters, [
    '出来高が20日平均の1.2倍以上',
    'ATRが3%未満',
  ]);
  assert.equal(Object.hasOwn(result, 'mega5'), false);
});
