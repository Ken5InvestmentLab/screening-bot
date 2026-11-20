/* Keep settings reads independent of the dashboard calculation. */
(function (g) {
 'use strict';
 const busy = state => ['loading','saving','calculating'].includes(state.phase);
 const defaultDisplay = {theme:'dark',font_size:'standard',page_size:20};
 g.mountOwnerSettings = async function(out,status,{
  transport,active, setBusy=()=>{},close,onSaved,onRevoked,
  dashboardPrices=false,recentAnalytics=false,
 }) {
  const ui = g.NewAMemberSettings.createForm(out,{showDisplay:true});
  function formValues(state) {
   return {
    preferences:state.draft,
    view_preferences:{...defaultDisplay,...state.viewPreferences,trial_preset:state.trialPreset},
   };
  }
  const controller = g.AFinite.createController({
   trialPreset:'balanced',calculateOnLoad:false,dashboardPrices,recentAnalytics,transport,
   onChange(state) {
    if (!active()) return;
    if (state.phase === 'denied' || state.phase === 'session-changed') { onRevoked(); return; }
    ui.lock(busy(state) || state.revision === null);
    setBusy(state.phase === 'saving');
    status.dataset.state = state.phase === 'error' ? 'error' : '';
    status.textContent = state.message;
    if (state.phase === 'ready' && !state.dirty) ui.paint(formValues(state));
   },
  });
  ui.cancel.addEventListener('click',() => {
   if (!active() || ui.cancel.disabled) return;
   if (close) return close();
   controller.cancel();
   ui.paint(formValues(controller.state()));
  });
  ui.form.addEventListener('submit',async event => {
   event.preventDefault();
   if (!active() || ui.save.disabled) return;
   const previous = controller.state();
   const draft = formValues(previous);
   for (const [group,key,value] of ui.edits()) draft[group][key]=value;
   try {
    const trialChanged = previous.trialPreset !== draft.view_preferences.trial_preset
     || Object.entries(draft.preferences).some(([key,value]) => previous.applied[key] !== value);
    controller.edit(draft.preferences);
    if (await controller.save(draft.view_preferences) && active()) onSaved(controller.state(),trialChanged);
   } catch (error) {
    if (!active()) return;
    status.dataset.state = 'error';
    status.textContent = error.message;
   }
  });
  if (!await controller.load() && active()) throw Error('settings_load_failed');
 };
})(globalThis);
