'use strict';
// Pure local calculation from the already verified daily bundle. No provider or
// notification transport is loaded, and no future price is read.
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
const path = require('node:path');
const { openVerifiedBundle } = require('./prepare-new-a-member-projection.cjs');
const { validateManifest } = require('../src/new-a-private.ts');
const { SHARED_TRIAL_DEFAULTS, OPEN_EXIT_POLICY } = require('../src/new-a-preferences.ts');
const { planNextEntries } = require('./new-a-ui-source/engine/finite-engine.cjs');
async function prepareEntryPlan(bundle, asOf, nextSession, snapshotSha) {
 const manifest = validateManifest(JSON.parse(await fs.readFile(path.join(bundle, 'manifest.json'), 'utf8')));
 assert(manifest.as_of === asOf && manifest.daily_snapshot_sha256 === snapshotSha, 'Entry plan snapshot differs');
 const data = await openVerifiedBundle(bundle, manifest);
 assert(data.current?.as_of === asOf && data.current.source_snapshot_sha256 === snapshotSha, 'Entry plan current differs');
 const options = { exitPolicy: OPEN_EXIT_POLICY, trialPreset: 'profit' };
 const full = data.runtime.simulate(SHARED_TRIAL_DEFAULTS, options);
 const portfolio = data.runtime.currentPortfolio(SHARED_TRIAL_DEFAULTS, asOf, { ...options, fullResult: full });
 const plan = planNextEntries({ asOf, nextSession, intents: data.runtime.input.intents,
  result: portfolio?.result ?? full, quotes: data.runtime.quotes,
  restrictionExits: data.runtime.input.limits.restrictionExitActions ?? [],
 }, SHARED_TRIAL_DEFAULTS, options);
 return { ...plan, source_version: manifest.source_version, snapshot_sha256: snapshotSha };
}
module.exports = { prepareEntryPlan };
if (require.main === module) prepareEntryPlan(...process.argv.slice(2))
 .then(value => process.stdout.write(JSON.stringify(value)))
 .catch(error => { console.error(error.message); process.exitCode = 1; });
