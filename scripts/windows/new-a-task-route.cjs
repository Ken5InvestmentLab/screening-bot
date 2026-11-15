// 既存task-entryへ差し込む新A契約確認。タスク定義・時刻・設定は変更しない。
'use strict';
const ENTRY='new-a-verified-daily-v1';
function newATaskPlan(task,date,prior,existingRecoveryPlan){
 if(task==='cloud-5')return {action:'separate-reminder',entry:null};
 if(!['cloud-2','cloud-3'].includes(task))throw Error('unexpected_daily_task');
 if(prior?.date===date&&prior.ok===true&&prior.businessDay===false&&prior.skipped==='bank_holiday')return{action:'complete',entry:ENTRY,marketClosed:true};
 if(prior?.date===date){
  if(prior.new_a?.entry!==ENTRY||prior.new_a?.strategy!=='A_BASE')return {action:'reconcile',entry:ENTRY,reason:'Existing same-day legacy or unknown receipt is not proof of New A completion'};
  if(prior.ok===true&&(!/^[a-f0-9]{64}$/.test(prior.new_a.snapshot_sha256||'')||prior.new_a.owner_publication_verified!==true))return {action:'reconcile',entry:ENTRY,reason:'New A completion lacks verified owner publication'};
 }
 return {...existingRecoveryPlan(prior,date),entry:ENTRY};
}
module.exports={newATaskPlan,ENTRY};
