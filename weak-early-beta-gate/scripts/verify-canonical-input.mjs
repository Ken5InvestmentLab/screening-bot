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
 const contract=JSON.parse(await readFile(new URL('./new-a-code-contract.json',import.meta.url),'utf8'));
 const legacy=await readFile(new URL('../src/cloud-canonical-input.generated.ts',import.meta.url));
 assert.equal(contract.schema,'NEW_A_CODE_RELEASE_CONTRACT_V1');
 assert.equal(sha(legacy.toString('utf8').replace(/\r\n?/g,'\n')),contract.legacyCanonicalSha256,'Legacy scheduler canonical content must remain unchanged (LF); do not regenerate it from A');
 await import('./sync-report.mjs');
 await import('./verify-new-a-code-only.mjs');
 console.log('New-A code-only frame verified; existing legacy scheduler input preserved.');
}
