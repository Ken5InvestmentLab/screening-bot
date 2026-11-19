export type SafeOwnerObservation={
 operation:'cloud_owner_response_observed';schema:'NEW_A_PROTECTED_OWNER_RESPONSE_V1';worker:'tentei-kyokuchi-cloud';
 source_commit:string; build_input_sha256:string;version_id:string;version_timestamp:string;route:string;status:200;strategy:'A_BASE';
 verified_access_contract?:{authorized:true;strategy:'A_BASE'};
};
type Ready = {prepare(sql:string):{bind(...v:(string|number)[]):{run():Promise<unknown>}}};
type Lifetime={waitUntil(p:Promise<unknown>):void};
const frames=['/weak_early_beta_latest.html','/api/cloud/new-a-finite/access'];
const INSERT=`INSERT INTO new_a_protected_owner_observations_v1
  (worker,version_id,build_input_sha256,source_commit,version_timestamp,route,observed_at_ms,observed_slot,status,strategy,api_contract_verified)
  VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(worker,version_id,route,observed_slot) DO NOTHING`;
export function passiveObservationSink(authority:{enabled:boolean;db?:Ready;ctx?:Lifetime},onError?:()=>void){
 return function observe(a:SafeOwnerObservation):void{
  // Private Worker module only. Caller is the existing final response gate.
  if(authority.enabled!==true||!authority.db||!authority.ctx)return;
  const isApi=a.route===frames[1];
  if(a.operation!=='cloud_owner_response_observed'||a.schema!=='NEW_A_PROTECTED_OWNER_RESPONSE_V1'||a.worker!=='tentei-kyokuchi-cloud'||
   a.status!==200||a.strategy!=='A_BASE'||!frames.includes(a.route)||
   (isApi?(a.verified_access_contract?.authorized!==true||a.verified_access_contract.strategy!=='A_BASE'):a.verified_access_contract!==undefined)||
   !/^[a-f0-9]{40}$/.test(a.source_commit)||!/^[a-f0-9]{64}$/.test(a.build_input_sha256)||
   !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(a.version_id)||
   !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/.test(a.version_timestamp))return;
  const now=Date.now(), start=Date.parse(a.version_timestamp);
  if(!Number.isFinite(start)||start>now)return;
  const captured=[a.worker,a.version_id,a.build_input_sha256,a.source_commit,a.version_timestamp,a.route,
    now,Math.floor(now/300000),a.status,a.strategy,isApi?1:0];
  const task=Promise.resolve().then(()=>authority.db!.prepare(INSERT).bind(...captured).run()).catch(()=>{try{onError?.();}catch{return;}});
  try{authority.ctx.waitUntil(task);}catch{return;}
 };
}
