(function(g){'use strict';
const specs=[['view_preferences','trial_preset','試算プリセット',['','defensive','balanced','profit']],['view_preferences','theme','テーマ',['dark','light','system']],['view_preferences','font_size','文字サイズ',['small','standard','large']],['view_preferences','page_size','1ページの件数',[20,50,100]],['preferences','price_cap_yen','株価上限（円）'],['preferences','exit_endpoint','比較する決済条件',['d5_close','d6_open','a20_close']],['preferences','base_shares','仮想株数'],['preferences','cost_percent','費用率（%）'],['preferences','year_scope','集計年',['all','2023','2024','2025','2026']],['preferences','allocation','配分方法',['all','unique','stacked']],['preferences','initial_cash_yen','仮想初期資金'],['preferences','max_positions','仮想同時保有上限'],['preferences','per_order_cap_yen','仮想1銘柄上限']];
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function state(){let saved=null,draft=null,busy=false;return {load:s=>{saved=structuredClone(s);draft=structuredClone(s);busy=false;},edit:(group,key,value)=>{if(busy||!saved)throw Error('locked');if(!specs.some(x=>x[0]===group&&x[1]===key))throw Error('field');draft[group][key]=value;},cancel:()=>{if(busy)throw Error('locked');draft=structuredClone(saved);return draft;},draft:()=>structuredClone(draft),begin:()=>{if(!saved||busy)throw Error('locked');busy=true;return {expected_revision:saved.revision,save_binding:saved.save_binding,preferences:draft.preferences,view_preferences:draft.view_preferences};},verify:s=>{if(!busy||s.revision!==saved.revision+1||!equal(s.preferences,draft.preferences)||!equal(s.view_preferences,draft.view_preferences))throw Error('receipt_mismatch');saved=structuredClone(s);draft=structuredClone(s);busy=false;},fail:()=>{busy=false;}};}
g.NewAMemberSettings={state,specs};if(typeof module!=='undefined')module.exports=g.NewAMemberSettings;
g.mountMemberSettings=async function(out,status,{signal,active,session,verifyAccess,accessDenied}){
 const model=state(),form=document.createElement('form'),inputs=[];const endpoint='/api/cloud/new-a-view/preferences';
 for(const [group,name,label,values]of specs){const l=document.createElement('label');l.textContent=label+' ';const f=document.createElement(values?'select':'input');if(values){for(const value of values){const o=document.createElement('option');o.value=String(value);o.textContent=String(value);f.append(o)}}else{f.type='number';f.step='any';}f.name=name;l.append(f);form.append(l);inputs.push({f,group,name,numeric:!values||name==='page_size'});}
 const save=document.createElement('button'),cancel=document.createElement('button');save.type='submit';save.textContent='自分の設定を保存';cancel.type='button';cancel.textContent='取消';form.append(save,cancel);out.replaceChildren(form);
 const lock=x=>{for(const {f}of inputs)f.disabled=x;save.disabled=cancel.disabled=x;};
 const paint=()=>{const d=model.draft();for(const {f,group,name}of inputs)f.value=d[group][name]??'';};
 async function request(options={}){
  const response=await fetch(endpoint,{credentials:'same-origin',cache:'no-store',redirect:'manual',signal,...options,
   headers:{...options.headers,'x-cloud-member-session':session}});
  const reauthenticate=response.type==='opaqueredirect'||response.status===401;
  if(reauthenticate||response.status===403){
   if(active())accessDenied(reauthenticate);
   throw Error('access_denied');
  }
  return response;
 }
 async function read(){
  const response=await request();
  if(!response.ok)throw Error('load');
  const saved=await response.json();
  if(!await verifyAccess())throw Error('access_denied');
  return saved;
 }
 async function reload(){
  lock(true);
  const saved=await read();
  if(!active())return;
  model.load(saved);
  paint();
  lock(false);
 }
 cancel.addEventListener('click',()=>{
  if(!active())return;
  model.cancel();
  paint();
  status.textContent='保存済みの設定に戻しました。';
 });
 form.addEventListener('submit',async event=>{
  event.preventDefault();
  if(!active()||save.disabled)return;
  for(const {f,group,name,numeric}of inputs)model.edit(group,name,f.value===''?null:numeric?Number(f.value):f.value);
  const body=model.begin();
  lock(true);
  status.textContent='保存中';
  try{
   const response=await request({method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
   if(!active())return;
   if(response.status===409){
    await reload();
    if(active())status.textContent='別の更新がありました。保存済み設定を再読込しました。';
    return;
   }
   if(!response.ok){
    model.fail();
    lock(false);
    status.textContent='保存できません。入力を保持しています。';
    return;
   }
   const saved=await read();
   if(!active())return;
   model.verify(saved);
   paint();
   lock(false);
   status.textContent='保存を確認しました。個別試算は準備でき次第反映します。';
  }catch{
    if(active()&&await verifyAccess()&&active())status.textContent='保存結果を確認できません。重複保存せず再読込してください。';
  }
 });
 await reload();
 if(active())status.textContent='自分の表示・仮想試算だけを変更します。';
};
})(globalThis);
