// Keep SQL in a private file and in memory, never in the OS child-process arguments.
// Run the installed Wrangler CLI's query mode; its file mode returns import totals.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { runMain } = require('node:module');

const ownerBinding = 'CLOUD_DB';
const memberBinding = 'CLOUD_MEMBER_DB';
const memberDatabaseId = '72edf9bf-b033-463b-a053-ff259db17cb5';

function canonicalMemberConfig(repo) {
  // Match publisher.py's production-only binding checks for standalone calls.
  const configPath = path.join(repo, 'weak-early-beta-gate/wrangler.jsonc');
  const invalid = () => Error('canonical_member_d1_config_required');
  let config;
  try {
    if (fs.realpathSync(configPath) !== configPath || !fs.statSync(configPath).isFile()) throw invalid();
    config = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, ''));
  } catch { throw invalid(); }
  const databases = config?.d1_databases;
  if (!Array.isArray(databases) || databases.some(db => !db || typeof db !== 'object' || Array.isArray(db))
    || config.name !== 'tentei-kyokuchi-cloud' || config.preview_urls !== false) throw invalid();
  const matches = databases.filter(db => db.binding === memberBinding || db.database_name === memberBinding
    || db.database_id === memberDatabaseId);
  const owners = databases.filter(db => db.binding === ownerBinding);
  const previewDatabases = config.env?.preview?.d1_databases;
  if (matches.length !== 1 || owners.length !== 1 || owners[0].database_id !== 'e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb'
    || owners[0].database_name !== 'tentei-cloud-settings' || databases.some(db => db.preview_database_id === memberDatabaseId)
    || !Array.isArray(previewDatabases) || previewDatabases.length !== 0) throw invalid();
  const member = matches[0];
  if (member.binding !== memberBinding || member.database_name !== 'tentei-cloud-member-view'
    || member.database_id !== memberDatabaseId || member.remote !== false || member.migrations_dir !== 'member-migrations'
    || Object.hasOwn(member, 'preview_database_id') || Object.hasOwn(member, 'database_internal_env')) throw invalid();
  return configPath;
}

function selectStatementsOnly(sql) {
  if (sql.includes('\0')) return false;
  let quote = null, start = 0;
  const statements = [];
  for (let i = 0; i < sql.length; i++) {
    const char = sql[i];
    if (quote) {
      if (char === quote) {
        if (sql[i + 1] === quote) i++;
        else quote = null;
      }
    } else if ("'\"`".includes(char)) quote = char;
    else if (char === '[') quote = ']';
    else if (sql.slice(i, i + 2) === '--' || sql.slice(i, i + 2) === '/*') return false;
    else if (char === ';') { statements.push(sql.slice(start, i).trim()); start = i + 1; }
  }
  if (quote) return false;
  const tail = sql.slice(start).trim();
  if (tail) statements.push(tail);
  return statements.length > 0 && statements.every(statement => /^SELECT\b/i.test(statement));
}

function prepareQueryArgs(cliBin, sqlFile, binding = ownerBinding) {
  if (binding !== ownerBinding && binding !== memberBinding) throw Error('unsupported_d1_binding');
  const cli = fs.realpathSync(cliBin);
  const repo = path.resolve(path.dirname(cli), '../../../..');
  const expected = path.join(repo, 'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js');
  if (cli !== expected) throw Error('unexpected_wrangler_cli');
  const input = fs.realpathSync(sqlFile);
  const root = fs.realpathSync(path.join(repo, '.cache/weak_early_beta/new-a-private'));
  const relative = path.relative(root, input);
  if (!relative || relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw Error('private_sql_file_required');
  }
  if (!fs.statSync(input).isFile() || fs.statSync(input).size > 1024 * 1024) throw Error('private_sql_budget_exceeded');
  const sql = fs.readFileSync(input, 'utf8');
  if (!selectStatementsOnly(sql)) throw Error('read_only_select_required');
  const main = path.resolve(path.dirname(cli), '../wrangler-dist/cli.js');
  if (!fs.statSync(main).isFile()) throw Error('existing_wrangler_main_unavailable');
  const config = binding === memberBinding ? ['--config', canonicalMemberConfig(repo), '--env='] : [];
  return [process.execPath, main, 'd1', 'execute', binding, '--remote', '--command', sql, '--yes', '--json', ...config];
}

if (require.main === module) {
  try {
    if (process.argv.length !== 4 && process.argv.length !== 5) throw Error('expected_cli_and_private_sql_file');
    const binding = process.argv[4];
    process.argv = prepareQueryArgs(process.argv[2], process.argv[3], binding);
    if (binding === memberBinding) process.env.CLOUDFLARE_API_BASE_URL = 'https://api.cloudflare.com/client/v4';
    runMain(process.argv[1]);
  } catch {
    console.error('private_wrangler_query_start_failed');
    process.exitCode = 1;
  }
}
module.exports = { prepareQueryArgs, selectStatementsOnly };
