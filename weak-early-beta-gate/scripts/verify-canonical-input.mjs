import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export function verifyCanonicalInput(source, ledger, calendarSource) {
 const value = name => {
  const match = new RegExp(`export const ${name} = (.+) as const;`).exec(source);
  assert.ok(match, 'missing private canonical input; generate it before deployment');
  return JSON.parse(match[1]);
 };
 const manifest = value('CANONICAL_MANIFEST'), calendar = value('BANK_CALENDAR');
 assert.ok(manifest && calendar, 'missing private canonical input');
 assert.equal(manifest.source_ledger_revision, sha(ledger), 'regenerate private input from current canonical ledger');
 assert.equal(calendar.source_sha256, sha(calendarSource), 'regenerate private input from current shared calendar');
 assert.equal(manifest.schema_version, 1);
 assert.equal(manifest.adapter_version, 'cloud-ledger-v1');
 assert.ok(Number.isFinite(Date.parse(manifest.observed_at)), 'invalid observation cutoff');
 assert.ok(Array.isArray(manifest.events) && manifest.events.length <= 1000);
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
 const repoRoot = new URL('../../', import.meta.url);
 const [source, ledger, calendar] = await Promise.all([
  readFile(new URL('../src/cloud-canonical-input.generated.ts', import.meta.url), 'utf8'),
  readFile(new URL('weak_early_beta/state/detections.csv', repoRoot)),
  readFile(new URL('weak_early_beta/bank_calendar.py', repoRoot)),
 ]);
 verifyCanonicalInput(source, ledger, calendar);
 console.log('Private canonical ledger/calendar input matches source. No remote operation.');
}
