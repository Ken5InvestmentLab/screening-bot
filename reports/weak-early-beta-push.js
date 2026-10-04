(function () {
  'use strict';
  const host = document.getElementById('cloud-notification-settings');
  if (!host) return;
  const panel = document.createElement('div');
  const status = document.createElement('p');
  status.id = 'cloud-device-status'; status.setAttribute('role', 'status');
  status.textContent = '端末へのプッシュ通知は現在利用できません。';
  const register = document.createElement('button');
  register.type = 'button'; register.id = 'cloud-device-register'; register.textContent = 'この端末を登録'; register.hidden = true;
  const revoke = document.createElement('button');
  revoke.type = 'button'; revoke.id = 'cloud-device-revoke'; revoke.textContent = 'この端末の登録を解除'; revoke.hidden = true;
  panel.append(status, register, revoke); host.append(panel);
  let busy = false, current = null, readyConfig = null;
  const supported = () => window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  async function api(path, method, body) {
    const response = await fetch(path, { method: method || 'GET', credentials: 'same-origin', cache: 'no-store',
      headers: body ? { 'content-type': 'application/json' } : { accept: 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const value = await response.json();
    if (!response.ok || !value.ok) throw new Error('unavailable');
    return value;
  }
  async function hash(endpoint) {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(endpoint));
    return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
  }
  async function ownedDevice(config) {
    // Read an existing registration; loading this page never registers a worker.
    const existing = await navigator.serviceWorker.getRegistration('./');
    const subscription = existing && await existing.pushManager.getSubscription();
    if (!subscription) return null;
    const digest = await hash(subscription.endpoint);
    const device = (config.devices || []).find(row => row.endpoint_hash === digest);
    return device ? { id: device.subscription_id, subscription } : null;
  }
  async function refresh() {
    register.hidden = true; revoke.hidden = true;
    try {
      const config = await api('/api/cloud/push-config');
      readyConfig = config.registration_available ? config : null;
      if (!supported()) { status.textContent = 'このブラウザでは端末へのプッシュ登録を利用できません。'; return; }
      current = await ownedDevice(config);
      revoke.hidden = !current;
      register.hidden = !config.registration_available || Boolean(current);
      status.textContent = current ? 'この端末は登録済みです。通知配信は現在利用できません。' :
        config.registration_available ? '通知配信は現在利用できません。端末登録はボタン操作と許可が必要です。' : '端末へのプッシュ通知は現在利用できません。';
    } catch (_) { readyConfig = null; status.textContent = '端末へのプッシュ通知は現在利用できません。'; }
  }
  register.addEventListener('click', async () => {
    if (busy || !supported()) return;
    busy = true; register.disabled = true;
    let subscription, created = false;
    try {
      if (!readyConfig || typeof readyConfig.public_key !== 'string') throw new Error('unavailable');
      // Invoke permission directly in the click task, before a network await.
      // Server eligibility is repeated below and again before subscription save.
      if (await Notification.requestPermission() !== 'granted') throw new Error('permission_denied');
      const config = await api('/api/cloud/push-config');
      if (!config.registration_available || typeof config.public_key !== 'string') throw new Error('unavailable');
      const worker = await navigator.serviceWorker.register('./weak-early-beta-service-worker.js', { scope: './', updateViaCache: 'none' });
      await navigator.serviceWorker.ready;
      subscription = await worker.pushManager.getSubscription();
      if (!subscription) {
        const key = Uint8Array.from(atob(config.public_key.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
        subscription = await worker.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }); created = true;
      }
      await api('/api/cloud/push-subscriptions', 'POST', { opt_in: true, subscription: subscription.toJSON() });
      await refresh();
    } catch (_) {
      if (created && subscription) try { await subscription.unsubscribe(); } catch (_) {}
      status.textContent = '端末を登録できませんでした。会員資格・通知許可・接続状態を確認してください。';
    } finally { busy = false; register.disabled = false; }
  });
  revoke.addEventListener('click', async () => {
    if (busy || !current) return;
    busy = true; revoke.disabled = true;
    try {
      await api('/api/cloud/push-subscriptions/device', 'DELETE', { subscription_id: current.id });
      // Server revocation takes precedence. Browser failure does not restore it.
      let removed = false;
      try { removed = await current.subscription.unsubscribe(); } catch (_) {}
      current = null; await refresh();
      status.textContent = removed ? 'この端末の登録を解除しました。' : 'サーバー側の端末登録を解除しました。ブラウザ側の解除を確認してください。';
    } catch (_) { status.textContent = '端末の登録を解除できませんでした。接続状態を確認してください。'; }
    finally { busy = false; revoke.disabled = false; }
  });
  // Explicit opt-in only; no localStorage dependency and no permission prompt.
  void refresh();
})();
