// Existing loader metadata only. Credentials stay in memory and never enter output.
import fs from 'node:fs';import path from 'node:path';import{createHash}from'node:crypto';
import{loadDailyConfig,loadDotEnv}from'./weak-early-beta-daily-runner.mjs';
import{fileURLToPath}from'node:url';
const sha=v=>createHash('sha256').update(typeof v==='string'||Buffer.isBuffer(v)||v instanceof Uint8Array?v:JSON.stringify(v)).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
async function get(url,headers){const r=await fetch(url,{headers,redirect:'error',signal:AbortSignal.timeout(30000)});if(r.status!==200)throw Error('normal_service_metadata_unavailable');return r.json();}
export async function operationalLoader(configFile,{fetchMetadata=get,configReader=loadDailyConfig,inheritedEnvironment=process.env}={}){
 const config=configReader(configFile),repo=path.resolve(config.repoPath),env={...inheritedEnvironment};
 const names=['ADMIN_USER_ID','DISCORD_TOKEN','WEAK_EARLY_BETA_DISCORD_BOT_TOKEN','WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL','WEAK_EARLY_BETA_REPORT_URL'];
 const configured={},references={};loadDotEnv(configured,path.join(repo,'.env'));for(const k of names)if(configured[k]!==undefined)references[k]='root';
 loadDotEnv(configured,path.join(repo,'weak-early-beta-gate/.env'));for(const k of names)if(!references[k]&&configured[k]!==undefined)references[k]='gate';
 loadDotEnv(env,path.join(repo,'.env'));loadDotEnv(env,path.join(repo,'weak-early-beta-gate/.env'));
 // Child inheritance is an implementation stage, not a new source selection.
 // Compare values only in memory. Record equivalence to the persistent selected
 // reference; an effective inherited override remains distinct and fails pins.
 const precedence=['INHERITED_THEN_ROOT_THEN_GATE_NO_REPLACEMENT_V1',...names.map(k=>[k,env[k]===undefined?'absent':env[k]===configured[k]?'configured:'+references[k]:'inherited_override'])];
 const worker=read(path.join(repo,'weak-early-beta-gate/wrangler.jsonc')),vars=worker.vars;
 const token=(env.WEAK_EARLY_BETA_DISCORD_BOT_TOKEN||env.DISCORD_TOKEN||'').trim(),webhook=(env.WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL||'').trim(),owner=(env.ADMIN_USER_ID||'').trim();
 if(!token||!/^\d{17,20}$/.test(owner)||!/^https:\/\/discord\.com\/api\/webhooks\/\d+\/[A-Za-z0-9_.-]+$/.test(webhook)||new URL(env.WEAK_EARLY_BETA_REPORT_URL).origin!=='https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev')throw Error('normal_loader_target_unavailable');
 const headers={'User-Agent':'DiscordBot (screening-bot, 1.0)'},app=await fetchMetadata('https://discord.com/api/v10/oauth2/applications/@me',{...headers,Authorization:'Bot '+token}),destination=await fetchMetadata(webhook,headers);
 const guild=String(vars.DISCORD_GUILD_ID),roles=String(vars.DISCORD_ALLOWED_ROLE_IDS).split(',').map(x=>x.trim()).filter(Boolean).sort();
 // The production identities are read from the existing owning source, not an env replacement.
 const notifySource=fs.readFileSync(path.join(repo,'weak_early_beta/notify.py'),'utf8');
 const constant=n=>notifySource.match(new RegExp('^'+n+'\\s*=\\s*[\"\']([0-9]+)[\"\']','m'))?.[1];
 const summary=await fetchMetadata('https://discord.com/api/v10/channels/'+constant('SUMMARY_CHANNEL_ID'),{...headers,Authorization:'Bot '+token});
 if(destination.guild_id!==guild||destination.channel_id!==constant('CHANNEL_ID')||summary.guild_id!==guild||summary.id!==constant('SUMMARY_CHANNEL_ID')||!/^\d{17,20}$/.test(String(app.id))||!/^\d{17,20}$/.test(String(destination.id)))throw Error('normal_notification_destination_changed');
 const policy=['NEW_A_OPERATIONAL_POLICY_V1',true,owner,guild,[...new Set(roles)],String(app.id),'https://discord.com/api',Number(vars.SESSION_TTL_SECONDS),'NEW_A_REPORT_IDENTITY_FRESH_ROLE_V1',[true,true,true]];
 const configuration=Object.fromEntries(['repoPath','runtimeDir','pythonPath','nodePath','npmPath','fundamentalConfigPath','maxFreshnessAttempts','freshnessRetryDelayMs'].map(k=>[k,config[k]??null]));
 const runtime=[process.version,sha(fs.readFileSync(config.nodePath)),sha(fs.readFileSync(config.pythonPath))];
 return{schema:'NEW_A_EXISTING_LOADER_METADATA_V1',runner_configuration_sha256:sha(JSON.stringify(configuration)),loader_precedence_sha256:sha(precedence),runtime_sha256:sha(runtime),report_origin:'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev',policy_sha256:sha(policy),signal_destination_sha256:sha('DISCORD_SIGNAL_DESTINATION_V1|'+guild+'|'+destination.channel_id+'|'+destination.id),summary_destination_sha256:sha(['DISCORD_SUMMARY_DESTINATION_V1',guild,constant('SUMMARY_CHANNEL_ID')]),credential_values_returned:false};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))operationalLoader(process.argv[2]).then(v=>console.log(JSON.stringify(v))).catch(()=>{console.error('operational_loader_metadata_unavailable');process.exitCode=1;});
