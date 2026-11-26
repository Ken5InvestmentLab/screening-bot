'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { runInNewContext } = require('node:vm');
const { validateManifest } = require('../src/new-a-private.ts');
const { SHARED_TRIAL_DEFAULTS, OPEN_EXIT_POLICY } = require('../src/new-a-preferences.ts');
const {
  attachFundamentals, dashboardRows, digest, historyPageSize, openVerifiedBundle, presets, readActiveEvidence,
  readBounded, safeHistory, sharedAnalytics, sharedChart,
} = require('./prepare-new-a-member-projection.cjs');
const { identityHold } = require('./new-a-ui-source/presentation-adapter.cjs');
const { planNextEntries } = require('./new-a-ui-source/engine/finite-engine.cjs');
function browserExport(name) {
  const filename = path.join(__dirname, 'new-a-ui-source/assets', name);
  const module = { exports: {} };
  runInNewContext(readFileSync(filename, 'utf8'), { module }, { filename });
  return module.exports;
}

const ownerPresentation = browserExport('owner-loader.js');
const finitePresentation = browserExport('finite-controller.js');

const proofLimit = 1024 * 1024;
const historyIndexLimit = 512 * 1024;
const preferences = Object.freeze({ ...SHARED_TRIAL_DEFAULTS });
const watchSection = '<section class="panel" aria-labelledby="new-a-watch-heading">';

function dashboardAdapter(history) {
  const locations = new Map();
  history.forEach((row, index) => {
    if (row.fundamental_sha256) {
      const key = row.date + '|' + row.symbol;
      locations.set(key, [Math.floor(index / historyPageSize) + 1, row.date, row.symbol].join('.'));
    }
  });
  return {
    identityHold,
    fundamentalMarkup(row) {
      const location = locations.get(row.signalDate + '|' + row.symbol);
      if (!location) return '';
      return '<button class="fundamental-toggle cloud-stock-action" type="button" aria-haspopup="dialog"'
        + ' aria-expanded="false" data-member-fundamental="' + location + '">ファンダ</button>';
    },
  };
}

function dashboardReferenceMarkup({ current, presentations, calendar, dashboardCloses, runtime, result, portfolio, adapter, entryPlan }) {
  assert(current && dashboardCloses?.date === current.as_of, 'Dashboard snapshot and quote date must match');
  const model = portfolio?.result ?? (result.period.at(-1) === current.as_of ? result : null);
  const dashboardYear = portfolio?.basis === 'LATEST_YEAR_STANDALONE' ? portfolio.result : null;
  const keys = ownerPresentation.dashboardIdentities(current, model, runtime.input.episodes);
  const rows = presentations.filter(row => keys.has(row.identity));
  const markup = ownerPresentation.currentMarkup([current], rows, {
    adapter, model, dashboardYear, preparedCloses: dashboardCloses, watchSelection: result.watches, entryPlan,
  });
  const details = ownerPresentation.stockDetails(current, rows, adapter, model, dashboardCloses, dashboardYear);
  const performance = ownerPresentation.holdingPerformance(current, rows, adapter, dashboardCloses);
  const holdings = finitePresentation.renderHoldings({ result, preferences, dashboard_year: dashboardYear }, {
    rows, calendar, details, performance, model, asOf: current.as_of,
  });
  const index = markup.indexOf(watchSection);
  assert(index > 0 && markup.lastIndexOf(watchSection) === index, 'Dashboard watch section differs from owner renderer');
  return markup.slice(0, index) + holdings + markup.slice(index);
}

function historyIndex(pages) {
  const names = [];
  const ids = new Map();
  const rows = pages.flatMap(({ rows }) => rows.map(({ date, symbol, companyName }) => {
    if (companyName === null) return [date, symbol, null];
    if (!ids.has(companyName)) {
      ids.set(companyName, names.length);
      names.push(companyName);
    }
    return [date, symbol, ids.get(companyName)];
  }));
  const index = JSON.stringify({ names, rows });
  assert(Buffer.byteLength(index) <= historyIndexLimit, 'Reference history index exceeds the display byte limit');
  return index;
}

async function prepareNewAReferenceView({ bundle, readyProof, readyProofSha256 }) {
  const [manifestRaw, proofRaw] = await Promise.all([
    readBounded(path.join(bundle, 'manifest.json'), proofLimit),
    readBounded(readyProof, proofLimit),
  ]);
  const manifest = validateManifest(JSON.parse(manifestRaw));
  const source = readActiveEvidence(proofRaw, readyProofSha256, digest(manifestRaw), manifest);
  const data = await openVerifiedBundle(bundle, manifest, { includeDisplay: true });
  assert(data.current?.as_of === source.as_of, 'Reference requires the current READY dashboard');
  const { history, episodes } = safeHistory(data.watches, source.as_of);
  attachFundamentals(history, episodes, data.presentations.filter(row => row?.fundamental?.auditStatus === 'pass'));
  const adapter = dashboardAdapter(history);
  const { analyticsReferenceMarkup } = require('./new-a-ui-source/reference-analytics.cjs');
  const { referenceHistoryPages } = require('./new-a-ui-source/reference-history.cjs');
  const variants = {};
  const models = {};
  for (const [preset, trialPreset] of presets) {
    const options = { exitPolicy: OPEN_EXIT_POLICY, trialPreset };
    const result = data.runtime.simulate(preferences, options);
    models[preset] = result;
    const portfolio = data.runtime.currentPortfolio(preferences, source.as_of, { ...options, fullResult: result });
    const latestYear = result.resolved ? null : data.runtime.simulateLatestYear(preferences, options);
    const nextDates = [...new Set(data.current.events.filter(e => e.kind === 'ENTRY_CANDIDATE'
      && e.session === source.as_of).map(e => e.reference_entry_date))];
    assert(nextDates.length <= 1, 'Entry plan has conflicting next sessions');
    const entryPlan = nextDates.length ? planNextEntries({ asOf: source.as_of, nextSession: nextDates[0],
      intents: data.runtime.input.intents, result: portfolio?.result ?? result, quotes: data.runtime.quotes,
      restrictionExits: data.runtime.input.limits.restrictionExitActions ?? [],
    }, preferences, { trialPreset }) : null;
    const render = { ...data, preferences, result, portfolio, adapter, preset, manifest, latestYear, entryPlan };
    variants['dashboard.' + preset] = dashboardReferenceMarkup(render);
    variants['analytics.' + preset] = analyticsReferenceMarkup(render, finitePresentation);
    variants['data.chart.' + preset] = JSON.stringify(sharedChart(result, source.as_of));
    if (preset === 'return_priority') {
      variants['data.dashboard'] = JSON.stringify(dashboardRows(
        data.current, portfolio?.result, episodes, new Set(data.calendar), source.as_of));
    }
  }
  variants['data.analytics'] = JSON.stringify(presets.map(([preset]) => sharedAnalytics(preset, models[preset], source.as_of)));
  const pages = referenceHistoryPages({
    history, episodes, presentations: data.presentations, models, pageSize: historyPageSize,
  }, finitePresentation);
  assert(pages.length === Math.max(1, Math.ceil(history.length / historyPageSize)) && pages.length <= 200,
    'Reference history must have the same Premium page count');
  for (const [index, { page, rows }] of pages.entries()) {
    const original = history.slice(index * historyPageSize, (index + 1) * historyPageSize);
    assert(page === index + 1 && rows.length === original.length && rows.every((row, rowIndex) => {
      const { date, symbol, fundamental_sha256 } = original[rowIndex];
      const item = fundamental_sha256 ? [page, date, symbol].join('.') : undefined;
      return row.date === date && row.symbol === symbol && row.item === item;
    }), 'Reference history differs from the exact Premium page order or report lookup');
    variants['history.' + page] = JSON.stringify({ page, rows });
  }
  variants['history.index'] = historyIndex(pages);
  assert(Object.values(variants).every(variant => typeof variant === 'string' && variant.length > 0),
    'Every reference must contain presentation');
  return { source, variants };
}

async function main(args) {
  const { values } = parseArgs({ args, options: {
    bundle: { type: 'string' },
    'ready-proof': { type: 'string' },
    'ready-proof-sha256': { type: 'string' },
    out: { type: 'string' },
  } });
  assert(Object.values(values).length === 4 && Object.values(values).every(Boolean),
    'Required arguments: --bundle --ready-proof --ready-proof-sha256 --out');
  const reference = await prepareNewAReferenceView({
    bundle: values.bundle, readyProof: values['ready-proof'], readyProofSha256: values['ready-proof-sha256'],
  });
  await fs.mkdir(values.out);
  await fs.writeFile(path.join(values.out, 'reference-view.json'), JSON.stringify(reference) + '\n', { flag: 'wx' });
}

module.exports = { prepareNewAReferenceView };
if (require.main === module) {
  main(process.argv.slice(2)).catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
