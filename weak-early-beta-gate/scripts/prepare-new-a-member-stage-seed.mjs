import { deepStrictEqual } from 'node:assert';
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import ts from 'typescript';
import { createMemberStageConfig } from './prepare-new-a-member-stage.mjs';

const gate = fileURLToPath(new URL('../', import.meta.url));
const stageRoot = path.join(gate, '.cache', 'new-a-member-stage');
const day = '2026-11-19';
const created = day + 'T08:00:00Z';
const symbol = '0000';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const literal = value => "'" + value.replaceAll("'", "''") + "'";
const descriptor = (json, rows) => ({ sha256: digest(json), bytes: Buffer.byteLength(json), rows });

export async function createSyntheticStageSeed() {
  const [ownerSchema, memberSchema] = await Promise.all([
    fs.readFile(path.join(gate, 'schema', 'new-a-private.sql'), 'utf8'),
    fs.readFile(path.join(gate, 'member-migrations', '0001_new_a_member_storage.sql'), 'utf8'),
  ]);

  const episode = { symbol, candidate_date: day, episode_id: 1 };
  const contents = {
    episodes: [episode],
    intents: [],
    watches: [{ ...episode, watch_status: 'WATCHING' }],
    presentation: [],
    current_daily: [],
    quotes: [[symbol, day, null]],
  };
  const parts = Object.entries(contents).map(([kind, rows]) => {
    const json = JSON.stringify(rows);
    return { kind, json, descriptor: { name: kind + '-000.json', ...descriptor(json, rows.length) } };
  });
  const version = digest(JSON.stringify(['SYNTHETIC_NEW_A_MEMBER_STAGE_V1', day, parts.map(part => part.descriptor)]));
  const ownerManifest = JSON.stringify({
    schema: 'A_BROWSER_PRIVATE_INPUT_V1',
    audience: 'EXISTING_CLOUD_OWNER_ONLY',
    strategy: 'A_BASE',
    source_version: version,
    as_of: day,
    live: false,
    input_header: { source_version: version, calendar: [day], limits: { identityUnverifiedBefore: {}, completeThrough: day } },
    collections: Object.fromEntries(parts.filter(part => part.kind !== 'quotes').map(part => [part.kind, [part.descriptor]])),
    quote_fields: ['open', 'high', 'low', 'close', 'volume', 'actual_close', 'actual_volume'],
    quotes: [parts.find(part => part.kind === 'quotes').descriptor],
    expected_quote_keys: contents.quotes.length,
  });
  const ownerHash = digest(ownerManifest);
  const id = 'a-' + ownerHash.slice(0, 24);
  const source = { status: 'READY', dataset_id: id, revision: 1, as_of: day, source_version: version };
  const identity = JSON.stringify(source);
  const presets = ['defensive', 'medium', 'return_priority'];
  const sharedParts = [
    { kind: 'history', index: 0, rows: [{ date: day, symbol, state: 'WATCHING' }] },
    { kind: 'analytics', index: 0, rows: presets.map(preset => ({ preset, from: day, through: day, resolved: false, metrics: null })) },
    ...presets.map((_, index) => ({ kind: 'chart', index, rows: [{ date: day, equity_yen: null, holding_count: null }] })),
  ].map(part => {
    const json = JSON.stringify(part);
    return { json, kind: part.kind, index: part.index, ...descriptor(json, part.rows.length) };
  });
  const shared = JSON.stringify({
    schema: 'NEW_A_SHARED_READONLY_VIEW_V1', audience: 'EXISTING_DESIGNATED_DISCORD_ROLE',
    basis: 'SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS', source,
    parts: sharedParts.map(({ json, ...meta }) => meta),
  });
  const sharedHash = digest(shared);
  const warning = '-- Synthetic fixture for the separate New A member stage only.';
  // SQLite has no general assertion statement. An invalid JSON literal aborts a nonempty import.
  const requireEmpty = "SELECT CASE WHEN EXISTS (SELECT 1 FROM sqlite_schema WHERE type = 'table'"
    + " AND substr(name, 1, 7) <> 'sqlite_' AND substr(name, 1, 4) <> '_cf_')"
    + " THEN json('Stage seed requires an empty database') ELSE 1 END;";

  const ownerSql = [
    warning,
    requireEmpty,
    ownerSchema.trim(),
    'INSERT INTO new_a_private_datasets (dataset_id, source_version, manifest_json, manifest_sha256, status, created_at) VALUES'
      + ` (${literal(id)}, ${literal(version)}, ${literal(ownerManifest)}, ${literal(ownerHash)}, 'STAGING', ${literal(created)});`,
    ...parts.map(({ descriptor: part, json }) =>
      'INSERT INTO new_a_private_parts (dataset_id, name, payload_json, sha256, byte_length) VALUES'
      + ` (${literal(id)}, ${literal(part.name)}, ${literal(json)}, ${literal(part.sha256)}, ${part.bytes});`),
    `UPDATE new_a_private_datasets SET status = 'READY' WHERE dataset_id = ${literal(id)};`,
    'INSERT INTO new_a_active_pointer (pointer_key, dataset_id, revision, updated_at) VALUES'
      + ` ('owner', ${literal(id)}, 1, ${literal(created)});`,
    '',
  ].join('\n');
  const memberSql = [
    warning,
    requireEmpty,
    memberSchema.trim(),
    `INSERT INTO private_projection_manifest (identity, digest, json) VALUES (${literal(identity)}, ${literal(sharedHash)}, ${literal(shared)});`,
    ...sharedParts.map(part => 'INSERT INTO private_projection_part (identity, kind, idx, json) VALUES'
      + ` (${literal(identity)}, ${literal(part.kind)}, ${part.index}, ${literal(part.json)});`),
    `INSERT INTO private_projection_ready (singleton, identity, digest) VALUES (1, ${literal(identity)}, ${literal(sharedHash)});`,
    '',
  ].join('\n');
  return { ownerSql, memberSql, source, symbol };
}

export async function verifyStageSeedTarget(candidate) {
  const configured = path.resolve(candidate);
  const relative = path.relative(stageRoot, configured).split(path.sep);
  if (relative.length !== 2 || !/^stage-[a-zA-Z0-9]{6}$/.test(relative[0]) || relative[1] !== 'wrangler.json') {
    throw Error('Use the generated, ignored member stage wrangler.json.');
  }
  const [file, realGate] = await Promise.all([fs.realpath(configured), fs.realpath(gate)]);
  const expectedPath = path.join(realGate, '.cache', 'new-a-member-stage', ...relative);
  if (path.relative(expectedPath, file) !== '') throw Error('Stage config must be inside its own generated directory.');
  const info = await fs.lstat(file);
  if (!info.isFile() || info.size > 16384) throw Error('Stage config is not a normal generated file.');
  let config;
  try {
    config = JSON.parse(await fs.readFile(file, 'utf8'));
  } catch {
    throw Error('Could not parse the generated member stage configuration.');
  }
  const canonicalPath = path.join(gate, 'wrangler.jsonc');
  const canonical = ts.parseConfigFileTextToJson(canonicalPath, await fs.readFile(canonicalPath, 'utf8'));
  if (canonical.error) throw Error('Could not read canonical release configuration.');
  const expected = createMemberStageConfig({
    accountId: config.account_id,
    publicBaseUrl: config.vars?.PUBLIC_BASE_URL,
    ownerDatabaseId: config.d1_databases?.[0]?.database_id,
    memberDatabaseId: config.d1_databases?.[1]?.database_id,
    ownerDiscordId: config.vars?.CLOUD_OWNER_DISCORD_ID,
  }, canonical.config, path.dirname(file));
  try {
    deepStrictEqual(config, expected);
  } catch {
    throw Error('Stage config differs from the dedicated stage configuration.');
  }
  return { configPath: file, stageDir: path.dirname(file) };
}

async function main() {
  let config;
  try {
    config = parseArgs({ options: { config: { type: 'string' } } }).values.config;
  } catch {
    throw Error('Use --config with the generated member stage wrangler.json.');
  }
  if (!config) throw Error('Use --config with the generated member stage wrangler.json.');
  const target = await verifyStageSeedTarget(config);
  const seed = await createSyntheticStageSeed();
  const out = await fs.mkdtemp(path.join(target.stageDir, 'seed-'));
  const ownerSqlPath = path.join(out, 'owner-seed.sql');
  const memberSqlPath = path.join(out, 'member-seed.sql');
  await Promise.all([
    fs.writeFile(ownerSqlPath, seed.ownerSql, { flag: 'wx' }),
    fs.writeFile(memberSqlPath, seed.memberSql, { flag: 'wx' }),
  ]);
  console.log(JSON.stringify({ configPath: target.configPath, ownerSqlPath, memberSqlPath, synthetic: true, applied: false }));
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  await main().catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
