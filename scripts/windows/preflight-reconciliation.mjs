// Private operator records, issued after independent host approval and artifact checks.
// No source acquisition, D1, notification or account operation occurs here.
import fs from 'node:fs';import path from 'node:path';import {createHash}from'node:crypto';import{isDeepStrictEqual}from'node:util';
const sha=v=>createHash('sha256').update(v).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const stable=v=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const inside=(root,p)=>{const rel=path.relative(fs.realpathSync(root),fs.realpathSync(p));return rel&&rel!=='..'&&!rel.startsWith('..'+path.sep)&&!path.isAbsolute(rel);};
const check=(v,m)=>{if(!v)throw Error(m);};
const timeoutError = 'timeout: approved-release-before-detection';
const timeoutSchema = 'CLOUD_APPROVAL_TIMEOUT_RECONCILIATION_V1';
const sha256 = /^[a-f0-9]{64}$/;
const commit = /^[a-f0-9]{40}$/;
const version = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const jst = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' });
const timeoutChildren = ['business-day', 'process-preflight', 'gh-preflight', 'previous-release',
  'git-1-branch', 'git-2-status', 'git-3-remote', 'git-4-rev-parse', 'git-5-ls-remote', 'approved-release-before-detection'];
const timeoutResultKeys = new Set(['identity', 'startedAt', 'pid', 'ok', 'date', 'stage', 'progressAt', 'businessDay',
  'networkPreflight', 'startCommit', 'fundamentals', 'fundamental', 'previousSuccessfulDeployment', 'error', 'completedAt']);

function checkedFile(root, file) {
  check(inside(root, file) && fs.lstatSync(file).isFile(), 'exact private regular file required');
  return fs.readFileSync(file);
}

export function inspectApprovalTimeout(runtime, prior, date) {
  check(prior?.identity === 'WEAK_EARLY_CLOUD_DAILY_V1' && prior.date === date && prior.ok === false
    && prior.stage === 'preflight' && prior.error === timeoutError && Object.keys(prior).every(key => timeoutResultKeys.has(key))
    && commit.test(prior.startCommit) && Number.isSafeInteger(prior.pid) && prior.pid > 0
    && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(prior.startedAt), 'only original approval preflight timeout may reconcile');
  const started = Date.parse(prior.startedAt), completed = Date.parse(prior.completedAt), progress = Date.parse(prior.progressAt);
  check(started <= progress && progress <= completed && jst.format(started) === date && jst.format(completed) === date,
    'approval timeout chronology differs');
  check(prior.businessDay === true && prior.networkPreflight?.blocked === false && Array.isArray(prior.networkPreflight?.groups)
    && Number.isFinite(prior.networkPreflight?.waitedMs) && prior.networkPreflight.waitedMs >= 0
    && isDeepStrictEqual(prior.fundamentals, []) && isDeepStrictEqual(prior.fundamental, {ok:true, status:'NOT_REQUESTED', imported:0, posted:0}),
    'approval timeout has ambiguous detection or fundamental state');

  const folder = path.join(runtime, 'daily-' + prior.startedAt.replace(/[:.]/g, '-'));
  check(inside(runtime, folder) && fs.lstatSync(folder).isDirectory(), 'approval timeout directory differs');
  const expected = ['invoked.json', 'progress.jsonl', 'result.json',
    ...timeoutChildren.flatMap(stem => ['stdout', 'stderr', 'process.json'].map(suffix => `${stem}.${suffix}`))];
  check(isDeepStrictEqual(fs.readdirSync(folder).sort(), expected.slice().sort()), 'approval timeout artifact inventory differs');
  const files = Object.fromEntries(expected.map(name => [name, checkedFile(folder, path.join(folder, name))]));
  const latest = checkedFile(runtime, path.join(runtime, 'daily-latest.json'));
  check(latest.equals(files['result.json']) && isDeepStrictEqual(JSON.parse(latest), prior)
    && isDeepStrictEqual(JSON.parse(files['invoked.json']), {identity:'CLOUD_RUNNER_INVOKED_V1',
      startedAt:prior.startedAt, pid:prior.pid, ok:false, date}), 'approval timeout run identity differs');

  const processReceipt = stem => JSON.parse(files[`${stem}.process.json`]);
  for (const stem of timeoutChildren) {
    const child = processReceipt(stem), at = Date.parse(child.completedAt);
    check(child.identity === 'CLOUD_CHILD_PROCESS_V1' && child.status === 'exited' && started <= at && at <= completed
      && Number.isSafeInteger(child.pid) && child.pid > 0 && child.pid !== prior.pid
      && child.code === (stem === 'approved-release-before-detection' ? 1 : 0), 'approval timeout child outcome differs');
  }
  const timedChild = processReceipt('approved-release-before-detection');
  check(Date.parse(timedChild.completedAt) - Date.parse(processReceipt('previous-release').completedAt) >= 60_000
    && files['approved-release-before-detection.stdout'].length === 0 && files['approved-release-before-detection.stderr'].length === 0,
    'approval timeout child output or duration differs');

  const stages = files['progress.jsonl'].toString('utf8').trim().split(/\r?\n/).map(line => JSON.parse(line));
  const ready = stages.filter(event => event.stage === 'network-preflight' && event.networkPreflight?.status === 'ready');
  check(stages[0]?.stage === 'branch' && stages.at(-1)?.stage === 'preflight' && stages.at(-1)?.at === prior.progressAt
    && stages.every((event, index) => ['branch', 'preflight', 'network-preflight'].includes(event.stage)
      && Date.parse(index ? stages[index - 1].at : prior.startedAt) <= Date.parse(event.at) && Date.parse(event.at) <= completed),
    'approval timeout pipeline already entered or progress differs');
  check(ready.length === 1 && ready[0].networkPreflight.blocked === false
    && ready[0].networkPreflight.elapsedMs === prior.networkPreflight.waitedMs
    && isDeepStrictEqual(ready[0].networkPreflight.groups, prior.networkPreflight.groups), 'approval timeout network readback differs');
  const output = stem => files[stem + '.stdout'].toString('utf8').trim();
  check(JSON.parse(output('business-day')).business_day === true && output('git-1-branch') === 'research/weak-early-beta'
    && output('git-2-status') === '' && /^(?:https:\/\/github\.com\/|git@github\.com:)Ken5InvestmentLab\/screening-bot(?:\.git)?$/.test(output('git-3-remote'))
    && output('git-4-rev-parse') === prior.startCommit
    && output('git-5-ls-remote').split(/\s+/).join(' ') === prior.startCommit + ' refs/heads/research/weak-early-beta',
    'approval timeout original source differs');
  const previous = JSON.parse(output('previous-release'))[0];
  check(isDeepStrictEqual(previous, prior.previousSuccessfulDeployment) && previous?.headSha === prior.startCommit
    && previous.status === 'completed' && previous.conclusion === 'success', 'approval timeout prior release differs');
  return {original_sha256: sha(latest), original_started_at: prior.startedAt, original_source_commit: prior.startCommit,
    artifact_hashes: Object.fromEntries(Object.entries(files).map(([name, bytes]) => [name, sha(bytes)]))};
}

function checkedTimeoutRelease(repo, head, proof, release) {
  check(release?.schema === 'NEW_A_ORDINARY_RUNTIME_RELEASE_V1' && release.source_commit === head
    && head !== proof.original_source_commit && release.worker === 'tentei-kyokuchi-cloud' && release.database === 'tentei-cloud-settings'
    && version.test(release.version_id) && sha256.test(release.activation_sha256) && sha256.test(release.build_input_sha256)
    && sha256.test(release.policy_sha256) && Number.isSafeInteger(release.ci_run_id) && release.ci_run_id > 0
    && /^cloud-deploy-[A-Za-z0-9._-]+$/.test(release.tag), 'exact approved successor release required');
  const root = path.join(repo, '.cache/weak_early_beta/new-a-private');
  const activationRaw = checkedFile(repo, path.join(root, 'activation.json'));
  const activation = JSON.parse(activationRaw.toString('utf8').replace(/^\uFEFF/, ''));
  const application = activation.owner_acceptance?.application_id;
  check(sha(activationRaw) === release.activation_sha256 && sha256.test(application)
    && activation.schema === 'NEW_A_OWNER_ACTIVATION_V1' && activation.strategy === 'A_BASE'
    && activation.active === true && activation.external_actions_approved === true && activation.operational_admission == null,
    'exact approved successor activation changed');
  const archive = path.join(root, 'continuing-acceptance', 'applications', application);
  const completed = JSON.parse(checkedFile(repo, path.join(archive, 'completed.json')));
  const auditedRaw = checkedFile(repo, path.join(archive, 'member-ordinary.json'));
  const audited = JSON.parse(auditedRaw.toString('utf8').replace(/^\uFEFF/, ''));
  const keys = ['source_commit', 'version_id', 'build_input_sha256', 'policy_sha256', 'ci_run_id', 'tag'];
  check(completed.schema === 'NEW_A_MEMBER_ORDINARY_APPLICATION_V1' && completed.source_commit === head
    && completed.after_sha256 === release.activation_sha256 && completed.member_ordinary_sha256 === sha(auditedRaw)
    && audited.predecessor?.source_commit === proof.original_source_commit && version.test(audited.predecessor?.version_id)
    && audited.predecessor.version_id !== release.version_id && keys.every(key => audited.deployment?.[key] === release[key]),
    'exact approved successor audit differs');
}

function checkedTimeoutEffects(value, date, proof, release) {
  const observed = Date.parse(value?.observed_at), now = Date.now();
  check(value?.schema === 'CLOUD_APPROVAL_TIMEOUT_NO_EFFECTS_V1' && value.date === date && value.read_only === true
    && value.original_started_at === proof.original_started_at && value.source_commit === release.source_commit
    && value.worker_version_id === release.version_id && sha256.test(value.receipt_sha256)
    && Date.parse(proof.original_started_at) <= observed && now - 300_000 <= observed && observed <= now
    && ['target_owner_datasets', 'target_member_datasets', 'target_outbox_entries', 'target_discord_results'].every(key => value[key] === 0),
    'fresh independent approval timeout no-effect evidence required');
}

function checkTimeoutDate(date, expiresAt) {
  const now = Date.now(), expiry = Date.parse(expiresAt);
  check(jst.format(now) === date && now < expiry && expiry <= Date.parse(`${date}T00:00:00+09:00`) + 86_400_000,
    'approval timeout reconciliation must stay on the same JST day');
}
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
export async function issuePreflightReconciliation({repo,runtime,date,head,prior,binding,reader,authority,expiresAt,
  approvedReleaseReader,sideEffectReader}){
 check(typeof reader==='function','independent host reader required');check(/^[a-f0-9]{40}$/.test(head),'invalid repaired head');
 check(binding&&['message_id','room_id','author_id'].every(k=>typeof binding[k]==='string'&&binding[k].length>0)&&/^[a-f0-9]{64}$/.test(binding.text_sha256),'owner identity binding required');
 check(authority&&binding.author_id===authority.author_id&&binding.room_id===authority.room_id,'host-verified owner authority required');
 const raw=await reader(binding.message_id),m=raw?.message;
 check(raw?.partial===false&&raw.room_id===binding.room_id&&m?.author==='user'&&m.author_id===binding.author_id&&m.channel==='chatgpt'&&m.message_id===binding.message_id&&m.deleted_at==null&&sha(stable(m.content?.text))===binding.text_sha256,'independent recovery approval mismatch');
 const isTimeout = prior?.error === timeoutError;
 let proof, timeoutEvidence;
 if (isTimeout) {
  checkTimeoutDate(date, expiresAt);
  check(typeof approvedReleaseReader === 'function' && typeof sideEffectReader === 'function', 'independent timeout evidence readers required');
  const ownerAt = Date.parse(m.sent_at);
  check(Date.parse(prior.completedAt) <= ownerAt && ownerAt <= Date.now() && jst.format(ownerAt) === date,
    'same-day owner approval after the stopped run required');
  proof = inspectApprovalTimeout(runtime, prior, date);
  const exactScope = {repo:fs.realpathSync(repo), runtime:fs.realpathSync(runtime), date, head,
    original_sha256:proof.original_sha256, original_started_at:proof.original_started_at, original_source_commit:proof.original_source_commit};
  const release = structuredClone(await approvedReleaseReader(Object.freeze(exactScope)));
  checkedTimeoutRelease(repo, head, proof, release);
  const effects = structuredClone(await sideEffectReader(Object.freeze({...exactScope, worker_version_id:release.version_id})));
  checkedTimeoutEffects(effects, date, proof, release);
  checkTimeoutDate(date, expiresAt);
  check(isDeepStrictEqual(inspectApprovalTimeout(runtime, prior, date), proof), 'approval timeout artifacts changed while issuing');
  checkedTimeoutRelease(repo, head, proof, release);
  timeoutEvidence = {approved_release:release, no_side_effects:effects};
 } else {
  check(date==='2026-11-16'&&jst.format(new Date())===date&&Date.parse(expiresAt)>Date.now()&&Date.parse(expiresAt)<=Date.parse('2026-11-17T00:00:00+09:00'),'reconciliation approval validity: Nov16 once only');
  proof = inspectPreflightFailure(repo,runtime,prior,date);
 }
 const record={schema:isTimeout?timeoutSchema:'CLOUD_PREFLIGHT_RECONCILIATION_V1',service:'tentei-kyokuchi-cloud',strategy:'A_BASE',repo:fs.realpathSync(repo),runtime:fs.realpathSync(runtime),date,head,...proof,...timeoutEvidence,owner_message:{...binding,sent_at:m.sent_at},expires_at:expiresAt,issuance:'INDEPENDENT_HOST_READ_VERIFIED_OPERATOR_RECORD',platform_signature_claimed:false};
 const digest=sha(stable(record)),directory=path.join(runtime,'preflight-reconciliations',digest);fs.mkdirSync(directory,{recursive:true});
 const original=path.join(directory,'original.json');if(!fs.existsSync(original)){const f=fs.openSync(original,'wx');try{fs.writeFileSync(f,fs.readFileSync(path.join(runtime,'daily-latest.json')));fs.fsyncSync(f);}finally{fs.closeSync(f);}}
 check(sha(fs.readFileSync(original))===proof.original_sha256,'preserved original bytes mismatch');
 const file=path.join(directory,'record.json'),text=stable(record)+'\n';if(!fs.existsSync(file)){const f=fs.openSync(file,'wx');try{fs.writeFileSync(f,text);fs.fsyncSync(f);}finally{fs.closeSync(f);}}else check(fs.readFileSync(file,'utf8')===text,'immutable reconciliation conflict');
 return {file,digest};
}
export function verifyPreflightReconciliation({repo,runtime,date,head,prior,file}){
 check(inside(path.join(runtime,'preflight-reconciliations'),file)&&path.basename(file)==='record.json','private reconciliation record required');const r=read(file);
 const isTimeout = r.schema === timeoutSchema;
 check((isTimeout||r.schema==='CLOUD_PREFLIGHT_RECONCILIATION_V1')&&r.service==='tentei-kyokuchi-cloud'&&r.strategy==='A_BASE'&&r.repo===fs.realpathSync(repo)&&r.runtime===fs.realpathSync(runtime)&&r.date===date&&r.head===head&&r.issuance==='INDEPENDENT_HOST_READ_VERIFIED_OPERATOR_RECORD'&&r.platform_signature_claimed===false&&Date.parse(r.expires_at)>Date.now(),'reconciliation binding changed');
 check(path.basename(path.dirname(file))===sha(stable(r)),'reconciliation record digest mismatch');
 const proof=isTimeout?inspectApprovalTimeout(runtime,prior,date):inspectPreflightFailure(repo,runtime,prior,date);
 for(const k of Object.keys(proof))check(isDeepStrictEqual(r[k],proof[k]),'failure artifacts changed');
 if (isTimeout) {
  checkTimeoutDate(date, r.expires_at);
  checkedTimeoutRelease(repo, head, proof, r.approved_release);
  checkedTimeoutEffects(r.no_side_effects, date, proof, r.approved_release);
 }
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
