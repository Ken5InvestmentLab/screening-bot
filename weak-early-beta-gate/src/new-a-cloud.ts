// New-A routing only. The existing index owner gate and identity implementation inject context.
import {cloudMemberId,type CloudEnv} from './cloud-api';
import {readActiveManifest,readPrivatePart,PART_NAME,DATASET_ID} from './new-a-private';
import {readTrial,saveTrial,validateTrial,validateView,type ViewPreferences} from './new-a-preferences';
import {ownerFrame,FRAME_PATHS} from './research-a/frame.generated';
import {ASSET_NAMES,COMPAT_ASSET_NAMES} from './research-a/assets.generated';
export type TrustedOwnerContext={ownerAuthorized:boolean;roleAuthorized:boolean;current:boolean;subject?:string};
export const PRIVATE_HEADERS={'cache-control':'private, no-store, max-age=0',vary:'Cookie','x-content-type-options':'nosniff','referrer-policy':'no-referrer','cross-origin-resource-policy':'same-origin','content-security-policy':"default-src 'none'; script-src 'self'; worker-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"};
const legacyData=/^\/(?:weak_early_beta_data_|report-interactions\.js|report-theme-init\.js|weak-early-beta-)|^\/(?:api\/research-a\/details|research-a\/details\.json)$/;
export function isNewAPath(path:string):boolean{return FRAME_PATHS.includes(path)||path.startsWith('/api/cloud/new-a-finite/')||path.startsWith('/new-a-assets/')||legacyData.test(path)||path.startsWith('/report-assets/');}
export function protectedReply(request:Request,status:number,value:unknown,json=true):Response{return new Response(request.method==='HEAD'?null:json?JSON.stringify(value):String(value),{status,headers:{...PRIVATE_HEADERS,'content-type':json?'application/json; charset=utf-8':'text/html; charset=utf-8'}});}
export function newAEarlyRefusal(request:Request):Response|null{
 const u=new URL(request.url),document=FRAME_PATHS.includes(u.pathname),read=['GET','HEAD'].includes(request.method);
 if((document||u.pathname==='/api/cloud/new-a-finite/access')&&!read)return protectedReply(request,405,{error:'method_not_allowed'});
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
  if(resource==='input/manifest.json'){
   if(!['GET','HEAD'].includes(request.method))return protectedReply(request,405,{error:'method_not_allowed'});
   return protectedReply(request,200,await readActiveManifest(env.CLOUD_DB));
  }
  const part=/^input\/([^/]+)\/([^/]+)$/.exec(resource);
  if(part){if(!['GET','HEAD'].includes(request.method)||!DATASET_ID.test(part[1])||!PART_NAME.test(part[2]))return protectedReply(request,404,{error:'not_found'});const body=await readPrivatePart(env.CLOUD_DB,part[1],part[2]);return body===null?protectedReply(request,404,{error:'not_found'}):new Response(request.method==='HEAD'?null:body,{status:200,headers:{...PRIVATE_HEADERS,'content-type':'application/json; charset=utf-8'}});}
  if(resource==='simulate')return protectedReply(request,409,{error:'owner_browser_worker_required'});
  if(resource!=='preferences')return protectedReply(request,404,{error:'not_found'});
  const member=await cloudMemberId(context.subject);
  if(['GET','HEAD'].includes(request.method))return protectedReply(request,200,await readTrial(env.CLOUD_DB,member));
  if(request.method!=='PUT')return protectedReply(request,405,{error:'method_not_allowed'});
  if(request.headers.get('origin')!==url.origin)return protectedReply(request,403,{error:'origin_required'});
  if(!(request.headers.get('content-type')||'').toLowerCase().startsWith('application/json'))return protectedReply(request,415,{error:'json_required'});
  const raw=await request.text();if(new TextEncoder().encode(raw).byteLength>8192)return protectedReply(request,413,{error:'request_too_large'});
  let body:unknown;try{body=JSON.parse(raw);}catch{return protectedReply(request,400,{error:'invalid_json'});}
  if(!body||typeof body!=='object'||Array.isArray(body))return protectedReply(request,400,{error:'request_fields'});
  const b=body as Record<string,unknown>;
  if(Object.keys(b).some(k=>!['preferences','view_preferences','expected_revision','request_id'].includes(k))||typeof b.request_id!=='string'||!/^[-A-Za-z0-9_:]{1,80}$/.test(b.request_id)||!Number.isSafeInteger(b.expected_revision)||Number(b.expected_revision)<0||Number(b.expected_revision)>=Number.MAX_SAFE_INTEGER)return protectedReply(request,400,{error:'request_fields'});
  let preferences;try{preferences=validateTrial(b.preferences);}catch{return protectedReply(request,400,{error:'invalid_preferences'});}
  let view: ViewPreferences | undefined;
  if(Object.hasOwn(b,'view_preferences')){
   try{view=validateView(b.view_preferences);}catch{return protectedReply(request,400,{error:'invalid_view_preferences'});}
  }
  const saved=await saveTrial(env.CLOUD_DB,member,preferences,Number(b.expected_revision),view);if(!saved.ok)return protectedReply(request,409,{error:'revision_conflict',revision:saved.revision,request_id:b.request_id});
  return protectedReply(request,200,{schema_version:1,has_saved_preferences:true,has_saved_finite_preferences:true,preferences,...(view?{view_preferences:view}:{}),revision:saved.revision,default_proposal_verified:false,preference_source:'new-a-saved',request_id:b.request_id});
 }catch{return protectedReply(request,503,{error:'new_a_service_unavailable'});}
}
