'use strict';

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { DATASET_ID, validateManifest } = require('../src/new-a-private.ts');
const { DEFAULTS, OPEN_EXIT_POLICY } = require('../src/new-a-preferences.ts');
const { createDatasetRuntime } = require('./new-a-ui-source/engine/dataset-runtime.cjs');

const digest = raw => createHash('sha256').update(raw).digest('hex');
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const manifestLimit = 1024 * 1024;
const partLimit = 196608;
const historyPageSize = 100;
const chartLimit = 3000;
const sharedPreferences = Object.freeze({ ...DEFAULTS, price_cap_yen: null });
const presets = [['defensive', 'defensive'], ['medium', 'balanced'], ['return_priority', 'profit']];
const states = new Set(['WATCHING', 'TRIGGERED', 'EXPIRED', 'UP_ESCAPED', 'DOWN_INVALIDATED', 'REFERENCE_ONLY']);

function validDay(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const time = Date.parse(value + 'T00:00:00Z');
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

async function readBounded(file, limit) {
  const info = await fs.lstat(file);
  assert(info.isFile() && info.size <= limit, 'Invalid input file or byte limit exceeded');
  const raw = await fs.readFile(file);
  assert(raw.length <= limit, 'Input exceeded its byte limit');
  return raw;
}

function readActiveEvidence(proofRaw, proofSha256, bundleManifestSha256, manifest) {
  assert(hash(proofSha256) && digest(proofRaw) === proofSha256, 'Owner readback proof pin mismatch');
  const proof = JSON.parse(proofRaw);
  assert.equal(proof.schema, 'NEW_A_OPERATIONAL_OBSERVATION_V1', 'Unsupported owner readback proof');
  assert(hash(proof.raw_response_sha256) && hash(proof.active_manifest_sha256)
    && hash(proof.active_logical_manifest_sha256) && typeof proof.observed_at === 'string'
    && Number.isFinite(Date.parse(proof.observed_at)), 'Incomplete verified owner readback');
  assert(bundleManifestSha256 === proof.active_manifest_sha256
    || bundleManifestSha256 === proof.active_logical_manifest_sha256, 'Bundle differs from the verified owner READY manifest');
  assert(typeof proof.active_dataset_id === 'string' && DATASET_ID.test(proof.active_dataset_id)
    && Number.isSafeInteger(proof.active_revision) && proof.active_revision > 0
    && hash(proof.active_source_version) && validDay(proof.active_as_of), 'Invalid owner READY identity');
  const active = ['NEW_A_ACTIVE_METADATA_V1', proof.active_dataset_id, proof.active_revision, 'READY',
    proof.active_source_version, proof.active_manifest_sha256, proof.active_as_of];
  assert.equal(digest(JSON.stringify(active)), proof.d1_active_sha256, 'Owner READY metadata digest mismatch');
  assert(manifest.strategy === 'A_BASE' && manifest.as_of === proof.active_as_of
    && manifest.source_version === proof.active_source_version, 'Bundle generation mismatch');
  return {
    status: 'READY',
    dataset_id: proof.active_dataset_id,
    revision: proof.active_revision,
    as_of: proof.active_as_of,
    source_version: proof.active_source_version,
  };
}

async function openVerifiedBundle(bundle, manifest) {
  async function readPart(descriptor) {
    const raw = await readBounded(path.join(bundle, descriptor.name), partLimit);
    assert(raw.length === descriptor.bytes && digest(raw) === descriptor.sha256, 'Canonical source part hash or size mismatch');
    const values = JSON.parse(raw);
    assert(Array.isArray(values) && values.length === descriptor.rows, 'Canonical source part row count mismatch');
    return values;
  }
  async function collectParts(descriptors) {
    const rows = [];
    for (const descriptor of descriptors) {
      for (const row of await readPart(descriptor)) rows.push(row);
    }
    return rows;
  }

  const input = { ...manifest.input_header };
  for (const key of ['episodes', 'intents', 'watches']) input[key] = await collectParts(manifest.collections[key]);
  for (const key of ['presentation', 'current_daily']) {
    for (const descriptor of manifest.collections[key]) await readPart(descriptor);
  }
  assert(Array.isArray(input.calendar) && input.calendar.length > 0 && input.calendar.length <= chartLimit
    && input.calendar.at(-1) === manifest.as_of
    && input.calendar.every((day, i) => validDay(day) && (i === 0 || input.calendar[i - 1] < day)), 'Invalid canonical calendar');

  const fields = manifest.quote_fields;
  assert(Array.isArray(fields) && fields.length > 0 && fields.every(field => typeof field === 'string')
    && new Set(fields).size === fields.length, 'Invalid canonical quote fields');
  const quotes = new Map();
  for (const descriptor of manifest.quotes) {
    for (const row of await readPart(descriptor)) {
      assert(Array.isArray(row) && row.length === 3, 'Invalid canonical quote row');
      const [symbol, date, values] = row;
      const key = symbol + '|' + date;
      assert(typeof symbol === 'string' && /^[0-9A-Z]{4}$/.test(symbol) && validDay(date) && !quotes.has(key)
        && (values === null || Array.isArray(values) && values.length === fields.length), 'Invalid canonical quote key or values');
      quotes.set(key, values === null ? null : Object.fromEntries(fields.map((field, index) => [field, values[index]])));
    }
  }
  assert.equal(quotes.size, manifest.expected_quote_keys, 'Canonical quote key count mismatch');
  return {
    watches: input.watches,
    runtime: createDatasetRuntime(input, {
      get(symbol, date) {
        const key = symbol + '|' + date;
        assert(quotes.has(key), 'Canonical simulation requires an unavailable quote key');
        return quotes.get(key);
      },
    }),
  };
}

function safeHistory(watches, asOf) {
  const rows = new Map();
  for (const { symbol, candidate_date: date, watch_status: state } of watches) {
    assert(typeof symbol === 'string' && /^[0-9A-Z]{4}$/.test(symbol)
      && validDay(date) && date <= asOf && states.has(state), 'Invalid shared history row');
    const key = date + '|' + symbol;
    assert(!rows.has(key) || rows.get(key).state === state, 'Ambiguous shared history state');
    rows.set(key, { date, symbol, state });
  }
  return Array.from(rows.values()).sort((a, b) => b.date.localeCompare(a.date) || a.symbol.localeCompare(b.symbol, 'en'));
}

function amount(value) {
  assert(Number.isFinite(value) && Math.abs(value) < 1e12, 'Invalid shared simulation amount');
  return Math.round(value * 100) / 100;
}

function sharedAnalytics(preset, result, asOf) {
  assert(Array.isArray(result.period) && validDay(result.period[0]) && result.period.at(-1) === asOf
    && typeof result.resolved === 'boolean', 'Simulation does not match the canonical period');
  const row = { preset, from: result.period[0], through: asOf, resolved: result.resolved, metrics: null };
  if (!result.resolved) return row;
  const { netProfit, maxDrawdown, winRate, closed } = result.metrics;
  assert(Number.isSafeInteger(closed) && closed >= 0 && Number.isFinite(maxDrawdown) && maxDrawdown >= -1
    && maxDrawdown <= 0 && (closed === 0 ? winRate === null : Number.isFinite(winRate) && winRate >= 0 && winRate <= 1),
  'Invalid shared simulation metrics');
  return {
    ...row,
    metrics: {
      net_profit: amount(netProfit),
      max_drawdown_pct: amount(maxDrawdown * 100),
      win_rate_pct: winRate === null ? null : amount(winRate * 100),
      trade_count: closed,
    },
  };
}

function sharedChart(result, asOf) {
  const rows = result.daily.map((day, index) => {
    assert(validDay(day.date) && (index === 0 || result.daily[index - 1].date < day.date)
      && typeof day.unresolved === 'boolean', 'Invalid shared simulation day');
    if (day.unresolved) return { date: day.date, equity_yen: null, holding_count: null };
    assert(Number.isSafeInteger(day.positions) && day.positions >= 0, 'Invalid shared holding count');
    return { date: day.date, equity_yen: amount(day.equity_diagnostic), holding_count: day.positions };
  });
  assert(rows.length <= chartLimit && rows.at(-1)?.date === asOf, 'Invalid shared simulation chart range');
  return rows;
}

async function prepareNewAMemberProjection({ bundle, readyProof, readyProofSha256 }) {
  const [manifestRaw, proofRaw] = await Promise.all([
    readBounded(path.join(bundle, 'manifest.json'), manifestLimit),
    readBounded(readyProof, manifestLimit),
  ]);
  const sourceManifestSha256 = digest(manifestRaw);
  const manifest = validateManifest(JSON.parse(manifestRaw));
  const source = readActiveEvidence(proofRaw, readyProofSha256, sourceManifestSha256, manifest);
  const { runtime, watches } = await openVerifiedBundle(bundle, manifest);
  const history = safeHistory(watches, source.as_of);
  const parts = [];
  function add(kind, index, rows) {
    const json = JSON.stringify({ kind, index, rows });
    const bytes = Buffer.byteLength(json);
    assert(bytes <= partLimit, 'Shared projection part exceeds the storage limit');
    parts.push({ kind, index, rows: rows.length, bytes, sha256: digest(json), json });
  }
  for (let offset = 0; offset < history.length; offset += historyPageSize) {
    add('history', offset / historyPageSize, history.slice(offset, offset + historyPageSize));
  }
  const analytics = [];
  for (const [index, [preset, trialPreset]] of presets.entries()) {
    const result = runtime.simulate(sharedPreferences, { trialPreset, exitPolicy: OPEN_EXIT_POLICY });
    analytics.push(sharedAnalytics(preset, result, source.as_of));
    add('chart', index, sharedChart(result, source.as_of));
  }
  add('analytics', 0, analytics);
  assert(parts.length <= 204, 'Shared projection exceeds the reader part count');
  const projection = {
    schema: 'NEW_A_SHARED_READONLY_VIEW_V1',
    audience: 'EXISTING_DESIGNATED_DISCORD_ROLE',
    basis: 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS',
    source,
    parts: parts.map(({ json, ...descriptor }) => descriptor),
  };
  const manifestJson = JSON.stringify(projection);
  assert(Buffer.byteLength(manifestJson) <= 65_536, 'Shared projection manifest exceeds the storage limit');
  return {
    manifestJson,
    parts,
    receipt: {
      schema: 'NEW_A_MEMBER_PROJECTION_OFFLINE_V1',
      source,
      source_manifest_sha256: sourceManifestSha256,
      owner_readback_sha256: readyProofSha256,
      projection_manifest_sha256: digest(manifestJson),
      history_rows: history.length,
      parts: parts.length,
      activated: false,
    },
  };
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
  const { manifestJson, parts, receipt } = await prepareNewAMemberProjection({
    bundle: values.bundle, readyProof: values['ready-proof'], readyProofSha256: values['ready-proof-sha256'],
  });
  await fs.mkdir(values.out);
  await fs.writeFile(path.join(values.out, 'manifest.json'), manifestJson, { flag: 'wx' });
  for (const part of parts) {
    await fs.writeFile(path.join(values.out, part.kind + '-' + part.index + '.json'), part.json, { flag: 'wx' });
  }
  await fs.writeFile(path.join(values.out, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
}

module.exports = { prepareNewAMemberProjection };
if (require.main === module) {
  main(process.argv.slice(2)).catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
