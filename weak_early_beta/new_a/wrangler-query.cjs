// Keep SQL in a private file and in memory, never in the OS child-process arguments.
// Run the installed Wrangler CLI's query mode; its file mode returns import totals.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { runMain } = require('node:module');

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

function prepareQueryArgs(cliBin, sqlFile) {
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
  return [process.execPath, main, 'd1', 'execute', 'CLOUD_DB', '--remote', '--command', sql, '--yes', '--json'];
}

if (require.main === module) {
  try {
    if (process.argv.length !== 4) throw Error('expected_cli_and_private_sql_file');
    process.argv = prepareQueryArgs(process.argv[2], process.argv[3]);
    runMain(process.argv[1]);
  } catch {
    console.error('private_wrangler_query_start_failed');
    process.exitCode = 1;
  }
}
module.exports = { prepareQueryArgs, selectStatementsOnly };
