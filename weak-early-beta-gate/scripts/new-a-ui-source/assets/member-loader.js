/* The Worker grants the dashboard view and checks every data request. */
(function (g) {
  'use strict';
  const base = '/api/cloud/new-a-view/';
  const accessDenied = 'アクセス権を確認してください';
  const unavailable = '現在読み込めません';
  const changed = 'データが更新されました。再試行してください。';
  const presets = new Set(['defensive', 'medium', 'return_priority']);
  const defaultPreset = 'return_priority';
  const historyPartSize = 100;
  const defaultDisplay = { theme: 'dark', font_size: null, page_size: null };
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
    if (!response.ok) {
      const error = Error(unavailable);
      error.missing = response.status === 404;
      error.status = response.status;
      throw error;
    }
    return response.json();
  }
  g.NewAMemberTransport = {
    history: (page, options) => read('history.json?page=' + page, options),
    fundamental: (item, options) => read('fundamental.json?item=' + encodeURIComponent(item), options),
    reference: (item, options) => read('reference.json?item=' + encodeURIComponent(item), options),
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
  let selected = defaultPreset;
  let presetStorageKey = null;
  let page = 1;
  let historyOffset = 0;
  let display = defaultDisplay;
  let displayRevision = -1;
  let updateHistorySize;
  const systemTheme = g.matchMedia?.('(prefers-color-scheme: dark)');
  let snapshot = null;
  let memberSession = null;
  let memberAccess = null;
  let attempt;
  let accessCheck;
  let fundamentalPage = null;
  let openFundamental = null;
  let historySearch = null;
  let historyObserver = null;
  let historyAttempt = null;
  const initialHistoryQuery = { symbol: '', from: '', through: '', order: 'newest' };
  let historyQuery = { ...initialHistoryQuery };
  const referenceTags = new Set(('article section div h2 h3 h4 h5 p span small strong b em abbr details summary '
    + 'dl dt dd ol ul li table thead tbody tfoot caption tr th td colgroup col time button a br '
    + 'svg g line polyline path rect text title desc defs clippath circle polygon ellipse lineargradient stop template').split(' '));

  async function optionalReference(item, options) {
    let result;
    try {
      result = await g.NewAMemberTransport.reference(item, options);
    } catch (error) {
      if (error.missing) return null;
      throw error;
    }
    if (!g.NewAMemberPresentation.referencePayload(result, item)) throw Error(unavailable);
    return result;
  }

  function referenceLink(href) {
    if (href === './weak_early_beta_settings.html' || /^#[a-z][a-z0-9_-]*$/i.test(href)) return true;
    return /^https:\/\/jp\.tradingview\.com\/chart\/\?symbol=TSE(?:%3A|:)[0-9A-Z]{4}$/.test(href);
  }

  function verifiedReference(markup, asOf, { aggregatesOnly = false } = {}) {
    const template = document.createElement('template');
    template.innerHTML = markup;
    const items = new Map();
    const ids = new Set();
    for (const element of template.content.querySelectorAll('*')) {
      const tag = element.localName.toLowerCase();
      const id = element.id;
      if (!referenceTags.has(tag) || (id && (ids.has(id) || /^(?:member-|cloud-settings-|cloud-help-)/.test(id)
        || id === 'history' || id === 'detection-table'))) throw Error(unavailable);
      if (id) ids.add(id);
      if (tag === 'template' && (id !== 'new-a-reference-daily-values' || element.content.children.length)) {
        throw Error(unavailable);
      }
      for (const { name, value } of element.attributes) {
        if (/^(?:on|src)|^(?:action|form|formaction|ping|xlink:href|background|autofocus|is)$/i.test(name)
          || (name === 'href' && (tag !== 'a' || !referenceLink(value)
            || (aggregatesOnly && !value.startsWith('#'))))
          || (name === 'target' && (tag !== 'a' || value !== '_blank'))
          || (/@import|url\s*\(/i.test(value) && !/^url\(#[a-z][a-z0-9_-]*\)$/i.test(value))) throw Error(unavailable);
      }
      if (element.hasAttribute('data-member-fundamental')) {
        const item = element.dataset.memberFundamental;
        const row = g.NewAMemberPresentation.fundamentalSelector(item);
        if (aggregatesOnly || tag !== 'button' || !row || row.date > asOf) throw Error(unavailable);
        items.set(item, row);
      }
    }
    if (!aggregatesOnly && markup.includes('data-reference-cards')) expandStockCards(template.content);
    return { fragment: template.content, items };
  }

  // Saved and future canonical references share this member presentation.
  // MONITOR_RESET closes a detector episode, not necessarily a live watch.
  // Keep the actual WATCH_TERMINAL card and omit that internal bookkeeping.
  function expandStockCards(fragment) {
    for (const card of fragment.querySelectorAll('.cloud-stock-grid > article')) {
      if (card.dataset.referenceKind === 'MONITOR_RESET') {
        card.remove();
        continue;
      }
      if (card.dataset.referenceKind === 'ENTRY_CANDIDATE') {
        const label = card.querySelector(':scope > .badge');
        if (label) label.classList.add('cloud-transition', 'cloud-transition--entry-candidate');
      }
      for (const detail of card.querySelectorAll('details.cloud-stock-detail')) {
        const panel = document.createElement('div');
        panel.className = detail.className;
        panel.append(...Array.from(detail.childNodes).filter(node => node.localName !== 'summary'));
        detail.replaceWith(panel);
      }
    }
    for (const group of fragment.querySelectorAll('details.cloud-other-events')) {
      if (!group.querySelector('.cloud-stock-grid > article')) {
        group.remove();
        continue;
      }
      const panel = document.createElement('section');
      panel.className = group.className;
      const heading = document.createElement('h4');
      heading.textContent = 'その他の動き・記録';
      const summary = group.querySelector(':scope > summary');
      panel.append(heading, ...Array.from(group.childNodes).filter(node => node !== summary));
      group.replaceWith(panel);
    }
  }

  async function analyticsOverview(preset, options, allowLegacy) {
    try {
      return await optionalReference('analytics.overview.' + preset, options);
    } catch (error) {
      // A tab may encounter an earlier Worker version while the UI is being deployed.
      if (!allowLegacy || error.status !== 400) throw error;
      return optionalReference('analytics.' + preset, options);
    }
  }

  async function analyticsDaily(item, options, source, active) {
    try {
      const response = await g.NewAMemberTransport.reference(item, { ...options, generation: source.generation });
      if (!active()) return null;
      if (!g.NewAMemberPresentation.referencePayload(response, item)) throw Error(unavailable);
      if (response.generation !== source.generation || response.as_of !== source.as_of) throw Error(changed);
      const { fragment } = verifiedReference(response.markup, source.as_of);
      const template = fragment.querySelector('#new-a-reference-daily-values');
      if (!template || fragment.children.length !== 1) throw Error(unavailable);
      const current = await verifyAccess();
      return current && active() ? template.content.textContent : null;
    } catch (error) {
      if (!active()) return null;
      if (error.message !== changed && error.message !== accessDenied) throw error;
      clearDisplay(error.message, error.requiresLogin);
      return null;
    }
  }

  async function legacyProjection(options, analytics) {
    const transport = g.NewAMemberTransport;
    const [summary, chart, personal, dashboard] = await Promise.all([
      transport.analytics(options),
      transport.chart(selected, options),
      analytics ? transport.personal(options) : null,
      analytics ? null : transport.dashboard(options),
    ]);
    return { summary, chart, personal, dashboard };
  }

  async function restorePreset(session) {
    try {
      const storage = g.sessionStorage;
      if (!storage) return;
      // Scope the in-tab display choice without storing the authenticated session tag.
      const digest = new Uint8Array(await g.crypto.subtle.digest('SHA-256', new TextEncoder().encode(session)));
      if (memberSession !== session) return;
      const scope = Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('');
      presetStorageKey = 'cloud-operating-level:' + scope;
      const saved = storage.getItem(presetStorageKey);
      if (presets.has(saved)) selected = saved;
    } catch {
      // The picker still works on the current page when storage is unavailable.
    }
  }

  function paintTheme() {
    document.documentElement.dataset.theme = display.theme === 'system'
      ? systemTheme?.matches ? 'dark' : 'light' : display.theme;
  }
  systemTheme?.addEventListener?.('change', paintTheme);

  function applyDisplaySettings(saved, session) {
    const { revision, view_preferences: view } = saved ?? {};
    if (memberSession !== session || memberAccess === null || !Number.isSafeInteger(revision)
      || revision < displayRevision || !['dark', 'light', 'system'].includes(view?.theme)
      || !['small', 'standard', 'large'].includes(view.font_size) || ![20, 50, 100].includes(view.page_size)) return;
    const sizeChanged = display.page_size !== view.page_size;
    display = view;
    displayRevision = revision;
    paintTheme();
    document.documentElement.dataset.fontSize = view.font_size;
    if (sizeChanged) updateHistorySize?.();
  }

  function clearDisplay(message, reauthenticate = false) {
    g.CloudSettingsDialog?.close(true);
    stopHistory();
    historyQuery = { ...initialHistoryQuery };
    clearFundamentalPage();
    attempt?.abort();
    attempt = undefined;
    snapshot = null;
    memberSession = null;
    memberAccess = null;
    selected = defaultPreset;
    presetStorageKey = null;
    display = defaultDisplay;
    displayRevision = -1;
    paintTheme();
    delete document.documentElement.dataset.fontSize;
    page = 1;
    historyOffset = 0;
    updateHistorySize = undefined;
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

  function suspendDisplay() {
    dismissFundamental();
    g.CloudSettingsDialog?.close(true);
    out.hidden = true;
  }

  async function verifyAccess(hideUntilChecked = false) {
    if (hideUntilChecked) suspendDisplay();
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
        const newSession = memberSession === null;
        memberSession = session;
        memberAccess = access;
        if (newSession && (access === 'premium' || document.body.dataset.page === 'analytics')) {
          await restorePreset(session);
        }
        if (memberSession !== session) return false;
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

  function historyNavigation(label, previous, next, step) {
    if (!previous && !next) return null;
    const nav = document.createElement('nav');
    nav.setAttribute('class', 'history-pagination');
    nav.setAttribute('aria-label', '検出履歴のページ');
    const position = document.createElement('span');
    position.textContent = label;
    for (const [text, available, direction] of [['前へ', previous, -1], ['次へ', next, 1]]) {
      const button = document.createElement('button');
      button.textContent = text;
      button.disabled = !available;
      button.addEventListener('click', () => step(direction));
      nav.append(button);
      if (direction < 0) nav.append(position);
    }
    return nav;
  }

  function historyPagination(current, pages, onPage, exact = true) {
    const label = exact ? current + ' / ' + pages + 'ページ' : current + 'ページ';
    return historyNavigation(label, current > 1, current < pages, direction => onPage(current + direction));
  }

  function mountFreeHistory(history, active) {
    const region = document.getElementById('member-free-history');
    const rows = history.rows.filter(row => row.state === 'HOLD_ENDED');

    function render() {
      const size = display.page_size ?? historyPartSize;
      const chunks = Math.max(1, Math.ceil(rows.length / size));
      const current = Math.min(Math.floor(historyOffset / size) + 1, chunks);
      historyOffset = (current - 1) * size;
      region.replaceChildren();
      region.innerHTML = g.NewAMemberPresentation.freeHistoryRows(rows.slice(historyOffset, historyOffset + size));
      const label = page + ' / ' + history.pages + 'ページ'
        + (chunks > 1 ? '（' + current + ' / ' + chunks + '）' : '');
      const nav = historyNavigation(label, current > 1 || page > 1, current < chunks || page < history.pages,
        async direction => {
          const next = current + direction;
          if (next >= 1 && next <= chunks) {
            if (!await verifyAccess() || !active()) return;
            historyOffset = (next - 1) * size;
            render();
          } else {
            page += direction;
            historyOffset = direction > 0 ? 0 : historyPartSize;
            load();
          }
        });
      if (nav) region.append(nav);
    }
    updateHistorySize = render;
    render();
  }

  function stopHistorySearch() {
    if (!historySearch) return;
    clearTimeout(historySearch.timer);
    historySearch.controller?.abort();
    historySearch = null;
  }

  function stopHistory() {
    historyObserver?.disconnect();
    historyObserver = null;
    historyAttempt?.abort();
    historyAttempt = null;
    stopHistorySearch();
  }

  function mountHistorySearch(native, scope, dashboardItems, resetPage) {
    const controls = document.getElementById('member-history-filters');
    const target = document.getElementById('member-history-results');
    const notice = document.getElementById('member-history-filter-status');
    if (!controls || !target || !notice) return;
    const state = { index: null, controller: null, timer: undefined };
    historySearch = state;
    const ui = g.NewAMemberPresentation;
    const keys = Object.keys(initialHistoryQuery);
    const inputs = Object.fromEntries(keys.map(key => [key, controls.querySelector('[data-history-filter="' + key + '"]')]));
    const current = () => historySearch === state && scope.generation === snapshot
      && scope.session === memberSession && memberAccess === 'premium';
    const usingFilter = () => historyQuery.symbol.trim() || historyQuery.from || historyQuery.through || historyQuery.order !== 'newest';
    const updateScope = rows => {
      const entries = new Map(dashboardItems);
      for (const row of rows) if (row.item && !entries.has(row.item)) entries.set(row.item, row);
      scope.rows = entries;
    };
    async function readReference(item, options) {
      const result = await g.NewAMemberTransport.reference(item, options);
      if (!ui.referencePayload(result,item)) throw Error(unavailable);
      if (result.generation !== scope.generation || result.as_of !== scope.asOf) throw Error(changed);
      return result.markup;
    }
    async function apply(resultPage = 1) {
      if (!current()) return;
      state.controller?.abort();
      const controller = new AbortController();
      state.controller = controller;
      const active = () => current() && state.controller === controller;
      dismissFundamental();
      updateScope([]);
      target.replaceChildren();
      if (!usingFilter()) {
        notice.textContent = '';
        target.removeAttribute('aria-busy');
        if (native.page !== 1 || historyOffset !== 0) {
          resetPage();
          return;
        }
        target.innerHTML = ui.referenceHistoryTable(native.visible, selected);
        updateScope(native.visible);
        if (native.nav) target.append(native.nav);
        return;
      }
      const { from, through } = historyQuery;
      if (from && through && from > through) {
        notice.textContent = '開始日と終了日を確認してください。';
        target.removeAttribute('aria-busy');
        return;
      }
      notice.textContent = '検出履歴を検索しています。';
      target.setAttribute('aria-busy', 'true');
      try {
        if (!await verifyAccess() || !active()) return;
        const options = { signal: controller.signal, generation: scope.generation, session: scope.session };
        if (state.index === null) {
          const markup = await readReference('history.index', options);
          if (!active()) return;
          const index = ui.referenceHistoryIndex(markup, scope.asOf, native.pages);
          if (!index) throw Error(unavailable);
          const first = (native.page - 1) * historyPartSize;
          if (native.rows.some((row,offset) => {
            const item = index.rows[first + offset];
            return !item || row.date !== item[0] || row.symbol !== item[1] || row.companyName !== (index.names[item[2]] ?? null);
          })) throw Error(unavailable);
          state.index = index;
        }
        const matches = ui.matchingHistory(state.index, historyQuery);
        const size = display.page_size ?? 20;
        const offsets = matches.slice((resultPage - 1) * size, resultPage * size);
        const needed = new Set(offsets.map(offset => Math.floor(offset / historyPartSize) + 1));
        const available = new Map(await Promise.all([...needed].map(async number => {
          if (number === native.page) return [number,native.rows];
          const first = (number - 1) * historyPartSize;
          const expected = state.index.rows.slice(first,first + historyPartSize).map(([date,symbol,name]) => ({
            date, symbol, companyName: state.index.names[name] ?? null,
          }));
          const markup = await readReference('history.' + number, options);
          const rows = ui.referenceHistory(markup, number, scope.asOf, expected, true);
          if (!rows) throw Error(unavailable);
          return [number,rows];
        })));
        if (!active() || !await verifyAccess() || !active()) return;
        const rows = offsets.map(offset => available.get(Math.floor(offset / historyPartSize) + 1)[offset % historyPartSize]);
        updateScope(rows);
        target.innerHTML = ui.referenceHistoryTable(rows, selected);
        notice.textContent = '検索結果 ' + matches.length.toLocaleString('ja-JP') + '件';
        const nav = historyPagination(resultPage, Math.ceil(matches.length / size), number => {
          notice.setAttribute('tabindex','-1');
          notice.focus();
          apply(number);
        });
        if (nav) target.append(nav);
      } catch (error) {
        if (!active()) return;
        if (error.message === changed || error.message === accessDenied) {
          clearDisplay(error.message, error.requiresLogin);
          return;
        }
        notice.textContent = '検出履歴の検索結果を読み込めませんでした。';
        const retrySearch = document.createElement('button');
        retrySearch.type = 'button';
        retrySearch.textContent = '再試行';
        retrySearch.addEventListener('click', () => apply(resultPage));
        target.append(retrySearch);
      } finally {
        if (active()) target.removeAttribute('aria-busy');
      }
    }
    for (const key of keys) inputs[key].value = historyQuery[key];
    controls.addEventListener('input', event => {
      if (event.target !== inputs.symbol) return;
      historyQuery.symbol = inputs.symbol.value;
      state.controller?.abort();
      clearTimeout(state.timer);
      state.timer = setTimeout(apply, 240);
    });
    controls.addEventListener('change', event => {
      const key = event.target.dataset.historyFilter;
      if (!['from','through','order'].includes(key) || event.target !== inputs[key]) return;
      historyQuery[key] = event.target.value;
      clearTimeout(state.timer);
      apply();
    });
    controls.querySelector('[data-history-clear]').addEventListener('click', () => {
      clearTimeout(state.timer);
      historyQuery = { ...initialHistoryQuery };
      for (const key of keys) inputs[key].value = historyQuery[key];
      apply();
      inputs.symbol.focus();
    });
    if (usingFilter()) apply();
  }

  function dismissFundamental(restoreFocus = false) {
    const current = openFundamental;
    if (!current) return;
    openFundamental = null;
    current.controller.abort();
    current.button.removeAttribute('aria-busy');
    current.button.setAttribute('aria-expanded', 'false');
    if (current.dialog?.open) current.dialog.close();
    current.dialog?.remove();
    if (restoreFocus && current.button.isConnected) current.button.focus();
  }

  function clearFundamentalPage() {
    fundamentalPage = null;
    dismissFundamental();
  }

  async function showFundamental(button) {
    const scope = fundamentalPage;
    const item = button.dataset.memberFundamental;
    const row = scope?.rows.get(item);
    if (!row || memberAccess !== 'premium' || out.hidden || openFundamental?.button === button) return;
    dismissFundamental();
    const controller = new AbortController();
    const current = { controller, button, dialog: null };
    openFundamental = current;
    const active = () => openFundamental === current && fundamentalPage === scope && button.isConnected
      && memberAccess === 'premium' && scope.generation === snapshot && scope.session === memberSession
      && scope.rows.get(item) === row;
    button.setAttribute('aria-busy', 'true');
    try {
      const report = await g.NewAMemberTransport.fundamental(item, {
        signal: controller.signal, generation: scope.generation, session: scope.session,
      });
      if (!active()) return;
      if (report?.generation !== scope.generation || report?.as_of !== scope.asOf) throw Error(changed);
      const markup = g.NewAMemberPresentation.fundamentalMarkup(report, {
        date: row.date, symbol: row.symbol, asOf: scope.asOf, generation: scope.generation,
      });
      if (!markup) throw Error(unavailable);
      if (!await verifyAccess() || !active()) return;
      const dialog = document.createElement('dialog');
      current.dialog = dialog;
      dialog.className = 'fundamental-detail';
      dialog.setAttribute('aria-label', 'ファンダ分析の詳細');
      dialog.innerHTML = markup;
      dialog.querySelector('.fundamental-close').addEventListener('click', () => dialog.close());
      dialog.addEventListener('click', event => {
        if (event.target === dialog) dialog.close();
      });
      dialog.addEventListener('close', () => {
        if (openFundamental === current) dismissFundamental(true);
      });
      out.append(dialog);
      dialog.showModal();
      button.removeAttribute('aria-busy');
      button.setAttribute('aria-expanded', 'true');
    } catch (error) {
      if (!active()) return;
      if (error.message === changed || error.message === accessDenied) {
        clearDisplay(error.message, error.requiresLogin);
        return;
      }
      dismissFundamental();
      if (error.missing) {
        scope.rows.delete(item);
        button.remove();
      } else {
        status.textContent = unavailable;
      }
    }
  }

  let settingsScript;
  function prepareSettings() {
    if (typeof g.mountMemberSettings === 'function') return;
    settingsScript ??= new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/new-a-assets/member-settings.js';
      script.onload = resolve;
      script.onerror = () => { settingsScript = undefined; script.remove(); reject(Error(unavailable)); };
      document.head.append(script);
    });
    return settingsScript;
  }

  async function openSettings(target, message, context) {
    const session = memberSession;
    const active = () => context.active() && memberSession === session && memberAccess !== null;
    await prepareSettings();
    if (!active()) return;
    await g.mountMemberSettings(target, message, {
      ...context, active, session, verifyAccess,
      accessDenied: reauthenticate => clearDisplay(accessDenied, reauthenticate),
      onLoaded: saved => applyDisplaySettings(saved, session),
      onSaved: saved => applyDisplaySettings(saved, session),
    });
  }

  g.CloudSettingsDialog?.connect(openSettings, () => memberAccess !== null && !out.hidden);

  function mountDeferredHistory(scope, dashboardItems, isDashboardActive) {
    const panel = document.getElementById('history');
    const region = document.getElementById('member-history-content');
    const notice = document.getElementById('member-history-state');
    const button = document.getElementById('member-history-open');
    const ui = g.NewAMemberPresentation;
    let requestedPage = page;
    let requestedOffset = historyOffset;
    let loaded;
    let knownPageCount;
    const active = () => isDashboardActive() && scope.generation === snapshot
      && scope.session === memberSession && memberAccess === 'premium';

    function renderHistory(number, offset, { history, referenceRows }, restoreFocus = false) {
      stopHistorySearch();
      if (openFundamental && region.contains(openFundamental.button)) dismissFundamental();
      if (restoreFocus) panel.focus();
      const size = display.page_size ?? historyPartSize;
      const pagesPerPart = historyPartSize / size;
      page = number;
      historyOffset = Math.floor(offset / size) * size;
      const basic = history.rows.slice(historyOffset, historyOffset + size);
      const detailed = referenceRows && referenceRows.slice(historyOffset, historyOffset + size);
      const rows = new Map(dashboardItems);
      if (detailed) {
        for (const row of detailed) if (row.item && !rows.has(row.item)) rows.set(row.item, row);
      } else {
        for (const row of basic) {
          if (row.has_fundamental !== true) continue;
          const item = ui.fundamentalItem(number, row);
          if (item && !rows.has(item)) rows.set(item, row);
        }
      }
      scope.rows = rows;
      region.innerHTML = ui.historyContent(basic, number, detailed, selected);
      notice.textContent = detailed ? '' : '検出履歴の詳細を読み込めませんでした。';
      button.textContent = '再試行';
      button.hidden = !!detailed;
      if (number === history.pages) knownPageCount = (history.pages - 1) * historyPartSize + history.rows.length;
      const current = (number - 1) * pagesPerPart + historyOffset / size + 1;
      const total = knownPageCount === undefined ? history.pages * pagesPerPart : Math.ceil(knownPageCount / size);
      const go = next => readHistory(Math.ceil(next / pagesPerPart), true, (next - 1) % pagesPerPart * size);
      const nav = historyPagination(current, total, go, pagesPerPart === 1 || knownPageCount !== undefined);
      if (nav) (document.getElementById('member-history-results') ?? region).append(nav);
      if (referenceRows) mountHistorySearch({ rows: referenceRows, page: number, pages: history.pages, visible: detailed, nav },
        scope, dashboardItems, () => readHistory(1));
    }

    updateHistorySize = () => {
      if (active() && loaded && !historyAttempt) renderHistory(page, historyOffset, loaded);
    };

    async function readHistory(number, restoreFocus = false, offset = 0, force = false) {
      if (!active() || historyAttempt) return;
      requestedPage = number;
      requestedOffset = offset;
      if (loaded?.history.page === number && !force) {
        if (!await verifyAccess() || !active() || historyAttempt || requestedPage !== number || requestedOffset !== offset) return;
        renderHistory(number, offset, loaded, restoreFocus);
        return;
      }
      stopHistory();
      if (openFundamental && region.contains(openFundamental.button)) dismissFundamental();
      scope.rows = new Map(dashboardItems);
      const controller = new AbortController();
      historyAttempt = controller;
      const current = () => active() && historyAttempt === controller;
      const options = { signal: controller.signal, generation: scope.generation, session: scope.session };
      if (restoreFocus) panel.focus();
      region.replaceChildren();
      region.setAttribute('aria-busy', 'true');
      button.hidden = true;
      notice.textContent = '検出履歴を読み込んでいます。';

      try {
        if (!await verifyAccess() || !current()) return;
        const [history, reference] = await Promise.all([
          g.NewAMemberTransport.history(number, options),
          optionalReference('history.' + number, options),
        ]);
        if (!current()) return;
        if (history.generation !== scope.generation || history.as_of !== scope.asOf
          || reference && (reference.generation !== scope.generation || reference.as_of !== scope.asOf)) {
          throw Error(changed);
        }
        if (!Array.isArray(history.rows) || history.page !== number || !Number.isSafeInteger(history.pages)
          || history.pages < number || history.pages > 200) throw Error(unavailable);
        const referenceRows = reference && ui.referenceHistory(reference.markup, number, scope.asOf, history.rows);
        if (reference && !referenceRows) throw Error(unavailable);
        if (!await verifyAccess() || !current()) return;

        loaded = { history, referenceRows };
        renderHistory(number, offset, loaded);
      } catch (error) {
        if (!current()) return;
        if (error.message === changed || error.message === accessDenied) {
          clearDisplay(error.message, error.requiresLogin);
          return;
        }
        notice.textContent = '検出履歴を読み込めませんでした。';
        button.textContent = '再試行';
        button.hidden = false;
      } finally {
        if (current()) {
          historyAttempt = null;
          region.removeAttribute('aria-busy');
        }
      }
    }

    button.addEventListener('click', () => readHistory(requestedPage, true, requestedOffset, true));
    if (g.location.hash === '#history') {
      readHistory(page, false, historyOffset);
    } else if (typeof g.IntersectionObserver === 'function') {
      historyObserver = new g.IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) readHistory(page, false, historyOffset);
      }, { rootMargin: '200px 0px' });
      historyObserver.observe(panel);
    }
  }

  async function load({ restorePresetFocus = false } = {}) {
    stopHistory();
    updateHistorySize = undefined;
    clearFundamentalPage();
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
    const analytics = mode === 'analytics';
    const freeHome = free && mode === 'home';
    try {
      if (mode === 'settings') {
        await openSettings(out, status, { signal, active });
        return;
      }
      if (displayRevision < 0) {
        const session = memberSession;
        // Preferences are independent of market data and must not delay the cards.
        void g.NewAMemberTransport.preferences({ signal, session })
          .then(saved => { if (active()) applyDisplaySettings(saved, session); })
          .catch(() => {});
      }

      const options = { signal, generation: snapshot, session: memberSession };
      const [reference, history] = await Promise.all([
        analytics ? analyticsOverview(selected, options, !free)
          : freeHome ? null : optionalReference('dashboard.' + selected, options),
        freeHome ? g.NewAMemberTransport.history(page, options) : null,
      ]);
      if (!active()) return;
      if (free && analytics && !reference) throw Error(unavailable);
      const legacyDashboard = !free && reference === null;
      const projection = legacyDashboard ? await legacyProjection(options, analytics) : {};
      if (!active()) return;
      const { summary, chart, personal, dashboard } = projection;
      const source = reference ?? summary ?? history;
      if (!source || !isToken(source.generation) || (snapshot !== null && snapshot !== source.generation)
        || [history, chart, personal, dashboard].some(result => result && result.generation !== source.generation)
        || [history, dashboard].some(result => result && result.as_of !== source.as_of)) {
        throw Error(changed);
      }
      if (history && (!Array.isArray(history.rows) || history.page !== page || !Number.isSafeInteger(history.pages)
        || history.pages < page || history.pages > 200)) {
        throw Error(unavailable);
      }
      const display = reference && verifiedReference(reference.markup, reference.as_of, { aggregatesOnly: free });
      if (!await verifyAccess() || !active()) return;

      snapshot = source.generation;
      const dashboardAnalyses = display?.items ?? new Map();
      const scope = { asOf: source.as_of, generation: snapshot, session: memberSession, rows: dashboardAnalyses };
      if (!free) fundamentalPage = scope;
      out.innerHTML = g.NewAMemberPresentation.view({
        mode,
        access: memberAccess,
        asOf: source.as_of,
        presets: summary?.presets,
        selected,
        rows: history?.rows ?? [],
        deferHistory: !free && !analytics,
        chartRows: chart?.rows,
        personal: personal?.metrics,
        dashboard,
        reference: display !== null,
      });
      if (display) {
        const target = document.getElementById('member-reference-content');
        target.append(display.fragment);
        if (analytics) {
          const item = 'analytics.daily.' + selected;
          g.NewAReferenceAnalytics.mount(target, () => analyticsDaily(item, options, source, active));
        }
      }
      status.textContent = legacyDashboard ? '一部の表示を読み込めませんでした。' : '';
      retry.hidden = !legacyDashboard;
      const preset = document.getElementById('member-preset');
      preset?.addEventListener('change', event => {
        const { value } = event.target;
        if (!presets.has(value) || value === selected) return;
        selected = value;
        if (presetStorageKey) {
          try { g.sessionStorage.setItem(presetStorageKey, selected); } catch {}
        }
        load({ restorePresetFocus: event.target === document.activeElement });
      });
      if (restorePresetFocus && document.activeElement === document.body) {
        preset?.querySelector('input:checked')?.focus();
      }
      if (!free && !analytics) mountDeferredHistory(scope, dashboardAnalyses, active);
      if (history) mountFreeHistory(history, active);
    } catch (error) {
      if (!active()) return;
      if (freeHome && error.message !== accessDenied
        && await verifyAccess() && active() && memberAccess === 'free') {
        snapshot = null;
        page = 1;
        historyOffset = 0;
        out.innerHTML = g.NewAMemberPresentation.freeHome();
        status.textContent = error.message === changed ? changed : '終了済みの検出履歴を読み込めませんでした。';
        retry.hidden = false;
        return;
      }
      if (active()) clearDisplay([changed, accessDenied].includes(error.message) ? error.message : unavailable, error.requiresLogin);
    }
  }

  out.addEventListener('click', event => {
    const button = event.target.closest?.('[data-member-fundamental]');
    if (button && out.contains(button)) {
      showFundamental(button);
      return;
    }
    const historyButton = event.target.closest?.('[data-member-history-details]');
    if (memberAccess === 'premium' && !out.hidden && historyButton && out.contains(historyButton)) {
      const record = historyButton.closest('#detection-table .history-record');
      if (!record) return;
      const open = historyButton.getAttribute('aria-expanded') !== 'true';
      record.classList.toggle('history-details-open', open);
      historyButton.setAttribute('aria-expanded', String(open));
      historyButton.textContent = open ? '詳細を閉じる' : '詳細を見る';
      return;
    }
    const reference = document.getElementById('member-reference-content');
    if (memberAccess !== 'premium' || out.hidden || !reference?.contains(event.target)) return;
    const sortButton = event.target.closest?.('[data-reference-sort]');
    if (sortButton) {
      const group = sortButton.closest('.cloud-reference-events');
      const grids = group?.querySelectorAll('[data-reference-cards]');
      const order = sortButton.dataset.referenceSort;
      if (!grids?.length || !['kind','symbol','name'].includes(order)) return;
      for (const grid of grids) {
        const cards=Array.from(grid.children).filter(card=>card.hasAttribute('data-reference-kind'));
        grid.append(...g.NewAMemberPresentation.sortReferenceCards(cards,order));
      }
      for (const option of group.querySelectorAll('[data-reference-sort]')) {
        option.setAttribute('aria-pressed',String(option===sortButton));
      }
      return;
    }
    const moreWatches = event.target.closest?.('#new-a-current-more');
    if (moreWatches) {
      const hidden = reference.querySelectorAll('[data-current-watch][hidden]');
      for (const row of hidden) row.hidden = false;
      moreWatches.hidden = true;
      hidden[0]?.querySelector('summary,td')?.focus();
      return;
    }
  });
  retry.addEventListener('click', load);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') verifyAccess(true);
    else suspendDisplay();
  });
  g.addEventListener('pagehide', suspendDisplay);
  g.addEventListener('pageshow', event => {
    if (event.persisted) verifyAccess(true);
  });
  g.setInterval(() => {
    if (document.visibilityState === 'visible') verifyAccess();
  }, 30000);
  load();
})(globalThis);
