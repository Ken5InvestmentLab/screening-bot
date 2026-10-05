import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {reportsMatchClaim, reusableClaimReport, stampAnalysisStart} from './weak-early-beta-fundamental-runner.mjs';

function fixture(fn) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'weak-early-beta-analysis-start-'));
  try { return fn(root); }
  finally {
    const resolved=path.resolve(root);
    if(!resolved.startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(resolved).startsWith('weak-early-beta-analysis-start-'))throw Error('unexpected fixture path');
    fs.rmSync(resolved,{recursive:true,force:true});
  }
}
const alert={alertId:'weak-early-beta:2026-10-05:336A',signalDate:'2026-10-05',receivedAt:'2026-10-05T16:15:00+09:00',symbolCode:'336A'};

test('fundamental analysis start is separate from detection and can be on a later day',()=>fixture(root=>{
  const statePath=path.join(root,'state.json');
  const claim={claimId:'same-owner',alerts:[{...alert}]};
  fs.writeFileSync(statePath,JSON.stringify({claims:{[alert.alertId]:{claimId:claim.claimId,...alert}},completed:{},posted:{}}));
  const original=structuredClone(claim);
  for(const start of ['2026-10-05T08:00:00.123Z','2026-10-05T09:00:00.456Z','2026-10-06T00:00:00.789Z']){
    const stamped=stampAnalysisStart(statePath,claim,start);
    assert.equal(stamped.analysisStartedAt,start);
    assert.equal(stamped.alerts[0].analysisCutoff,start);
    assert.equal(stamped.alerts[0].receivedAt,alert.receivedAt);
    assert.equal(stamped.alerts[0].signalDate,alert.signalDate);
    const state=JSON.parse(fs.readFileSync(statePath,'utf8'));
    assert.equal(state.claims[alert.alertId].analysisCutoff,start);
    assert.equal(state.claims[alert.alertId].receivedAt,alert.receivedAt);
    assert.equal(state.claims[alert.alertId].claimId,claim.claimId);
    assert.deepEqual(state.posted,{});
  }
  assert.deepEqual(claim,original);
}));

test('analysis stamp verifies all ownership before changing any claim',()=>fixture(root=>{
  const statePath=path.join(root,'state.json');
  const claim={claimId:'same-owner',alerts:[{...alert},{...alert,alertId:'other'}]};
  const original=JSON.stringify({claims:{[alert.alertId]:{claimId:claim.claimId},other:{claimId:'different-owner'}}});
  fs.writeFileSync(statePath,original);
  assert.throws(()=>stampAnalysisStart(statePath,claim,'2026-10-05T09:00:00.000Z'),/ownership mismatch/);
  assert.equal(fs.readFileSync(statePath,'utf8'),original);
  assert.throws(()=>stampAnalysisStart(statePath,claim,'invalid'),/invalid analysis start/);
  assert.equal(fs.readFileSync(statePath,'utf8'),original);
}));

test('report reuse requires exact identity, signal date and analysis start timestamp',()=>fixture(root=>{
  const reportsPath=path.join(root,'reports.json');
  const analysisCutoff='2026-10-05T09:00:00.123Z';
  const claim={claimId:'owner',alerts:[{...alert,analysisCutoff}]};
  const report={alertId:alert.alertId,signalDate:alert.signalDate,analysisCutoff};
  fs.writeFileSync(reportsPath,JSON.stringify({reports:[report]}));
  assert.equal(reportsMatchClaim(reportsPath,claim),true);
  for(const changed of [{...report,analysisCutoff:alert.receivedAt},{...report,analysisCutoff:'2026-10-05T09:00:00.124Z'},{...report,signalDate:'2026-10-06'},{...report,alertId:'other'}]){
    fs.writeFileSync(reportsPath,JSON.stringify({reports:[changed]}));
    assert.equal(reportsMatchClaim(reportsPath,claim),false);
  }
  fs.writeFileSync(reportsPath,JSON.stringify({reports:[report,report]}));
  assert.equal(reportsMatchClaim(reportsPath,claim),false);
}));

test('an import-only retry preserves a validated legacy cutoff but an unsaved legacy candidate is refreshed',()=>fixture(root=>{
  const reportsPath=path.join(root,'reports.json');
  const claim={claimId:'owner',alerts:[{...alert}]};
  fs.writeFileSync(reportsPath,JSON.stringify({reports:[{alertId:alert.alertId,signalDate:alert.signalDate,analysisCutoff:alert.receivedAt}]}));
  assert.equal(reusableClaimReport(reportsPath,claim,{completed:{}}),false);
  const saved={completed:{[alert.alertId]:{delivery:'html',analysisCutoff:alert.receivedAt}}};
  assert.equal(reusableClaimReport(reportsPath,claim,saved),true);
  saved.completed[alert.alertId].analysisCutoff='2026-10-05T09:00:00.000Z';
  assert.equal(reusableClaimReport(reportsPath,claim,saved),false);
}));
