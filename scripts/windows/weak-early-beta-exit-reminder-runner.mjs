import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); }
function loadDotEnv(env, file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!match || env[match[1]] !== undefined) continue;
    let value = match[2];
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    env[match[1]] = value;
  }
}
async function run(exe, args, { cwd, env }) {
  return await new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    const child = spawn(exe, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', reject);
    child.on('exit', code => resolve({ code, stdout, stderr }));
  });
}
function jstDate() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

async function main(configFile) {
  const config = readJson(path.resolve(configFile));
  const repo = path.resolve(config.repoPath);
  const env = { ...process.env };
  loadDotEnv(env, path.join(repo, '.env'));
  const date = config.date || jstDate();
  const branch = await run('git', ['branch', '--show-current'], { cwd: repo, env });
  if (branch.code !== 0 || branch.stdout.trim() !== 'research/weak-early-beta') throw new Error('refusing to run outside research/weak-early-beta');
  const reminder = await run(config.pythonPath, ['-m', 'weak_early_beta.cli', 'remind-exits', '--date', date], { cwd: repo, env });
  if (reminder.code !== 0) throw new Error(`reminder failed: ${reminder.stderr.slice(-500)}`);
  const summary = JSON.parse(reminder.stdout.trim());
  if (summary.reminders > 0) {
    const add = await run('git', ['add', '-A', '--', 'reports/weak_early_beta*.html', 'weak_early_beta/state'], { cwd: repo, env });
    if (add.code !== 0) throw new Error('git add failed');
    const diff = await run('git', ['diff', '--cached', '--quiet'], { cwd: repo, env });
    if (diff.code === 1) {
      const commit = await run('git', ['commit', '-m', `chore: record Cloud exit reminders ${date} [skip ci]`], { cwd: repo, env });
      if (commit.code !== 0) throw new Error('git commit failed');
      const push = await run('git', ['push', 'origin', 'research/weak-early-beta'], { cwd: repo, env });
      if (push.code !== 0) throw new Error('git push failed');
    }
  }
  console.log(JSON.stringify({ identity: 'WEAK_EARLY_CLOUD_EXIT_REMINDER_V1', ...summary, ok: true }));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-exit-reminder-runner.mjs <config.json>');
  await main(process.argv[2]);
}
