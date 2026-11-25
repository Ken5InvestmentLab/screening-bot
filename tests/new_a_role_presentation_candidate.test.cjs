const {test}=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {webcrypto}=require('node:crypto');
const src=path.join(__dirname,'../weak-early-beta-gate/scripts/new-a-ui-source/assets');
const context={module:{exports:{}},TextEncoder,URL,require:require('node:module').createRequire(path.join(src,'member-presentation.js'))};vm.runInNewContext(fs.readFileSync(path.join(src,'member-presentation.js'),'utf8'),context);const ui=context.module.exports;
const metrics={net_profit:1200,max_drawdown_pct:-3.25,win_rate_pct:60,trade_count:5};const presets=['defensive','medium','return_priority'].map(preset=>({preset,from:'2026-01-01',through:'2026-11-19',resolved:true,metrics}));
const premiumHome = {
 mode:'home',access:'premium',asOf:'2026-11-19',presets,selected:'medium',
 rows:[{date:'2026-11-19',symbol:'1234',state:'WATCHING'}],chartRows:[],personal:null,
 dashboard:{
  today:[
   {date:'2026-11-19',symbol:'234A',state:'WATCH_STARTED',price:39213},
   {date:'2026-11-19',symbol:'456A',state:'HOLD_STARTED',owner_position:'owner-only'},
   {date:'2026-11-19',symbol:'567A',state:'HOLD_ENDED'},
  ],
  watching:[{date:'2026-11-18',symbol:'345A',state:'WATCHING'}],
 },
};
test('record card sorting keeps every item and uses deterministic kind, code and Japanese name order',()=>{
 const cards=[['MONITOR_RESET','3000','あさ'],['ENTRY_CANDIDATE','2000','かさ'],['ENTRY_CANDIDATE','1000','さけ']]
  .map(([referenceKind,referenceSymbol,referenceName])=>({dataset:{referenceKind,referenceSymbol,referenceName}}));
 const codes=order=>ui.sortReferenceCards(cards,order).map(card=>card.dataset.referenceSymbol);
 a.deepEqual(Array.from(codes('kind')),['1000','2000','3000']);
 a.deepEqual(Array.from(codes('symbol')),['1000','2000','3000']);
 a.deepEqual(Array.from(codes('name')),['3000','2000','1000']);
 a.equal(cards[0].dataset.referenceSymbol,'3000');
});
test('shared dashboard follows the prior owner heading, daily cards, holdings, watch and history order',()=>{
 const html=ui.view({...premiumHome,chartRows:[{date:premiumHome.asOf,equity_yen:9500,holding_count:2}]});
 const order=['データ更新日','ダッシュボード','運用レベル','対象日の動き',
  '234A','456A','567A','現在の仮想保有','現在の監視','345A','>検出履歴<','1234'];
 let previous=-1;
 for(const label of order){
  const index=html.indexOf(label);
  a.ok(index>previous,label);
  previous=index;
 }
 a.match(html,/class="page-heading"/);
 a.doesNotMatch(html,/検出履歴へ|href="#history"/);
 a.match(html,/<section class="panel" id="history" tabindex="-1" aria-labelledby="member-history-heading">/);
 a.doesNotMatch(html,/today-kpis|純損益|最大DD|勝率|日足始値と仮想保有の結果/);
 a.match(html,/class="cloud-stock-grid"/);
 a.match(html,/現在の仮想保有<\/h2><span class="badge">2銘柄/);
 a.match(html,/cloud-transition--watch-start/);
 a.match(html,/cloud-transition--hold-start/);
 a.match(html,/cloud-transition--hold-end/);
 a.match(html,/aria-label="対象日の件数".*監視開始 <b>1件.*仮想保有開始 <b>1件.*仮想保有終了 <b>1件/);
 a.match(html,/<p class="note">データ更新日 <time datetime="2026-11-19">2026-11-19<\/time><\/p>/);
 a.equal((html.match(/データ更新日/g)||[]).length,1);
 a.doesNotMatch(html,/<select|owner-only|39213|決済件数|新A|（A）|運用レベルは|仮想保有の動き|日次資金推移|対象 <time/);
});
test('shared action details use only the verified projected candidate code',()=>{
 const today=[...premiumHome.dashboard.today,{date:premiumHome.asOf,symbol:'987A',state:'ENTRY_CANDIDATE',
  company_name:'DO_NOT_SHOW_COMPANY',price:87431,holding_detail:'DO_NOT_SHOW_POSITION'}];
 const html=ui.view({...premiumHome,dashboard:{...premiumHome.dashboard,today}});
 a.match(html,/<section class="cloud-reference-events"><h3><span class="cloud-transition cloud-transition--entry-candidate">仮想保有開始候補<\/span><\/h3>.*987A<\/span>/);
 a.doesNotMatch(html,/<details[^>]*cloud-reference-events/);
 a.doesNotMatch(html,/DO_NOT_SHOW|87431|日足始値/);
});
test('current monitoring shows eight recent rows and a closed native disclosure for remaining rows',()=>{
 const watching=Array.from({length:11},(_,i)=>({symbol:String(9000+i),date:'2026-11-'+(19-i),state:'WATCHING'}));
 const report=rows=>ui.view({...premiumHome,dashboard:{...premiumHome.dashboard,watching:rows}});
 const section=html=>html.slice(html.indexOf('<section class="panel" aria-labelledby="member-watching-heading">'))
  .split('</section>')[0];
 const watch=section(report(watching));
 a.match(watch,/現在の監視.*11銘柄/);
 a.doesNotMatch(watch,/状況|監視中<\/span>/);
 const disclosure='<details class="cloud-table-details"><summary>残り3銘柄</summary>';
 a.ok(watch.includes(disclosure));
 const [visible, remaining]=watch.split(disclosure);
 a.equal((visible.match(/<tr><td/g)||[]).length,8);
 a.equal((remaining.match(/<tr><td/g)||[]).length,3);
 watching.forEach(({symbol},index)=>a.match(index<8?visible:remaining,new RegExp('>'+symbol+'</td>')));
 a.doesNotMatch(section(report(watching.slice(0,8))),/<details/);
 a.match(section(report([])),/監視中の銘柄なし/);
});
test('dashboard level offers three native radio choices and the current choice matches the holdings count',()=>{
 const changed=presets.map(item=>item.preset==='return_priority'
  ? {...item,metrics:{...metrics,net_profit:5678}} : item);
 const html=ui.view({...premiumHome,presets:changed,selected:'return_priority',
  chartRows:[{date:premiumHome.asOf,equity_yen:9500,holding_count:0}]});
 a.match(html,/<fieldset id="member-preset" class="member-level"><legend>運用レベル<\/legend>/);
 for (const [value,label] of [['defensive','守り'],['medium','中間'],['return_priority','利益優先']]){
  a.ok(html.includes('name="new-a-dashboard-level" value="'+value+'"'+(value==='return_priority'?' checked':'')+
   '><span>'+label+'</span>'),value);
 }
 a.equal((html.match(/type="radio"/g)||[]).length,3);
 a.equal((html.match(/ checked>/g)||[]).length,1);
 a.doesNotMatch(html,/5,678円/);
 a.match(html,/現在の仮想保有<\/h2><span class="badge">0銘柄/);
});
test('dashboard does not substitute stale or unresolved holding counts',()=>{
 const older={date:'2026-11-18',equity_yen:9500,holding_count:7};
 const latest={date:premiumHome.asOf,equity_yen:9500,holding_count:2};
 const unknown=presets.map(item=>item.preset==='medium'?{...item,resolved:false,metrics:null}:item);
 a.match(ui.view({...premiumHome,chartRows:[older]}),/現在の仮想保有<\/h2><span class="badge">未確定/);
 a.match(ui.view({...premiumHome,presets:unknown,chartRows:[latest]}),/現在の仮想保有<\/h2><span class="badge">未確定/);
 a.match(ui.view({...premiumHome,chartRows:[{...latest,equity_yen:null,holding_count:null}]}),/現在の仮想保有<\/h2><span class="badge">未確定/);
 a.match(ui.view({...premiumHome,dashboard:{today:[],watching:[]}}),/仮想保有開始 <b>未確定/);
});
async function renderLevelPage({mode,session,storage,access='premium'}) {
 const body={dataset:{page:mode}}, requested=[];
 let change, focused=false, rendered=Promise.withResolvers();
 const preset={
  addEventListener(type,listener){if(type==='change')change=listener;},
  querySelector(selector){a.equal(selector,'input:checked');return {focus(){focused=true;}};},
 };
 const node=()=>({addEventListener(){},append(){},setAttribute(){}});
 const status=node(),retry=node();
 const out={...node(),replaceChildren(){document.activeElement=body;}};
 const elements={
  'member-state':status,'member-retry':retry,'member-content':out,'member-preset':preset,
  history:node(),'member-history-content':node(),'member-history-open':node(),'member-history-state':node(),
  'member-free-history':{...node(),replaceChildren(){}},
 };
 const document={
  body,activeElement:body,visibilityState:'visible',createElement:node,addEventListener(){},
  getElementById:id=>elements[id],querySelectorAll:()=>[],
 };
 vm.runInNewContext(fs.readFileSync(path.join(src,'member-loader.js'),'utf8'),{
  document,location:{hash:''},AbortController,AbortSignal,TextEncoder,crypto:webcrypto,sessionStorage:storage,
  addEventListener(){},setInterval(){},
  NewAMemberPresentation:{view(value){rendered.resolve(value);return '';},freeHistoryRows:ui.freeHistoryRows},
  async fetch(route){
   const url=new URL(route,'https://fixture.invalid');
   if(url.pathname.endsWith('/session'))return new Response(null,{status:204,headers:{
    'x-cloud-member-session':session,'x-cloud-member-access':access,
   }});
   if(url.pathname.endsWith('/reference.json'))return new Response(null,{status:404});
   if(url.pathname.endsWith('/chart.json'))requested.push(url.searchParams.get('preset'));
   return Response.json({as_of:premiumHome.asOf,generation:'2'.repeat(64),presets,rows:[],page:1,pages:1});
  },
 });
 const initial=await rendered.promise;
 return {
  initial,status,requested,
  async choose(value){
   rendered=Promise.withResolvers();
   const radio={value};
   document.activeElement=radio;
   change({target:radio});
   return {view:await rendered.promise,focused};
  },
 };
}
test('both pages default to 利益優先 and retain the chosen radio for the same verified tab session', {timeout:3000}, async()=>{
 const stored=new Map();
 const storage={getItem:key=>stored.get(key),setItem:(key,value)=>stored.set(key,value)};
 const session='1'.repeat(64);
 const home=await renderLevelPage({mode:'home',session,storage});
 a.equal(home.initial.selected,'return_priority');
 a.match(home.status.textContent,/一部の表示/);
 const changed=await home.choose('defensive');
 a.equal(changed.view.selected,'defensive');
 a.ok(changed.focused);
 a.deepEqual(home.requested,['return_priority','defensive']);
 a.deepEqual([...stored.values()],['defensive']);
 a.ok(![...stored.keys()].some(key=>key.includes(session)));
 const analytics=await renderLevelPage({mode:'analytics',session,storage});
 a.equal(analytics.initial.selected,'defensive');
 const recent=await analytics.choose('medium');
 a.equal(recent.view.selected,'medium');
 a.ok(recent.focused);
 a.deepEqual(analytics.requested,['defensive','medium']);
 const returnHome=await renderLevelPage({mode:'home',session,storage});
 a.equal(returnHome.initial.selected,'medium');

 const anotherUser=await renderLevelPage({mode:'analytics',session:'a'.repeat(64),storage});
 a.equal(anotherUser.initial.selected,'return_priority');
 a.deepEqual(anotherUser.requested,['return_priority']);
 let freeStorageReads=0;
 const freeStorage={getItem(){freeStorageReads++;return 'defensive';}};
 const free=await renderLevelPage({mode:'home',session,storage:freeStorage,access:'free'});
 a.equal(free.initial.access,'free');
 a.equal(freeStorageReads,0);
 a.deepEqual(free.requested,[]);
});
test('the radio remains usable when the browser blocks tab storage', {timeout:3000}, async()=>{
 const storage={getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}};
 const analytics=await renderLevelPage({mode:'analytics',session:'1'.repeat(64),storage});
 a.equal(analytics.initial.selected,'return_priority');
 const chosen=await analytics.choose('defensive');
 a.equal(chosen.view.selected,'defensive');
 a.ok(chosen.focused);
});
test('Premium Analytics annualizes only the selected resolved projection over its actual calendar days',()=>{
 const from='2025-01-02',through='2026-01-02';
 const chartRows=[{date:from,equity_yen:10_000_000},{date:through,equity_yen:11_400_000}];
 const selected={...presets[0],from,through,metrics:{...metrics,net_profit:1_400_000}};
 const pages={mode:'analytics',access:'premium',asOf:through,presets:[selected,...presets.slice(1)],
  selected:selected.preset,rows:[],chartRows,personal:metrics};
 const value=label=>new RegExp('年率換算損益率</span><b>'+label+'</b>');
 const html=ui.view(pages);
 a.match(html,value('14\\.01%'));
 a.match(html,/<h2>日次資金推移<\/h2><div class="research-chart"/);
 const operatingLevel=html.match(/<fieldset id="member-preset"[\s\S]*?<\/fieldset>/)?.[0];
 const home=ui.view({...premiumHome,selected:selected.preset});
 a.ok(operatingLevel);
 a.ok(home.includes(operatingLevel));
 a.doesNotMatch(html,/見方を変える|<select/);
 a.doesNotMatch(html,/運用レベルの比較/);
 a.equal((html.match(/年率換算損益率/g)||[]).length,1);
 a.match(html,/累積損益率を経過年数で割った値/);
 a.doesNotMatch(ui.view(premiumHome),/年率換算損益率/);

 const loss={...selected,metrics:{...selected.metrics,net_profit:-1_000_000}};
 a.match(ui.view({...pages,presets:[loss],chartRows:[chartRows[0],{...chartRows[1],equity_yen:9_000_000}]}),value('-10\\.01%'));
 const cases=[
  {chartRows:[]},
  {chartRows:[chartRows[0]]},
  {chartRows:[{...chartRows[0],equity_yen:0},chartRows[1]]},
  {chartRows:[chartRows[0],{...chartRows[1],equity_yen:null}]},
  {chartRows:[chartRows[0],{...chartRows[1],equity_yen:11_500_000}]},
  {chartRows:[chartRows[0],{...chartRows[1],date:'2026-01-01'}]},
  {presets:[{...selected,resolved:false,metrics:null}]},
  {presets:[{...selected,from:'2025-02-29'}]},
 ];
 for(const patch of cases)a.match(ui.view({...pages,...patch}),value('未確定'));
});
test('analytics offers the three controls without duplicating the preset comparisons',()=>{
 const html=ui.view({mode:'analytics',access:'premium',asOf:'2026-11-19',presets,selected:'defensive',rows:[],chartRows:[],personal:null});
 for(const text of ['守り','中間','利益優先','準備中'])a.ok(html.includes(text));
 a.doesNotMatch(html,/運用レベルの比較/);
});
test('shared reference document leaves only an authorized insertion slot and retains Premium history',()=>{
 const home=ui.view({...premiumHome,reference:true});
 a.match(home,/<h1>ダッシュボード<\/h1>.*id="member-preset".*id="member-reference-content".*<h2 id="member-history-heading">検出履歴/);
 a.doesNotMatch(home,/検出履歴へ|日足始値と仮想保有の結果|39213|owner-only/);
 const analytics=ui.view({...premiumHome,mode:'analytics',reference:true});
 a.match(analytics,/<h1>アナリティクス<\/h1>.*id="member-preset".*id="member-reference-content"/);
 a.doesNotMatch(analytics,/member-history-heading|運用レベルの比較/);
 a.doesNotMatch(ui.view({...premiumHome,access:'free',reference:true}),/member-reference-content|member-preset/);
});
test('reference envelope requires the verified date, generation and variant selection',()=>{
 const item='dashboard.return_priority';
 const payload={as_of:premiumHome.asOf,generation:'a'.repeat(64),markup:'<section>合成データ</section>'};
 a.equal(ui.referencePayload(payload,item),true);
 a.equal(ui.referencePayload({...payload,item},item),true);
 for (const invalid of [null,{...payload,item:'dashboard.medium'},{...payload,markup:''},{...payload,generation:'b'},
   {...payload,as_of:'2026-02-31'},{...payload,owner:'private'},{...payload,markup:'あ'.repeat(700000)}]){
  a.equal(ui.referencePayload(invalid,item),false);
 }
});
test('reference history restores the old columns and selected trial details using only confirmed row tokens',()=>{
 const asOf='2026-11-19',date='2026-11-10',entry=['2026-11-12',100,100,10000];
 const visible={date,symbol:'234A',has_fundamental:true};
 const other={date,symbol:'456A',has_fundamental:false};
 const row={date,symbol:visible.symbol,companyName:'<合成>',chartAllowed:true,signalClose:95,
  d5:['2026-11-17',105,true],d6:null,item:'2.2026-11-10.234A',
  levels:[['PRICE_CAP',false,null,null],['FILLED',true,entry,null],['FILLED',true,entry,['2026-11-19',120,2000,.2]]]};
 const {item,...unlinked}=row;
 const held={...unlinked,symbol:other.symbol,companyName:null,signalClose:null,chartAllowed:false};
 const decode=(rows,page=2)=>ui.referenceHistory(JSON.stringify({page,rows}),2,asOf,[visible,other]);
 const referenceHistoryRows=decode([row,held]);
 a.equal(referenceHistoryRows.length,2);
 const render=selected=>ui.view({...premiumHome,asOf,selected,reference:true,referenceHistoryRows});
 const html=render('return_priority');
 for(const text of ['検出日','銘柄','試算条件','状況','試算開始日・始値','5営業日後 終値','6営業日後 始値','試算損益',
   '価格のみ参照','検出日終値 95円','仮想決済済','寄付 100円','2,000円','決済 2026-11-19','チャート保留']){
  a.ok(html.includes(text),text);
 }
 a.match(html,/colspan="8" class="history-record"/);
 a.match(html,/data-member-history-details aria-expanded="false">詳細を見る/);
 for (const control of ['証券コード・銘柄名で検索','開始日','終了日','新しい順','古い順','証券コード順','検索をクリア']) {
  a.ok(html.includes(control),control);
 }
 a.match(html,/data-member-fundamental="2\.2026-11-10\.234A">ファンダ/);
 a.match(html,/symbol=TSE%3A234A/);
 a.match(html,/&lt;合成&gt;/);
 a.doesNotMatch(html,/<合成>|symbol=TSE%3A456A|検出履歴へ|運用レベルの比較/);
 a.match(render('medium'),/仮想保有中/);
 a.doesNotMatch(render('medium'),/決済 2026-11-19/);
 a.match(render('defensive'),/株価上限/);
 a.equal(decode([row,held],1),null);
 a.equal(decode([held,row]),null);
 for(const invalid of [{...row,item:'1.2026-11-10.234A'},{...row,chartAllowed:false},{...row,d5:['2026-11-20',22,true]},
   {...row,levels:[row.levels[0],row.levels[1],['EXPIRED',true,null,['2026-11-19',120,2000,.2]]]},
   {...row,owner_preference:10}]){
  a.equal(decode([invalid,held]),null);
 }
});
test('history index lookup supports legacy code/name, date range and sort while rejecting malformed indexes',()=>{
 const names=['岡田','合成システム'];
 const index={names,rows:[['2026-11-19','4444',1],['2026-11-18','234A',1],['2026-11-16','3210',0],['2026-11-15','1001',null]]};
 const asOf='2026-11-19';
 const validated=ui.referenceHistoryIndex(JSON.stringify(index),asOf,1);
 a.equal(JSON.stringify(validated),JSON.stringify(index));
 const defaults={symbol:'',from:'',through:'',order:'newest'};
 a.deepEqual(Array.from(ui.matchingHistory(validated,{...defaults,symbol:'　２３４ａ　'})),[1]);
 a.deepEqual(Array.from(ui.matchingHistory(validated,{...defaults,symbol:'合成',from:'2026-11-18',through:'2026-11-18'})),[1]);
 a.deepEqual(Array.from(ui.matchingHistory(validated,{...defaults,order:'oldest'})),[3,2,1,0]);
 a.deepEqual(Array.from(ui.matchingHistory(validated,{...defaults,order:'symbol'})),[3,1,2,0]);
 for (const invalid of [{...index,rows:[index.rows[0],index.rows[0]]},{...index,rows:[['2026-11-20','234A',0]]},
   {...index,rows:[['2026-11-18','234A',-1]]},{...index,rows:[['2026-11-18','234A',2]]}]){
  a.equal(ui.referenceHistoryIndex(JSON.stringify(invalid),asOf,1),null);
 }
});
test('free dashboard shares the Premium section order with data-free locked rows',()=>{
 const rows=[
  {date:'2026-11-18',symbol:'1234',state:'HOLD_ENDED'},
  {date:'2026-11-18',symbol:'4321',state:'EXPIRED'},
  {date:'2026-11-19',symbol:'999Z',state:'HOLD_STARTED',companyName:'PRIVATE_NAME'},
 ];
 const privateRow={symbol:'567Z',companyName:'PRIVATE_NAME',price:987654};
 const dashboard={today:[privateRow],watching:[privateRow],holding:[privateRow]};
 const shell={...premiumHome,access:'free',rows,personal:metrics};
 const html=ui.view({...shell,dashboard});
 a.equal(html,ui.view({...shell,dashboard:undefined}));
 for(const value of ['<h1>ダッシュボード</h1>','member-free-history','仮想保有が終了した銘柄','1234','仮想保有終了'])a.ok(html.includes(value),value);
 a.doesNotMatch(html,/4321|999Z|567Z|PRIVATE_NAME|987654|member-preset|日次資金推移/);
 a.doesNotMatch(html,/today-summary|today-kpis|運用レベル|data-symbol|data-member-fundamental|class="badge"|member-locked-mask/);

 const headings=markup=>Array.from(markup.matchAll(/<h2 [^>]+>([^<]+)<\/h2>/g),entry=>entry[1]);
 const premium=ui.view(premiumHome);
 a.deepEqual(headings(html),['対象日の動き','現在の仮想保有','現在の監視','検出履歴']);
 a.deepEqual(headings(html),headings(premium));
 const rowsWithUpgrade=Array.from(html.matchAll(/<details class="member-locked-row">([\s\S]*?)<\/details>/g));
 a.equal(rowsWithUpgrade.length,3);
 for(const [index,[,body]] of rowsWithUpgrade.entries()){
  a.ok(body.includes('<summary aria-label="' + headings(html)[index] + 'の詳細を見る">'));
  a.match(body,/<span class="member-locked-message">銘柄・詳細はPremium限定<\/span><span class="member-locked-action">詳細を見る<\/span><\/summary>/);
  a.match(body,/<a class="member-purchase" href="\/purchase">Premiumアクセス権を購入する<\/a><\/div>$/);
 }
 a.equal((html.match(/href="\/purchase"/g)||[]).length,rowsWithUpgrade.length);
 a.doesNotMatch(premium,/member-locked-row/);
 a.match(ui.freeHome(),/member-locked-row/);
 a.match(ui.freeHome(),/<div id="member-free-history"><\/div>/);
 a.match(ui.view({mode:'home',access:'free',rows:[]}),/このページに仮想保有終了銘柄はありません。/);
 const analytics=ui.view({...premiumHome,mode:'analytics',access:'free',reference:true,personal:metrics});
 a.match(analytics,/<h1>アナリティクス<\/h1>.*id="member-preset".*id="member-reference-content"/);
 a.doesNotMatch(analytics,/href="\/purchase"|検出履歴|試算結果を準備中|TODAY_ONLY|234A/);
});
test('only verified Premium history rows have the exact page, date and symbol analysis button',()=>{
 const match={date:'2026-11-18',symbol:'234A',state:'EXPIRED',has_fundamental:true};
 const rows=[match,{...match,symbol:'345A',has_fundamental:false},
   {...match,symbol:'456A',has_fundamental:'true'},{...match,symbol:'567A',date:'2026-11-31'}];
 const html=ui.view({...premiumHome,rows,historyPage:42});
 a.equal((html.match(/data-member-fundamental=/g)||[]).length,1);
 a.match(html,/class="fundamental-toggle cloud-stock-action"[^>]*aria-haspopup="dialog"/);
 a.match(html,/data-member-fundamental="42\.2026-11-18\.234A">ファンダ<\/button>/);
 a.doesNotMatch(ui.view({...premiumHome,rows}),/>ファンダ<\/button>/);
 a.doesNotMatch(ui.view({...premiumHome,rows,access:'free',historyPage:42}),/ファンダ|has_fundamental|data-member-fundamental/);
});
test('verified report fields keep the existing dialog copy, escape content and reject mismatches',()=>{
 const expected={asOf:'2026-11-19',date:'2026-11-18',symbol:'234A',generation:'a'.repeat(64)};
 const labels=['材料インパクト','事業概要','足元材料','ファンダ要点','注意点','開示リンク','Sources'];
 const report={as_of:expected.asOf,date:expected.date,symbol:expected.symbol,generation:expected.generation,
  company_name:'<銘柄名>',analysis_cutoff:'2026-11-18T16:15:00+09:00',
  fields:labels.map(label=>({label,text:'確定\n<script>alert(1)</script> https://example.invalid/'})),
 };
 const html=ui.fundamentalMarkup(report,expected);
 a.match(html,/ファンダ分析を閉じる/);
 a.match(html,/<dl><dt>材料インパクト<\/dt><dd>/);
 a.match(html,/&lt;銘柄名&gt;\(234A\)/);
 a.match(html,/検出日 2026-11-18/);
 a.match(html,/分析時点 2026-11-18T16:15:00\+09:00/);
 a.match(html,/確定<br>&lt;script&gt;/);
 a.doesNotMatch(html,/<script|href=/);
 for(const invalid of [{...report,date:'2026-11-17'},{...report,symbol:'345A'},{...report,generation:'b'.repeat(64)},
   {...report,draft:true},{...report,fields:[...report.fields].reverse()},{...report,analysis_cutoff:'2026-11-18T16:15:00'}]){
  a.equal(ui.fundamentalMarkup(invalid,expected),null);
 }
});
test('the member popup uses the old report palette only for a leading verified impact category',()=>{
 const expected={asOf:'2026-11-19',date:'2026-11-18',symbol:'234A',generation:'a'.repeat(64)};
 const labels=['材料インパクト','事業概要','足元材料','ファンダ要点','注意点','開示リンク','Sources'];
 const cases=[
  ['  ポジティブ材料：確定事項',' impact-positive'],
  ['ネガティブ材料：確認結果',' impact-negative'],
  ['様子見：要確認',' impact-watch'],
  ['混在/要確認：確定事項あり',' impact-watch'],
  ['分類未記載。ポジティブ材料を後日確認。',''],
  ['ポジティブ材料を確認中',''],
 ];
 for (const [impact, palette] of cases) {
  const fields=labels.map((label,index)=>({label,text:index===0?impact:'様子見の補足'}));
  const report={as_of:expected.asOf,date:expected.date,symbol:expected.symbol,generation:expected.generation,
   company_name:null,analysis_cutoff:'2026-11-18T16:15:00+09:00',fields};
  const html=ui.fundamentalMarkup(report,expected);
  a.ok(html.includes('class="discord-embed'+palette+'"'));
  a.ok(html.includes(impact));
  a.match(html,/<dt>注意点<\/dt><dd>様子見の補足<\/dd>/);
 }
});
test('verified disclosure and Sources fields render only safe titled HTTPS links',()=>{
 const expected={asOf:'2026-11-19',date:'2026-11-18',symbol:'234A',generation:'a'.repeat(64)};
 const fields=['材料インパクト','事業概要','足元材料','ファンダ要点','注意点','開示リンク','Sources']
  .map(label=>({label,text:'確認済みの本文'}));
 fields[1].text='[事業概要内の文字列](https://body.example/)';
 fields[3].text='判断の根拠\n・[決算解説 [資料]](https://fundamental.example/report)';
 fields[5].text='・[2026-11-18 決算資料 \\[別紙\\](15:00)](https://disclosure.example/file?a=1&b=2)\n'
  +'[危険](javascript:alert%281%29)\n[HTTP](http://insecure.example/)\n[無題](https://invalid [url])';
 fields[6].text='・[公式IR・開示一覧 <IR>](https://source.example/)\n'
  +'[認証情報付き](https://user:pw@source.example/)\n[https://bare.example/](https://bare.example/)\n'
  +'https://unlabeled.example/\n<a href="https://markup.example/">未確認</a>';
 const html=ui.fundamentalMarkup({as_of:expected.asOf,date:expected.date,symbol:expected.symbol,
  generation:expected.generation,company_name:null,analysis_cutoff:'2026-11-18T16:15:00+09:00',fields},expected);
 a.equal((html.match(/<a href=/g)||[]).length,3);
 a.match(html,/・<a href="https:\/\/disclosure\.example\/file\?a=1&amp;b=2" target="_blank" rel="noopener noreferrer">2026-11-18 決算資料 \[別紙\]\(15:00\)<\/a>/);
 a.match(html,/・<a href="https:\/\/source\.example\/" target="_blank" rel="noopener noreferrer">公式IR・開示一覧 &lt;IR&gt;<\/a>/);
 a.match(html,/<dt>ファンダ要点<\/dt><dd>判断の根拠<br>・<a href="https:\/\/fundamental\.example\/report" [^>]+>決算解説 \[資料\]<\/a>/);
 a.match(html,/\[事業概要内の文字列\]\(https:\/\/body\.example\/\)/);
 a.doesNotMatch(html,/href="(?:javascript|http:|https:\/\/(?:invalid|user:|bare\.example|unlabeled\.example|body\.example))/);
 a.match(html,/&lt;a href=&quot;https:\/\/markup\.example\/&quot;&gt;/);
});
test('chart gaps never joined and values not normalized to fake zero',()=>{const html=ui.chart([{date:'2026-11-17',equity_yen:100},{date:'2026-11-18',equity_yen:null},{date:'2026-11-19',equity_yen:120}]);a.equal((html.match(/<polyline/g)||[]).length,2);a.ok(!/NaN|Infinity/.test(html));a.ok(ui.chart([{date:'2026-11-19',equity_yen:null}]).includes('未確定'));});
test('untrusted labels escaped and unresolved metrics never shown',()=>{a.ok(!ui.history([{date:'<script>',symbol:'<img>',state:'<script>'}]).includes('<script>'));a.ok(ui.metrics(null).includes('未確定'));a.ok(!ui.metrics(null).includes('0円'));});
test('member transport never loads owner inputs, worker or notifications',()=>{const js=fs.readFileSync(path.join(src,'member-loader.js'),'utf8');a.doesNotMatch(js,/new-a-finite|input\/manifest|new Worker|notification-preferences/);});
