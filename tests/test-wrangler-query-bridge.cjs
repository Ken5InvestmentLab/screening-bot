'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const bridge=path.resolve(__dirname,'../weak_early_beta/new_a/wrangler-query.cjs');
const {prepareQueryArgs,selectStatementsOnly}=require(bridge);
function fixture(t){
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),'new-a-synthetic-query-'));t.after(()=>fs.rmSync(repo,{recursive:true,force:true}));
 const cli=path.join(repo,'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js');
 const main=path.join(repo,'weak-early-beta-gate/node_modules/wrangler/wrangler-dist/cli.js');
 const root=path.join(repo,'.cache/weak_early_beta/new-a-private');
 for(const p of [path.dirname(cli),path.dirname(main),root])fs.mkdirSync(p,{recursive:true});
 fs.writeFileSync(cli,'// fake CLI, never a real provider');fs.writeFileSync(main,'// fake CLI body');
 const file=path.join(root,'query.sql');fs.writeFileSync(file,'SELECT 1 AS connection_test;','utf8');return{repo,cli,main,root,file};
}
test('in-memory CLI argv uses query mode and exact private UTF-8 SQL',t=>{
 const f=fixture(t),sql="SELECT '合成?;値' AS label; SELECT 2 AS other;";fs.writeFileSync(f.file,sql);
 const args=prepareQueryArgs(f.cli,f.file);assert.deepEqual(args,[process.execPath,f.main,'d1','execute','CLOUD_DB','--remote','--command',sql,'--yes','--json']);
});
test('bridge runs CLI as main without spawning SQL as OS command arguments',t=>{
 const f=fixture(t);fs.writeFileSync(f.main,`if(require.main!==module)process.exit(8);if(process.argv[6]!=='--command'||process.argv[7]!=='SELECT 1 AS connection_test;')process.exit(9);console.log(JSON.stringify([{success:true,results:[{connection_test:1}]}]));`);
 const args=[bridge,f.cli,f.file];assert(!args.some(x=>x.includes('SELECT')));
 const r=spawnSync(process.execPath,args,{encoding:'utf8',env:{SystemRoot:process.env.SystemRoot,TEMP:os.tmpdir()}});
 assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),[{success:true,results:[{connection_test:1}]}]);
});
test('CLI nonzero result is preserved and never retried',t=>{
 const f=fixture(t);fs.writeFileSync(f.main,'process.exitCode=7;');const r=spawnSync(process.execPath,[bridge,f.cli,f.file],{encoding:'utf8'});assert.equal(r.status,7);
});
test('outside files, wrong CLI, empty input and oversized input are refused',t=>{
 const f=fixture(t),outside=path.join(f.repo,'outside.sql');fs.writeFileSync(outside,'SELECT 1');
 assert.throws(()=>prepareQueryArgs(f.cli,outside),/private_sql_file_required/);
 const wrong=path.join(f.repo,'wrangler.js');fs.writeFileSync(wrong,'');assert.throws(()=>prepareQueryArgs(wrong,f.file),/unexpected_wrangler_cli/);
 fs.writeFileSync(f.file,'  ');assert.throws(()=>prepareQueryArgs(f.cli,f.file),/read_only_select_required/);
 fs.writeFileSync(f.file,Buffer.alloc(1024*1024+1,32));assert.throws(()=>prepareQueryArgs(f.cli,f.file),/budget/);
});
test('standalone bridge refuses writes and mixed or disguised batches',t=>{
 const f=fixture(t);
 for(const sql of ['UPDATE t SET value=1;','SELECT 1; DELETE FROM t;','WITH x AS (SELECT 1) DELETE FROM t;','SELECT 1 -- comment\n;','SELECT 1 /* comment */;',"SELECT 'broken;"]){
  fs.writeFileSync(f.file,sql);assert.throws(()=>prepareQueryArgs(f.cli,f.file),/read_only_select_required/);
 }
 assert(selectStatementsOnly("SELECT 'semi; quote'' -- /*' AS label; SELECT 2;"));
 assert(!selectStatementsOnly('SELECT 1;;'));
});
test('startup failure emits only a fixed safe category',t=>{
 const f=fixture(t),outside=path.join(f.repo,'SYNTHETIC_PRIVATE_MARKER.sql');fs.writeFileSync(outside,'SYNTHETIC_PRIVATE_MARKER');
 const r=spawnSync(process.execPath,[bridge,f.cli,outside],{encoding:'utf8'});assert.equal(r.status,1);assert.equal(r.stdout,'');assert.equal(r.stderr.trim(),'private_wrangler_query_start_failed');
});

function writeMemberConfig(f, change = () => {}) {
 const relative = 'weak-early-beta-gate/wrangler.jsonc';
 const config = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', relative), 'utf8'));
 change(config);
 const file = path.join(f.repo, relative);
 fs.writeFileSync(file, JSON.stringify(config));
 return file;
}

test('member query uses canonical production config and pins top-level environment', t => {
 const f = fixture(t), config = writeMemberConfig(f);
 const args = prepareQueryArgs(f.cli, f.file, 'CLOUD_MEMBER_DB');
 assert.deepEqual(args, [process.execPath, f.main, 'd1', 'execute', 'CLOUD_MEMBER_DB', '--remote',
  '--command', 'SELECT 1 AS connection_test;', '--yes', '--json', '--config', config, '--env=']);
 fs.writeFileSync(f.main, `const assert=require('node:assert/strict');
  assert.deepEqual(process.argv.slice(2), ${JSON.stringify(args.slice(2))});
  assert.equal(process.env.CLOUDFLARE_API_BASE_URL,'https://api.cloudflare.com/client/v4');`);
 const child = spawnSync(process.execPath, [bridge, f.cli, f.file, 'CLOUD_MEMBER_DB'], {encoding:'utf8',
  env:{...process.env, CLOUDFLARE_ENV:'preview', CLOUDFLARE_API_BASE_URL:'https://example.invalid'}});
 assert.equal(child.status, 0, child.stderr);
});

test('standalone member query refuses alternate targets and conflicting aliases', t => {
 const f = fixture(t);
 assert.throws(() => prepareQueryArgs(f.cli, f.file, 'arbitrary'), /unsupported_d1_binding/);
 assert.throws(() => prepareQueryArgs(f.cli, f.file, 'CLOUD_MEMBER_DB'), /canonical_member_d1_config_required/);
 for (const change of [c => { c.name += '-member-stage'; },
  c => { c.d1_databases[1].database_id = c.d1_databases[0].database_id; },
  c => { c.d1_databases[1].database_name = 'other-member-view'; },
  c => { c.d1_databases[1].database_internal_env = 'other'; },
  c => { c.d1_databases.unshift({ database_name: 'CLOUD_MEMBER_DB' }); },
  c => { c.env.preview.d1_databases.push(c.d1_databases[1]); }]) {
  writeMemberConfig(f, change);
  assert.throws(() => prepareQueryArgs(f.cli, f.file, 'CLOUD_MEMBER_DB'), /canonical_member_d1_config_required/);
 }
});
