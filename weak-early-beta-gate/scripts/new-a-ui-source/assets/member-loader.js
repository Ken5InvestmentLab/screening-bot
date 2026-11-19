/* The Worker grants the dashboard view and checks every data request. */
(function (g) {
  'use strict';
  const base = '/api/cloud/new-a-view/';
  const accessDenied = 'アクセス権を確認してください';
  const unavailable = '現在読み込めません';
  const changed = 'データが更新されました。再試行してください。';
  const presets = new Set(['defensive', 'medium', 'return_priority']);
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
    dashboard: options => read('dashboard.json', options),
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
  let memberAccess = null;
  let attempt;
  let accessCheck;

  function updateNavigation() {
    for (const link of document.querySelectorAll('[data-member-premium-nav]')) {
      link.hidden = memberAccess !== 'premium';
    }
  }

  function clearDisplay(message, reauthenticate = false) {
    attempt?.abort();
    attempt = undefined;
    snapshot = null;
    memberSession = null;
    memberAccess = null;
    updateNavigation();
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
        const access = response.headers.get('x-cloud-member-access');
        if (response.status !== 204 || !isToken(session) || (access !== 'premium' && access !== 'free')) {
          clearDisplay(denied(response) ? accessDenied : unavailable, requiresLogin(response));
          return false;
        }
        if (memberSession !== null && (memberSession !== session || memberAccess !== access)) {
          clearDisplay(accessDenied);
          return false;
        }
        memberSession = session;
        memberAccess = access;
        updateNavigation();
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

  function prepareSettings() {
    if (typeof g.mountMemberSettings === 'function') return;
    // A role can be restored while a previously locked settings page is open.
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/new-a-assets/member-settings.js';
      script.onload = resolve;
      script.onerror = () => reject(Error(unavailable));
      document.head.append(script);
    });
  }

  async function load({ restorePresetFocus = false } = {}) {
    attempt?.abort();
    const controller = new AbortController();
    attempt = controller;
    const active = () => attempt === controller;
    const signal = controller.signal;
    out.replaceChildren();
    retry.hidden = true;
    status.textContent = '読込中';
    if (!await verifyAccess() || !active()) return;

    const mode = document.body.dataset.page;
    const free = memberAccess === 'free';
    try {
      if (free && mode !== 'home') {
        out.innerHTML = g.NewAMemberPresentation.lockedPage(mode);
        status.textContent = '';
        return;
      }
      if (mode === 'settings') {
        await prepareSettings();
        if (!active()) return;
        await g.mountMemberSettings(out, status, {
          signal, active, session: memberSession, verifyAccess,
          accessDenied: reauthenticate => clearDisplay(accessDenied, reauthenticate),
        });
        return;
      }

      const analytics = mode === 'analytics';
      const options = { signal, generation: snapshot, session: memberSession };
      const transport = g.NewAMemberTransport;
      const [summary, history, chart, personal, dashboard] = await Promise.all([
        free ? null : transport.analytics(options),
        analytics ? null : transport.history(page, options),
        free ? null : transport.chart(selected, options),
        analytics ? transport.personal(options) : null,
        !free && !analytics ? transport.dashboard(options) : null,
      ]);
      if (!active()) return;
      const source = free ? history : summary;
      if (!source || !isToken(source.generation) || (snapshot !== null && snapshot !== source.generation)
        || [history, chart, personal, dashboard].some(result => result !== null && result.generation !== source.generation)
        || (dashboard && dashboard.as_of !== source.as_of)) {
        throw Error(changed);
      }
      if (history && (!Array.isArray(history.rows) || !Number.isSafeInteger(history.pages) || history.pages < 1)) {
        throw Error(unavailable);
      }
      if (!await verifyAccess() || !active()) return;

      snapshot = source.generation;
      out.innerHTML = g.NewAMemberPresentation.view({
        mode,
        access: memberAccess,
        asOf: source.as_of,
        presets: summary?.presets,
        selected,
        rows: history?.rows ?? [],
        chartRows: chart?.rows,
        personal: personal?.metrics,
        dashboard,
      });
      status.textContent = free ? '' : '共通データ ' + source.as_of;
      const preset = document.getElementById('member-preset');
      preset?.addEventListener('change', event => {
        const { value } = event.target;
        if (!presets.has(value) || value === selected) return;
        selected = value;
        load({ restorePresetFocus: event.target === document.activeElement });
      });
      if (restorePresetFocus && document.activeElement === document.body) {
        const activePreset = mode === 'home' ? preset?.querySelector('input:checked') : preset;
        activePreset?.focus();
      }
      if (history) addPagination(history.pages);
    } catch (error) {
      if (!active()) return;
      if (free && mode === 'home' && error.message !== accessDenied
        && await verifyAccess() && active() && memberAccess === 'free') {
        snapshot = null;
        page = 1;
        out.innerHTML = g.NewAMemberPresentation.freeHome();
        status.textContent = error.message === changed ? changed : '終了済みの検出履歴を読み込めませんでした。';
        retry.hidden = false;
        return;
      }
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
