// Private operator records, issued after independent host approval and artifact checks.
// No source acquisition, D1, notification or account operation occurs here.
import fs from 'node:fs';import path from 'node:path';import {createHash}from'node:crypto';import{isDeepStrictEqual}from'node:util';
const sha=v=>createHash('sha256').update(v).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const stable=v=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const inside=(root,p)=>{const rel=path.relative(fs.realpathSync(root),fs.realpathSync(p));return rel&&rel!=='..'&&!rel.startsWith('..'+path.sep)&&!path.isAbsolute(rel);};
const check=(v,m)=>{if(!v)throw Error(m);};
export function inspectPreflightFailure(repo,runtime,prior,date){
 check(prior?.identity==='WEAK_EARLY_CLOUD_DAILY_V1'&&prior.date===date&&prior.ok===false&&prior.stage==='preflight'&&prior.completedAt&&prior.error==='local HEAD is not the latest origin/research/weak-early-beta','only proven HEAD preflight failure may reconcile');
 for(const k of ['new_a','deployment','notifications','notificationPreview','latestSession','selectorRows','acquisitionEvidence','generatedCommit','fundamentals'])check(prior[k]===undefined,'downstream work or ambiguous metadata exists');
 check(!prior.systemLogErrors?.length&&isDeepStrictEqual(prior.systemLogEvents,['error']),'error log outcome must be known');
 const folder=path.join(runtime,'daily-'+prior.startedAt.replace(/[:.]/g,'-'));check(inside(runtime,folder),'failure directory escapes runtime');
 const result=path.join(folder,'result.json'),invoked=read(path.join(folder,'invoked.json'));
 check(isDeepStrictEqual(read(path.join(runtime,'daily-latest.json')),prior)&&isDeepStrictEqual(read(result),prior)&&invoked.identity==='CLOUD_RUNNER_INVOKED_V1'&&invoked.startedAt===prior.startedAt&&invoked.date===date&&invoked.pid===prior.pid&&Date.parse(prior.completedAt)>=Date.parse(prior.startedAt),'failure identity mismatch');
 const hashes={};
 for(const name of fs.readdirSync(folder)){
  check(/^(?:invoked\.json|result\.json|progress\.jsonl|(?:business-day|process-preflight|system-log-error|git-\d+-(?:branch|status|remote|rev-parse|ls-remote))\.(?:stdout|stderr|process\.json))$/.test(name),'unexpected failure artifact');
  const p=path.join(folder,name);check(inside(folder,p)&&fs.statSync(p).isFile(),'failure artifact is not a private regular file');hashes[name]=sha(fs.readFileSync(p));
  if(name.endsWith('.process.json')){const m=read(p);check(m.identity==='CLOUD_CHILD_PROCESS_V1'&&m.status==='exited'&&m.code===0&&m.completedAt,'child outcome not confirmed');}
 }
 for(const stem of ['business-day','process-preflight','system-log-error','git-1-branch','git-2-status','git-3-remote','git-4-rev-parse','git-5-ls-remote'])for(const suffix of ['stdout','stderr','process.json'])check(hashes[stem+'.'+suffix],'required child artifact missing');
 const stages=fs.readFileSync(path.join(folder,'progress.jsonl'),'utf8').trim().split(/\r?\n/).map(l=>JSON.parse(l).stage);
 check(stages.length>0&&stages.every(s=>['branch','preflight','network-preflight'].includes(s)),'pipeline stage already entered');
 const errorPost=read(path.join(folder,'system-log-error.stdout'));check(errorPost.posted===true&&errorPost.duplicate===false&&typeof errorPost.message_id==='string'&&/^\d+$/.test(errorPost.message_id),'error notification receipt unavailable');
 check(read(path.join(folder,'business-day.stdout')).business_day===true,'business day unproven');
 const outputs=Object.keys(hashes).filter(n=>/^git-\d+-/.test(n)&&n.endsWith('.stdout'));
 const output=kind=>{const n=outputs.find(n=>n.endsWith('-'+kind+'.stdout'));check(n,'required Git artifact missing');return fs.readFileSync(path.join(folder,n),'utf8').trim();};
 check(output('branch')==='research/weak-early-beta'&&output('status')===''&&/^(?:https:\/\/github\.com\/|git@github\.com:)Ken5InvestmentLab\/screening-bot(?:\.git)?$/.test(output('remote')),'original Git boundary mismatch');
 const oldHead=output('rev-parse'),remote=output('ls-remote');check(/^[a-f0-9]{40}$/.test(oldHead)&&/^[a-f0-9]{40}\s+refs\/heads\/research\/weak-early-beta$/.test(remote)&&remote.split(/\s/)[0]!==oldHead,'recorded HEAD failure not corroborated');
 check(!fs.existsSync(path.join(repo,'.cache/weak_early_beta/new-a-private/daily-live.sqlite')),'live store needs separate reconciliation');
 return {original_sha256:sha(fs.readFileSync(path.join(runtime,'daily-latest.json'))),original_started_at:prior.startedAt,artifact_hashes:hashes,error_message_id:errorPost.message_id};
}
export async function issuePreflightReconciliation({repo,runtime,date,head,prior,binding,reader,authority,expiresAt}){
 check(typeof reader==='function','independent host reader required');check(/^[a-f0-9]{40}$/.test(head),'invalid repaired head');
 check(binding&&['message_id','room_id','author_id'].every(k=>typeof binding[k]==='string'&&binding[k].length>0)&&/^[a-f0-9]{64}$/.test(binding.text_sha256),'owner identity binding required');
 check(authority&&binding.author_id===authority.author_id&&binding.room_id===authority.room_id,'host-verified owner authority required');
 const raw=await reader(binding.message_id),m=raw?.message;
 check(raw?.partial===false&&raw.room_id===binding.room_id&&m?.author==='user'&&m.author_id===binding.author_id&&m.channel==='chatgpt'&&m.message_id===binding.message_id&&m.deleted_at==null&&sha(stable(m.content?.text))===binding.text_sha256,'independent recovery approval mismatch');
 check(date==='2026-11-16'&&new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())===date&&Date.parse(expiresAt)>Date.now()&&Date.parse(expiresAt)<=Date.parse('2026-11-17T00:00:00+09:00'),'reconciliation approval validity: Nov16 once only');
 const proof=inspectPreflightFailure(repo,runtime,prior,date),record={schema:'CLOUD_PREFLIGHT_RECONCILIATION_V1',service:'tentei-kyokuchi-cloud',strategy:'A_BASE',repo:fs.realpathSync(repo),runtime:fs.realpathSync(runtime),date,head,...proof,owner_message:{...binding,sent_at:m.sent_at},expires_at:expiresAt,issuance:'INDEPENDENT_HOST_READ_VERIFIED_OPERATOR_RECORD',platform_signature_claimed:false};
 const digest=sha(stable(record)),directory=path.join(runtime,'preflight-reconciliations',digest);fs.mkdirSync(directory,{recursive:true});
 const original=path.join(directory,'original.json');if(!fs.existsSync(original)){const f=fs.openSync(original,'wx');try{fs.writeFileSync(f,fs.readFileSync(path.join(runtime,'daily-latest.json')));fs.fsyncSync(f);}finally{fs.closeSync(f);}}
 check(sha(fs.readFileSync(original))===proof.original_sha256,'preserved original bytes mismatch');
 const file=path.join(directory,'record.json'),text=stable(record)+'\n';if(!fs.existsSync(file)){const f=fs.openSync(file,'wx');try{fs.writeFileSync(f,text);fs.fsyncSync(f);}finally{fs.closeSync(f);}}else check(fs.readFileSync(file,'utf8')===text,'immutable reconciliation conflict');
 return {file,digest};
}
export function verifyPreflightReconciliation({repo,runtime,date,head,prior,file}){
 check(inside(path.join(runtime,'preflight-reconciliations'),file)&&path.basename(file)==='record.json','private reconciliation record required');const r=read(file);
 check(r.schema==='CLOUD_PREFLIGHT_RECONCILIATION_V1'&&r.service==='tentei-kyokuchi-cloud'&&r.strategy==='A_BASE'&&r.repo===fs.realpathSync(repo)&&r.runtime===fs.realpathSync(runtime)&&r.date===date&&r.head===head&&r.issuance==='INDEPENDENT_HOST_READ_VERIFIED_OPERATOR_RECORD'&&r.platform_signature_claimed===false&&Date.parse(r.expires_at)>Date.now(),'reconciliation binding changed');
 check(path.basename(path.dirname(file))===sha(stable(r)),'reconciliation record digest mismatch');
 const proof=inspectPreflightFailure(repo,runtime,prior,date);for(const k of Object.keys(proof))check(isDeepStrictEqual(r[k],proof[k]),'failure artifacts changed');
 check(sha(fs.readFileSync(path.join(path.dirname(file),'original.json')))===r.original_sha256&&isDeepStrictEqual(read(path.join(runtime,'daily-latest.json')),prior),'latest failure changed');
 return {record:r,digest:sha(stable(r)),file:path.resolve(file)};
}
export function claimPreflightReconciliation(runtime,verified,invocation){
 const p=path.join(runtime,'preflight-claim-'+verified.record.original_sha256+'.json'),v={schema:'CLOUD_PREFLIGHT_CLAIM_V1',digest:verified.digest,invocation,original_sha256:verified.record.original_sha256};
 const f=fs.openSync(p,'wx');try{fs.writeFileSync(f,stable(v));fs.fsyncSync(f);}finally{fs.closeSync(f);}return p;
}
export function consumePreflightReconciliation(runtime,verified,invocation,newRunId){
 const p=path.join(runtime,'preflight-claim-'+verified.record.original_sha256+'.json'),claim=read(p);check(claim.digest===verified.digest&&claim.invocation===invocation,'task-entry reconciliation claim required');
 const target=p+'.consumed',f=fs.openSync(target,'wx');try{fs.writeFileSync(f,stable({...claim,new_run_id:newRunId}));fs.fsyncSync(f);}finally{fs.closeSync(f);}
 return {originalRunId:verified.record.original_started_at,reconciliation_sha256:verified.digest,claim:p};
}
