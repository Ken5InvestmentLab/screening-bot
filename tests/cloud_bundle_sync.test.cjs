const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const pages = ['latest','analytics','silence','dive','shadow','fusion','balance','guide'];
const filename = (audience, page) => `weak_early_beta_data_${audience}_${page}_${'a'.repeat(16)}_0000.json`;
async function fixture(t, fault) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'cloud-bundle-sync-'));
  t.after(async () => {
    assert.equal(path.dirname(root), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('cloud-bundle-sync-'));
    await fs.rm(root, {recursive:true,force:true});
  });
  const reports = path.join(root,'reports'), gate = path.join(root,'weak-early-beta-gate');
  await fs.mkdir(path.join(reports,'report-assets'),{recursive:true});
  await fs.mkdir(path.join(gate,'scripts'),{recursive:true});
  await fs.mkdir(path.join(gate,'public'),{recursive:true});
  await fs.copyFile(path.resolve(__dirname,'../weak-early-beta-gate/scripts/sync-report.mjs'),path.join(gate,'scripts/sync-report.mjs'));
  for (const page of pages) for (const audience of ['full','free']) {
    const name = filename(audience,page);
    const context = {audience,page,snapshot:'a'.repeat(16)};
    const bundle = {version:1,encoding:'gzip-base64-json',...context,chunk:0,variants:{'d6_open:all':{gzip:'cHJpdmF0ZS1vci1yZWxlYXNlZA=='}}};
    const payload = {bundleContext:context,variants:{'d6_open:all':{bundle:`./${name}`}}};
    if (page === 'analytics' && audience === 'free') {
      if (fault === 'path') payload.variants['d6_open:all'].bundle = '../private.json';
      if (fault === 'audience') payload.variants['d6_open:all'].bundle = `./${filename('full',page)}`;
      if (fault === 'metadata') bundle.audience = 'full';
      if (fault === 'key') bundle.variants = {};
    }
    await fs.writeFile(path.join(reports,name),fault === 'size' && page === 'analytics' && audience === 'free' ? ' '.repeat(1024*1024+1) : JSON.stringify(bundle));
    await fs.writeFile(path.join(reports,`weak_early_beta_${page}${audience==='free'?'_free':''}.html`),page === 'guide' ? '<html>guide</html>' : `<script id="cloud-analytics-data" type="application/json">${JSON.stringify(payload)}</script>`);
  }
  for (const name of ['weak-early-beta-interactions.js','weak-early-beta-theme-init.js','weak-early-beta-scenarios.js','weak-early-beta-push.js','weak-early-beta-service-worker.js']) await fs.writeFile(path.join(reports,name),'// generated');
  for (const name of ['discord-light','discord-dark','coconala-light','coconala-dark','x-light','x-dark','cloud-logo-light','cloud-logo-dark']) await fs.writeFile(path.join(reports,'report-assets',name+'.png'),'fixture');
  await fs.writeFile(path.join(reports,'private.json'),'PRIVATE RECEIPTS');
  await fs.writeFile(path.join(gate,'public','keep.json'),'keep');
  const stale = `weak_early_beta_data_full_analytics_${'b'.repeat(16)}_0000.json`;
  await fs.writeFile(path.join(gate,'public',stale),'stale');
  const result = spawnSync(process.execPath,[path.join(gate,'scripts/sync-report.mjs')],{encoding:'utf8'});
  return {result,publicDir:path.join(gate,'public'),stale};
}
test('actual sync copies only validated current bundles and preserves unrelated files',async t=>{
  const f=await fixture(t);
  assert.equal(f.result.status,0,f.result.stderr);
  const names=await fs.readdir(f.publicDir);
  assert.ok(names.includes(filename('free','analytics')));
  assert.ok(names.includes(filename('full','analytics')));
  assert.ok(names.includes('keep.json'));
  assert.ok(!names.includes('private.json'));
  assert.ok(!names.includes(f.stale));
});
for (const fault of ['path','audience','metadata','key','size']) test(`sync refuses ${fault} before touching existing public assets`,async t=>{
  const f=await fixture(t,fault);
  assert.notEqual(f.result.status,0);
  assert.deepEqual((await fs.readdir(f.publicDir)).sort(),['keep.json',f.stale].sort());
});

test('v05 calculator is a public code asset and private price evidence stays outside sync',async t=>{
 const f=await fixture(t);assert.equal(f.result.status,0,f.result.stderr);
 const names=await fs.readdir(f.publicDir);assert.ok(names.includes('weak-early-beta-scenarios.js'));
 assert.ok(!names.includes('private.json'));
});
