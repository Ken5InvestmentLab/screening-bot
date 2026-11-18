// New-A routing only. The existing index owner gate and identity implementation inject context.
import {cloudMemberId,type CloudEnv} from './cloud-api';
import {DEFAULT_PREFERENCES,isObject} from './cloud-membership';
import {ownerNoticeEnrollmentConfigured} from './cloud-web-push';
import {readActiveManifest,readPrivatePart,PART_NAME,DATASET_ID} from './new-a-private';
import {readTrial,saveTrial,validateTrial,validateView,type ViewPreferences} from './new-a-preferences';
import {OPENING_OBSERVATION_PATH,readOpeningObservation} from './new-a-opening-observation';
import {ownerFrame,FRAME_PATHS} from './research-a/frame.generated';
import {ASSET_NAMES,COMPAT_ASSET_NAMES} from './research-a/assets.generated';
export type TrustedOwnerContext={ownerAuthorized:boolean;roleAuthorized:boolean;current:boolean;subject?:string};
export const PRIVATE_HEADERS={'cache-control':'private, no-store, max-age=0',vary:'Cookie','x-content-type-options':'nosniff','referrer-policy':'no-referrer','cross-origin-resource-policy':'same-origin','content-security-policy':"default-src 'none'; script-src 'self'; worker-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"};
const bindingEncoder = new TextEncoder();
const saveBindingPattern = /^[a-f0-9]{64}$/;
async function saveBindingKey(secret: string | undefined): Promise<CryptoKey> {
 if (!secret?.trim()) throw Error('session_key_unavailable');
 return crypto.subtle.importKey('raw', bindingEncoder.encode(secret), {name:'HMAC', hash:'SHA-256'}, false, ['sign','verify']);
}
function saveBindingInput(subject: string, revision: number) {
 return bindingEncoder.encode(JSON.stringify(['new-a-preferences-save-v1', subject, revision]));
}
async function issueSaveBinding(key: CryptoKey, subject: string, revision: number): Promise<string> {
 const signature = await crypto.subtle.sign('HMAC', key, saveBindingInput(subject, revision));
 return Array.from(new Uint8Array(signature), byte => byte.toString(16).padStart(2, '0')).join('');
}
function matchesSaveBinding(key: CryptoKey, subject: string, revision: number, value: string): Promise<boolean> {
 const signature = Uint8Array.from({length: 32}, (_, i) => parseInt(value.slice(i * 2, i * 2 + 2), 16));
 return crypto.subtle.verify('HMAC', key, signature, saveBindingInput(subject, revision));
}
const legacyData=/^\/(?:weak_early_beta_data_|report-interactions\.js|report-theme-init\.js|weak-early-beta-)|^\/(?:api\/research-a\/details|research-a\/details\.json)$/;
export function isNewAPath(path:string):boolean{return FRAME_PATHS.includes(path)||path.startsWith('/api/cloud/new-a-finite/')||path.startsWith('/new-a-assets/')||legacyData.test(path)||path.startsWith('/report-assets/');}
export function protectedReply(request:Request,status:number,value:unknown,json=true):Response{return new Response(request.method==='HEAD'?null:json?JSON.stringify(value):String(value),{status,headers:{...PRIVATE_HEADERS,'content-type':json?'application/json; charset=utf-8':'text/html; charset=utf-8'}});}

async function ownerNotificationPreferences(request: Request, env: CloudEnv, subject: string): Promise<Response> {
 const member = await cloudMemberId(subject);
 const validOwner = /^[0-9]{17,20}$/.test(subject) && subject === env.CLOUD_OWNER_DISCORD_ID?.trim();
 if (!validOwner) return protectedReply(request, 403, {error: 'owner_required'});
 const available = ownerNoticeEnrollmentConfigured(env) && String(env.CLOUD_PUSH_AUDIENCE) === 'paid' &&
  env.CLOUD_PUSH_MEMBERSHIP_POLICY === 'whop_managed_discord_role' && member === env.CLOUD_PUSH_TEST_MEMBER_ID;
 const db = env.CLOUD_DB!;
 const read = async () => {
  const row = await db.prepare('SELECT preferences_json FROM cloud_member_preferences WHERE member_id=?')
   .bind(member).first<{preferences_json: string}>();
  if (!row) return DEFAULT_PREFERENCES.notifications;
  const stored: unknown = JSON.parse(row.preferences_json);
  if (!isObject(stored)) throw Error('invalid_notification_preferences');
  const notifications = stored.notifications ?? {};
  if (!isObject(notifications) || ['new_detection', 'reminder'].some(key =>
      Object.hasOwn(notifications, key) && typeof notifications[key] !== 'boolean')) throw Error('invalid_notification_preferences');
  return {new_detection: notifications.new_detection === true, reminder: notifications.reminder === true};
 };
 if (request.method === 'GET') return protectedReply(request, 200, {ok: true, notifications: await read(), available});
 if (request.method !== 'PUT') return protectedReply(request, 405, {error: 'method_not_allowed'});
 if (!available) return protectedReply(request, 503, {error: 'owner_notice_settings_unavailable'});
 if (request.headers.get('origin') !== new URL(request.url).origin)
  return protectedReply(request, 403, {error: 'origin_required'});
 if (!(request.headers.get('content-type') ?? '').toLowerCase().startsWith('application/json'))
  return protectedReply(request, 415, {error: 'json_required'});
 const raw = await request.text();
 if (new TextEncoder().encode(raw).byteLength > 1024) return protectedReply(request, 413, {error: 'request_too_large'});
 let body: unknown;
 try { body = JSON.parse(raw); } catch { return protectedReply(request, 400, {error: 'invalid_json'}); }
 const notifications = isObject(body) && Object.keys(body).join(',') === 'notifications' ? body.notifications : null;
 if (!isObject(notifications) || Object.keys(notifications).sort().join(',') !== 'new_detection,reminder' ||
     typeof notifications.new_detection !== 'boolean' || typeof notifications.reminder !== 'boolean')
  return protectedReply(request, 400, {error: 'invalid_notification_preferences'});
 await read();
 const patch = JSON.stringify({notifications});
 const saved = await db.prepare(`INSERT INTO cloud_member_preferences(member_id,preferences_json,updated_at)
  VALUES (?,?,?) ON CONFLICT(member_id) DO UPDATE SET
  preferences_json=json_patch(cloud_member_preferences.preferences_json,?), updated_at=excluded.updated_at`)
  .bind(member, JSON.stringify({...DEFAULT_PREFERENCES, notifications}), new Date().toISOString(), patch).run();
 if (!saved.success || saved.meta.changes !== 1) return protectedReply(request, 503, {error: 'notification_save_failed'});
 const confirmed = await read();
 if (confirmed.new_detection !== notifications.new_detection || confirmed.reminder !== notifications.reminder)
  return protectedReply(request, 409, {error: 'notification_preferences_changed'});
 return protectedReply(request, 200, {ok: true, notifications: confirmed, available});
}
export function newAEarlyRefusal(request:Request):Response|null{
 const u=new URL(request.url),document=FRAME_PATHS.includes(u.pathname),read=['GET','HEAD'].includes(request.method);
 if((document||u.pathname==='/api/cloud/new-a-finite/access'||u.pathname===OPENING_OBSERVATION_PATH)&&!read)return protectedReply(request,405,{error:'method_not_allowed'});
 const top=document&&read&&request.headers.get('sec-fetch-mode')==='navigate'&&request.headers.get('sec-fetch-dest')==='document';
 if(request.headers.get('sec-fetch-site')==='cross-site'&&!top)return protectedReply(request,403,{error:'cross_site_request'});
 if(request.headers.get('origin')&&request.headers.get('origin')!==u.origin)return protectedReply(request,403,{error:'origin_mismatch'});
 if(legacyData.test(u.pathname)||u.pathname.startsWith('/report-assets/'))return protectedReply(request,410,{error:'legacy_data_not_served'});
 return null;
}
export function isCompatibilityAsset(path:string):boolean{return COMPAT_ASSET_NAMES.includes(path);}
// These existing push-only scripts contain no A data and were owner-gated without report-role lookup.
// Never register/unregister a worker or change notification preferences from this response.
export async function compatibilityCodeResponse(request:Request,env:CloudEnv):Promise<Response>{
 const u=new URL(request.url);if(env.CLOUD_OWNER_ONLY_ENABLED?.trim().toLowerCase()!=='true')return protectedReply(request,503,{error:'owner_mode_required'});
 if(!isCompatibilityAsset(u.pathname)||u.search||!['GET','HEAD'].includes(request.method))return protectedReply(request,404,{error:'not_found'});
 if(request.headers.get('sec-fetch-site')==='cross-site'||request.headers.get('origin')&&request.headers.get('origin')!==u.origin)return protectedReply(request,403,{error:'cross_site_request'});
 const result=await env.ASSETS.fetch(new URL(u.pathname,'https://assets.local').toString());if(!result.ok)return protectedReply(request,404,{error:'not_found'});
 return new Response(request.method==='HEAD'?null:result.body,{status:200,headers:{...PRIVATE_HEADERS,'content-type':'application/javascript; charset=utf-8'}});
}
export async function newACloudRoute(request:Request,env:CloudEnv,context:TrustedOwnerContext):Promise<Response>{
 const url=new URL(request.url),p=url.pathname,document=FRAME_PATHS.includes(p);
 // No database, pointer, manifest or ASSETS request precedes this context check.
 if(!context.ownerAuthorized||!context.subject)return protectedReply(request,401,{error:'owner_required'});
 if(!context.current)return protectedReply(request,503,{error:'authentication_unavailable'});
 if(!context.roleAuthorized)return protectedReply(request,403,{error:'role_required'});
 const refused=newAEarlyRefusal(request);if(refused)return refused;
 if(document){if(!['GET','HEAD'].includes(request.method))return protectedReply(request,405,{error:'method_not_allowed'});return protectedReply(request,200,ownerFrame(p,context),false);}
 if(legacyData.test(p)||p.startsWith('/report-assets/'))return protectedReply(request,410,{error:'legacy_data_not_served'});
 if(p.startsWith('/new-a-assets/')){
  const name=p.slice('/new-a-assets/'.length);if(url.search||!ASSET_NAMES.includes(name)||!['GET','HEAD'].includes(request.method))return protectedReply(request,404,{error:'not_found'});
  const asset=await env.ASSETS.fetch(new URL(p,'https://assets.local').toString());if(!asset.ok)return protectedReply(request,404,{error:'not_found'});
  return new Response(request.method==='HEAD'?null:asset.body,{status:200,headers:{...PRIVATE_HEADERS,'content-type':name.endsWith('.png')?'image/png':'application/javascript; charset=utf-8'}});
 }
 if(p==='/api/cloud/new-a-finite/access'){
  if(url.search)return protectedReply(request,404,{error:'not_found'});
  if(!['GET','HEAD'].includes(request.method))return protectedReply(request,405,{error:'method_not_allowed'});
  return protectedReply(request,200,{authorized:true,strategy:'A_BASE'});
 }
 if(!env.CLOUD_DB)return protectedReply(request,503,{error:'storage_unavailable'});
 if(url.search)return protectedReply(request,404,{error:'not_found'});
 const resource=p.slice('/api/cloud/new-a-finite/'.length);
 try{
  if(p===OPENING_OBSERVATION_PATH){
   if(context.subject!==env.CLOUD_OWNER_DISCORD_ID?.trim())return protectedReply(request,403,{error:'owner_required'});
   return protectedReply(request,200,await readOpeningObservation(env.CLOUD_DB,await cloudMemberId(context.subject)));
  }
  if(resource==='input/manifest.json'){
   if(!['GET','HEAD'].includes(request.method))return protectedReply(request,405,{error:'method_not_allowed'});
   return protectedReply(request,200,await readActiveManifest(env.CLOUD_DB));
  }
  const part=/^input\/([^/]+)\/([^/]+)$/.exec(resource);
  if(part){if(!['GET','HEAD'].includes(request.method)||!DATASET_ID.test(part[1])||!PART_NAME.test(part[2]))return protectedReply(request,404,{error:'not_found'});const body=await readPrivatePart(env.CLOUD_DB,part[1],part[2]);return body===null?protectedReply(request,404,{error:'not_found'}):new Response(request.method==='HEAD'?null:body,{status:200,headers:{...PRIVATE_HEADERS,'content-type':'application/json; charset=utf-8'}});}
  if(resource==='notification-preferences')return await ownerNotificationPreferences(request,env,context.subject);
  if(resource==='simulate')return protectedReply(request,409,{error:'owner_browser_worker_required'});
  if(resource!=='preferences')return protectedReply(request,404,{error:'not_found'});
  const member=await cloudMemberId(context.subject);
  if(['GET','HEAD'].includes(request.method)){
   const state = await readTrial(env.CLOUD_DB,member);
   const key = await saveBindingKey(env.SESSION_SECRET);
   const save_binding = await issueSaveBinding(key, context.subject, state.revision);
   return protectedReply(request,200,{...state,save_binding});
  }
  if(request.method!=='PUT')return protectedReply(request,405,{error:'method_not_allowed'});
  if(request.headers.get('origin')!==url.origin)return protectedReply(request,403,{error:'origin_required'});
  if(!(request.headers.get('content-type')||'').toLowerCase().startsWith('application/json'))return protectedReply(request,415,{error:'json_required'});
  const raw=await request.text();if(new TextEncoder().encode(raw).byteLength>8192)return protectedReply(request,413,{error:'request_too_large'});
  let body:unknown;try{body=JSON.parse(raw);}catch{return protectedReply(request,400,{error:'invalid_json'});}
  if(!body||typeof body!=='object'||Array.isArray(body))return protectedReply(request,400,{error:'request_fields'});
  const b=body as Record<string,unknown>;
  if(Object.keys(b).some(k=>!['preferences','view_preferences','save_binding','expected_revision','request_id'].includes(k))||typeof b.request_id!=='string'||!/^[-A-Za-z0-9_:]{1,80}$/.test(b.request_id)||!Number.isSafeInteger(b.expected_revision)||Number(b.expected_revision)<0||Number(b.expected_revision)>=Number.MAX_SAFE_INTEGER)return protectedReply(request,400,{error:'request_fields'});
  const expectedRevision = Number(b.expected_revision);
  let preferences;try{preferences=validateTrial(b.preferences);}catch{return protectedReply(request,400,{error:'invalid_preferences'});}
  let view: ViewPreferences | undefined;
  let saveBinding: string | undefined;
  if(Object.hasOwn(b,'view_preferences')){
   try{view=validateView(b.view_preferences);}catch{return protectedReply(request,400,{error:'invalid_view_preferences'});}
   if(typeof b.save_binding!=='string'||!saveBindingPattern.test(b.save_binding))return protectedReply(request,400,{error:'save_binding_required'});
   const key=await saveBindingKey(env.SESSION_SECRET);
   if(!await matchesSaveBinding(key,context.subject,expectedRevision,b.save_binding))return protectedReply(request,409,{error:'settings_session_changed',request_id:b.request_id});
   // Prepare the next receipt before writing, so a signing failure cannot hide a completed save.
   saveBinding=await issueSaveBinding(key,context.subject,expectedRevision+1);
  } else if(Object.hasOwn(b,'save_binding')){
   return protectedReply(request,400,{error:'request_fields'});
  }
  const saved=await saveTrial(env.CLOUD_DB,member,preferences,expectedRevision,view);if(!saved.ok)return protectedReply(request,409,{error:'revision_conflict',revision:saved.revision,request_id:b.request_id});
  return protectedReply(request,200,{schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,preferences,...(view?{view_preferences:view,save_binding:saveBinding}:{}),revision:saved.revision,default_proposal_verified:false,preference_source:'new-a-saved',request_id:b.request_id});
 }catch{return protectedReply(request,503,{error:'new_a_service_unavailable'});}
}
