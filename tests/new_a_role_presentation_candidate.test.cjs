const {test}=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=path.join(__dirname,'../weak-early-beta-gate/scripts/new-a-ui-source/assets');
const context={module:{exports:{}}};vm.runInNewContext(fs.readFileSync(path.join(src,'member-presentation.js'),'utf8'),context);const ui=context.module.exports;
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
test('analytics compares all 3 presets; missing personal result not fabricated',()=>{const html=ui.view({mode:'analytics',access:'premium',asOf:'2026-11-19',presets,selected:'defensive',rows:[],chartRows:[],personal:null});for(const s of ['守り','中間','利益優先','準備中','以前の結果では代用しません'])a.ok(html.includes(s));});
test('free presentation shows server-provided closed history and one existing purchase action',()=>{
 const html=ui.view({mode:'home',access:'free',asOf:'2026-11-19',presets,selected:'medium',rows:[{date:'2026-11-18',symbol:'1234',state:'HOLD_ENDED'}],chartRows:[],personal:metrics,dashboard:{today:[{symbol:'TODAY_ONLY'}],watching:[{symbol:'WATCH_ONLY'}]}});
 for(const value of ['終了済みの検出履歴','1234','仮想保有終了','今日の動きと監視状況','href="/purchase"'])a.ok(html.includes(value),value);
 a.doesNotMatch(html,/TODAY_ONLY|WATCH_ONLY|member-preset|日次資金推移|対象日 2026-11-19/);
 a.doesNotMatch(html,/today-summary|today-kpis|運用レベル/);
 a.equal((html.match(/href="\/purchase"/g)||[]).length,1);
 for(const mode of ['analytics','settings'])a.match(ui.view({mode,access:'free'}),/Premium会員限定.*href="\/purchase"/);
});
test('chart gaps never joined and values not normalized to fake zero',()=>{const html=ui.chart([{date:'2026-11-17',equity_yen:100},{date:'2026-11-18',equity_yen:null},{date:'2026-11-19',equity_yen:120}]);a.equal((html.match(/<polyline/g)||[]).length,2);a.ok(!/NaN|Infinity/.test(html));a.ok(ui.chart([{date:'2026-11-19',equity_yen:null}]).includes('未確定'));});
test('untrusted labels escaped and unresolved metrics never shown',()=>{a.ok(!ui.history([{date:'<script>',symbol:'<img>',state:'<script>'}]).includes('<script>'));a.ok(ui.metrics(null).includes('未確定'));a.ok(!ui.metrics(null).includes('0円'));});
test('member transport never loads owner inputs, worker or notifications',()=>{const js=fs.readFileSync(path.join(src,'member-loader.js'),'utf8');a.doesNotMatch(js,/new-a-finite|input\/manifest|new Worker|notification-preferences/);});
