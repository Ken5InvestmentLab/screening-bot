'use strict';
// Push only. No fetch handler, offline cache, ledger or report interception.
self.addEventListener('push', event => {
  let value;
  try { value = event.data && event.data.json(); } catch (_) { return; }
  if (!value || value.version !== 1 || !['new_detection', 'reminder'].includes(value.kind) ||
      typeof value.body !== 'string' || value.body.length > 500 || typeof value.tag !== 'string' || value.tag.length > 300) return;
  event.waitUntil((async () => {
    // Tags are opaque: signal identifiers must not reach the lock-screen API.
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value.tag));
    const tag = Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
    await self.registration.showNotification('天底極致 -Cloud-', { body: value.body, tag,
      data: { url: new URL('./weak_early_beta_latest.html', self.location.href).href } });
  })());
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  // Ignore every URL supplied in a push payload or notification data.
  const url = new URL('./weak_early_beta_latest.html', self.location.href).href;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find(client => client.url === url);
    if (existing) await existing.focus();
    else await self.clients.openWindow(url);
  })());
});
