import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

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

async function main(configPath) {
  const config = JSON.parse(fs.readFileSync(path.resolve(configPath), 'utf8'));
  const repo = path.resolve(config.repoPath);
  const env = { ...process.env };
  loadDotEnv(env, path.join(repo, '.env'));
  const result = await new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    const child = spawn(config.pythonPath, ['-m', 'weak_early_beta.cli', 'watch-cloud-start'], {
      cwd: repo, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    });
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', reject);
    child.on('exit', code => resolve({ code, stdout, stderr }));
  });
  if (result.code !== 0) throw new Error(`Cloud start watchdog failed: ${result.stderr.slice(-500)}`);
  console.log(result.stdout.trim());
}

if (!process.argv[2]) throw new Error('usage: node weak-early-beta-start-watchdog.mjs <daily-runner.config.json>');
await main(process.argv[2]);
