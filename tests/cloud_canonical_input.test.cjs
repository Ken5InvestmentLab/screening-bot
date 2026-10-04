const test=require('node:test'),assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const load=()=>import('../weak-early-beta-gate/scripts/verify-canonical-input.mjs');
const ledger=Buffer.from('synthetic ledger'),calendar=Buffer.from('synthetic calendar');
const sha=b=>createHash('sha256').update(b).digest('hex');
function source(change=()=>{}) {
 const manifest={schema_version:1,adapter_version:'cloud-ledger-v1',source_ledger_revision:sha(ledger),observed_at:'2026-10-04T00:00:00Z',events:[]};
 const bank={source_sha256:sha(calendar)};change(manifest,bank);
 return `export const CANONICAL_MANIFEST = ${JSON.stringify(manifest)} as const;\nexport const BANK_CALENDAR = ${JSON.stringify(bank)} as const;\n`;
}
test('current private input passes without remote operations',async()=>{
 const {verifyCanonicalInput}=await load();verifyCanonicalInput(source(),ledger,calendar);
});
test('changed ledger blocks deployment until input is regenerated',async()=>{
 const {verifyCanonicalInput}=await load();assert.throws(()=>verifyCanonicalInput(source(),Buffer.from('new ledger'),calendar),/current canonical ledger/);
});
test('changed calendar blocks deployment until input is regenerated',async()=>{
 const {verifyCanonicalInput}=await load();assert.throws(()=>verifyCanonicalInput(source(),ledger,Buffer.from('new calendar')),/current shared calendar/);
});
test('old null stub cannot pass the deployment gate',async()=>{
 const {verifyCanonicalInput}=await load();assert.throws(()=>verifyCanonicalInput('export const CANONICAL_MANIFEST: unknown = null;',ledger,calendar),/missing private canonical input/);
});
test('unsupported adapter and malformed cutoff cannot pass the deployment gate',async()=>{
 const {verifyCanonicalInput}=await load();
 for(const change of [m=>m.adapter_version='unknown',m=>m.observed_at='invalid'])assert.throws(()=>verifyCanonicalInput(source(change),ledger,calendar));
});
