import test from 'node:test';
import assert from 'node:assert/strict';
import {cleanEnvironment,remainingAlerts,assertOwned,assertComplete} from './premium-runner.mjs';
const batch={claimId:'batch-a',alerts:[{alertId:'a'},{alertId:'b'}]};
test('subscription execution cannot inherit either API billing key',()=>{
  assert.deepEqual(cleanEnvironment({OPENAI_API_KEY:'secret',codex_api_key:'secret',PATH:'node',CODEX_HOME:'auth'}),{PATH:'node',CODEX_HOME:'auth'});
});
test('posted IDs are excluded even when a saved batch still contains them',()=>{
  const state={posted:{a:{}},claims:{b:{claimId:'batch-a'}}};
  assert.deepEqual(remainingAlerts(batch,state),[{alertId:'b'}]);
  assert.doesNotThrow(()=>assertOwned(batch,state));
});
test('foreign or lost claims fail closed',()=>{
  assert.throws(()=>assertOwned(batch,{posted:{a:{}},claims:{b:{claimId:'other'}}}),/Foreign/);
  assert.throws(()=>assertOwned(batch,{posted:{a:{}},claims:{}}),/lost/);
  assert.throws(()=>assertOwned(batch,{posted:{a:{},b:{}},claims:{c:{claimId:'batch-a'}}}),/Foreign/);
});
test('completion requires every receipt and no pending log events or failed claims',()=>{
  const clean={posted:{a:{},b:{}},claims:{},failed:{},pendingLogEvents:[]};
  assert.doesNotThrow(()=>assertComplete(batch,clean));
  for(const state of [{...clean,posted:{a:{}}},{...clean,pendingLogEvents:[{}]},{...clean,failed:{b:{}}},{...clean,claims:{c:{}}}]) assert.throws(()=>assertComplete(batch,state),/incomplete/);
});
