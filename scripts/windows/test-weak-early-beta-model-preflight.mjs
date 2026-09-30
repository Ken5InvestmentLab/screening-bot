import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { probeFundamentalModel } from './weak-early-beta-daily-runner.mjs';

test('Cloud beta checks Luna xhigh with ChatGPT before detection', async () => {
  const parent = path.resolve(os.tmpdir());
  const fixture = fs.mkdtempSync(path.join(parent, 'weak-early-beta-model-preflight-'));
  try {
    const cliJs = path.join(fixture, 'fake-codex.mjs');
    fs.writeFileSync(cliJs, `
const args = process.argv.slice(2);
if (!args.includes('gpt-5.6-luna') ||
    !args.includes('model_reasoning_effort="xhigh"') ||
    !args.includes('forced_login_method="chatgpt"') ||
    process.env.OPENAI_API_KEY) process.exit(2);
if (process.env.FAIL_PROBE === '1') {
  console.log(JSON.stringify({ type: 'turn.failed' }));
  process.exit(1);
}
console.log(JSON.stringify({ type: 'turn.completed' }));
`);
    const fundamentalConfigPath = path.join(fixture, 'fundamental.json');
    fs.writeFileSync(fundamentalConfigPath, JSON.stringify({
      nodePath: process.execPath,
      cliJs,
      codexHome: fixture,
    }));
    const config = { fundamentalConfigPath };
    await probeFundamentalModel(config, path.join(fixture, 'success'), {
      ...process.env,
      OPENAI_API_KEY: 'must-not-reach-child',
      FAIL_PROBE: '0',
    });
    await assert.rejects(
      probeFundamentalModel(config, path.join(fixture, 'failure'), {
        ...process.env,
        OPENAI_API_KEY: 'must-not-reach-child',
        FAIL_PROBE: '1',
      }),
      /model preflight failed/,
    );
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${parent}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-model-preflight-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});
