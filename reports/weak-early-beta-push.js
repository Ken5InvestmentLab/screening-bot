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
  const registration = document.createElement('p');
  registration.id = 'cloud-device-registration';
  const instruction = document.createElement('p');
  instruction.id = 'cloud-device-instruction'; instruction.textContent = '通知を受け取りたい端末で設定してください。';
  const test = document.createElement('button');
  test.type = 'button'; test.id = 'cloud-device-test'; test.textContent = 'この端末へテスト通知'; test.hidden = true;
  const eligibility = document.createElement('div'); eligibility.id = 'cloud-notification-eligibility';
  const eligibilityStatus = document.createElement('p'); eligibilityStatus.id = 'cloud-notification-eligibility-status'; eligibilityStatus.setAttribute('role', 'status');
  const retry = document.createElement('button'); retry.type = 'button'; retry.id = 'cloud-notification-retry'; retry.textContent = '再試行'; retry.hidden = true;
  eligibility.append(eligibilityStatus, retry);
  panel.append(registration, instruction, permission, status, provider, eligibility); host.prepend(panel);
  const actions = document.createElement('div'); actions.append(test); host.append(actions);
  let busy = false, current = null, readyConfig = null, verified = false;
  const qualificationMessage = reason => ({
    refresh_required: 'もう一度ログインしてください。',
    login_required: 'このブラウザでDiscordにログインしてください。',
    personal_test_member_required: '本人テスト用のDiscordアカウントでログインしてください。',
    discord_role_lookup_401: 'もう一度ログインしてください。',
  }[reason] || '通知を利用できません。時間を置いて再試行してください。');
  function showEligibility(membership, notificationEligible = false) {
    eligibility.hidden = !membership || notificationEligible === true;
    retry.hidden = !membership || notificationEligible === true;
    eligibilityStatus.textContent = membership && !notificationEligible ? '通知を利用できません。再試行してください。' : '';
    if (typeof CustomEvent === 'function') window.dispatchEvent?.(new CustomEvent('cloud-notification-membership', { detail: { membership, notification_eligible: notificationEligible === true } }));
  }
  const supported = () => window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  async function api(path, method, body) {
    const response = await fetch(path, { method: method || 'GET', credentials: 'same-origin', cache: 'no-store',
      headers: body ? { 'content-type': 'application/json' } : { accept: 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const value = await response.json();
    if (!response.ok || !value.ok) throw new Error(qualificationMessage(value.membership?.reason || value.reason));
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
    registration.textContent = current?.id && !verified ? '登録状態を確認できません' : registered ? '登録済み' : '';
    test.hidden = !registered || !readyConfig?.personal_test_available || current.id !== readyConfig.personal_test_subscription_id || browserPermission === 'denied';
    test.disabled = busy;
    retry.disabled = busy;
    permission.textContent = !supported() ? 'このブラウザはプッシュ通知に対応していません。' :
      browserPermission === 'denied' ? '通知が拒否されています。ブラウザ設定で許可してください。' : '';
  }
  async function refresh() {
    readyConfig = null; showEligibility(null); render();
    try {
      const config = await api('/api/cloud/push-config');
      showEligibility(config.membership, config.notification_eligible ?? config.membership?.status === 'paid');
      readyConfig = config.registration_available || config.preparation_available ? config : null;
      if (!supported()) { readyConfig = null; render(); status.textContent = 'このブラウザでは端末へのプッシュ登録を利用できません。'; return true; }
      current = await ownedDevice(config);
      verified = true;
      render();
      status.textContent = current && current.id ? '' : current ? '端末登録が残っています。再登録、または解除できます。' :
        readyConfig || !config.notification_eligible ? '' : qualificationMessage(config.reason);
      return true;
    } catch (error) { readyConfig = null; verified = false; showEligibility({status:'unavailable'}); render(); status.textContent = ''; return false; }
  }
  retry.addEventListener('click', async () => {
    if (busy) return;
    busy = true; render();
    try { await refresh(); } finally { busy = false; render(); }
  });
  async function registerDevice() {
    if (busy || !supported() || Notification.permission === 'denied') return false;
    if (verified && current?.id) return true;
    busy = true; render();
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
        return false;
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
      status.textContent = '端末を登録できませんでした。通知許可・接続状態を確認してください。';
    } finally { busy = false; render(); }
    return Boolean(verified && current?.id);
  }
  window.addEventListener?.('cloud-notification-enable', event => {
    if (typeof event.detail?.complete !== 'function') return;
    event.detail.handled = true;
    // The switch's user event invokes this before any await, preserving the
    // browser activation needed by Notification.requestPermission().
    void registerDevice().then(event.detail.complete, () => event.detail.complete(false));
  });
  async function revokeDevice() {
    if (busy) return false;
    if (!verified && !await refresh()) return false;
    if (!current) return true;
    busy = true; render();
    try {
      if (current.id) await api('/api/cloud/push-subscriptions/device', 'DELETE', { subscription_id: current.id });
      // Server revocation takes precedence. Browser failure does not restore it.
      current.id = null; current.serverRevoked = true; render();
      await current.subscription.unsubscribe();
      const worker = await navigator.serviceWorker.getRegistration('./');
      if (worker && await worker.pushManager.getSubscription()) throw new Error('browser_revocation_incomplete');
      current = null;
      if (!await refresh()) throw new Error('revocation_confirmation_failed');
      status.textContent = '';
    } catch (_) { status.textContent = current?.serverRevoked ? 'この端末の解除が未完了です。「設定を保存」で再試行してください。' : 'この端末の解除を確認できません。「設定を保存」で再試行してください。'; return false; }
    finally { busy = false; render(); }
    return true;
  }
  window.addEventListener?.('cloud-notification-disable', event => {
    if (typeof event.detail?.complete !== 'function') return;
    event.detail.handled = true;
    void revokeDevice().then(event.detail.complete, () => event.detail.complete(false));
  });
  test.addEventListener('click', async () => {
    if (busy || test.hidden || !current) return;
    busy = true; test.disabled = true;
    try {
      const result = await api('/api/cloud/notifications/personal-test', 'POST', {});
      status.textContent = result.status === 'accepted' ? '配信サービスが受け付けました。この端末の通知表示を確認してください。' :
        result.status === 'unknown' ? '送信結果を確認できません。再送せずこの端末の通知表示を確認してください。' :
        result.status === 'suppressed' ? 'このテストは送信済み、または結果確認中です。この端末の通知表示を確認してください。' :
        result.reason === 'notification_opt_in_required' ? '通知設定がOFFのため、送信を停止しました。' :
        result.reason === 'fresh_discord_role_unavailable' || result.reason === 'fresh_discord_role_required' ? '送信前の確認に失敗したため、送信を停止しました。' :
        'テスト通知を送れませんでした。通知設定・端末登録を確認してください。';
    } catch (_) { status.textContent = 'テスト通知の結果を確認できません。再送せずこの端末の通知表示を確認してください。'; }
    finally { busy = false; test.disabled = false; }
  });
  // Explicit opt-in only; no localStorage dependency and no permission prompt.
  void refresh();
})();
