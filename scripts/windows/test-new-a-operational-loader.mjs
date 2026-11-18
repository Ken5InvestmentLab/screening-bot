import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import{createHash}from'node:crypto';
import{operationalLoader}from'./new-a-operational-loader.mjs';
import{observeOwnerNoticeRuntime}from'./new-a-owner-notice-host.mjs';
const sha=v=>createHash('sha256').update(typeof v==='string'||Buffer.isBuffer(v)?v:JSON.stringify(v)).digest('hex');
const ids={owner:'100000000000000001',guild:'100000000000000002',signal:'100000000000000003',summary:'100000000000000004',client:'100000000000000005',hook:'100000000000000006',role:'100000000000000007'};
function fixture(){const repo=fs.mkdtempSync(path.join(os.tmpdir(),'new-a-loader-'));fs.mkdirSync(path.join(repo,'weak-early-beta-gate'));fs.mkdirSync(path.join(repo,'weak_early_beta'));fs.writeFileSync(path.join(repo,'node.exe'),Buffer.from([0,1,2,255]));fs.writeFileSync(path.join(repo,'python.exe'),Buffer.from([9,8,7,128]));const config={repoPath:repo,nodePath:path.join(repo,'node.exe'),pythonPath:path.join(repo,'python.exe')};
 const vars={DISCORD_GUILD_ID:ids.guild,DISCORD_ALLOWED_ROLE_IDS:ids.role+','+ids.role,SESSION_TTL_SECONDS:'31536000'};fs.writeFileSync(path.join(repo,'weak-early-beta-gate/wrangler.jsonc'),JSON.stringify({vars}));fs.writeFileSync(path.join(repo,'weak_early_beta/notify.py'),`CHANNEL_ID = "${ids.signal}"\nSUMMARY_CHANNEL_ID = "${ids.summary}"\n`);
 const env={ADMIN_USER_ID:ids.owner,DISCORD_TOKEN:'synthetic-token',WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL:`https://discord.com/api/webhooks/${ids.hook}/synthetic`,WEAK_EARLY_BETA_REPORT_URL:'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/'};fs.writeFileSync(path.join(repo,'.env'),Object.entries(env).map(([k,v])=>k+'='+v).join('\n'));fs.writeFileSync(path.join(repo,'weak-early-beta-gate/.env'),'');
 const fetchMetadata=async url=>url.endsWith('/applications/@me')?{id:ids.client}:url.includes('/webhooks/')?{id:ids.hook,guild_id:ids.guild,channel_id:ids.signal}:{id:ids.summary,guild_id:ids.guild};return{repo,config,env,fetchMetadata,close:()=>fs.rmSync(repo,{recursive:true,force:true})};}
test('same effective selection survives normal child inheritance without losing override detection',async()=>{const f=fixture();try{const args={configReader:()=>f.config,fetchMetadata:f.fetchMetadata};const parent=await operationalLoader('synthetic',{...args,inheritedEnvironment:{}}),child=await operationalLoader('synthetic',{...args,inheritedEnvironment:f.env});assert.deepEqual(parent,child);const different=await operationalLoader('synthetic',{...args,inheritedEnvironment:{ADMIN_USER_ID:'100000000000000009'}});assert.notEqual(different.loader_precedence_sha256,parent.loader_precedence_sha256);assert.notEqual(different.policy_sha256,parent.policy_sha256);}finally{f.close();}});
test('policy deduplicates roles exactly like runtime and hashes raw executable bytes',async()=>{const f=fixture();try{const value=await operationalLoader('synthetic',{configReader:()=>f.config,fetchMetadata:f.fetchMetadata,inheritedEnvironment:{}});assert.equal(value.policy_sha256,sha(['NEW_A_OPERATIONAL_POLICY_V1',true,ids.owner,ids.guild,[ids.role],ids.client,'https://discord.com/api',31536000,'NEW_A_REPORT_IDENTITY_FRESH_ROLE_V1',[true,true,true]]));assert.equal(value.runtime_sha256,sha([process.version,sha(fs.readFileSync(f.config.nodePath)),sha(fs.readFileSync(f.config.pythonPath))]));assert(!JSON.stringify(value).includes('synthetic-token'));assert(!JSON.stringify(value).includes('/api/webhooks/'));}finally{f.close();}});
test('real metadata destination mismatch or failed service GET never provides a pin',async()=>{const f=fixture();try{await assert.rejects(operationalLoader('synthetic',{configReader:()=>f.config,fetchMetadata:async()=>({id:'wrong'}),inheritedEnvironment:{}}),/destination_changed/);}finally{f.close();}});
test('owner binding is available only by explicit in-process projection',async()=>{const f=fixture();try{
 const args={configReader:()=>f.config,fetchMetadata:f.fetchMetadata,inheritedEnvironment:{}};
 const defaults=await operationalLoader('synthetic',args);
 const {owner_binding_sha256,...privateProjection}=await operationalLoader('synthetic',{...args,includeOwnerBinding:true});
 assert.equal(defaults.owner_binding_sha256,undefined);
 assert.deepEqual(privateProjection,defaults);
 assert.equal(owner_binding_sha256,sha('cloud-member:'+ids.owner));
 assert(!JSON.stringify(privateProjection).includes(ids.owner));
}finally{f.close();}});

test('fresh owner role reads only the expected member and fails closed on mixed identity',async()=>{const f=fixture();try{
 const configFile=path.join(f.repo,'weak-early-beta-gate/wrangler.jsonc');
 const config=JSON.parse(fs.readFileSync(configFile,'utf8'));
 config.vars.CLOUD_PUSH_MEMBERSHIP_POLICY='whop_managed_discord_role';
 fs.writeFileSync(configFile,JSON.stringify(config));
 const ownerPath='https://discord.com/api/v10/guilds/'+ids.guild+'/members/'+ids.owner;
 let role=ids.role, subject=ids.owner;
 const args={configReader:()=>f.config,inheritedEnvironment:{},includeOwnerBinding:true,checkOwnerRole:true,
  fetchMetadata:(url,headers)=>{
   if(!url.includes('/members/'))return f.fetchMetadata(url,headers);
   assert.equal(url,ownerPath);
   assert.equal(headers.Authorization,'Bot synthetic-token');
   return Promise.resolve({user:{id:subject},roles:[role]});
 }};
 const result=await operationalLoader('synthetic',args);
 assert.equal(result.fresh_paid_role,true);
 assert(Number.isSafeInteger(result.owner_role_observed_at_ms));
 assert(!JSON.stringify(result).includes(ids.owner));
 role='100000000000000020';
 assert.equal((await operationalLoader('synthetic',args)).fresh_paid_role,false);
 subject='100000000000000021';
 await assert.rejects(operationalLoader('synthetic',args),/normal_owner_role_unavailable/);
}finally{f.close();}});

test('host operation joins the approved Worker with a time-bounded owner role and active D1 proof',async()=>{
 const instant=Date.parse('2026-11-18T08:25:00Z');
 const release={source_commit:'a'.repeat(40),version_id:'11111111-2222-3333-4444-555555555555',
  build_input_sha256:'b'.repeat(64),policy_sha256:'c'.repeat(64)};
 const metadata={schema:'NEW_A_EXISTING_LOADER_METADATA_V1',policy_sha256:release.policy_sha256,
  owner_binding_sha256:'d'.repeat(64),fresh_paid_role:true,owner_role_observed_at_ms:instant-1000};
 const args={readConfig:()=>({repoPath:process.cwd()}),loader:async(_,options)=>{
   assert.deepEqual(options,{includeOwnerBinding:true,checkOwnerRole:true});return metadata;
 },now:()=>instant,request:async()=>Response.json({d1_active_sha256:'e'.repeat(64)}),
 readWorker:async(accepted,head,request)=>{
   assert.equal(accepted,release); assert.equal(head,release.source_commit);
   const health=await request('https://synthetic.invalid/healthz');
   assert.equal(health.status,200);
   return {sourceCommit:head,versionId:release.version_id,buildInputSha256:release.build_input_sha256};
 }};
 const result=await observeOwnerNoticeRuntime('synthetic',release,args);
 assert.equal(result.owner_binding_sha256,metadata.owner_binding_sha256);
 assert.equal(result.d1_active_sha256,'e'.repeat(64));
 assert.equal(result.expires_at,new Date(instant+29_000).toISOString());
 await assert.rejects(observeOwnerNoticeRuntime('synthetic',release,{...args,now:()=>instant+29_000}),/expired/);
 await assert.rejects(observeOwnerNoticeRuntime('synthetic',release,{...args,loader:async()=>({...metadata,policy_sha256:'f'.repeat(64)})}),/policy_unavailable/);
});
