(function (global) {
  'use strict';
  const endpoint = '/api/cloud/new-a-finite/notification-preferences';
  async function mount({ document, window, fetch, loadPush }) {
    const byId = id => document.getElementById(id);
    const section = byId('new-a-notification-settings');
    if (!section || window.AFiniteRevoked) return;
    const host = byId('new-a-notification-device');
    const register = byId('new-a-notification-register');
    const options = byId('new-a-notification-opt-in');
    const status = byId('new-a-notification-status');
    const save = byId('new-a-notification-save');
    const retry = byId('new-a-notification-retry');
    const inputs = { new_detection: byId('new-a-notify-detection'), reminder: byId('new-a-notify-reminder') };
    let stored = null;
    let available = false;
    let pushLoaded = false;
    let confirmed = false;
    let busy = false;
    let eligible = false;
    const readDraft = () => ({ new_detection: inputs.new_detection.checked, reminder: inputs.reminder.checked });
    const changes = (a, b) => a.new_detection !== b.new_detection || a.reminder !== b.reminder;
    const enables = (next, previous) => (next.new_detection && !previous.new_detection) || (next.reminder && !previous.reminder);

    function sync() {
      const active = available && pushLoaded && !busy && !window.AFiniteRevoked;
      register.disabled = !active || !eligible || confirmed;
      options.disabled = !active;
      save.disabled = !active || !stored || !changes(readDraft(), stored);
      retry.disabled = busy;
    }
    function restore(notifications) {
      stored = notifications;
      inputs.new_detection.checked = notifications.new_detection;
      inputs.reminder.checked = notifications.reminder;
    }
    async function request(notifications) {
      const response = await fetch(endpoint, {
        method: notifications ? 'PUT' : 'GET', credentials: 'same-origin', cache: 'no-store',
        headers: notifications ? { 'content-type': 'application/json' } : { accept: 'application/json' },
        ...(notifications && { body: JSON.stringify({ notifications }) }),
      });
      const result = await response.json();
      if (!response.ok || result.ok !== true || typeof result.available !== 'boolean' ||
          typeof result.notifications?.new_detection !== 'boolean' || typeof result.notifications?.reminder !== 'boolean') {
        throw new Error('notification_preferences_unavailable');
      }
      return result;
    }
    async function refresh() {
      if (busy || window.AFiniteRevoked) return;
      busy = true;
      retry.hidden = true;
      sync();
      try {
        const result = await request();
        if (window.AFiniteRevoked) return;
        restore(result.notifications);
        available = result.available;
        if (available && !pushLoaded) {
          // The legacy interactions already booted. Give only the push script its established host.
          host.id = 'cloud-notification-settings';
          await loadPush();
          // The inherited manual action starts hidden. Detach it before it can be used on this page.
          byId('cloud-device-test')?.remove();
          pushLoaded = true;
        }
        status.textContent = available ? '' : 'プッシュ通知は現在利用できません。';
      } catch (_) {
        available = false;
        retry.hidden = false;
        status.textContent = '通知設定を読み込めませんでした。';
      } finally {
        busy = false;
        sync();
      }
    }
    window.addEventListener('cloud-notification-membership', event => {
      eligible = event.detail?.notification_eligible === true;
      if (!eligible) confirmed = false;
      sync();
    });
    register.addEventListener('click', async () => {
      if (register.disabled || window.AFiniteRevoked) return;
      busy = true;
      status.textContent = '';
      sync();
      const verified = await new Promise(resolve => {
        const detail = { complete: resolve };
        // Dispatch from the button click, before any network await or permission prompt.
        window.dispatchEvent(new window.CustomEvent('cloud-notification-enable', { detail }));
        if (!detail.handled) resolve(false);
      });
      if (verified && !window.AFiniteRevoked) {
        confirmed = true;
        status.textContent = 'この端末の登録を確認しました。';
      }
      busy = false;
      sync();
    });
    options.addEventListener('change', sync);
    save.addEventListener('click', async () => {
      if (save.disabled || window.AFiniteRevoked) return;
      const next = readDraft();
      if (enables(next, stored) && !confirmed) {
        status.textContent = '通知を有効にするには、この端末を登録してください。';
        register.focus();
        return;
      }
      busy = true;
      status.textContent = '';
      sync();
      try {
        const saved = await request(next);
        if (window.AFiniteRevoked) return;
        if (!saved.available || changes(saved.notifications, next)) throw new Error('notification_preferences_save_unconfirmed');
        restore(saved.notifications);
        status.textContent = '通知設定を保存しました。';
      } catch (_) {
        status.textContent = '通知設定の保存を確認できませんでした。';
      } finally {
        busy = false;
        sync();
      }
    });
    retry.addEventListener('click', refresh);
    section.hidden = false;
    await refresh();
  }
  const api = { mount };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else global.AOwnerNotifications = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
