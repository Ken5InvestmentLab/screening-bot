import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export function cleanEnvironment(source) {
  const result = { ...source };
  for (const key of Object.keys(result)) if (/^(OPENAI_API_KEY|CODEX_API_KEY)$/i.test(key)) delete result[key];
  return result;
}
export function remainingAlerts(batch, state) {
  return batch.alerts.filter(a => !state.posted[a.alertId]);
}
export function assertOwned(batch, state) {
  const ids = new Set(batch.alerts.map(a => a.alertId));
  for (const [id, claim] of Object.entries(state.claims || {})) {
    if (!ids.has(id) || claim.claimId !== batch.claimId) throw new Error('Foreign active claim; stop without collecting or posting.');
  }
  for (const alert of remainingAlerts(batch, state)) {
    if (state.claims[alert.alertId]?.claimId !== batch.claimId) throw new Error('A pending alert lost its claim; manual reconciliation required.');
  }
}
export function assertComplete(batch, state) {
  if (remainingAlerts(batch, state).length || Object.keys(state.claims || {}).length || Object.keys(state.failed || {}).length || (state.pendingLogEvents || []).length) {
    throw new Error('Premium state is incomplete; do not report success or send an HTML notice.');
  }
}
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); }
function writeJson(file, value) {
  const tmp = file + '.tmp'; fs.writeFileSync(tmp, JSON.stringify(value, null, 2) + '\n'); fs.renameSync(tmp, file);
}
function loadEnvironment(repo) {
  const result = cleanEnvironment(process.env);
  for (const file of [path.join(repo, '.env'), path.join(repo, 'premium_worker', '.env')]) {
    if (!fs.existsSync(file)) continue;
    for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
      const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (!m || result[m[1]] !== undefined) continue;
      let value = m[2];
      if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1,-1);
      result[m[1]] = value;
    }
  }
  return cleanEnvironment(result);
}
async function command(exe, args, {cwd, env, log, input = '', timeoutMs = 12_000_000}) {
  const out = fs.openSync(log + '.stdout', 'w'), err = fs.openSync(log + '.stderr', 'w');
  try {
    return await new Promise((resolve, reject) => {
      const child = spawn(exe, args, {cwd, env, windowsHide:true, stdio:['pipe', out, err]});
      const timer = setTimeout(() => {
        // Stop only this runner's child tree; never kill the desktop app or unrelated tasks.
        if (process.platform === 'win32') spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], {windowsHide:true, stdio:'ignore'});
        else child.kill('SIGTERM');
        reject(new Error('Execution timeout; inspect receipts and claims before retrying.'));
      }, timeoutMs);
      child.on('error', e => { clearTimeout(timer); reject(e); });
      child.on('exit', code => { clearTimeout(timer); resolve(code); });
      child.stdin.on('error', () => {});
      child.stdin.end(input);
    });
  } finally { fs.closeSync(out); fs.closeSync(err); }
}
async function probeFetch(url, options = {}) {
  for (let attempt=0; attempt<4; attempt++) {
    try {
      const response = await fetch(url,{...options,signal:AbortSignal.timeout(30000)});
      if (![429,500,502,503,504].includes(response.status) || attempt===3) return response;
      await response.body?.cancel();
    } catch(error) { if (attempt===3) throw error; }
    await new Promise(resolve=>setTimeout(resolve,1000*(attempt+1)));
  }
}
async function probeSheets(config, env) {
  const raw = env.GOOGLE_SERVICE_ACCOUNT_JSON || (env.GOOGLE_SERVICE_ACCOUNT_JSON_B64 && Buffer.from(env.GOOGLE_SERVICE_ACCOUNT_JSON_B64, 'base64').toString('utf8')) || fs.readFileSync(path.resolve(config.repoPath, env.GOOGLE_APPLICATION_CREDENTIALS || env.GOOGLE_SERVICE_ACCOUNT_FILE), 'utf8');
  const account = JSON.parse(raw), now = Math.floor(Date.now()/1000);
  const enc = v => Buffer.from(JSON.stringify(v)).toString('base64url');
  const payload = enc({alg:'RS256',typ:'JWT'}) + '.' + enc({iss:account.client_email,scope:'https://www.googleapis.com/auth/spreadsheets.readonly',aud:'https://oauth2.googleapis.com/token',iat:now,exp:now+600});
  const signature = crypto.sign('RSA-SHA256', Buffer.from(payload), account.private_key).toString('base64url');
  const response = await probeFetch('https://oauth2.googleapis.com/token', {method:'POST',body:new URLSearchParams({grant_type:'urn:ietf:params:oauth:grant-type:jwt-bearer',assertion:payload+'.'+signature})});
  if (!response.ok) throw new Error('Probe Google authentication HTTP '+response.status);
  const token = (await response.json()).access_token;
  const id = env.PREMIUM_SPREADSHEET_ID || env.SPREADSHEET_ID;
  const range = encodeURIComponent((env.PREMIUM_SHEET_NAME || 'alerts_raw')+'!A1:B4');
  const sheet = await probeFetch(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${range}`, {headers:{Authorization:'Bearer '+token}});
  if (!sheet.ok) throw new Error('Probe read-only Sheets request HTTP '+sheet.status);
  if (!(await sheet.json()).values?.length) throw new Error('Probe Sheets returned no header.');
  // GET only: verify existing Discord credentials without sending a test message.
  const discord = await probeFetch(env.DISCORD_PREMIUM_WEBHOOK_URL);
  if (!discord.ok) throw new Error('Probe Discord webhook GET HTTP '+discord.status);
}
async function main(mode, configFile) {
  const config = readJson(configFile), startedAt = new Date().toISOString();
  fs.mkdirSync(config.runtimeDir, {recursive:true});
  const runDir = path.join(config.runtimeDir, mode.toLowerCase()+'-'+startedAt.replace(/[:.]/g,'-'));
  fs.mkdirSync(runDir);
  const resultFile = path.join(config.runtimeDir, mode.toLowerCase()+'-latest.json');
  const result = {startedAt,mode,ok:false,sessionId:Number(process.env.PREMIUM_RUNNER_SESSION_ID ?? -1),runDir,model:config.model,reasoningEffort:config.reasoningEffort};
  const env = loadEnvironment(config.repoPath);
  env.CODEX_HOME = config.codexHome;
  // Explicit Node location also works in a noninteractive Windows token.
  const pathKeys = Object.keys(env).filter(key=>/^path$/i.test(key));
  const inheritedPath = pathKeys.length ? env[pathKeys[0]] : '';
  for (const key of pathKeys) delete env[key];
  env.PATH = path.dirname(config.nodePath) + path.delimiter + inheritedPath;
  const stateFile = path.join(config.repoPath,'premium_worker/state/premium_alert_state.json');
  const worker = async (args, name) => {
    const log = path.join(runDir,name);
    const exit = await command(config.nodePath,[path.join(config.repoPath,'premium_worker/worker.mjs'),...args],{cwd:config.repoPath,env,log,timeoutMs:180000});
    if (exit !== 0) throw new Error('Worker '+name+' failed; see bounded local logs.');
    return readJson(log+'.stdout');
  };
  const cli = async (prompt, name, cwd, sandbox) => {
    const log = path.join(runDir,name);
    const exit = await command(config.nodePath,[config.cliJs,'--search','-a','never','exec','--ignore-user-config','--cd',cwd,'--skip-git-repo-check','--sandbox',sandbox,'-m',config.model,'-c',`model_reasoning_effort="${config.reasoningEffort}"`,'-c','forced_login_method="chatgpt"','--json','-o',log+'.final.txt','-'],{cwd,env:cleanEnvironment(env),log,input:prompt,timeoutMs:mode==='Probe'?180000:12_000_000});
    if (exit !== 0) throw new Error('Codex CLI failed. No API billing fallback and no automatic repost. See local logs.');
    return fs.readFileSync(log+'.final.txt','utf8');
  };
  try {
    if (mode === 'Probe') {
      await worker(['status'],'status'); await probeSheets(config,env);
      const answer = await cli('This is an authorized read-only runtime acceptance test using the same process permissions as the scheduled worker. Do not perform any Premium collection, posting, scheduling, editing or deployment. Use live web search to open https://learn.chatgpt.com/docs/auth and verify ChatGPT subscription login is supported for Codex CLI. Use a shell read to read premium_worker/FUNDAMENTAL_EXAMPLES.md and report its first heading. Do not read secrets. Only if BOTH file reading and live web retrieval succeed, finish with the exact marker PREMIUM_PROBE_OK and a short official source link. No other work.', 'cli-probe',config.repoPath,'danger-full-access');
      if (!answer.includes('PREMIUM_PROBE_OK') || !answer.includes('https://learn.chatgpt.com/')) throw new Error('CLI read/search acceptance marker missing.');
      const events = fs.readFileSync(path.join(runDir,'cli-probe.stdout'),'utf8').split(/\r?\n/).filter(Boolean).flatMap(line=>{try{return [JSON.parse(line)];}catch{return [];}});
      const items = events.filter(e=>e.type==='item.completed').map(e=>e.item);
      if (!items.some(i=>i.type==='web_search') || !items.some(i=>i.type==='command_execution' && i.exit_code===0 && /FUNDAMENTAL_EXAMPLES/.test(i.command || ''))) throw new Error('Successful CLI search and file-read tool events are required.');
      result.ok=true; result.sheetsRead=true; result.discordRead=true; result.cli=true;
      return;
    }
    if (mode !== 'Scheduled') throw new Error('Unknown mode');
    for (const automation of config.automationFiles) {
      if (!/^status\s*=\s*"PAUSED"/m.test(fs.readFileSync(automation,'utf8'))) throw new Error('Desktop Premium automation must be paused before CLI production starts.');
    }
    // Wake ten minutes early. A delayed StartWhenAvailable invocation runs immediately.
    const jst = new Date(Date.now()+9*3600000);
    const minute = jst.getUTCHours()*60+jst.getUTCMinutes();
    const target = minute >= 775 && minute < 785 ? 785 : minute >= 926 && minute < 936 ? 936 : minute;
    if (target > minute) await new Promise(r=>setTimeout(r,(target-minute)*60000-jst.getUTCSeconds()*1000));
    const manifestFile = path.join(config.runtimeDir,'active-batch.json');
    let batch;
    if (fs.existsSync(manifestFile)) {
      batch = readJson(manifestFile);
      const state = readJson(stateFile);
      assertOwned(batch,state);
      if (!remainingAlerts(batch,state).length) {
        // Already posted: never call the model again merely to replay logs.
        await worker(['collect','--force'],'reconcile-and-collect');
        const fresh = readJson(path.join(config.repoPath,'premium_worker/out/latest_claim.json'));
        batch = fresh;
      } else {
        throw new Error('An interrupted batch remains. Inspect prior Discord receipts before resuming; no blind repost.');
      }
    } else {
      const state = readJson(stateFile);
      if (Object.keys(state.claims || {}).length) throw new Error('Active claims exist outside this runner. Reconcile before collecting.');
      await worker(['collect','--force'],'collect');
      batch=readJson(path.join(config.repoPath,'premium_worker/out/latest_claim.json'));
    }
    writeJson(manifestFile,batch);
    writeJson(path.join(runDir,'claim.json'),batch);
    assertOwned(batch,readJson(stateFile));
    result.claimed=batch.alerts.length;
    if (!batch.alerts.length) { assertComplete(batch,readJson(stateFile)); result.ok=true; result.posted=0; fs.unlinkSync(manifestFile); return; }
    const prompt = [
      'Run the existing Premium Alert Snapshot Worker with unchanged company-specific research quality. Use $premium-fundamental-snapshot.',
      'Read premium_worker/AUTOMATION_PROMPT.md, premium_worker/FUNDAMENTAL_EXAMPLES.md and the skill references/report_quality.md before research.',
      `The deterministic scheduler ALREADY ran collect --force for this intended 13:05/15:36 JST job. Do not collect again. The immutable claim is ${path.join(runDir,'claim.json')}. Read it and the authoritative premium_worker/state/premium_alert_state.json. Process only those alert IDs; skip every already-posted ID.`,
      `Write reports to ${path.join(config.repoPath,'premium_worker/out/premium_reports.json')}. Follow all seven fields and exact worker contract. Build evidence in batches of 4-6; open each official IR and IRBANK/TDnet list, check at least 45 days and newer live disclosures, read selected disclosure contents. Do not draft from snippets or reuse generic text.`,
      'Preserve the same analysis model and depth. Keep output bounded. Probe the existing cached Python with pypdf for PDFs; do not install runtime dependencies during a live job.',
      'Do not edit gas.txt, GAS triggers, alerts_raw, source code, worker state manually, automation definitions or git branches. Use only the existing worker for state transitions and Discord posting.',
      'Run post --input premium_worker/out/premium_reports.json --dry-run, save verbose output locally, summarize only errors, repair EVERY validator-named report after reading missing disclosures, and repeat until passing. Then real post using the same input. Recheck authoritative state before any retry; a network-ambiguous post requires reconciliation, never blindly send again.',
      'Only if official IR, IRBANK and TDnet-equivalent checks truly cannot provide sufficient verified sources, use the existing fail command with reason "insufficient verified sources" as the established worker contract requires. Never use it to avoid research or validation repair.',
      'Discord fundamental reports are authorized once per alert ID. No separate completion, HTML-ready, test or status Discord message. GitHub Actions already handles HTML generation, deployment and its single deduplicated completion notice; do not dispatch workflows.',
      'Finish only after worker status and self-test pass and claims=0, failed=0, pendingLogEvents=0. If incomplete, state the failure honestly and leave existing receipts intact. Respond in Japanese.'
    ].join('\n\n');
    fs.writeFileSync(path.join(runDir,'prompt.txt'),prompt);
    await cli(prompt,'premium',config.repoPath,'danger-full-access');
    const state=readJson(stateFile); assertComplete(batch,state);
    await worker(['self-test'],'self-test');
    result.posted=batch.alerts.length;result.ok=true;
    fs.renameSync(manifestFile,path.join(runDir,'completed-batch.json'));
  } catch(error) {
    result.error=error.message; process.exitCode=1;
  } finally {
    result.completedAt=new Date().toISOString(); writeJson(resultFile,result); console.log(JSON.stringify(result));
  }
}
if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) await main(process.argv[2],process.argv[3]);
