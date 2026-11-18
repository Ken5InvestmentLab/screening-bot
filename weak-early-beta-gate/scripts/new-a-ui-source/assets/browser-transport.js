// 資金配分は本人端末のWorkerで実行。Cloudflareは本人認証・保存・private小分け入力のみ。
(function(){'use strict';
 const response=(status,body)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json','cache-control':'private, no-store'}});
 function create({fetch:network,createWorker,crypto=globalThis.crypto,pinnedManifest=null,onSimulationPhase=()=>{}}){
  let worker=null,ready=null,early=null,loading=null,next=0,generation=0;const jobs=new Map();
  function resetWorker(){
   generation++;loading?.abort();loading=null;worker?.terminate();worker=null;ready=null;
   for(const j of jobs.values())j.reject(Error('authorization_reset'));
   jobs.clear();
  }
  function clear(){early=null;resetWorker();}
  function rpc(message,transfer=[]){return new Promise((resolve,reject)=>{
   if(!worker){reject(Error('authorization_reset'));return;}
   const id=++next;jobs.set(id,{resolve,reject});
   try{worker.postMessage({...message,id},transfer);}catch(error){jobs.delete(id);reject(error);}
  });}
  async function initialized(){
   if(ready)return ready;
   const started=generation,controller=new AbortController();
   loading=controller;
   const stillCurrent=()=>{if(started!==generation)throw Error('authorization_reset');};
   const preparing=(async()=>{
    const options={credentials:'same-origin',cache:'no-store',signal:controller.signal};
    let manifest=pinnedManifest;if(!manifest){const r=await network('/api/cloud/new-a-finite/input/manifest.json',options);if(!r.ok)throw {status:r.status};manifest=await r.json();}
    if(manifest.schema!=='A_BROWSER_PRIVATE_INPUT_V1'||manifest.audience!=='EXISTING_CLOUD_OWNER_ONLY'||manifest.input_header?.source_version!==manifest.source_version)throw Error('manifest_schema');
    if(!/^a-[a-f0-9]{20,64}$/.test(manifest.dataset_id))throw Error('manifest_dataset');
    const kinds=['episodes','intents','watches'];
    const descriptors=[...kinds.flatMap(k=>manifest.collections[k]),...manifest.quotes];if(descriptors.length>512||new Set(descriptors.map(d=>d.name)).size!==descriptors.length||descriptors.some(d=>!(/^(episodes|intents|watches|quotes)-\d{3}\.json$/).test(d.name)||d.dataset_id!==undefined&&!/^a-[a-f0-9]{20,64}$/.test(d.dataset_id)||!Number.isSafeInteger(d.bytes)||d.bytes>192*1024||d.bytes<2||!Number.isSafeInteger(d.rows)||d.rows<0||!(/^[a-f0-9]{64}$/).test(d.sha256)))throw Error('manifest_bounds');
    const quoteNames=new Set(manifest.quotes.map(d=>d.name)),decoder=new TextDecoder();
    const loaded=new Map();let cursor=0;
    async function load(){
     while(cursor<descriptors.length){
      stillCurrent();
      const d=descriptors[cursor++],r=await network('/api/cloud/new-a-finite/input/'+(d.dataset_id||manifest.dataset_id)+'/'+d.name,options);
      if(!r.ok)throw {status:r.status};
      const bytes=await r.arrayBuffer();
      if(bytes.byteLength!==d.bytes)throw Error('chunk_bytes');
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
      if(hash!==d.sha256)throw Error('chunk_hash');
      stillCurrent();
      if(quoteNames.has(d.name)){loaded.set(d.name,bytes);continue;}
      const rows=JSON.parse(decoder.decode(bytes));
      if(!Array.isArray(rows)||rows.length!==d.rows)throw Error('chunk_rows');
      loaded.set(d.name,rows);
     }
    }
    await Promise.all(Array.from({length:Math.min(4,descriptors.length)},load));stillCurrent();
    const input={...manifest.input_header};for(const kind of kinds)input[kind]=manifest.collections[kind].flatMap(d=>loaded.get(d.name));
    // Transfer verified original quote bytes to avoid parsing and cloning the
    // full price history on the UI thread.
    const quoteChunks=manifest.quotes.map(d=>loaded.get(d.name));
    worker=createWorker();worker.onmessage=e=>{const j=jobs.get(e.data.id);if(!j)return;jobs.delete(e.data.id);e.data.error?j.reject(Error(e.data.error)):j.resolve(e.data);};worker.onerror=()=>{if(started===generation)resetWorker();};
    const result=await rpc({kind:'initialize',manifest:{...manifest,input},quoteChunks},quoteChunks);
    stillCurrent();loading=null;return result;
   })();ready=preparing;
   try{return await preparing;}catch(e){if(started===generation)resetWorker();throw e;}
  }
  function preload(){return early??=initialized();}
  async function transport(url,options={}){
   if(url!=='/api/cloud/new-a-finite/simulate'||options.method!=='POST')return network(url,options);
   // キャッシュ済み価格を使う場合も、既存本人・role・sessionの最新可否を先に確認する。
   const started=generation;
   const access=await network('/api/cloud/new-a-finite/preferences',{cache:'no-store'});if(!access.ok){clear();return access;}
   let policy;try{const state=await access.json();policy=state.exit_policy;if(!policy||policy.version!=='A_OPEN_EXIT_V2'||!/^\d{4}-\d{2}-\d{2}$/.test(policy.first_d5_entry_session)||policy.legacy_endpoint!=='d6_open'||policy.new_endpoint!=='d5_open')throw Error('exit_policy_invalid');}catch{clear();return response(503,{error:'local_simulation_unavailable'});}
   const pending=early;
   early=null;
   try{
    if(started!==generation&&!pending)throw Error('authorization_reset');
    if(!worker)onSimulationPhase('prices');await (pending??initialized());
    if(started!==generation)throw Error('authorization_reset');
    const body=JSON.parse(options.body);if(body.expected_source_version!==undefined){const pin=await rpc({kind:'source_version'});if(body.expected_source_version!==pin.source_version)return response(409,{error:'source_version_changed'});}
    onSimulationPhase('calculation');const value=await rpc({kind:'simulate',preferences:body.preferences,exit_policy:policy,request_id:body.request_id,...(body.recent_analytics===true?{recent_analytics:true}:{}),...(body.dashboard_prices===true?{dashboard_prices:true}:{}),...(body.trial_preset!==undefined?{trial_preset:body.trial_preset}:{})});
    if(started!==generation)throw Error('authorization_reset');
    delete value.id;return response(200,value);
   }catch(e){if(e.status===401||e.status===403)clear();return response(e.status||503,{error:e.status===401?'login_required':e.status===403?'owner_required':'local_simulation_unavailable'});}
  }
  return{transport,preload,clear};
 }
 const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else globalThis.AFiniteBrowserTransport=api;
})();
