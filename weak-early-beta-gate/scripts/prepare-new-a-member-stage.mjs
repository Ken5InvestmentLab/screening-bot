import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import ts from 'typescript';

const gate = fileURLToPath(new URL('../', import.meta.url));
const stageName = 'tentei-kyokuchi-cloud-member-stage';
export const stageOrigin = 'https://' + stageName + '.ipo-ken5-5489.workers.dev';
const outputParent = path.join(gate, '.cache', 'new-a-member-stage');
const snowflake = /^[1-9]\d{16,19}$/;
const uuid = /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const assets = [
  'browser-transport.js', 'finite-controller.js', 'finite-dom.js', 'initial-display.js',
  'member-loader.js', 'member-presentation.js', 'member-settings.js',
  'new-a-finite-worker.generated.js', 'new-a-legacy-interactions.generated.js',
  'owner-loader.js', 'owner-notifications.js', 'presentation-adapter.generated.js',
  'weak-early-beta-scenarios.js', 'weak-early-beta-theme-init.js',
  ...['cloud-logo', 'discord', 'coconala', 'x'].flatMap(brand =>
    ['dark', 'light'].map(theme => 'report-assets/' + brand + '-' + theme + '.png')),
];

function requireValue(condition, reason) {
  if (!condition) throw Error(reason);
}

export function createMemberStageConfig(options, canonical, outputDir) {
  const { accountId, publicBaseUrl, ownerDatabaseId, memberDatabaseId, ownerDiscordId, audience = 'tiered' } = options;
  requireValue(audience === 'tiered' || audience === 'role_only', 'Use a supported member stage audience.');
  requireValue(publicBaseUrl === stageOrigin || publicBaseUrl === stageOrigin + '/', 'Use the exact HTTPS member stage origin.');
  requireValue(/^[a-f0-9]{32}$/.test(accountId) && accountId !== '0'.repeat(32), 'Provide the verified Cloudflare account ID.');
  requireValue(snowflake.test(ownerDiscordId), 'Provide the trusted stage owner Discord ID.');
  requireValue([ownerDatabaseId, memberDatabaseId].every(id => uuid.test(id) && /[1-9a-f]/.test(id)),
    'Provide two valid, newly provisioned D1 database IDs for the stage.');
  requireValue(ownerDatabaseId !== memberDatabaseId, 'Stage owner and member databases must be distinct.');

  const productionD1 = canonical.d1_databases?.find(database => database.binding === 'CLOUD_DB');
  requireValue(productionD1 && uuid.test(productionD1.database_id), 'Could not verify the canonical database exclusion.');
  const canonicalDatabases = [canonical, ...Object.values(canonical.env ?? {})]
    .flatMap(environment => environment.d1_databases ?? [])
    .flatMap(database => [database.database_id, database.preview_database_id])
    .filter(id => typeof id === 'string')
    .map(id => id.toLowerCase());
  requireValue(![ownerDatabaseId, memberDatabaseId].some(id => canonicalDatabases.includes(id)),
    'Stage cannot bind a canonical database.');
  requireValue(canonical.name !== stageName && canonical.env?.preview?.name !== stageName
    && /^\d{4}-\d\d-\d\d$/.test(canonical.compatibility_date), 'Canonical Worker configuration is unexpected.');

  const { DISCORD_API_BASE, DISCORD_GUILD_ID, DISCORD_ALLOWED_ROLE_IDS } = canonical.vars ?? {};
  requireValue(DISCORD_API_BASE === 'https://discord.com/api'
    && snowflake.test(DISCORD_GUILD_ID) && snowflake.test(DISCORD_ALLOWED_ROLE_IDS)
    && canonical.env?.preview?.vars?.DISCORD_GUILD_ID === DISCORD_GUILD_ID
    && canonical.env?.preview?.vars?.DISCORD_ALLOWED_ROLE_IDS === DISCORD_ALLOWED_ROLE_IDS,
    'Could not verify the existing Discord guild and allowed-role pin.');

  return {
    name: stageName,
    account_id: accountId,
    main: path.relative(outputDir, path.join(gate, 'src', 'index.ts')).split(path.sep).join('/'),
    compatibility_date: canonical.compatibility_date,
    workers_dev: true,
    preview_urls: false,
    version_metadata: { binding: 'CLOUD_VERSION_METADATA' },
    assets: { directory: './public', binding: 'ASSETS', run_worker_first: true },
    durable_objects: { bindings: [{ name: 'CLOUD_ROLE_AUTHORITY', class_name: 'CloudRoleAuthority' }] },
    migrations: [{ tag: 'cloud-role-authority-v1', new_sqlite_classes: ['CloudRoleAuthority'] }],
    triggers: { crons: [] },
    keep_vars: false,
    d1_databases: [
      { binding: 'CLOUD_DB', database_name: 'tentei-cloud-member-stage-owner', database_id: ownerDatabaseId },
      { binding: 'CLOUD_MEMBER_DB', database_name: 'tentei-cloud-member-stage-member', database_id: memberDatabaseId },
    ],
    vars: {
      DISCORD_API_BASE, DISCORD_GUILD_ID, DISCORD_ALLOWED_ROLE_IDS,
      PUBLIC_BASE_URL: stageOrigin,
      CLOUD_MEMBER_STAGE_ORIGIN: stageOrigin,
      CLOUD_OWNER_ONLY_ENABLED: 'true',
      CLOUD_OWNER_DISCORD_ID: ownerDiscordId,
      CLOUD_MEMBER_VIEW_ENABLED: 'true',
      ...(audience === 'role_only' ? { CLOUD_MEMBER_AUDIENCE: audience } : {}),
      CLOUD_PUSH_REGISTRATION_ENABLED: 'false',
      CLOUD_PUSH_MODE: 'disabled',
      CLOUD_PUSH_SCHEDULER_ENABLED: 'false',
      CLOUD_NEW_A_OWNER_PUSH_ENABLED: 'false',
    },
  };
}

async function readStageAssets() {
  return Promise.all(assets.map(async name => {
    const source = path.join(gate, 'public', 'new-a-assets', name);
    const info = await fs.lstat(source).catch(() => null);
    requireValue(info?.isFile() && info.size > 0, 'Build the canonical data-free assets with npm run sync-report first.');
    return [name, await fs.readFile(source)];
  }));
}

function argumentsFrom(argv) {
  let values;
  try {
    ({ values } = parseArgs({
      args: argv,
      options: {
        'account-id': { type: 'string' },
        'public-base-url': { type: 'string' },
        'owner-database-id': { type: 'string' },
        'member-database-id': { type: 'string' },
        'owner-discord-id': { type: 'string' },
        audience: { type: 'string' },
      },
    }));
  } catch {
    // Never echo command-line values if the caller supplied an unexpected argument.
    throw Error('Use --account-id, --public-base-url, --owner-database-id, --member-database-id, --owner-discord-id and optional --audience.');
  }
  return {
    accountId: values['account-id'],
    publicBaseUrl: values['public-base-url'],
    ownerDatabaseId: values['owner-database-id'],
    memberDatabaseId: values['member-database-id'],
    ownerDiscordId: values['owner-discord-id'],
    audience: values.audience,
  };
}

async function main() {
  const options = argumentsFrom(process.argv.slice(2));
  const canonicalPath = path.join(gate, 'wrangler.jsonc');
  const { config, error } = ts.parseConfigFileTextToJson(canonicalPath, await fs.readFile(canonicalPath, 'utf8'));
  requireValue(!error && config, 'Could not read canonical release configuration.');
  createMemberStageConfig(options, config, outputParent);
  const stageAssets = await readStageAssets();
  await fs.mkdir(outputParent, { recursive: true });
  const outputDir = await fs.mkdtemp(path.join(outputParent, 'stage-'));
  const output = createMemberStageConfig(options, config, outputDir);
  await Promise.all(stageAssets.map(async ([name, contents]) => {
    const target = path.join(outputDir, 'public', 'new-a-assets', name);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, contents, { flag: 'wx' });
  }));
  const configPath = path.join(outputDir, 'wrangler.json');
  await fs.writeFile(configPath, JSON.stringify(output, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ configPath, callbackUrl: stageOrigin + '/auth/callback', deployed: false }));
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  await main().catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
