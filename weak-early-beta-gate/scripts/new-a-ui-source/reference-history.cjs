'use strict';

const assert = require('node:assert/strict');
const { identityHold } = require('./presentation-adapter.cjs');

const levelPresets = [
  ['defensive', 'defensive'],
  ['medium', 'balanced'],
  ['return_priority', 'profit'],
];
const visibleStatuses = new Set([
  'WATCHING', 'TRIGGERED', 'EXPIRED', 'UP_ESCAPED', 'DOWN_INVALIDATED', 'REFERENCE_ONLY',
  'DATA_GAP', 'BASIS_CHANGED', 'IDENTITY_CHANGED', 'HOLD_ENDED', 'DAILY_FILLED_CAP', 'FILLED',
  'CAPACITY', 'LOT_EXCEEDS_ALLOCATION', 'CASH_INSUFFICIENT', 'DUPLICATE_HELD', 'PRICE_CAP',
  'SIGNAL_PRICE_UNVERIFIED', 'UNFILLED', 'UNFILLED_UNCERTAIN_ONE_PRICE', 'HALTED_UNRESOLVED',
  'IDENTITY_UNVERIFIED',
]);
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const positive = value => Number.isFinite(value) && value > 0;
const detectionKey = (date, symbol) => date + '|' + symbol;

function projectReference(reference) {
  const priceOnly = reference?.status === 'reference_price_only';
  if ((!priceOnly && reference?.status !== 'verified')
    || !datePattern.test(reference.date) || !positive(reference.price)) return null;
  return [reference.date, reference.price, priceOnly];
}

function projectLevel(record, fallback) {
  const { w, o, t, open } = record ?? {};
  const position = t ?? open;
  const status = w?.selection_reason ?? o?.status ?? w?.watch_status ?? fallback;
  assert(visibleStatuses.has(status), 'Invalid status in reference history');
  const selected = w?.selection_reason === null;
  let entry = null;
  let exit = null;
  if (position) {
    assert(datePattern.test(position.entry_date) && positive(position.entry_price_nominal)
      && positive(position.shares) && positive(position.entry_cost), 'Invalid reference history buy');
    entry = [position.entry_date, position.entry_price_nominal, position.shares, position.entry_cost];
  }
  if (t) {
    assert(datePattern.test(t.exit_date) && t.exit_date >= t.entry_date && positive(t.exit_price_nominal)
      && Number.isFinite(t.profit) && Number.isFinite(t.return), 'Invalid reference history settlement');
    exit = [t.exit_date, t.exit_price_nominal, t.profit, t.return];
  }
  return [status, selected, entry, exit];
}

function referenceHistoryPages({ history, episodes, presentations, models, pageSize = 100 }, finite) {
  assert(Number.isSafeInteger(pageSize) && pageSize > 0 && pageSize <= 100, 'Invalid reference history page size');
  const matchingEpisodes = new Map();
  for (const [key, watch] of episodes) {
    const detection = detectionKey(watch.candidate_date, watch.symbol);
    matchingEpisodes.set(detection, matchingEpisodes.has(detection) ? null : key);
  }

  const sourceRows = new Map();
  for (const row of presentations) {
    const detection = detectionKey(row.signalDate, row.symbol);
    const episode = matchingEpisodes.get(detection);
    if (typeof episode !== 'string' || episode !== row.identity || row.signalDate !== row.candidateDate) continue;
    assert(!sourceRows.has(detection), 'Duplicate reference history presentation');
    sourceRows.set(detection, row);
  }
  const matchingRows = [...sourceRows.values()];
  const levelRecords = levelPresets.map(([preset, trialPreset]) => {
    const model = models[preset];
    assert(model?.trial_policy?.id === trialPreset, 'Reference history simulation does not match its operating level');
    return finite.historyRecords(matchingRows, model);
  });

  const pages = [];
  for (let start = 0; start < Math.max(history.length, 1); start += pageSize) {
    const page = pages.length + 1;
    const rows = history.slice(start, start + pageSize).map(({ date, symbol, state, fundamental_sha256 }) => {
      const source = sourceRows.get(detectionKey(date, symbol));
      const close = source?.signalClose;
      const companyName = typeof source?.companyName === 'string' && source.companyName.trim()
        && Buffer.byteLength(source.companyName) <= 256 ? source.companyName : null;
      const chartAllowed = Boolean(source && source.chartAllowed !== false && !identityHold(source));
      const signalClose = close?.status === 'verified' && close.date === date && positive(close.price) ? close.price : null;
      return {
        date, symbol, companyName, chartAllowed, signalClose,
        d5: projectReference(source?.endpoints?.d5_close),
        d6: projectReference(source?.endpoints?.d6_open),
        levels: levelRecords.map(records => projectLevel(records.get(source?.identity), state)),
        ...chartAllowed && /^[a-f0-9]{64}$/.test(fundamental_sha256) ? { item: [page, date, symbol].join('.') } : {},
      };
    });
    pages.push({ page, rows });
  }
  return pages;
}

module.exports = { referenceHistoryPages };
