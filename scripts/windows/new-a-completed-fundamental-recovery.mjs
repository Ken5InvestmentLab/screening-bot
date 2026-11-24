// Resume only the retained analysis claim of one successfully published daily.
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { command, loadFundamentalEnvironment } from './weak-early-beta-fundamental-runner.mjs';
import { runNewAFundamentalStage } from './new-a-fundamental-stage.mjs';

const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=file=>JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));
const check=(ok,reason)=>{if(!ok)throw new Error(reason);};

export async function recoverCompletedFundamentals({repo,date,runStep,runAnalysis=runNewAFundamentalStage,
  loadEnvironment=loadFundamentalEnvironment}) {
  repo=fs.realpathSync(repo);
  check(/^\d{4}-\d{2}-\d{2}$/.test(date),'An exact completed session is required');
  const config=read(path.join(repo,'.cache/weak_early_beta/daily-runner.config.json'));
  check(fs.realpathSync(config.repoPath)===repo,'Completed recovery checkout differs from its runner config');
  const runtime=fs.realpathSync(config.runtimeDir),dailyFile=path.join(runtime,'daily-latest.json');
  const root=path.join(repo,'.cache/weak_early_beta/new-a-private');
  const producer=path.join(root,'latest-run.json'),daily=read(dailyFile),run=read(producer);
  check(runtime.startsWith(repo+path.sep)&&!fs.existsSync(path.join(runtime,'daily.lock'))
    &&daily.ok===true&&daily.completedAt&&daily.date===date&&run.latest_session===date
    &&run.identity==='NEW_A_CLOUD_DAILY_V1'&&run.detection_executed===true&&run.dry_run===false,
    'Only the still-current completed daily can recover its retained analysis');
  const claimFile=path.join(root,'runs',date,run.source_sha256,'live','fundamental-analysis','claim.json');
  check(fs.realpathSync(claimFile)===claimFile,'An exact retained claim is required');
  const claim=read(claimFile);
  check(Number.isSafeInteger(claim.claimedCount)&&claim.claimedCount>0
    &&claim.claimedCount===daily.selectorRows,'The retained analysis claim does not match completed detections');
  const fconfig=read(config.fundamentalConfigPath),env=loadEnvironment(fconfig);
  const work=path.join(runtime,'fundamental-recovery',new Date().toISOString().replace(/[:.]/g,'-')+'-'+randomUUID());
  fs.mkdirSync(work,{recursive:true});
  const step=runStep??(async(exe,args,options)=>{
    const code=await command(exe,args,options);
    check(code===0,'Completed fundamental recovery child failed; inspect its retained log');
    return {stdout:fs.readFileSync(options.log+'.stdout','utf8')};
  });
  const accepted=await step(config.pythonPath,['-B','-c',
    'from pathlib import Path; from weak_early_beta.new_a.fundamentals import approved_recovery_source; print(approved_recovery_source(Path.cwd()))'],
    {cwd:repo,env,log:path.join(work,'approved-source'),timeoutMs:300000});
  const source=accepted.stdout.trim();check(/^[a-f0-9]{40}$/.test(source),'The current approved source was not verified');
  const lease={schema:'NEW_A_COMPLETED_FUNDAMENTAL_RECOVERY_V1',source_commit:source,day:date,
    original_daily_started_at:daily.startedAt,completed_daily_sha256:hash(fs.readFileSync(dailyFile)),
    producer_sha256:hash(fs.readFileSync(producer)),claim_sha256:hash(fs.readFileSync(claimFile)),token:randomUUID()};
  const lock=path.join(runtime,'fundamental-recovery.lock'),bytes=JSON.stringify(lease)+'\n';
  fs.writeFileSync(lock,bytes,{flag:'wx',mode:0o600});
  const leaseSha=hash(bytes);
  let result={identity:'NEW_A_COMPLETED_FUNDAMENTAL_RECOVERY_V1',date,source_commit:source,
    claimSha256:lease.claim_sha256,startedAt:new Date().toISOString(),work,ok:false,
    detectionExecuted:false,notificationsSent:0,productionPublished:false};
  try {
    const receipt=await runAnalysis({config,repo,runtime,today:date,startedAt:daily.startedAt,runDir:work,env,
      runStep:step,expectedCount:claim.claimedCount,completedRecoverySha256:leaseSha});
    check(hash(fs.readFileSync(claimFile))===lease.claim_sha256&&hash(fs.readFileSync(dailyFile))===lease.completed_daily_sha256,
      'The retained claim or original daily result changed during recovery');
    result={...result,ok:true,receipt,completedAt:new Date().toISOString()};
    return result;
  } catch(error) {
    result={...result,status:'HELD',error:String(error.message),completedAt:new Date().toISOString()};
    throw error;
  } finally {
    fs.writeFileSync(path.join(work,'result.json'),JSON.stringify(result,null,2)+'\n');
    check(hash(fs.readFileSync(lock))===leaseSha,'Recovery ownership changed; preserve the current lock');
    fs.unlinkSync(lock);
  }
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const {values}=parseArgs({options:{date:{type:'string'}}});
  recoverCompletedFundamentals({repo:path.resolve(import.meta.dirname,'../..'),date:values.date})
    .then(value=>console.log(JSON.stringify(value)))
    .catch(error=>{console.error(error.message);process.exitCode=1;});
}
