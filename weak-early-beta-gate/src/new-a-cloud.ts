// 現在の配信コードを変更せず、本人ゲートを通った新A経路だけを置き換える。
import { reportIdentity as migrationReportIdentity } from "./shared-report-gate";
import { cloudReportRole as migrationCloudReportRole } from "./cloud-role-authority";
import type { CloudEnv } from "./cloud-api";
import { createResearchAHandler, isResearchAPath } from "./research-a/owner-view.generated";
import { readResearchASnapshot } from "./new-a-data";
const PRIVATE = { 'cache-control':'private, no-store, max-age=0', vary:'Cookie', 'x-content-type-options':'nosniff',
 'referrer-policy':'no-referrer','cross-origin-resource-policy':'same-origin',
 'content-security-policy':"default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" };
const oldDocument = /^\/weak_early_beta_(?:latest|analytics|silence|dive|shadow|fusion|balance|guide)(?:_free)?\.html$/;
const oldAssets = /^(?:\/weak_early_beta_data_|\/weak-early-beta-|\/report-assets\/|\/report-interactions\.js$|\/report-theme-init\.js$)/;
function reply(request:Request,status:number,body:any,json=false){return new Response(request.method==='HEAD'?null:json?JSON.stringify(body):body,{status,headers:{...PRIVATE,'content-type':json?'application/json; charset=utf-8':'text/html; charset=utf-8'}});}
function ownedPath(path:string){return path==='/'||path==='/report'||isResearchAPath(path)||oldDocument.test(path)||oldAssets.test(path);}
export async function newACloudRoute(request:Request,env:CloudEnv):Promise<Response|null>{
  const url=new URL(request.url),path=url.pathname;
  // OAuth、セッション更新、D1設定等は現行の入口・実装へそのまま渡す。
  if(!ownedPath(path))return null;
  // この関数は現行index.tsのownerOnlyGateを通った後にだけ呼ばれる。
  const json=path.startsWith('/api/')||path.endsWith('.json');
  // 本人限定が現状どおり有効でなければ、新Aを出すことはない。
  if(env.CLOUD_OWNER_ONLY_ENABLED?.trim().toLowerCase()!=='true')return reply(request,503,json?{available:false,reason:'owner_mode_required'}:'Unavailable',json);
  if(!['GET','HEAD'].includes(request.method))return reply(request,405,'Method not allowed');
  if(request.headers.get('sec-fetch-site')==='cross-site'||(request.headers.get('origin')&&request.headers.get('origin')!==url.origin))return reply(request,403,'Forbidden');
  // 旧結果はバックアップと既存ASSETSに保全するが、新A画面からは配信しない。
  if(oldAssets.test(path))return reply(request,410,json?{available:false,reason:'legacy_asset_retained_offline'}:'Gone',json);
  if(oldDocument.test(path))return new Response(null,{status:302,headers:{...PRIVATE,location:'/research-a'}});
  try{
   const identity=await migrationReportIdentity(request,{...env,REPORT_ROLE_LOOKUP:(subject,token)=>migrationCloudReportRole(env,subject,token,'/research-a')},true);
   if(identity.reason==='refresh_required'){
    if(json)return reply(request,401,{authorized:false,reason:'refresh_required'},true);
    // 現行の/auth/guard.js→/auth/checkが既存Cookieを更新してから再表示する。
    return reply(request,200,'<!doctype html><html lang="ja" data-auth-recovery><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Discord認証確認</title><script src="/auth/guard.js" defer></script></head><body>Discord認証を確認しています。</body></html>');
   }
   if(identity.reason||!identity.subject)return reply(request,identity.reason==='login_required'?401:503,json?{authorized:false,reason:'authentication_unavailable'}:'Unavailable',json);
   if(identity.discord_authorized!==true)return reply(request,403,json?{authorized:false,reason:'role_required'}:'Forbidden',json);
   const target=new URL(request.url);if(path==='/'||path==='/report')target.pathname='/research-a';
   const snapshot=await readResearchASnapshot(env.CLOUD_DB);
   const handleResearchA=createResearchAHandler(snapshot);
   const result=handleResearchA(new Request(target,request));
   const headers=new Headers(result.headers);for(const[k,v]of Object.entries(PRIVATE))headers.set(k,v);
   const html=headers.get('content-type')?.startsWith('text/html');
   const body=request.method==='HEAD'?null:html?(await result.text()).replace('</head>','<script src="/auth/guard.js" defer></script></head>'):result.body;
   return new Response(body,{status:result.status,headers});
  }catch{return reply(request,503,json?{available:false,reason:'authentication_unavailable'}:'Unavailable',json);}
}
