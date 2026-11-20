const {test}=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=path.join(__dirname,'../weak-early-beta-gate/scripts/new-a-ui-source/assets');
const context={module:{exports:{}},TextEncoder,URL};vm.runInNewContext(fs.readFileSync(path.join(src,'member-presentation.js'),'utf8'),context);const ui=context.module.exports;
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
test('Premium restores the vertical dashboard panels with the original top KPI layout',()=>{
 const html=ui.view({...premiumHome,chartRows:[{date:premiumHome.asOf,equity_yen:9500,holding_count:2}]});
 const order=['ダッシュボード','運用レベル','純損益','最大DD','勝率','保有件数','対象日の動き',
  '234A','456A','567A','現在の監視','345A','検出履歴','1234'];
 let previous=-1;
 for(const label of order){
  const index=html.indexOf(label);
  a.ok(index>previous,label);
  previous=index;
 }
 a.match(html,/class="kpis today-kpis"/);
 a.match(html,/class="cloud-stock-grid"/);
 a.match(html,/保有件数<\/small><b>2件/);
 a.match(html,/cloud-transition--watch-start/);
 a.match(html,/cloud-transition--hold-start/);
 a.match(html,/cloud-transition--hold-end/);
 a.match(html,/aria-label="対象日の件数".*監視開始 <b>1件.*仮想保有開始 <b>1件.*仮想保有終了 <b>1件/);
 a.doesNotMatch(html,/<select|owner-only|39213|決済件数|新A|（A）|運用レベルは|仮想保有の動き/);
});
test('dashboard level offers three native radio choices and the current choice matches the selected KPI',()=>{
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
 a.match(html,/純損益<\/small><b>5,678円/);
 a.match(html,/保有件数<\/small><b>0件/);
});
test('dashboard does not substitute stale or unresolved holding counts',()=>{
 const older={date:'2026-11-18',equity_yen:9500,holding_count:7};
 const latest={date:premiumHome.asOf,equity_yen:9500,holding_count:2};
 const unknown=presets.map(item=>item.preset==='medium'?{...item,resolved:false,metrics:null}:item);
 a.match(ui.view({...premiumHome,chartRows:[older]}),/保有件数<\/small><b>未確定/);
 a.match(ui.view({...premiumHome,presets:unknown,chartRows:[latest]}),/保有件数<\/small><b>未確定/);
 a.match(ui.view({...premiumHome,chartRows:[{...latest,equity_yen:null,holding_count:null}]}),/保有件数<\/small><b>未確定/);
 a.match(ui.view({...premiumHome,dashboard:{today:[],watching:[]}}),/仮想保有開始 <b>未確定/);
});
test('changing dashboard radio reloads the selected chart and restores keyboard focus',async()=>{
 const body={dataset:{page:'home'}}, requested=[], rendered=[];
 let change, focused=false;
 const preset={
  addEventListener(type,listener){if(type==='change')change=listener;},
  querySelector(selector){a.equal(selector,'input:checked');return {focus(){focused=true;}};},
 };
 const node=()=>({addEventListener(){},append(){},setAttribute(){}});
 const status=node(),retry=node();
 const out={...node(),replaceChildren(){document.activeElement=body;}};
 const elements={'member-state':status,'member-retry':retry,'member-content':out,'member-preset':preset};
 const document={
  body,activeElement:body,visibilityState:'visible',createElement:node,addEventListener(){},
  getElementById:id=>elements[id],querySelectorAll:()=>[],
 };
 vm.runInNewContext(fs.readFileSync(path.join(src,'member-loader.js'),'utf8'),{
  document,AbortController,AbortSignal,addEventListener(){},setInterval(){},
  NewAMemberPresentation:{view(value){rendered.push(value);return '';}},
  async fetch(route){
   const url=new URL(route,'https://fixture.invalid');
   if(url.pathname.endsWith('/session'))return new Response(null,{status:204,headers:{
    'x-cloud-member-session':'1'.repeat(64),'x-cloud-member-access':'premium',
   }});
   if(url.pathname.endsWith('/chart.json'))requested.push(url.searchParams.get('preset'));
   return Response.json({as_of:premiumHome.asOf,generation:'2'.repeat(64),presets,rows:[],pages:1});
  },
 });
 const flush=()=>new Promise(resolve=>setImmediate(resolve));
 await flush();
 a.equal(rendered[0].selected,'medium');
 const radio={value:'defensive'};
 document.activeElement=radio;
 change({target:radio});
 await flush();
 a.deepEqual(requested,['medium','defensive']);
 a.equal(rendered[1].selected,'defensive');
 a.ok(focused);
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
test('analytics compares all 3 presets; missing personal result not fabricated',()=>{const html=ui.view({mode:'analytics',access:'premium',asOf:'2026-11-19',presets,selected:'defensive',rows:[],chartRows:[],personal:null});for(const s of ['守り','中間','利益優先','準備中','以前の結果では代用しません'])a.ok(html.includes(s));});
test('free presentation shows server-provided closed history and one existing purchase action',()=>{
 const html=ui.view({mode:'home',access:'free',asOf:'2026-11-19',presets,selected:'medium',rows:[{date:'2026-11-18',symbol:'1234',state:'HOLD_ENDED'}],chartRows:[],personal:metrics,dashboard:{today:[{symbol:'TODAY_ONLY'}],watching:[{symbol:'WATCH_ONLY'}]}});
 for(const value of ['終了済みの検出履歴','1234','仮想保有終了','今日の動きと監視状況','href="/purchase"'])a.ok(html.includes(value),value);
 a.doesNotMatch(html,/TODAY_ONLY|WATCH_ONLY|member-preset|日次資金推移|対象日 2026-11-19/);
 a.doesNotMatch(html,/today-summary|today-kpis|運用レベル/);
 a.equal((html.match(/href="\/purchase"/g)||[]).length,1);
 for(const mode of ['analytics','settings'])a.match(ui.view({mode,access:'free'}),/Premium会員限定.*href="\/purchase"/);
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
  .map(label=>({label,text:'[本文の参照](https://body.example/)'}));
 fields[5].text='・[2026-11-18 決算資料 \\[別紙\\](15:00)](https://disclosure.example/file?a=1&b=2)\n'
  +'[危険](javascript:alert%281%29)\n[HTTP](http://insecure.example/)\n[無題](https://invalid [url])';
 fields[6].text='・[公式IR・開示一覧 <IR>](https://source.example/)\n'
  +'[認証情報付き](https://user:pw@source.example/)\n[https://bare.example/](https://bare.example/)\n'
  +'https://unlabeled.example/\n<a href="https://markup.example/">未確認</a>';
 const html=ui.fundamentalMarkup({as_of:expected.asOf,date:expected.date,symbol:expected.symbol,
  generation:expected.generation,company_name:null,analysis_cutoff:'2026-11-18T16:15:00+09:00',fields},expected);
 a.equal((html.match(/<a href=/g)||[]).length,2);
 a.match(html,/・<a href="https:\/\/disclosure\.example\/file\?a=1&amp;b=2" target="_blank" rel="noopener noreferrer">2026-11-18 決算資料 \[別紙\]\(15:00\)<\/a>/);
 a.match(html,/・<a href="https:\/\/source\.example\/" target="_blank" rel="noopener noreferrer">公式IR・開示一覧 &lt;IR&gt;<\/a>/);
 a.match(html,/\[本文の参照\]\(https:\/\/body\.example\/\)/);
 a.doesNotMatch(html,/href="(?:javascript|http:|https:\/\/(?:invalid|user:|bare\.example|unlabeled\.example|body\.example))/);
 a.match(html,/&lt;a href=&quot;https:\/\/markup\.example\/&quot;&gt;/);
});
test('chart gaps never joined and values not normalized to fake zero',()=>{const html=ui.chart([{date:'2026-11-17',equity_yen:100},{date:'2026-11-18',equity_yen:null},{date:'2026-11-19',equity_yen:120}]);a.equal((html.match(/<polyline/g)||[]).length,2);a.ok(!/NaN|Infinity/.test(html));a.ok(ui.chart([{date:'2026-11-19',equity_yen:null}]).includes('未確定'));});
test('untrusted labels escaped and unresolved metrics never shown',()=>{a.ok(!ui.history([{date:'<script>',symbol:'<img>',state:'<script>'}]).includes('<script>'));a.ok(ui.metrics(null).includes('未確定'));a.ok(!ui.metrics(null).includes('0円'));});
test('member transport never loads owner inputs, worker or notifications',()=>{const js=fs.readFileSync(path.join(src,'member-loader.js'),'utf8');a.doesNotMatch(js,/new-a-finite|input\/manifest|new Worker|notification-preferences/);});
