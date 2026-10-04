const test=require('node:test'),assert=require('node:assert/strict');
const calc=require('../reports/weak-early-beta-scenarios.js');
const prefs=require('../reports/weak-early-beta-interactions.js');
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);
const dataset={date:'2026-09-01',symbol:'A001',selectors:'silence dive',signalActualClose:'1000',signalPriceVerified:'true',
  entryDate:'2026-09-02',entryCost:'100000',entryOpen:'1000',entryShares:'100',d5Date:'2026-09-08',
  d5Proceeds:'101000',d5Return:'.01',d5Close:'1010',d5ExitShares:'100',d6Date:'2026-09-09',
  d6EntryDate:'2026-09-02',d6EntryCost:'100000',d6EntryOpen:'1000',d6EntryShares:'100',
  d6Proceeds:'100500',d6Return:'.005',d6Open:'502.5',d6ExitShares:'200',reference:'false'};
const pref={priceCapYen:1000,exitKey:'d5_close',baseShares:100,costPercent:0};
const payload={generated:'2026-10-04',scopes:{all:{label:'すべて',years:null},'2026':{label:'2026年',years:[2026]}},modeNames:{},page:'analytics'};
test('a quarter percent is charged to both notionals, then shares scale all cash flows',()=>{
  const t=calc.trade(dataset,{...pref,baseShares:300,costPercent:.25});
  close(t.cost,300750);close(t.proceeds,302242.5);close(t.pl,1492.5);close(t.returnPct,1492.5/300750*100);
  close(t.entryFee,750);close(t.exitFee,757.5);assert.equal(t.exitShares,300);
});
test('D6 uses its own held-share receipt including splits and consolidations',()=>{
  const split=calc.trade(dataset,{...pref,exitKey:'d6_open',baseShares:300});
  close(split.pl,1500);assert.equal(split.exitShares,600);
  const consolidated=calc.trade({...dataset,d6Open:'2010',d6ExitShares:'50'},{...pref,exitKey:'d6_open',baseShares:300});
  close(consolidated.pl,1500);assert.equal(consolidated.exitShares,150);
  assert.equal(dataset.entryCost,'100000');assert.equal(dataset.d5ExitShares,'100');
});
test('cost can change winners and all dependent statistics',()=>{
  const before=calc.calculate([dataset],pref,{yearScope:'all'},payload),after=calc.calculate([dataset],{...pref,costPercent:1},{yearScope:'all'},payload);
  assert.equal(before.strategies.unique.win_pct,100);assert.equal(after.strategies.unique.win_pct,0);
  close(after.strategies.unique.cash_pl_100_yen,-1010);close(after.strategies.stacked.cash_pl_100_yen,-2020);
  close(after.strategies.unique.required_capital_yen,101000);assert.ok(after.strategies.unique.average_loss_pct<0);
});
test('pending prices and unsupported acquisition quantities remain unavailable',()=>{
  const t=calc.trade({...dataset,d5Proceeds:'',d5Return:''},pref);assert.equal(t.pl,null);assert.equal(t.returnPct,null);assert.equal(t.cost,100000);
  const missing=calc.trade({...dataset,entryCost:'',entryOpen:'',d5Return:'',d5Proceeds:''},pref);assert.equal(missing.cost,null);assert.equal(missing.pl,null);
});
test('same-session purchases require funding before any sale receipts',()=>{
  const trades=[{entry:'2026-01-05',exit:'2026-01-06',symbol:'A',cost:100,proceeds:200},
    {entry:'2026-01-06',exit:'2026-01-07',symbol:'B',cost:150,proceeds:150}];
  const r=calc.risk(trades);assert.equal(r.capital,250);assert.equal(r.initialCash,250);assert.equal(r.maxLots,2);assert.equal(r.maxSymbols,2);
});
test('inclusive actual-close filtering, references and empty overlap bins stay consistent',()=>{
  const above={...dataset,symbol:'B001',signalActualClose:'1000.01'},unknown={...dataset,symbol:'B002',signalPriceVerified:'false'},reference={...dataset,symbol:'REF1',reference:'true'};
  const result=calc.calculate([dataset,above,unknown,reference],pref,{yearScope:'all'},payload);
  assert.equal(result.trades.length,2);assert.equal(result.referenceCount,1);assert.equal(result.strategies.unique.n,1);
  assert.equal(result.strategies.stacked.n,2);assert.deepEqual(result.overlap.map(r=>r.count),[1,2,3,4,5]);
  assert.equal(result.overlap[2].n,0);assert.equal(result.overlap[2].mean_pct,null);
  const csv=calc.csvMetrics(result,pref,{allocation:'all'});assert.equal(csv[0]['結果ありの取引数'],1);assert.equal(csv[1]['結果ありの取引数'],2);
  assert.ok(!/source_sha256|provenance|observed_at|selector_id|symbol|entry_cost_yen/.test(JSON.stringify(csv)));
});
test('public validation is identical for saved and typed share/cost choices',()=>{
  for(const baseShares of [0,99,101,150,1000001,Infinity,true,''])assert.throws(()=>prefs.normalize({...pref,baseShares}));
  for(const costPercent of [-1,10.01,.001,Infinity,true,''])assert.throws(()=>prefs.normalize({...pref,costPercent}));
  assert.deepEqual(prefs.normalize({...pref,baseShares:'300',costPercent:'0.25'}),{...pref,baseShares:300,costPercent:.25});
});
