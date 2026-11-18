'use strict';

const fs = require('node:fs');
const { MORNING_CRON, planEvaluationMorning, planHoldingTransitions } = require('./new-a-evaluation-morning.cjs');

async function plan({ kind, now, scheduledAt, targetDate, active, owner, preferences, calendar, parts }) {
  // Reuse the actual owner endpoint preference parser and the same exit policy.
  // Any query outside the selected owner row (including defaults) must fail.
  const { readTrial } = await import('../../weak-early-beta-gate/src/new-a-preferences.ts');
  const member = 'cloud_' + owner;
  const preferencesSource = {
    prepare(sql) {
      if (!sql.includes('FROM new_a_finite_trial_preferences AS trial')) throw Error('unexpected owner preference query');
      return {
        bind(viewKey, memberKey) {
          if (viewKey !== 'new-a-view:v1:' + member || memberKey !== member) throw Error('owner preference identity differs');
          return { first: async () => preferences };
        },
      };
    },
  };

  const readers = {
    now,
    bankBusinessDate: async date => date === targetDate,
    readActive: async () => active,
    readOwnerPreferences: async () => ({ ...await readTrial(preferencesSource, member), owner_binding_sha256: owner }),
    readCalendar: async () => calendar,
    readPart: async (dataset, name) => parts[dataset + '/' + name],
  };
  if (kind === 'EVALUATION_DAY_MORNING') return planEvaluationMorning({ ...readers, scheduledAt, cron: MORNING_CRON });
  if (kind === 'WATCH_TO_SIMULATED_HOLDING') return planHoldingTransitions({ ...readers, targetDate });
  throw Error('unknown lifecycle notice');
}

if (require.main === module) {
  Promise.resolve().then(() => plan(JSON.parse(fs.readFileSync(0, 'utf-8'))))
    .then(value => process.stdout.write(JSON.stringify(value)))
    .catch(() => {
      // The private payload and exception may contain owner state or quote data.
      process.stderr.write('new_a_lifecycle_inputs_rejected\n');
      process.exitCode = 1;
    });
}
module.exports = { plan };
