// Proposed finite manual continuation, not an automatic retry-counter reset.
// No issuer CLI: independent host readers must supply real approval/evidence.
import fs from 'node:fs';import path from 'node:path';import os from 'node:os';
import{createHash}from'node:crypto';import{execFileSync}from'node:child_process';import{isDeepStrictEqual}from'node:util';
const check=(ok,m)=>{if(!ok)throw Error('Native admission continuation: '+m);};
const stable=v=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const hash=v=>createHash('sha256').update(v).digest('hex');const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const day=n=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(n);
const inside=(root,file)=>{const rel=path.relative(fs.realpathSync(root),fs.realpathSync(file));check(rel&&rel!=='..'&&!rel.startsWith('..'+path.sep)&&!path.isAbsolute(rel),'private path escapes');};
const immutable=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});const fd=fs.openSync(file,'wx');try{fs.writeFileSync(fd,stable(value)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}};
const key=v=>String(v).replace(/[^0-9TZ-]/g,'');
function folder(runtime,started){check(typeof started==='string'&&Number.isFinite(Date.parse(started)),'invalid original start');const p=path.join(runtime,'daily-'+started.replace(/[:.]/g,'-'));inside(runtime,p);return p;}
export function originalProcessesAbsent(pids,bounds,observed,now=Date.now()){
 return pids.every(pid=>{const current=observed.find(p=>p.pid===pid);if(!current)return true;const terminal=Date.parse(bounds?.[pid]),birth=Date.parse(current.created_at);return Number.isFinite(terminal)&&Number.isFinite(birth)&&birth>terminal&&birth<=now;});
}
export function noLivePids(pids,bounds){
 check(process.platform==='win32','normal Windows process inspection required');
 const raw=execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',"$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object { @{pid=$_.ProcessId;created_at=$_.CreationDate.ToUniversalTime().ToString('o')} }) | ConvertTo-Json -Compress"],{encoding:'utf8',windowsHide:true,timeout:30000});
 const live=JSON.parse(raw);check(Array.isArray(live)&&originalProcessesAbsent(pids,bounds,live),'original or child process alive or birth unknown');return true;
}
export function inspectAdmissionStop({repo,runtime,prior,date,auditDirectory=path.join(os.homedir(),'Documents','Codex','Cloud_task_invocations'),processReader=noLivePids}){
 check(date==='2026-11-17'&&prior?.date===date&&prior.identity==='WEAK_EARLY_CLOUD_DAILY_V1'&&prior.ok===false&&prior.stage==='detection'&&prior.completedAt&&prior.error==='native-source-recovery failed; inspect bounded local logs','not the exact terminal pre-detection inspection failure');
 check(isDeepStrictEqual(read(path.join(runtime,'daily-latest.json')),prior),'latest stopped record changed');
 check(!fs.existsSync(path.join(runtime,'daily.lock')),'active daily lock exists');
 const current=folder(runtime,prior.startedAt);check(isDeepStrictEqual(read(path.join(current,'result.json')),prior),'preserved stopped result differs');
 const originalInput=path.join(runtime,`recovery-input-${key(prior.originalRunId)}.json`),reservation=path.join(runtime,`recovery-${key(prior.originalRunId)}.json`);
 inside(runtime,originalInput);inside(runtime,reservation);const original=read(originalInput),claim=read(reservation),originalFolder=folder(runtime,original.startedAt);
 check(original.startedAt===prior.originalRunId&&original.date===date&&original.identity===prior.identity&&original.ok===false&&original.stage==='detection'&&original.completedAt&&!original.originalRunId,'original source failure differs');
 check(isDeepStrictEqual(read(path.join(originalFolder,'result.json')),original)&&claim.priorStartedAt===original.startedAt,'original failure or reservation differs');
 check(Date.parse(original.completedAt)>=Date.parse(original.startedAt)&&Date.parse(prior.startedAt)>=Date.parse(original.completedAt)&&Date.parse(prior.completedAt)>=Date.parse(prior.startedAt)&&day(new Date(prior.startedAt))===date,'failure chronology differs');
 const invocation=path.join(auditDirectory,`cloud-2-${date}-${claim.invocation}.json`);inside(auditDirectory,invocation);const invokedTask=read(invocation);
 check(invokedTask.identity==='CLOUD_TASK_INVOCATION_V1'&&invokedTask.id===claim.invocation&&invokedTask.status==='launched'&&invokedTask.date===date&&invokedTask.childPid===prior.pid,'original task-entry launch is unproven');
 const called=read(path.join(current,'invoked.json'));check(called.identity==='CLOUD_RUNNER_INVOKED_V1'&&['pid','date','startedAt','originalRunId'].every(k=>called[k]===prior[k]),'stopped invocation mismatch');
 for(const value of [original,prior])for(const name of ['deployment','notifications','notificationPreview','latestSession','selectorRows','generatedCommit'])check(!(name in value),'downstream outcome exists or is ambiguous');
 check(!prior.fundamentals?.length&&!prior.systemLogErrors?.length&&isDeepStrictEqual(prior.systemLogEvents,['error']),'external-management outcome ambiguous');
 const files={},pids=[],bounds={};let inspector=false;
 const remember=(pid,terminal)=>{check(Number.isInteger(pid)&&pid>0&&Number.isFinite(Date.parse(terminal)),'terminal process identity unavailable');pids.push(pid);if(!bounds[pid]||Date.parse(bounds[pid])<Date.parse(terminal))bounds[pid]=terminal;};remember(original.pid,original.completedAt);remember(prior.pid,prior.completedAt);
 for(const name of fs.readdirSync(originalFolder).filter(n=>/^detect-\d\.process\.json$/.test(n))){const child=read(path.join(originalFolder,name));check(child.status==='exited'&&Number.isInteger(child.pid),'original child terminal receipt missing');remember(child.pid,child.completedAt);}
 const allowed=/^(?:invoked\.json|result\.json|progress\.jsonl|(?:business-day|process-preflight|gh-preflight|previous-release|native-source-recovery|system-log-error|git-\d+-(?:branch|status|remote|rev-parse|ls-remote))\.(?:stdout|stderr|process\.json))$/;
 for(const name of fs.readdirSync(current)){
  check(allowed.test(name),'unexpected artifact: detection/publication/send may have started');const p=path.join(current,name);inside(current,p);check(fs.statSync(p).isFile(),'non-regular artifact');files[name]=hash(fs.readFileSync(p));
  if(name.endsWith('.process.json')){const r=read(p);check(r.identity==='CLOUD_CHILD_PROCESS_V1'&&r.status==='exited'&&r.completedAt&&Number.isInteger(r.pid)&&r.code===(name==='native-source-recovery.process.json'?1:0),'child not proven terminal');remember(r.pid,r.completedAt);if(name==='native-source-recovery.process.json')inspector=true;}
 }
 check(inspector&&fs.statSync(path.join(current,'native-source-recovery.stdout')).size===0,'inspection outcome uncertain');
 check(fs.readFileSync(path.join(current,'native-source-recovery.stderr'),'utf8').trim().endsWith('ValueError: Native acquisition recovery: latest terminal receipt changed'),'different inspection failure');
 const post=read(path.join(current,'system-log-error.stdout'));check(post.posted===true&&post.duplicate===false&&/^\d+$/.test(post.message_id),'error-management receipt ambiguous');
 check(processReader(pids,bounds)===true,'process termination not proven');
 const local=path.join(repo,'.cache/weak_early_beta/new-a-private'),localFiles={};
 for(const name of ['daily-live.sqlite','notification-outbox.sqlite','latest-run.json']){const p=path.join(local,name);localFiles[name]=fs.existsSync(p)?hash(fs.readFileSync(p)):null;}
 check(!fs.existsSync(path.join(local,'latest-publication.json'))||read(path.join(local,'latest-publication.json')).as_of!==date,'target publication receipt needs separate reconciliation');
 return{original_run_id:original.startedAt,stopped_run_id:prior.startedAt,original_input:originalInput,original_input_sha256:hash(fs.readFileSync(originalInput)),reservation_sha256:hash(fs.readFileSync(reservation)),original_result_sha256:hash(fs.readFileSync(path.join(originalFolder,'result.json'))),stopped_result_sha256:hash(fs.readFileSync(path.join(current,'result.json'))),task_invocation_sha256:hash(fs.readFileSync(invocation)),artifact_hashes:files,local_files:localFiles,error_message_id:post.message_id};
}
export async function issueAdmissionContinuation({repo,runtime,prior,date,executionDate=date,head,binding,authority,reader,questionReader,decisionReader,sourceReader,externalReader,preflightReader,expiresAt,...options}){
 const now=new Date();check(day(now)===executionDate&&date==='2026-11-17'&&['2026-11-17','2026-11-18'].includes(executionDate)&&Date.parse(expiresAt)>+now&&Date.parse(expiresAt)<=Math.min(+now+30*60000,Date.parse(executionDate+'T23:59:59+09:00')),'finite bound target/execution authority required');
 check(/^[a-f0-9]{40}$/.test(head)&&typeof reader==='function'&&typeof decisionReader==='function'&&typeof sourceReader==='function'&&typeof externalReader==='function'&&typeof preflightReader==='function','independent host readers required');
 check(binding?.author_id===authority?.author_id&&binding?.room_id===authority?.room_id&&/^[a-f0-9]{64}$/.test(binding?.text_sha256),'host owner identity missing');
 const raw=await reader(binding.message_id),m=raw?.message;
 check(raw?.partial===false&&raw.room_id===binding.room_id&&m?.author==='user'&&['chatgpt','slack'].includes(m.channel)&&m.author_id===binding.author_id&&m.message_id===binding.message_id&&m.deleted_at==null&&Date.parse(m.sent_at)<=Date.now()&&hash(stable(m.content?.text))===binding.text_sha256,'actual primary approval mismatch');
 if(m.channel==='slack'){
  check(binding.channel==='slack'&&typeof questionReader==='function'&&binding.question_id&&/^[a-f0-9]{64}$/.test(binding.question_text_sha256),'actual Slack question binding required');
  const qraw=await questionReader(binding.question_id),q=qraw?.message;
  const thread=x=>x?.reply_destination?.message_id?.split(':').slice(0,3).join(':');
  check(qraw?.partial===false&&qraw.room_id===binding.room_id&&q?.channel==='slack'&&q.author==='aeon'&&q.message_id===binding.question_id&&q.deleted_at==null&&hash(stable(q.content?.text))===binding.question_text_sha256&&q.reply_root_message_id&&q.reply_root_message_id===m.reply_root_message_id&&thread(q)?.startsWith('slack:')&&thread(q)===thread(m)&&Date.parse(q.sent_at)<=Date.parse(m.sent_at)&&Date.parse(m.sent_at)-Date.parse(q.sent_at)<=30*60000,'actual Slack owner reply/context mismatch');
 }
 const proof=inspectAdmissionStop({repo,runtime,prior,date,...options}),source=await sourceReader(proof.original_input),external=await externalReader(),ready=await preflightReader();
 const worker=read(path.join(repo,'weak-early-beta-gate/wrangler.jsonc')),database=worker.d1_databases?.filter(d=>d.binding==='CLOUD_DB');
 check(worker.name==='tentei-kyokuchi-cloud'&&database?.length===1,'fixed service/database target missing');
 const target={service:worker.name,...database[0]};check(isDeepStrictEqual(external.target,target)&&external.source_commit===head,'external evidence target/version differs');
 const decision=await decisionReader(binding.message_id);
 check(decision?.schema==='NEW_A_HOST_OPERATOR_INTERPRETATION_V1'&&decision.decision==='CONTINUE_NOV17_NATIVE_ADMISSION_ONCE'&&decision.scope==='NEW_A_NOV17_SOURCE_ADMISSION_ONCE_V1'&&decision.date===date&&decision.source_commit===head&&isDeepStrictEqual(decision.target,target)&&decision.original_run_id===proof.original_run_id&&decision.stopped_run_id===proof.stopped_run_id&&decision.original_input_sha256===proof.original_input_sha256&&['message_id','room_id','author_id','text_sha256'].every(k=>decision[k]===binding[k])&&decision.platform_signature_claimed===false,'host-reviewed one-continuation intent is missing or broader than approved');
 if(m.channel==='slack')check(decision.channel==='slack'&&decision.question_id===binding.question_id&&decision.question_text_sha256===binding.question_text_sha256&&decision.execution_date===executionDate,'Slack delayed intent scope mismatch');
 check(source?.schema==='CLOUD_NATIVE_SOURCE_REPLAY_V1'&&source.date===date&&source.original_run_id===proof.original_run_id&&source.inspection_wrote_or_sent===false&&source.network_fallback===false&&/^[a-f0-9]{64}$/.test(source.inventory_sha256),'original acquisition quality unproven');
 check(prior.recoveryCache?.sha256===source.previous_source_sha256,'stopped inspection input differs');
 check(external?.target_date===date&&external.read_only===true&&external.d1?.read_success===true&&Array.isArray(external.d1.nov17_datasets)&&external.d1.nov17_datasets.length===0&&external.d1.active?.length===1&&external.d1.active[0].as_of<date,'remote target state unclear');
 check(external.discord?.GET_only_success===true&&external.discord.destinations?.length===2&&external.discord.destinations.every(d=>d.guild_matches===true&&d.covered_since_run_start===true&&Array.isArray(d.a_base_results_after_run_start)&&d.a_base_results_after_run_start.length===0),'result delivery state unclear');
 check(ready.notification_destinations?.length===2,'independent existing destination metadata required');
 for(const role of['signal','summary']){const expected=ready.notification_destinations.filter(d=>d.role===role);check(expected.length===1&&/^\d{17,20}$/.test(expected[0].channel_id),'configured destination metadata missing');const id=expected[0].channel_id;check(external.discord.destinations.filter(d=>d.role===role&&d.channel_id===id&&d.actual_channel_id===id).length===1,'existing result destination coverage differs');}
 check(Date.parse(external.at)<=+now&&+now-Date.parse(external.at)<5*60000&&ready?.ok===true&&ready.head===head&&ready.sourceSha256===source.previous_source_sha256&&ready.acceptance_valid===true&&/^[a-f0-9]{64}$/.test(ready.activation_sha256),'current source, acceptance or fresh evidence missing');
 check(Date.now()<Date.parse(expiresAt)&&Date.now()-Date.parse(external.at)<5*60000&&isDeepStrictEqual(proof,inspectAdmissionStop({repo,runtime,prior,date,...options})),'evidence expired or changed while issuing');
 const record={schema:'CLOUD_NATIVE_ADMISSION_CONTINUATION_V1',service:'tentei-kyokuchi-cloud',strategy:'A_BASE',date,execution_date:executionDate,head,target,repo:fs.realpathSync(repo),runtime:fs.realpathSync(runtime),proof,source,external,notification_destinations:ready.notification_destinations,activation_sha256:ready.activation_sha256,owner_message:{...binding,channel:m.channel,sent_at:m.sent_at},host_decision:decision,issued_at:now.toISOString(),expires_at:expiresAt,platform_signature_claimed:false,automatic_retry_counter_reset:false};
 const digest=hash(stable(record)),dir=path.join(runtime,'native-admission-continuations',digest),file=path.join(dir,'record.json');immutable(file,record);
 for(const [name,input]of[['original-input.json',proof.original_input],['stopped-result.json',path.join(folder(runtime,prior.startedAt),'result.json')],['original-reservation.json',path.join(runtime,`recovery-${key(proof.original_run_id)}.json`)]]){const dst=path.join(dir,name);fs.copyFileSync(input,dst,fs.constants.COPYFILE_EXCL);check(hash(fs.readFileSync(dst))===hash(fs.readFileSync(input)),'audit preservation mismatch');}
 return{file,digest};
}
export function verifyAdmissionContinuation({repo,runtime,date,head,prior,file,sourceSha256,...options}){
 inside(path.join(runtime,'native-admission-continuations'),file);const record=read(file),digest=hash(stable(record));
 check(record.schema==='CLOUD_NATIVE_ADMISSION_CONTINUATION_V1'&&record.service==='tentei-kyokuchi-cloud'&&record.strategy==='A_BASE'&&record.repo===fs.realpathSync(repo)&&record.runtime===fs.realpathSync(runtime)&&record.date===date&&date==='2026-11-17'&&['2026-11-17','2026-11-18'].includes(record.execution_date||record.date)&&day(new Date())===(record.execution_date||record.date)&&record.head===head&&record.platform_signature_claimed===false&&record.automatic_retry_counter_reset===false,'continuation scope changed');
 check(path.basename(file)==='record.json'&&path.basename(path.dirname(file))===digest&&Date.parse(record.expires_at)>Date.now()&&Date.now()-Date.parse(record.external.at)<5*60000,'record changed, expired or external evidence stale');
 check(isDeepStrictEqual(record.proof,inspectAdmissionStop({repo,runtime,prior,date,...options})),'preserved evidence changed');
 check(sourceSha256===record.source.previous_source_sha256,'input version changed');
 check(hash(fs.readFileSync(path.join(repo,'.cache/weak_early_beta/new-a-private/activation.json')))===record.activation_sha256,'acceptance changed');
 for(const [name,expected]of[['original-input.json',record.proof.original_input_sha256],['stopped-result.json',record.proof.stopped_result_sha256],['original-reservation.json',record.proof.reservation_sha256]])check(hash(fs.readFileSync(path.join(path.dirname(file),name)))===expected,'audit copy changed');
 return{record,digest,file:path.resolve(file)};
}
export function claimAdmissionContinuation(runtime,verified,invocation){
 const file=path.join(runtime,'native-admission-once-'+verified.record.proof.original_input_sha256+'.json');immutable(file,{schema:'CLOUD_NATIVE_ADMISSION_ONCE_V1',record:verified.digest,invocation,original_run_id:verified.record.proof.original_run_id});return file;
}
export function continuationForRunner({repo,runtime,file}){
 const head=execFileSync('git',['--no-optional-locks','rev-parse','HEAD'],{cwd:repo,encoding:'utf8',windowsHide:true,timeout:30000}).trim();
 const prior=read(path.join(runtime,'daily-latest.json')),quality=read(path.join(repo,'.cache/weak_early_beta/tse_daily.source-quality.json'));
 const verified=verifyAdmissionContinuation({repo,runtime,date:read(file).date,head,sourceSha256:quality.daily_sha256,prior,file});
 return verified;
}
export function consumeAdmissionContinuation(runtime,verified,invocation,startedAt,rootPid=process.pid){
 check(fs.readFileSync(path.join(runtime,'daily.lock'),'utf8')===startedAt,'continuation does not own lock');
 check(hash(fs.readFileSync(path.join(runtime,'daily-latest.json')))===verified.record.proof.stopped_result_sha256,'latest stopped record changed after verification');
 check(Date.parse(verified.record.expires_at)>Date.now()&&Date.now()-Date.parse(verified.record.external.at)<5*60000,'continuation proof expired before consume');
 const file=path.join(runtime,'native-admission-once-'+verified.record.proof.original_input_sha256+'.json'),claim=read(file);check(claim.record===verified.digest&&claim.invocation===invocation,'continuation claim owner differs');
 check(day(new Date())===(verified.record.execution_date||verified.record.date),'actual execution day changed');
 immutable(file+'.consumed',{...claim,schema:'CLOUD_NATIVE_ADMISSION_CONSUMED_V1',new_run_id:startedAt,root_pid:rootPid,record_file:verified.file,record_file_sha256:hash(fs.readFileSync(verified.file))});return{record:verified.digest,original_run_id:verified.record.proof.original_run_id,stopped_run_id:verified.record.proof.stopped_run_id,path:file+'.consumed'};
}
export function beginAdmissionExecution(config,consumed,startedAt,rootPid,env=process.env){
 return JSON.parse(execFileSync(config.pythonPath,['-B','-m','weak_early_beta.new_a.native_admission_context','begin','--record',consumed.path,'--root-pid',String(rootPid),'--started-at',startedAt],{cwd:config.repoPath,env,encoding:'utf8',windowsHide:true,timeout:300000}));
}
