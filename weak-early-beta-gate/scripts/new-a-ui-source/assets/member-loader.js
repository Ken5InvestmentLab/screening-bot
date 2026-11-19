/* Member transport uses only authorized aggregate and preferences endpoints. */
(function (g) {
  'use strict';
  const base = '/api/cloud/new-a-view/';
  const accessDenied = 'アクセス権を確認してください';
  const unavailable = '現在読み込めません';
  const changed = 'データが更新されました。再試行してください。';
  const isToken = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
  const requiresLogin = response => response.type === 'opaqueredirect' || response.status === 401;
  const denied = response => requiresLogin(response) || response.status === 403;
  function request(path, options = {}) {
    return fetch(base + path, { credentials: 'same-origin', cache: 'no-store', redirect: 'manual', ...options });
  }
  async function read(path, options = {}) {
    const { signal, generation, session } = options;
    const headers = {};
    if (session) headers['x-cloud-member-session'] = session;
    if (generation) headers['x-cloud-generation'] = generation;
    const response = await request(path, { signal, headers });
    if (response.status === 409) throw Error(changed);
    if (denied(response)) {
      const error = Error(accessDenied);
      error.requiresLogin = requiresLogin(response);
      throw error;
    }
    if (!response.ok) throw Error(unavailable);
    return response.json();
  }
  g.NewAMemberTransport = {
    history: (page, options) => read('history.json?page=' + page, options),
    analytics: options => read('analytics.json', options),
    chart: (preset, options) => read('chart.json?preset=' + encodeURIComponent(preset), options),
    personal: options => read('personal.json', options),
    preferences: options => read('preferences', options),
  };
  if (typeof document === 'undefined') return;

  const status = document.getElementById('member-state');
  const retry = document.getElementById('member-retry');
  const out = document.getElementById('member-content');
  let selected = 'medium';
  let page = 1;
  let snapshot = null;
  let memberSession = null;
  let attempt;
  let accessCheck;

  function clearDisplay(message, reauthenticate = false) {
    attempt?.abort();
    attempt = undefined;
    snapshot = null;
    memberSession = null;
    page = 1;
    out.replaceChildren();
    status.textContent = message;
    if (reauthenticate) {
      const link = document.createElement('a');
      link.href = '/auth/login?return_to=' + encodeURIComponent(g.location.pathname);
      link.textContent = 'Discordでログインし直す';
      status.append(' ', link);
    }
    retry.hidden = false;
  }

  async function verifyAccess(hideUntilChecked = false) {
    if (hideUntilChecked) out.hidden = true;
    if (accessCheck) return accessCheck;
    const check = (async () => {
      try {
        const response = await request('session', { signal: AbortSignal.timeout(8000) });
        const session = response.headers.get('x-cloud-member-session');
        if (response.status !== 204 || !isToken(session)) {
          clearDisplay(denied(response) ? accessDenied : unavailable, requiresLogin(response));
          return false;
        }
        if (memberSession !== null && memberSession !== session) {
          clearDisplay(accessDenied);
          return false;
        }
        memberSession = session;
        return true;
      } catch {
        clearDisplay(unavailable);
        return false;
      }
    })();
    accessCheck = check.finally(() => {
      out.hidden = document.visibilityState !== 'visible';
      accessCheck = undefined;
    });
    return accessCheck;
  }

  function addPagination(pages) {
    const nav = document.createElement('nav');
    nav.setAttribute('aria-label', '検出履歴のページ');
    for (const [label, number] of [['前へ', page - 1], ['次へ', page + 1]]) {
      const button = document.createElement('button');
      button.textContent = label;
      button.disabled = number < 1 || number > pages;
      button.addEventListener('click', () => { page = number; load(); });
      nav.append(button);
    }
    out.append(nav);
  }

  async function load() {
    attempt?.abort();
    const controller = new AbortController();
    attempt = controller;
    const active = () => attempt === controller;
    const signal = controller.signal;
    out.replaceChildren();
    retry.hidden = true;
    status.textContent = '読込中';
    if (!await verifyAccess() || !active()) return;

    try {
      if (document.body.dataset.page === 'settings') {
        await g.mountMemberSettings(out, status, {
          signal, active, session: memberSession, verifyAccess,
          accessDenied: reauthenticate => clearDisplay(accessDenied, reauthenticate),
        });
        return;
      }

      const analytics = document.body.dataset.page === 'analytics';
      const options = { signal, generation: snapshot, session: memberSession };
      const transport = g.NewAMemberTransport;
      const [summary, history, chart, personal] = await Promise.all([
        transport.analytics(options),
        analytics ? null : transport.history(page, options),
        transport.chart(selected, options),
        analytics ? transport.personal(options) : null,
      ]);
      if (!active()) return;
      if (!isToken(summary.generation) || (snapshot !== null && snapshot !== summary.generation)
        || [history, chart, personal].some(result => result !== null && result.generation !== summary.generation)) {
        throw Error(changed);
      }
      if (!await verifyAccess() || !active()) return;

      snapshot = summary.generation;
      out.innerHTML = g.NewAMemberPresentation.view({
        mode: analytics ? 'analytics' : 'home',
        asOf: summary.as_of,
        presets: summary.presets,
        selected,
        rows: history?.rows ?? [],
        chartRows: chart.rows,
        personal: personal?.metrics,
      });
      status.textContent = '共通データ ' + summary.as_of;
      document.getElementById('member-preset').addEventListener('change', event => {
        selected = event.target.value;
        load();
      });
      if (history) addPagination(history.pages);
    } catch (error) {
      if (active()) clearDisplay([changed, accessDenied].includes(error.message) ? error.message : unavailable, error.requiresLogin);
    }
  }

  retry.addEventListener('click', load);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') verifyAccess(true);
    else out.hidden = true;
  });
  g.addEventListener('pagehide', () => { out.hidden = true; });
  g.addEventListener('pageshow', event => {
    if (event.persisted) verifyAccess(true);
  });
  g.setInterval(() => {
    if (document.visibilityState === 'visible') verifyAccess();
  }, 30000);
  load();
})(globalThis);
