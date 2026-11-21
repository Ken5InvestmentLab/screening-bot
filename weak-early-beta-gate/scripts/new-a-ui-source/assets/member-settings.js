/* Account settings common to the current Cloud trial and display. */
(function (g) {
 'use strict';
 const specs = [
  { group:'preferences', key:'initial_cash_yen', label:'初期資金（円）', min:1, max:1e12, step:1 },
  { group:'preferences', key:'max_positions', label:'同時保有上限（銘柄）', min:1, max:1000, step:1 },
  { group:'preferences', key:'per_order_cap_yen', label:'1注文の購入上限（円）', min:1, max:1e12, step:1 },
  { group:'preferences', key:'cost_percent', label:'売買手数料（片道％）', min:0, max:10, step:.01 },
  { group:'view_preferences', key:'theme', label:'テーマ', display:true, options:[
   ['dark','ダーク'], ['light','ライト'], ['system','端末に合わせる'],
  ] },
  { group:'view_preferences', key:'font_size', label:'文字サイズ', display:true, options:[
   ['small','小さめ'], ['standard','標準'], ['large','大きめ'],
  ] },
  { group:'view_preferences', key:'page_size', label:'一覧件数', display:true, options:[
   [20,'20件'], [50,'50件'], [100,'100件'],
  ] },
 ];
 const equal = (a,b) => JSON.stringify(a) === JSON.stringify(b);
 function state() {
  let saved = null, draft = null, busy = false;
  return {
   load(s) { saved = structuredClone(s); draft = structuredClone(s); busy = false; },
   edit(group,key,value) {
    if (busy || !saved) throw Error('locked');
    if (!specs.some(item => item.group === group && item.key === key)) throw Error('field');
    draft[group][key] = value;
   },
   cancel() {
    if (busy) throw Error('locked');
    draft = structuredClone(saved);
    return draft;
   },
   draft: () => structuredClone(draft),
   begin() {
    if (!saved || busy) throw Error('locked');
    busy = true;
    return { expected_revision:saved.revision, save_binding:saved.save_binding,
     preferences:draft.preferences, view_preferences:draft.view_preferences };
   },
   verify(s) {
    if (!busy || s.revision !== saved.revision + 1 || !equal(s.preferences,draft.preferences)
      || !equal(s.view_preferences,draft.view_preferences)) throw Error('receipt_mismatch');
    saved = structuredClone(s); draft = structuredClone(s); busy = false;
   },
   fail() { busy = false; },
  };
 }
 function createForm(out,{showDisplay=false}={}) {
  const form = document.createElement('form');
  form.className = 'cloud-settings-current';
  const trial = document.createElement('div');
  trial.className = 'filters';
  const display = showDisplay ? document.createElement('div') : null;
  if (display) {
   const tablist = document.createElement('div');
   tablist.className = 'settings-tabs';
   tablist.setAttribute('role','tablist');
   tablist.setAttribute('aria-label','設定の項目');
   display.className = 'filters';
   const tabs = [['trial','試算方法',trial],['display','表示',display]].map(([key,label,panel]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'cloud-setting-tab-' + key;
    button.textContent = label;
    button.setAttribute('role','tab');
    button.setAttribute('aria-controls','cloud-setting-pane-' + key);
    panel.id = 'cloud-setting-pane-' + key;
    panel.setAttribute('role','tabpanel');
    panel.setAttribute('aria-labelledby',button.id);
    tablist.append(button);
    return { button,panel };
   });
   function selectTab(selected) {
    for (const item of tabs) {
     item.button.setAttribute('aria-selected',String(item === selected));
     item.button.tabIndex = item === selected ? 0 : -1;
     item.panel.hidden = item !== selected;
    }
   }
   for (const [i,item] of tabs.entries()) {
    item.button.addEventListener('click',() => selectTab(item));
    item.button.addEventListener('keydown',event => {
     if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
     event.preventDefault();
     const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[1-i];
     selectTab(next);
     next.button.focus();
    });
   }
   form.append(tablist,trial,display);
   selectTab(tabs[0]);
  } else {
   form.append(trial);
  }
  const fields = specs.filter(spec => showDisplay || !spec.display).map(spec => {
   const label = document.createElement('label');
   label.className = 'filter-field';
   const caption = document.createElement('span');
   caption.textContent = spec.label;
   const field = document.createElement(spec.options ? 'select' : 'input');
   field.name = spec.key;
   if (spec.options) {
    for (const [value, text] of spec.options) {
     const option = document.createElement('option');
     option.value = String(value);
     option.textContent = text;
     field.append(option);
    }
   } else {
    field.type = 'number';
    field.required = true;
    field.min = String(spec.min);
    field.max = String(spec.max);
    field.step = String(spec.step);
    field.inputMode = spec.step === 1 ? 'numeric' : 'decimal';
   }
   label.append(caption,field);
   (spec.display ? display : trial).append(label);
   return { spec, field };
  });
  const actions = document.createElement('div');
  actions.className = 'settings-actions';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'settings-secondary';
  cancel.textContent = 'キャンセル';
  const save = document.createElement('button');
  save.type = 'submit';
  save.className = 'settings-primary';
  save.textContent = '設定を保存';
  actions.append(cancel,save);
  form.append(actions);
  out.replaceChildren(form);
  return {
   form, cancel, save,
   lock(locked) {
    for (const {field} of fields) field.disabled = locked;
    save.disabled = cancel.disabled = locked;
   },
   paint(saved) {
    for (const {spec,field} of fields) {
     const value = saved[spec.group][spec.key];
     field.value = value ?? '';
    }
   },
   edits() {
    return fields.map(({spec,field}) => {
     const value = field.value === '' ? null : !spec.options || spec.key === 'page_size' ? Number(field.value) : field.value;
     return [spec.group,spec.key,value];
    });
   },
  };
 }
 g.NewAMemberSettings = { state, specs, createForm };
 if (typeof module !== 'undefined') module.exports = g.NewAMemberSettings;
 g.mountMemberSettings = async function(out,status,{ signal,active,session,verifyAccess,accessDenied,setBusy=()=>{},close,
    onLoaded=()=>{},onSaved=()=>{} }) {
  const model = state();
  const ui = createForm(out,{showDisplay:true});
  const endpoint = '/api/cloud/new-a-view/preferences';
  async function request(options = {}) {
   const response = await fetch(endpoint,{ credentials:'same-origin',cache:'no-store',redirect:'manual',signal,
    ...options,headers:{...options.headers,'x-cloud-member-session':session} });
   const reauthenticate = response.type === 'opaqueredirect' || response.status === 401;
   if (reauthenticate || response.status === 403) {
    if (active()) accessDenied(reauthenticate);
    throw Error('access_denied');
   }
   return response;
  }
  async function read() {
   const response = await request();
   if (!response.ok) throw Error('load');
   const saved = await response.json();
   if (!active() || !await verifyAccess()) throw Error('access_denied');
   return saved;
  }
  async function reload() {
   ui.lock(true);
   const saved = await read();
   if (!active()) return;
   model.load(saved);
   ui.paint(saved);
   ui.lock(false);
   onLoaded(saved);
  }
  ui.cancel.addEventListener('click',() => {
   if (!active()) return;
   if (close) return close();
   ui.paint(model.cancel());
   status.textContent = '';
  });
  ui.form.addEventListener('submit',async event => {
   event.preventDefault();
   if (!active() || ui.save.disabled) return;
   for (const [group,key,value] of ui.edits()) model.edit(group,key,value);
   const body = model.begin();
   ui.lock(true);
   setBusy(true);
   status.textContent = '設定を保存しています。';
   try {
    const response = await request({ method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(body) });
    if (!active()) return;
    if (response.status === 409) {
     await reload();
     if (active()) status.textContent = '別の更新がありました。保存済みの設定を読み直しました。';
     return;
    }
    if (!response.ok) {
     model.fail();
     ui.lock(false);
     status.textContent = '保存できませんでした。入力内容を保持しています。';
     return;
    }
    const saved = await read();
    if (!active()) return;
    model.verify(saved);
    ui.paint(saved);
    ui.lock(false);
    onSaved(saved);
    status.textContent = '設定を保存しました。';
   } catch {
    if (active() && await verifyAccess() && active()) status.textContent = '保存結果を確認できませんでした。開き直して確認してください。';
   } finally {
    if (active()) setBusy(false);
   }
  });
  await reload();
  if (active()) status.textContent = '';
 };
})(globalThis);
