import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { loadDailyConfig } from './weak-early-beta-daily-runner.mjs';

test('entry point rejects a foreign config before runtime creation or external commands', t => {
  const { clone, saved, writeConfig } = fixture(t);
  const runtime = path.join(saved, 'runtime');
  const file = writeConfig(saved, { repoPath: saved, runtimeDir: runtime });
  const runner = fileURLToPath(new URL('./weak-early-beta-daily-runner.mjs', import.meta.url));
  const child = spawnSync(process.execPath, [runner, file], {
    cwd: clone, encoding: 'utf8', timeout: 10_000,
    env: { SystemRoot: process.env.SystemRoot || '', PATH: '' },
  });
  assert.equal(child.status, 1);
  assert.match(child.stderr, /repository mismatch/);
  assert.equal(child.stdout, '');
  assert.equal(fs.existsSync(runtime), false);
  assert.deepEqual(fs.readdirSync(clone), []);
});

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'daily-config-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));

  const clone = path.join(root, 'clone');
  const saved = path.join(root, 'saved');

  fs.mkdirSync(clone);
  fs.mkdirSync(saved);

  function writeConfig(owner, values) {
    const file = path.join(
      owner,
      '.cache',
      'weak_early_beta',
      'daily-runner.config.json',
    );
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(values), 'utf8');
    return file;
  }

  return { root, clone, saved, writeConfig };
}

function withCwd(directory, fn) {
  const previous = process.cwd();
  try {
    process.chdir(directory);
    return fn();
  } finally {
    process.chdir(previous);
  }
}

// Keep these tests serial because two temporarily change process.cwd().

test('matching repo returns config unchanged', { concurrency: false }, t => {
  const { clone, writeConfig } = fixture(t);
  const config = {
    repoPath: clone,
    runtimeDir: path.join(clone, 'runtime'),
    fundamentalSettings: { unchanged: true },
  };
  const file = writeConfig(clone, config);

  assert.deepEqual(loadDailyConfig(file, clone), config);
  assert.equal(fs.existsSync(config.runtimeDir), false);
});

test('absolute clone config works from saved cwd', {
  concurrency: false,
}, t => {
  const { clone, saved, writeConfig } = fixture(t);
  const config = {
    repoPath: clone,
    runtimeDir: path.join(clone, 'runtime'),
  };
  const file = writeConfig(clone, config);

  withCwd(saved, () => {
    assert.deepEqual(loadDailyConfig(file, clone), config);
  });

  assert.equal(fs.existsSync(config.runtimeDir), false);
});

test('matching relative usage from clone cwd stays valid', {
  concurrency: false,
}, t => {
  const { clone, writeConfig } = fixture(t);
  const config = {
    repoPath: '.',
    runtimeDir: '.cache/weak_early_beta/runtime',
  };
  const file = writeConfig(clone, config);

  withCwd(clone, () => {
    assert.deepEqual(
      loadDailyConfig(path.relative(clone, file), clone),
      config,
    );
  });

  assert.equal(
    fs.existsSync(path.join(clone, config.runtimeDir)),
    false,
  );
});

test('incident: clone runner rejects relative saved config', {
  concurrency: false,
}, t => {
  const { clone, saved, writeConfig } = fixture(t);
  const runtime = path.join(saved, 'runtime');
  const file = writeConfig(saved, {
    repoPath: saved,
    runtimeDir: runtime,
  });

  withCwd(saved, () => {
    assert.throws(
      () => loadDailyConfig(path.relative(saved, file), clone),
      error => {
        assert.match(error.message, /repository mismatch/);
        assert.ok(error.message.includes(fs.realpathSync.native(saved)));
        assert.ok(error.message.includes(fs.realpathSync.native(clone)));
        return true;
      },
    );
  });

  assert.equal(fs.existsSync(runtime), false);
  assert.equal(fs.existsSync(path.join(clone, 'runtime')), false);
});

test('missing or empty repoPath is rejected', {
  concurrency: false,
}, t => {
  const { clone, writeConfig } = fixture(t);

  for (const repoPath of [undefined, null, '', '   ']) {
    const file = writeConfig(clone, { repoPath });
    assert.throws(
      () => loadDailyConfig(file, clone),
      /requires a non-empty repoPath/,
    );
  }
});

test('nonexistent configured repository is rejected', {
  concurrency: false,
}, t => {
  const { root, clone, writeConfig } = fixture(t);
  const file = writeConfig(clone, {
    repoPath: path.join(root, 'missing'),
    runtimeDir: path.join(root, 'runtime'),
  });

  assert.throws(
    () => loadDailyConfig(file, clone),
    /repoPath cannot be resolved/,
  );
  assert.equal(fs.existsSync(path.join(root, 'runtime')), false);
});

test('realpath accepts a repo alias and rejects a foreign alias', {
  concurrency: false,
}, t => {
  const { root, clone, saved, writeConfig } = fixture(t);
  const cloneAlias = path.join(root, 'clone-alias');
  const savedAlias = path.join(root, 'saved-alias');
  const linkType = process.platform === 'win32' ? 'junction' : 'dir';

  try {
    fs.symlinkSync(clone, cloneAlias, linkType);
    fs.symlinkSync(saved, savedAlias, linkType);
  } catch (error) {
    if (['EPERM', 'EACCES', 'ENOTSUP'].includes(error.code)) {
      t.skip(`Directory links unavailable: ${error.code}`);
      return;
    }
    throw error;
  }

  const matching = writeConfig(clone, { repoPath: cloneAlias });
  assert.deepEqual(loadDailyConfig(matching, clone), {
    repoPath: cloneAlias,
  });

  const foreign = writeConfig(saved, { repoPath: savedAlias });
  assert.throws(
    () => loadDailyConfig(foreign, clone),
    /repository mismatch/,
  );
});
