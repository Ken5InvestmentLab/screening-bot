// The old full/free price-bundle publication contract is replaced by code-only new-A.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process'),{createHash}=require('node:crypto');
const repo=path.resolve(__dirname,'..'),sourceGate=path.join(repo,'weak-early-beta-gate'),baseline=process.env.NEW_A_TEST_BASELINE_ROOT||repo;
const {pathToFileURL}=require('node:url');
function checkHelp(html,{stagedFree=false}={}){
 const nav=html.match(/<nav class="nav"[\s\S]*?<\/nav>/)[0];
 const opener=nav.match(/<button id="cloud-help-open"[^>]*>ヘルプ<\/button>/)[0];
 assert.match(opener,/aria-haspopup="dialog" aria-controls="cloud-help-dialog"/);
 if(stagedFree)assert.match(opener,/data-member-premium-nav hidden/);
 assert.doesNotMatch(nav,/>その他<|weak_early_beta_(?:silence|dive|shadow|fusion|balance)\.html/);
 const popup=html.match(/<dialog id="cloud-help-dialog"[\s\S]*?<\/dialog>/)[0];
 assert.match(popup,/aria-labelledby="cloud-help-title"/);
 assert.match(popup,/aria-label="ヘルプを閉じる"/);
 assert.match(popup,/表示は仮想運用の試算です。売買の推奨や将来の成果の保証は行いません。投資判断はご自身で行ってください。/);
 assert.equal((popup.match(/<p>/g)||[]).length,2);
 assert.match(popup,/<h3>ラベルの見方<\/h3>/);
 assert.deepEqual(Array.from(popup.matchAll(/<dt>([^<]+)<\/dt>/g), match=>match[1]),[
  '監視開始・監視中','監視終了','買付候補','仮想保有開始・仮想保有終了','データ保留','試算対象',
 ]);
 assert.doesNotMatch(popup,/<a |<ol /);
 assert.match(html,/\.cloud-help-dialog\{width:min\(520px,calc\(100vw - 20px\)\)\}/);
 assert.match(html,/\.topbar \.cloud-primary-nav\{display:flex;flex-wrap:wrap;justify-content:flex-start;gap:4px\}/);
}
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function inventory(dir,rel=''){const result={};for(const e of await fs.readdir(dir,{withFileTypes:true})){const name=path.posix.join(rel,e.name),p=path.join(dir,e.name);if(e.isDirectory())Object.assign(result,await inventory(p,name));else result[name]=sha(await fs.readFile(p));}return result;}
async function fixture(t,fault){const root=await fs.mkdtemp(path.join(os.tmpdir(),'new-a-code-sync-'));t.after(async()=>{assert.equal(path.dirname(root),path.resolve(os.tmpdir()));assert(path.basename(root).startsWith('new-a-code-sync-'));await fs.rm(root,{recursive:true,force:true});});const gate=path.join(root,'weak-early-beta-gate'),scripts=path.join(gate,'scripts'),publicDir=path.join(gate,'public');await fs.mkdir(scripts,{recursive:true});await fs.mkdir(publicDir,{recursive:true});
 for(const name of ['sync-report.mjs','build-new-a-frame.mjs','build-new-a-member-frame.mjs','verify-new-a-code-only.mjs','new-a-code-contract.json'])await fs.copyFile(path.join(sourceGate,'scripts',name),path.join(scripts,name));await fs.cp(path.join(sourceGate,'scripts/new-a-ui-source'),path.join(scripts,'new-a-ui-source'),{recursive:true});
 const contractFile=path.join(scripts,'new-a-code-contract.json'),contract=JSON.parse(await fs.readFile(contractFile,'utf8'));for(const asset of [...contract.staticAssets,...contract.compatibilityAssets]){const target=path.join(root,asset.source);await fs.mkdir(path.dirname(target),{recursive:true});await fs.copyFile(path.join(baseline,asset.source),target);}
 // These existing reports/private artifacts must never be opened or copied.
 await fs.writeFile(path.join(root,'reports/private.json'),'SYNTHETIC_PRIVATE_EVIDENCE_DO_NOT_PUBLISH');await fs.writeFile(path.join(root,'reports/weak_early_beta_data_full_latest_aaaaaaaaaaaaaaaa_0000.json'),'SYNTHETIC_PRIVATE_PRICE_BUNDLE');
 const stale='weak_early_beta_data_full_latest_bbbbbbbbbbbbbbbb_0000.json';await fs.writeFile(path.join(publicDir,stale),'stale generated data');for(const name of ['report-interactions.js','report-theme-init.js'])await fs.writeFile(path.join(publicDir,name),'stale shared code');
 if(fault==='path')contract.staticAssets[0].source='../private.json';if(fault==='audience')contract.private_source='PUBLIC';if(fault==='metadata')contract.staticAssets[0].sha256='0'.repeat(64);if(fault==='key')contract.staticAssets[1].target=contract.staticAssets[0].target;
 if(fault==='asset-date')await fs.appendFile(path.join(scripts,'new-a-ui-source/assets/finite-controller.js'),'\n// SYNTHETIC forbidden calendar literal 2001-02-03\n');
 if(fault==='size')await fs.appendFile(path.join(scripts,'new-a-ui-source/frame.html'),' '.repeat(128*1024));if(fault==='private-data')await fs.appendFile(path.join(scripts,'new-a-ui-source/frame.html'),'<table><tbody><tr data-date="synthetic-date"><td>private row</td></tr></tbody></table>');if(fault==='unknown-public')await fs.writeFile(path.join(publicDir,'keep.json'),'UNKNOWN_PRIVATE_PAYLOAD');
 await fs.writeFile(contractFile,JSON.stringify(contract));const before=await inventory(publicDir),result=spawnSync(process.execPath,[path.join(scripts,'sync-report.mjs')],{encoding:'utf8'});return {root,gate,publicDir,before,result,stale};}
test('actual sync builds the exact data-free public inventory and a worker-only member frame', async t => {
 const f = await fixture(t);
 assert.equal(f.result.status, 0, f.result.stderr);
 const files = await inventory(f.publicDir);
 const pages = ['latest', 'analytics', 'silence', 'dive', 'shadow', 'fusion', 'balance', 'guide'];
 const memberScripts = ['member-loader.js', 'member-presentation.js', 'member-settings.js', 'reference-analytics.js'];
 const scripts = [
  'browser-transport.js', 'finite-controller.js', 'finite-dom.js', 'initial-display.js',
  'owner-loader.js', 'owner-notifications.js', 'owner-settings.js', ...memberScripts,
  'weak-early-beta-theme-init.js', 'weak-early-beta-scenarios.js', 'new-a-legacy-interactions.generated.js',
  'presentation-adapter.generated.js', 'new-a-finite-worker.generated.js',
 ];
 const images = ['cloud-logo', 'coconala', 'discord', 'x'].flatMap(brand =>
  ['dark', 'light'].map(theme => 'new-a-assets/report-assets/' + brand + '-' + theme + '.png'));
 const frames = pages.flatMap(page => ['', '_free'].map(suffix => 'weak_early_beta_' + page + suffix + '.html'));
 const expected = [
  ...frames, 'weak-early-beta-push.js', 'weak-early-beta-service-worker.js',
  ...scripts.map(name => 'new-a-assets/' + name), ...images,
 ];
 assert.deepEqual(Object.keys(files).sort(), expected.sort());
 for (const name of frames) {
  const html = await fs.readFile(path.join(f.publicDir, name), 'utf8');
  assert.doesNotMatch(html, /data-date=|SYNTHETIC_PRIVATE|variants[.]bundle|member-loader[.]js/);
 }
 const memberFramePath = path.join(f.gate, 'src/new-a-member-frame.generated.ts');
 const memberFrame = await fs.readFile(memberFramePath, 'utf8');
 for (const name of memberScripts) assert(memberFrame.includes('/new-a-assets/' + name), name);
 assert.doesNotMatch(memberFrame, /owner-loader[.]js|\/auth\/guard[.]js|data-date=|SYNTHETIC_PRIVATE/);
 const { memberFrame: renderMemberFrame } = await import(pathToFileURL(memberFramePath).href);
 const freeHome = renderMemberFrame('/weak_early_beta_latest.html', 'free');
 const freeSettings = renderMemberFrame('/weak_early_beta_settings.html', 'free');
 const premiumSettings = renderMemberFrame('/weak_early_beta_settings.html', 'premium');
 const premiumHome = renderMemberFrame('/weak_early_beta_latest.html', 'premium');
 checkHelp(premiumHome);
 checkHelp(freeHome,{stagedFree:true});
 assert.match(freeHome, /href="\.\/weak_early_beta_analytics\.html" data-member-premium-nav hidden/);
 assert.match(freeHome, /href="\.\/weak_early_beta_settings\.html" data-member-premium-nav hidden/);
 assert.doesNotMatch(freeHome + freeSettings, /src="\/new-a-assets\/member-settings\.js"/);
 assert.match(premiumHome, /<dialog id="cloud-settings-dialog"/);
 assert.match(premiumHome, /aria-haspopup="dialog" aria-controls="cloud-settings-dialog"/);
 assert.doesNotMatch(freeHome + freeSettings + premiumSettings, /<dialog id="cloud-settings-dialog"/);
 assert.match(premiumSettings, /src="\/new-a-assets\/member-settings\.js"/);
 const premiumAnalytics = renderMemberFrame('/weak_early_beta_analytics.html', 'premium');
 assert.match(premiumAnalytics, /src="\/new-a-assets\/reference-analytics\.js"/);
 assert.doesNotMatch(premiumHome + freeHome, /reference-analytics/);
 const scan = spawnSync(process.execPath, [path.join(f.gate, 'scripts/verify-new-a-code-only.mjs')], {encoding: 'utf8'});
 assert.equal(scan.status, 0, scan.stderr);
});
for(const fault of ['path','audience','metadata','key','size','private-data','asset-date','unknown-public'])test(`code-only sync refuses ${fault} before touching existing public assets`,async t=>{const f=await fixture(t,fault);assert.notEqual(f.result.status,0);assert.deepEqual(await inventory(f.publicDir),f.before);});
test('same original calculator and shared finite Worker are code assets; private inputs stay outside sync',async t=>{const f=await fixture(t);assert.equal(f.result.status,0,f.result.stderr);const calculator=await fs.readFile(path.join(f.publicDir,'new-a-assets/weak-early-beta-scenarios.js'));assert.equal(calculator.toString('utf8'),(await fs.readFile(path.join(baseline,'reports/weak-early-beta-scenarios.js'),'utf8')).replace(/\r\n?/g,'\n'));const worker=await fs.readFile(path.join(f.publicDir,'new-a-assets/new-a-finite-worker.generated.js'),'utf8');assert(worker.includes('createDatasetRuntime'));assert(!worker.includes('SYNTHETIC_PRIVATE'));const first=await inventory(f.publicDir),again=spawnSync(process.execPath,[path.join(f.gate,'scripts/sync-report.mjs')],{encoding:'utf8'});assert.equal(again.status,0,again.stderr);assert.deepEqual(await inventory(f.publicDir),first);});
test('generated owner frames use descriptive history labels and direct settings fallback',async t=>{
 const f=await fixture(t);
 assert.equal(f.result.status,0,f.result.stderr);
 const framePath=path.join(f.gate,'.cache/new-a/frame.generated.mjs');
 const {ownerFrame}=await import(pathToFileURL(framePath).href);
 const owner={ownerAuthorized:true,roleAuthorized:true,current:true};
 const dashboard=ownerFrame('/weak_early_beta_latest.html',owner);
 const settings=ownerFrame('/weak_early_beta_settings.html',owner);
 const directHelp=ownerFrame('/weak_early_beta_guide.html',owner);
 checkHelp(dashboard);
 checkHelp(settings);
 assert.match(directHelp,/<h1 id="cloud-help-page-title">ヘルプ<\/h1>/);
 assert.doesNotMatch(directHelp,/監視から試算まで|画面を開く/);
 assert.match(dashboard,/<div>試算条件<\/div>/);
 assert.match(dashboard,/<dialog id="cloud-settings-dialog"/);
 const close = dashboard.match(/<button[^>]+id="cloud-settings-close"[\s\S]*?<\/button>/)[0];
 assert.match(close,/aria-label="設定を閉じる"/);
 assert.match(close,/<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">/);
 assert.match(close,/<path d="M6 6L18 18M18 6L6 18"/);
 assert.match(dashboard,/\.cloud-settings \.settings-close\{display:grid;place-items:center;flex:0 0 44px/);
 assert.match(dashboard,/aria-haspopup="dialog" aria-controls="cloud-settings-dialog"/);
 assert.match(settings,/<h1 id="cloud-settings-title">設定<\/h1>/);
 assert.match(settings,/id="cloud-settings-direct"/);
 assert.doesNotMatch(settings,/<dialog id="cloud-settings-dialog"|プッシュ通知|cloud-year-scope|cloud-price-preset/);
 assert.doesNotMatch(dashboard+settings,/>A<|>該当モード<|A検出の記録期間|新A/);
});
test('Windows CRLF and Git/Linux LF source checkouts produce identical code-only assets and member frames', async t => {
 const f = await fixture(t);
 assert.equal(f.result.status, 0, f.result.stderr);
 const before = await inventory(f.publicDir);
 const generated = path.join(f.gate, 'src/new-a-member-frame.generated.ts');
 const memberFrame = await fs.readFile(generated);
 async function normalize(dir) {
  for (const e of await fs.readdir(dir, {withFileTypes: true})) {
   const p = path.join(dir, e.name);
   if (e.isDirectory()) await normalize(p);
   else if (/\.(?:js|mjs|cjs|html)$/.test(e.name)) await fs.writeFile(p, (await fs.readFile(p, 'utf8')).replace(/\r\n?/g, '\n'));
  }
 }
 const source = path.join(f.gate, 'scripts/new-a-ui-source');
 await normalize(path.join(f.root, 'reports'));
 await normalize(source);
 const frame = path.join(source, 'frame.html');
 await fs.writeFile(frame, (await fs.readFile(frame, 'utf8')).replace(/\n/g, '\r\n'));
 const result = spawnSync(process.execPath, [path.join(f.gate, 'scripts/sync-report.mjs')], {encoding: 'utf8'});
 assert.equal(result.status, 0, result.stderr);
 assert.deepEqual(await inventory(f.publicDir), before);
 assert.deepEqual(await fs.readFile(generated), memberFrame);
});
