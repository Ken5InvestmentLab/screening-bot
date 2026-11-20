/* Keep Help and Settings in the current page. */
(function (g) {
 'use strict';
 if (typeof document === 'undefined') return;
 function bindClose(dialog, button, close) {
  button.addEventListener('click',close);
  dialog.addEventListener('cancel',event => { event.preventDefault(); close(); });
  dialog.addEventListener('click',event => {
   if (event.target !== dialog) return;
   const bounds = dialog.getBoundingClientRect();
   if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
  });
 }
 const help = document.getElementById('cloud-help-dialog');
 if (help && typeof help.showModal === 'function') {
  const trigger = document.getElementById('cloud-help-open');
  const button = document.getElementById('cloud-help-close');
  trigger.addEventListener('click',() => {
   if (trigger.hidden || help.open) return;
   help.showModal();
   button.focus();
  });
  bindClose(help,button,() => help.close());
  help.addEventListener('close',() => {
   if (trigger.isConnected && !trigger.hidden) trigger.focus({ preventScroll:true });
  });
 }
 const dialog = document.getElementById('cloud-settings-dialog');
 if (!dialog || typeof dialog.showModal !== 'function') return;
 const content = document.getElementById('cloud-settings-content');
 const status = document.getElementById('cloud-settings-status');
 const closeButton = document.getElementById('cloud-settings-close');
 const retry = document.getElementById('cloud-settings-retry');
 let current = null;
 function confirmLeave(event) {
  event.preventDefault();
  event.returnValue = true;
 }
 function setBusy(busy) {
  closeButton.disabled = busy;
  if (busy) g.addEventListener('beforeunload', confirmLeave);
  else g.removeEventListener('beforeunload', confirmLeave);
 }
 function finish() {
  if (!current) return;
  const { controller, trigger } = current;
  current = null;
  controller.abort();
  setBusy(false);
  content.replaceChildren();
  status.textContent = '';
  retry.hidden = true;
  if (trigger.isConnected && !trigger.hidden) trigger.focus({ preventScroll:true });
 }
 function close(force = false) {
  if (!current || (closeButton.disabled && !force)) return false;
  if (dialog.open) dialog.close();
  finish();
  return true;
 }
 bindClose(dialog,closeButton,() => close());
 dialog.addEventListener('close', () => { if (!dialog.open) finish(); });
 function connect(mount, canOpen = () => true) {
  document.addEventListener('click', event => {
   const trigger = event.target.closest?.('a[href="./weak_early_beta_settings.html"]');
   if (!trigger || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !canOpen()) return;
   event.preventDefault();
   if (current) return;
   function load() {
    current?.controller.abort();
    const job = { trigger, controller: new AbortController() };
    current = job;
    const active = () => current === job && dialog.open && !job.controller.signal.aborted;
    content.replaceChildren();
    retry.hidden = true;
    setBusy(false);
    status.textContent = '設定を読み込んでいます。';
    if (!dialog.open) {
     dialog.showModal();
     closeButton.focus();
    }
    Promise.resolve().then(() => mount(content, status, {
     active, signal: job.controller.signal, setBusy: busy => { if (active()) setBusy(busy); },
     close: () => { if (active()) close(); },
    })).catch(() => {
     if (!active()) return;
     status.textContent = '設定を読み込めませんでした。';
     retry.hidden = false;
    });
   }
   retry.onclick = load;
   load();
  });
 }
 g.CloudSettingsDialog = { connect, close };
})(globalThis);
