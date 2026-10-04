(function () {
  'use strict';
  const host = document.getElementById('cloud-notification-settings');
  if (!host) return;
  const panel = document.createElement('div');
  const status = document.createElement('p');
  status.id = 'cloud-device-status'; status.setAttribute('role', 'status');
  status.textContent = '端末へのプッシュ通知は現在利用できません。';
  const provider = document.createElement('p');
  provider.id = 'cloud-device-provider-origin'; provider.hidden = true;
  const permission = document.createElement('p');
  permission.id = 'cloud-device-permission';
  const register = document.createElement('button');
  register.type = 'button'; register.id = 'cloud-device-register'; register.textContent = 'この端末で通知を受け取る'; register.disabled = true;
  const revoke = document.createElement('button');
  revoke.type = 'button'; revoke.id = 'cloud-device-revoke'; revoke.textContent = 'この端末の通知登録を解除'; revoke.hidden = true;
  const test = document.createElement('button');
  test.type = 'button'; test.id = 'cloud-device-test'; test.textContent = 'この端末へテスト通知'; test.hidden = true;
  panel.append(register, permission, status, provider); host.prepend(panel);
  const actions = document.createElement('div'); actions.append(test, revoke); host.append(actions);
  let busy = false, current = null, readyConfig = null, verified = false;
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
    return { id: device ? device.subscription_id : null, subscription, serverRevoked: !device };
  }
  function render() {
    const registered = Boolean(verified && current && current.id);
    const browserPermission = typeof Notification === 'undefined' ? 'unavailable' : Notification.permission;
    register.hidden = false;
    register.textContent = current?.id && !verified ? '登録状態を確認できません' : registered ? '登録済み' : 'この端末で通知を受け取る';
    register.disabled = busy || Boolean(current?.id) || !readyConfig || browserPermission === 'denied';
    revoke.hidden = false; revoke.disabled = busy || !current;
    test.hidden = !registered || !readyConfig?.personal_test_available || current.id !== readyConfig.personal_test_subscription_id || browserPermission === 'denied';
    test.disabled = busy;
    permission.textContent = !supported() ? 'このブラウザはプッシュ通知に対応していません。' :
      browserPermission === 'granted' ? 'ブラウザの通知許可：許可済み。端末登録とは別の設定です。' :
      browserPermission === 'denied' ? 'ブラウザの通知許可：拒否。通知を受け取るにはブラウザ側で許可してください。' : 'ブラウザの通知許可：未設定。端末登録時に確認します。';
  }
  async function refresh() {
    try {
      const config = await api('/api/cloud/push-config');
      readyConfig = config.registration_available || config.preparation_available ? config : null;
      if (!supported()) { readyConfig = null; render(); status.textContent = 'このブラウザでは端末へのプッシュ登録を利用できません。'; return true; }
      current = await ownedDevice(config);
      verified = true;
      render();
      status.textContent = current && current.id ? 'この端末は登録済みです。通知ON／OFFは「設定を保存」で反映し、OFFでも登録は残ります。通常配信はまだ開始していません。' : current ? 'ブラウザ側の登録が残っています。受け取り登録、またはこの端末の解除を行えます。' :
        readyConfig ? 'この端末の通知登録にはボタン操作と許可が必要です。' : '端末へのプッシュ通知は現在利用できません。';
      return true;
    } catch (_) { readyConfig = null; verified = false; render(); status.textContent = '端末登録の状態を確認できません。接続状態を確認してください。'; return false; }
  }
  register.addEventListener('click', async () => {
    if (busy || !supported()) return;
    busy = true; register.disabled = true;
    let subscription, created = false, saveAttempted = false;
    try {
      if (!readyConfig || typeof readyConfig.public_key !== 'string') throw new Error('unavailable');
      // Invoke permission directly in the click task, before a network await.
      // Server eligibility is repeated below and again before subscription save.
      if (Notification.permission !== 'granted' && await Notification.requestPermission() !== 'granted') throw new Error('permission_denied');
      const config = await api('/api/cloud/push-config');
      if (!(config.registration_available || config.preparation_available) || typeof config.public_key !== 'string') throw new Error('unavailable');
      const worker = await navigator.serviceWorker.register('./weak-early-beta-service-worker.js', { scope: './', updateViaCache: 'none' });
      await navigator.serviceWorker.ready;
      subscription = await worker.pushManager.getSubscription();
      if (!subscription) {
        const key = Uint8Array.from(atob(config.public_key.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
        subscription = await worker.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }); created = true;
      }
      const origin = new URL(subscription.endpoint).origin;
      if (!config.registration_available || !(config.allowed_origins || []).includes(origin)) {
        // Retain this browser-only preparation for the same explicit retry after
        // operator approval. Never persist endpoint/key material or widen origins.
        provider.textContent = '通知サービスのorigin: ' + origin; provider.hidden = false;
        status.textContent = '通知サービスの確認待ちです。確認後にこの端末を登録してください。';
        return;
      }
      saveAttempted = true;
      const saved = await api('/api/cloud/push-subscriptions', 'POST', { opt_in: true, subscription: subscription.toJSON() });
      current = { id: saved.subscription_id || null, subscription, serverRevoked: false };
      provider.hidden = true;
      if (!await refresh()) throw new Error('registration_confirmation_failed');
    } catch (_) {
      // A lost save response may already have persisted this endpoint. Retain
      // browser preparation for an explicit, idempotent registration retry.
      if (created && subscription && !saveAttempted) try { await subscription.unsubscribe(); } catch (_) {}
      if (!current && subscription && saveAttempted) current = { id: null, subscription, serverRevoked: false };
      verified = false;
      status.textContent = '端末を登録できませんでした。会員資格・通知許可・接続状態を確認してください。';
    } finally { busy = false; render(); }
  });
  revoke.addEventListener('click', async () => {
    if (busy || !current) return;
    busy = true; revoke.disabled = true;
    try {
      if (current.id) await api('/api/cloud/push-subscriptions/device', 'DELETE', { subscription_id: current.id });
      // Server revocation takes precedence. Browser failure does not restore it.
      current.id = null; current.serverRevoked = true; render();
      await current.subscription.unsubscribe();
      const worker = await navigator.serviceWorker.getRegistration('./');
      if (worker && await worker.pushManager.getSubscription()) throw new Error('browser_revocation_incomplete');
      current = null;
      if (!await refresh()) throw new Error('revocation_confirmation_failed');
      status.textContent = 'この端末の通知登録を解除しました。ブラウザの通知許可は変わりません。';
    } catch (_) { status.textContent = current?.serverRevoked ? 'サーバー側は解除済みですが、ブラウザ側の解除は未完了です。もう一度解除してください。' : 'この端末の通知登録の解除を確認できません。完了していません。接続状態を確認してください。'; }
    finally { busy = false; render(); }
  });
  test.addEventListener('click', async () => {
    if (busy || test.hidden || !current) return;
    busy = true; test.disabled = true;
    try {
      const result = await api('/api/cloud/notifications/personal-test', 'POST', {});
      status.textContent = result.status === 'accepted' ? '配信サービスが受け付けました。Windowsの通知表示を確認してください。' :
        result.status === 'unknown' ? '送信結果を確認できません。再送せずWindowsの通知表示を確認してください。' :
        result.status === 'suppressed' ? 'このテストは送信済み、または結果確認中です。Windowsの通知表示を確認してください。' :
        result.reason === 'notification_opt_in_required' ? '通知設定がOFFのため、送信を停止しました。' :
        result.reason === 'fresh_discord_role_unavailable' ? 'Discordの通知資格を新規照会できなかったため、送信を停止しました。' :
        result.reason === 'fresh_discord_role_required' ? '必要なDiscordロールを確認できなかったため、送信を停止しました。' :
        'テスト通知を送れませんでした。会員資格・通知設定・端末登録を確認してください。';
    } catch (_) { status.textContent = 'テスト通知の結果を確認できません。再送せずWindowsの通知表示を確認してください。'; }
    finally { busy = false; test.disabled = false; }
  });
  // Explicit opt-in only; no localStorage dependency and no permission prompt.
  void refresh();
})();
