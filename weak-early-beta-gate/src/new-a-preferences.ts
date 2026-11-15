import type {NewADatabase} from './new-a-private';
export interface TrialPreferences {price_cap_yen:number|null;exit_endpoint:'d5_close'|'d6_open'|'a20_close';base_shares:number;cost_percent:number;year_scope:'all'|'2023'|'2024'|'2025'|'2026';allocation:'all'|'unique'|'stacked';initial_cash_yen:number;max_positions:number;per_order_cap_yen:number;}
export const DEFAULTS:TrialPreferences={price_cap_yen:1000,exit_endpoint:'d6_open',base_shares:100,cost_percent:0,year_scope:'all',allocation:'all',initial_cash_yen:10000000,max_positions:20,per_order_cap_yen:500000};
export function validateTrial(value:unknown):TrialPreferences {
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('invalid_preferences');const p=value as TrialPreferences;
 if(Object.keys(p).length!==9||Object.keys(DEFAULTS).some(k=>!Object.hasOwn(p,k)))throw Error('preferences_fields');
 for(const key of ['initial_cash_yen','per_order_cap_yen'] as const)if(!Number.isSafeInteger(p[key])||p[key]<=0||p[key]>1e12)throw Error(key);
 if(!Number.isSafeInteger(p.max_positions)||p.max_positions<1||p.max_positions>1000||!Number.isSafeInteger(p.base_shares)||p.base_shares<100||p.base_shares>1e6||p.base_shares%100)throw Error('allocation_fields');
 const decimal=(v:number,min:number,max:number)=>Number.isFinite(v)&&typeof v==='number'&&v>=min&&v<=max&&/^\d+(?:\.\d{1,2})?$/.test(String(v));
 if(!decimal(p.cost_percent,0,10)||p.price_cap_yen!==null&&!decimal(p.price_cap_yen,.01,1e9)||!['d5_close','d6_open','a20_close'].includes(p.exit_endpoint)||!['all','2023','2024','2025','2026'].includes(p.year_scope)||!['all','unique','stacked'].includes(p.allocation))throw Error('trial_fields');return {...p};
}
// Service policy, returned only inside the existing authenticated owner route.
export const OPEN_EXIT_POLICY={version:'A_OPEN_EXIT_V2',first_d5_entry_session:'2026-11-17',legacy_endpoint:'d6_open',new_endpoint:'d5_open'} as const;
export async function readTrial(db:NewADatabase,member:string){
 const row=await db.prepare('SELECT preferences_json,revision FROM new_a_finite_trial_preferences WHERE member_id=?').bind(member).first<{preferences_json:string;revision:number}>();
 if(row){if(!Number.isSafeInteger(row.revision)||row.revision<1)throw Error('revision');return {schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,preferences:validateTrial(JSON.parse(row.preferences_json)),revision:row.revision,default_proposal_verified:false,exit_policy:OPEN_EXIT_POLICY,preference_source:'new-a-saved'};}
 const legacy=await db.prepare('SELECT preferences_json FROM cloud_member_preferences WHERE member_id=?').bind(member).first<{preferences_json:string}>();
 const mapped={...DEFAULTS};if(legacy){const p:unknown=JSON.parse(legacy.preferences_json);if(!p||typeof p!=='object'||Array.isArray(p))throw Error('legacy_preferences');const v=p as Record<string,unknown>;for(const [a,b]of Object.entries({max_price:'price_cap_yen',exit_endpoint:'exit_endpoint',base_shares:'base_shares',cost_percent:'cost_percent'})){if(Object.hasOwn(v,a))(mapped as unknown as Record<string,unknown>)[b]=v[a];}}
 return {schema_version:1,has_saved_preferences:!!legacy,has_saved_finite_preferences:false,preferences:validateTrial(mapped),revision:0,default_proposal_verified:false,exit_policy:OPEN_EXIT_POLICY,preference_source:legacy?'legacy-saved':'legacy-default'};
}
export async function saveTrial(db:NewADatabase,member:string,p:TrialPreferences,expected:number):Promise<{ok:boolean;revision:number}>{
 const now=new Date().toISOString(),statement=expected===0?db.prepare('INSERT INTO new_a_finite_trial_preferences(member_id,schema_version,preferences_json,revision,updated_at) VALUES (?,1,?,1,?) ON CONFLICT(member_id) DO NOTHING RETURNING revision').bind(member,JSON.stringify(p),now):db.prepare('UPDATE new_a_finite_trial_preferences SET preferences_json=?,revision=revision+1,updated_at=? WHERE member_id=? AND revision=? RETURNING revision').bind(JSON.stringify(p),now,member,expected);
 const saved=await statement.first<{revision:number}>();if(saved)return {ok:true,revision:saved.revision};const row=await db.prepare('SELECT revision FROM new_a_finite_trial_preferences WHERE member_id=?').bind(member).first<{revision:number}>();return {ok:false,revision:row?.revision??0};
}
