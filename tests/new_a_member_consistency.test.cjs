const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const ts = require('../weak-early-beta-gate/node_modules/typescript');

const gate = path.resolve(__dirname, '../weak-early-beta-gate');
const transpile = filename => ts.transpileModule(fs.readFileSync(path.join(gate, 'src', filename), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;
const referenceModule = { exports: {} };
vm.runInNewContext(transpile('new-a-member-reference.ts'), {
  module: referenceModule, exports: referenceModule.exports, TextEncoder,
});
const projectionModule = { exports: {} };
vm.runInNewContext(transpile('new-a-member-projection.ts'), {
  module: projectionModule, exports: projectionModule.exports, TextEncoder,
});
const servicesModule = { exports: {} };
vm.runInNewContext(transpile('new-a-member-services.ts'), {
  module: servicesModule,
  exports: servicesModule.exports,
  require: name => {
    if (name === './new-a-member-reference') return referenceModule.exports;
    if (name === './new-a-member-projection') return projectionModule.exports;
    assert.equal(name, './new-a-member-frame.generated');
    return { memberFrame: () => '' };
  },
  crypto: webcrypto,
  TextEncoder,
  Request,
  Response,
  URL,
});
const { memberServices } = servicesModule.exports;
const subject = '123456789012345678';
const day = '2026-11-19';
const origin = 'https://example.invalid/api/cloud/new-a-view/';
function servicesFixture() {
  const source = {
    status: 'READY',
    dataset_id: 'synthetic-private-dataset',
    revision: 1,
    as_of: day,
    source_version: 'synthetic-private-source-version',
  };
  const adapters = {
    identity: async () => ({ subject, discord_authorized: true }),
    current: async () => source,
    common: async capture => ({ source: capture, history_pages: 2, rows: [] }),
    personal: async () => ({ trade_count: 2 }),
    preferences: async () => new Response(null),
    asset: async () => new Response(null),
  };
  return { source, adapters };
}

test('opaque generation is consistent across responses for a subject and rejects an old revision with unchanged date', async () => {
  const { source, adapters } = servicesFixture();
  const services = memberServices(adapters, 'synthetic-secret');
  const response = await services.aggregate(new Request(origin + 'analytics.json'), subject);
  const original = await response.json();
  assert.equal(response.status, 200);
  assert.match(original.generation, /^[a-f0-9]{64}$/);
  assert.doesNotMatch(JSON.stringify(original), /synthetic-private/);
  for (const route of ['history.json?page=2', 'chart.json?preset=medium', 'personal.json']) {
    const attached = await services.aggregate(new Request(origin + route, {
      headers: { 'x-cloud-generation': original.generation },
    }), subject);
    assert.equal(attached.status, 200, route);
    assert.equal((await attached.json()).generation, original.generation, route);
  }
  const other = await services.aggregate(new Request(origin + 'personal.json'), '223456789012345678');
  assert.notEqual((await other.json()).generation, original.generation);
  source.revision += 1;
  const changed = await services.aggregate(new Request(origin + 'history.json?page=2', {
    headers: { 'x-cloud-generation': original.generation },
  }), subject);
  assert.equal(changed.status, 409);
  const newer = await (await services.aggregate(new Request(origin + 'analytics.json'), subject)).json();
  assert.equal(newer.as_of, original.as_of);
  assert.notEqual(newer.generation, original.generation);
});

test('pointer changes during reads and missing signing configuration never return member data', async () => {
  const { source, adapters } = servicesFixture();
  adapters.personal = async () => {
    source.revision += 1;
    return { trade_count: 2 };
  };
  const request = new Request(origin + 'personal.json');
  const changed = await memberServices(adapters, 'synthetic-secret').aggregate(request, subject);
  assert.equal(changed.status, 409);
  assert.deepEqual(await changed.json(), { error: 'source_changed' });
  const unavailable = await memberServices(adapters, undefined).aggregate(request, subject);
  assert.equal(unavailable.status, 503);
});

const assets = path.join(gate, 'scripts/new-a-ui-source/assets');
const loader = fs.readFileSync(path.join(assets, 'member-loader.js'), 'utf8');
const settings = fs.readFileSync(path.join(assets, 'member-settings.js'), 'utf8');
const presenter = { require: require('node:module').createRequire(path.join(assets, 'member-presentation.js')), module: { exports:{} }, TextEncoder };
vm.runInNewContext(fs.readFileSync(path.join(assets, 'member-presentation.js'), 'utf8'), presenter);
const {
  fundamentalItem, fundamentalMarkup, fundamentalSelector, referencePayload, referenceHistory,
  referenceHistoryIndex, matchingHistory, referenceHistoryTable, historyContent,
} = presenter.module.exports;
const initialToken = 'a'.repeat(64);
const nextToken = 'b'.repeat(64);
const initialSession = 'c'.repeat(64);
const nextSession = 'd'.repeat(64);
const flush = () => new Promise(resolve => setImmediate(resolve));
function element(type) {
  let content = '';
  const node = {
    type,
    hidden: false,
    innerHTML: '',
    children: [],
    attributes: {},
    isConnected: true,
    get lastElementChild() { return this.children.at(-1); },
    get textContent() { return content; },
    set textContent(value) { content = value; this.children = []; },
    events: {},
    append(...children) {
      this.children.push(...children);
      for (const child of children) if (child && typeof child === 'object') child.parent = this;
    },
    replaceChildren(...children) { this.innerHTML = ''; this.children = children; },
    setAttribute(name, value) { this.attributes[name] = value; },
    getAttribute(name) { return this.attributes[name]; },
    removeAttribute(name) { delete this.attributes[name]; },
    contains(node) { return this.children.includes(node); },
    remove() {
      this.isConnected = false;
      if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this);
    },
    focus() { this.focused = true; },
    addEventListener(type, handler) { this.events[type] = handler; },
  };
  if (type === 'dialog') {
    const close = element('button');
    node.querySelector = () => close;
    node.showModal = () => { node.open = true; };
    node.close = () => { node.open = false; node.events.close(); };
  }
  return node;
}
function browser(options = {}) {
  let access = 204;
  let tier = options.tier ?? 'premium';
  let session = initialSession;
  let interval;
  const requests = [];
  const windowEvents = {};
  const settingsDialog = {
    open:false,
    connect(_mount,canOpen) { this.canOpen=canOpen; },
    close(force) { assert.equal(force,true); this.open=false; },
  };
  const nodes = Object.fromEntries(['state', 'retry', 'content', 'preset'].map(key => ['member-' + key, element()]));
  const historyPanel = element('section');
  const historyRegion = element('div');
  const containsMain = nodes['member-content'].contains.bind(nodes['member-content']);
  nodes['member-content'].contains = node => containsMain(node) || historyRegion.contains(node);
  const historyButton = element('button');
  const historyState = element('p');
  const historyRenderings = [];
  let intersectHistory;
  const historyFilters = element('div');
  const historyResults = element('div');
  const historyNotice = element('output');
  const clearSearch = element('button');
  const inputs = Object.fromEntries(['symbol','from','through','order'].map(key => [key, {
    ...element('input'), dataset:{historyFilter:key},
  }]));
  historyFilters.querySelector = selector => selector === '[data-history-clear]'
    ? clearSearch : inputs[selector.split('"')[1]];
  const referenceRoot = element('div');
  const referenceMounts = [];
  const premiumLink = { hidden: true };
  const document = {
    documentElement: { dataset: {} },
    body: { dataset: { page: options.page ?? 'home' } },
    visibilityState: 'visible',
    events: {},
    getElementById(id) {
      if (id === 'member-reference-content' && nodes['member-content'].innerHTML === 'synthetic-reference-slot') return referenceRoot;
      if (id === 'history') return historyPanel;
      if (id === 'member-history-content') return historyRegion;
      if (id === 'member-history-open') return historyButton;
      if (id === 'member-history-state') return historyState;
      if (options.historyFilters) {
        if (id === 'member-history-filters') return historyFilters;
        if (id === 'member-history-results') return historyResults;
        if (id === 'member-history-filter-status') return historyNotice;
      }
      return nodes[id];
    },
    querySelectorAll(selector) { return selector === '[data-member-premium-nav]' ? [premiumLink] : []; },
    createElement(type) {
      const node = element(type);
      if (type === 'template') node.content = { querySelectorAll: () => options.referenceElements ?? [] };
      return node;
    },
    addEventListener(type, handler) { this.events[type] = handler; },
  };
  const context = {
    document,
    location: { pathname: '/weak_early_beta_latest.html', hash: options.hash ?? '' },
    IntersectionObserver: class {
      constructor(callback) { this.callback = callback; }
      observe(panel) {
        assert.equal(panel, historyPanel);
        intersectHistory = () => {
          if (!this.disconnected) this.callback([{ isIntersecting: true }]);
        };
        if (!options.historyOffscreen) queueMicrotask(intersectHistory);
      }
      disconnect() { this.disconnected = true; }
    },
    AbortSignal,
    AbortController,
    addEventListener(name,handler) { windowEvents[name]=handler; },
    CloudSettingsDialog:settingsDialog,
    NewAReferenceAnalytics:{ mount(root) { referenceMounts.push(root); } },
    structuredClone,
    setTimeout: callback => setImmediate(callback),
    clearTimeout: clearImmediate,
    setInterval(handler) { interval = handler; },
    NewAMemberPresentation: {
      view: values => {
        options.capture?.(values);
        return values.reference ? 'synthetic-reference-slot'
          : values.access === 'premium' ? 'synthetic-private-content' : 'synthetic-closed-history';
      },
      lockedPage: mode => 'synthetic-premium-lock-' + mode,
      freeHome: () => 'synthetic-premium-purchase',
      fundamentalItem, fundamentalMarkup, fundamentalSelector, referencePayload, referenceHistory,
      referenceHistoryIndex, matchingHistory, referenceHistoryTable,
      historyContent(rows, page, referenceRows, selected) {
        historyRenderings.push({ page, referenceRows, selected });
        return historyContent(rows, page, referenceRows, selected);
      },
    },
    fetch: async (route, init) => {
      const url = new URL(route, 'https://example.invalid');
      const name = url.pathname.split('/').at(-1);
      requests.push({ name, url, init });
      if (name === 'session') return new Response(null, {
        status: access,
        headers: access === 204 && session ? { 'x-cloud-member-session': session, 'x-cloud-member-access': tier } : undefined,
      });
      if (options.read) {
        const result = await options.read(name, url, init);
        if (result) return result;
      }
      if (name === 'reference.json') return new Response(null,{status:404});
      return Response.json({ as_of: day, generation: initialToken, rows: [], presets: [], pages: 3,
        page: Number(url.searchParams.get('page')) });
    },
  };
  vm.createContext(context);
  if (options.page === 'settings') vm.runInContext(settings, context);
  vm.runInContext(loader, context);
  return {
    document, requests, nodes, premiumLink, referenceRoot, referenceMounts,
    historyFilters, historyResults, historyNotice, historyRegion, historyButton, historyState,
    historyRenderings, inputs, clearSearch, scrollToHistory() { intersectHistory(); },
    settingsDialog, restore() { windowEvents.pageshow({ persisted:true }); },
    navigateAway() { windowEvents.pagehide(); },
    poll() { interval(); },
    show() {
      document.visibilityState = 'visible';
      document.events.visibilitychange();
    },
    hide() {
      document.visibilityState = 'hidden';
      document.events.visibilitychange();
    },
    setAccess(status) { access = status; },
    setTier(value) { tier = value; },
    setSession(value) { session = value; },
  };
}

const availableAnalysis = { date: '2026-11-18', symbol: '234A', state: 'EXPIRED', has_fundamental: true };
const analysisItem = '1.2026-11-18.234A';
const analysis = {
  date: availableAnalysis.date, symbol: availableAnalysis.symbol, as_of: day, generation: initialToken,
  company_name: '合成の銘柄', analysis_cutoff: '2026-11-18T16:15:00+09:00',
  fields: ['材料インパクト','事業概要','足元材料','ファンダ要点','注意点','開示リンク','Sources']
    .map(label => ({ label, text: '検証済み分析' })),
};
const navigationView = { as_of: day, generation: initialToken, markup: '<section>合成旧表示</section>' };
function historyReference(page, rows = []) {
  return { ...navigationView, markup: JSON.stringify({ page, rows }) };
}
const detailRow = {
  date: availableAnalysis.date, symbol: availableAnalysis.symbol, companyName: '合成',
  chartAllowed: true, signalClose: 100, d5: null, d6: null, item: analysisItem,
  levels: [['EXPIRED',false,null,null],['EXPIRED',false,null,null],['EXPIRED',false,null,null]],
};
function projectedElement(localName, values = {}) {
  return {
    localName, id:values.id ?? '',
    attributes:Object.entries(values).map(([name,value])=>({name,value})),
    hasAttribute:name=>Object.hasOwn(values,name),
    dataset:{memberFundamental:values['data-member-fundamental']},
  };
}

test('approved reference renders with pinned member scope and uses neither legacy data nor quote downloads', async () => {
  for (const mode of ['home','analytics']) {
    const item = (mode === 'home' ? 'dashboard' : 'analytics.overview') + '.return_priority';
    const view = browser({ page:mode, read:(name,url)=>name === 'reference.json'
      ? Response.json(url.searchParams.get('item') === 'history.1' ? historyReference(1) : {...navigationView,item}) : null });
    await flush();
    const requests = view.requests.map(request=>request.name);
    assert.deepEqual(requests, mode === 'home'
      ? ['session','preferences','reference.json','session','session','history.json','reference.json','session']
      : ['session','preferences','reference.json','session']);
    const fetched = view.requests.find(request=>request.name==='reference.json');
    assert.equal(fetched.url.searchParams.get('item'),item);
    assert.equal(fetched.init.headers['x-cloud-member-session'],initialSession);
    assert.equal(view.nodes['member-content'].innerHTML,'synthetic-reference-slot');
    assert.equal(view.referenceRoot.children.length,1);
    assert.deepEqual(view.referenceMounts, mode === 'analytics' ? [view.referenceRoot] : []);
    assert.equal(view.nodes['member-state'].textContent,'');
  }
});

test('dashboard cards render before offscreen or stalled history and history uses the active generation', async () => {
  const delayedHistory = Promise.withResolvers();
  const dashboard = browser({
    historyOffscreen: true,
    read(name, url) {
      if (name === 'history.json') return delayedHistory.promise;
      if (name === 'reference.json') return Response.json(url.searchParams.get('item') === 'history.1'
        ? historyReference(1) : navigationView);
      return null;
    },
  });
  await flush();
  assert.deepEqual(dashboard.requests.map(call => call.name), ['session', 'preferences', 'reference.json', 'session']);
  assert.equal(dashboard.referenceRoot.children.length, 1);
  assert.equal(dashboard.historyRenderings.length, 0);
  dashboard.scrollToHistory();
  await flush();
  const history = dashboard.requests.find(call => call.name === 'history.json');
  assert.equal(history.init.headers['x-cloud-generation'], initialToken);
  assert.equal(history.init.headers['x-cloud-member-session'], initialSession);
  assert.equal(dashboard.historyRegion.getAttribute('aria-busy'), 'true');
  assert.equal(dashboard.historyRenderings.length, 0);
  assert.equal(dashboard.referenceRoot.children.length, 1);

  delayedHistory.resolve(Response.json({ as_of: day, generation: initialToken, page: 1, pages: 1, rows: [] }));
  await flush();
  assert.equal(dashboard.historyRenderings.length, 1);
  assert.equal(dashboard.historyRegion.getAttribute('aria-busy'), undefined);
  assert.equal(dashboard.referenceRoot.children.length, 1);
});

test('account display settings apply without blocking cards or skipping saved history', async () => {
  const preferences = Promise.withResolvers();
  const rows = Array.from({ length: 107 }, (_, index) => ({
    date: day, symbol: String(1000 + index), state: 'EXPIRED',
  }));
  const view = browser({ historyOffscreen: true, read: (name, url, init) => {
    if (name === 'preferences') {
      assert.equal(init.headers['x-cloud-member-session'], initialSession);
      return preferences.promise;
    }
    if (url.searchParams.get('item') === 'dashboard.return_priority') {
      return Response.json({ ...navigationView, item: 'dashboard.return_priority' });
    }
    if (name === 'history.json') {
      const page = Number(url.searchParams.get('page'));
      return Response.json({ ...navigationView, page, pages: 2, rows: rows.slice((page - 1) * 100, page * 100) });
    }
    return null;
  } });
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-reference-slot');
  preferences.resolve(Response.json({ revision: 2, view_preferences: { theme: 'light', font_size: 'large', page_size: 20 } }));
  await flush();
  assert.deepEqual(view.document.documentElement.dataset, { theme: 'light', fontSize: 'large' });
  view.scrollToHistory();
  const next = () => view.historyRegion.lastElementChild.children.at(-1).events.click();
  const historyReads = () => view.requests.filter(request => request.name === 'history.json');
  for (let index = 0; index < 5; index++) {
    await flush();
    assert.match(view.historyRegion.innerHTML, new RegExp(String(1000 + index * 20)));
    assert.doesNotMatch(view.historyRegion.innerHTML, new RegExp(String(1000 + (index + 1) * 20)));
    assert.equal(historyReads().length, 1);
    next();
  }
  await flush();
  assert.match(view.historyRegion.innerHTML, /1100/);
  assert.match(view.historyRegion.innerHTML, /1106/);
  assert.equal(view.historyRegion.lastElementChild.children.at(-1).disabled, true);
  assert.equal(historyReads().length, 2);
  view.setAccess(403);
  view.poll();
  await flush();
  assert.deepEqual(view.document.documentElement.dataset, { theme: 'dark' });
});

test('role loss aborts delayed dashboard history and does not repaint either protected region', async () => {
  const delayedHistory = Promise.withResolvers();
  const dashboard = browser({
    read(name) { return name === 'history.json' ? delayedHistory.promise
      : name === 'reference.json' ? Response.json(navigationView) : null; },
  });
  await flush();
  const history = dashboard.requests.find(call => call.name === 'history.json');
  assert.ok(history);
  dashboard.setAccess(403);
  dashboard.poll();
  await flush();
  assert.equal(history.init.signal.aborted, true);
  delayedHistory.resolve(Response.json({ as_of: day, generation: initialToken, page: 1, pages: 1, rows: [] }));
  await flush();
  assert.equal(dashboard.nodes['member-content'].innerHTML, '');
  assert.equal(dashboard.historyRenderings.length, 0);
  assert.match(dashboard.nodes['member-state'].textContent, /アクセス権/);
});

test('only absent reference uses a partial V3 render; mismatched, blocked and unsafe reference stays hidden', async () => {
  const missing = browser();
  await flush();
  assert.ok(missing.requests.some(request=>request.name==='dashboard.json'));
  assert.match(missing.nodes['member-state'].textContent,/一部の表示/);
  assert.equal(missing.nodes['member-retry'].hidden,false);
  const failures = [
    [()=>new Response(null,{status:403}), [], /アクセス権/],
    [()=>new Response(null,{status:409}), [], /データが更新/],
    [()=>Response.json(null), [], /現在読み込めません/],
    [()=>Response.json({...navigationView,item:'dashboard.medium'}), [], /現在読み込めません/],
    [()=>Response.json(navigationView), [projectedElement('script')], /現在読み込めません/],
    [()=>Response.json(navigationView), [projectedElement('button',{onclick:'bad'})], /現在読み込めません/],
    [()=>Response.json(navigationView), [projectedElement('a',{href:'javascript:false'})], /現在読み込めません/],
  ];
  for (const [response, referenceElements, message] of failures) {
    const view = browser({referenceElements,read:name=>name==='reference.json'?response():null});
    await flush();
    assert.equal(view.nodes['member-content'].innerHTML,'');
    assert.equal(view.referenceRoot.children.length,0);
    assert.match(view.nodes['member-state'].textContent,message);
    assert.equal(view.requests.some(request=>request.name==='dashboard.json'),false);
  }
});

test('a dashboard reference stock opens only its exact generation-scoped report even off the current history page', async () => {
  const item = '42.2026-11-18.234A';
  const view = browser({
    referenceElements:[projectedElement('button',{'data-member-fundamental':item})],
    read:(name,url)=>name==='reference.json'?Response.json(url.searchParams.get('item')==='history.1'
      ? historyReference(1) : navigationView)
      : name==='fundamental.json'?Response.json(analysis):null,
  });
  await flush();
  const content = view.nodes['member-content'];
  assert.equal(view.requests.some(request=>request.name==='fundamental.json'),false);
  const button = element('button');
  button.dataset = {memberFundamental:item};
  button.closest = () => button;
  content.append(button);
  content.events.click({target:button});
  await flush();
  const request = view.requests.find(call=>call.name==='fundamental.json');
  assert.equal(request.url.searchParams.get('item'),item);
  assert.equal(request.init.headers['x-cloud-generation'],initialToken);
  assert.equal(request.init.headers['x-cloud-member-session'],initialSession);
  assert.ok(content.children.some(child=>child.type==='dialog' && child.open));
  view.hide();
  assert.equal(content.children.some(child=>child.type==='dialog'),false);
});

function analysisBrowser(options = {}) {
  const view = browser({ ...options, read: (name, url, init) => {
    if (name === 'history.json') return Response.json({ as_of: day, generation: initialToken, pages: 3,
      page: Number(url.searchParams.get('page')), rows: [availableAnalysis] });
    return options.read?.(name, url, init);
  } });
  const content = view.nodes['member-content'];
  const button = element('button');
  button.dataset = { memberFundamental: analysisItem };
  button.closest = () => button;
  return { ...view, content, button, click() {
    view.historyRegion.append(button);
    content.events.click({ target: button });
  },
    dialog: () => content.children.find(child => child.type === 'dialog') };
}

test('loading history preserves an in-flight dashboard analysis with the same item and generation', async () => {
  const delayedReport = Promise.withResolvers();
  const delayedHistory = Promise.withResolvers();
  const view = browser({
    historyOffscreen: true,
    referenceElements: [projectedElement('button', { 'data-member-fundamental': analysisItem })],
    read(name, url) {
      if (name === 'history.json') return delayedHistory.promise;
      if (name === 'fundamental.json') return delayedReport.promise;
      if (name === 'reference.json') return Response.json(url.searchParams.get('item') === 'history.1'
        ? historyReference(1, [detailRow]) : navigationView);
      return null;
    },
  });
  await flush();
  const content = view.nodes['member-content'];
  const button = element('button');
  button.dataset = { memberFundamental: analysisItem };
  button.closest = () => button;
  content.append(button);
  content.events.click({ target: button });
  view.scrollToHistory();
  await flush();
  const report = view.requests.find(request => request.name === 'fundamental.json');
  assert.ok(report);
  delayedHistory.resolve(Response.json({ as_of: day, generation: initialToken, page: 1, pages: 1, rows: [availableAnalysis] }));
  await flush();
  assert.equal(view.historyRenderings.length, 1);
  assert.equal(report.init.signal.aborted, false);
  delayedReport.resolve(Response.json(analysis));
  await flush();
  assert.ok(content.children.find(child => child.type === 'dialog' && child.open));
});

test('reference history follows the page generation, controls mobile details and opens only a verified exact analysis', async () => {
  const view = analysisBrowser({ read: (name,url) => {
    const item = url.searchParams.get('item');
    if (name === 'reference.json') return Response.json(item.startsWith('dashboard.') ? navigationView
      : historyReference(Number(item.split('.')[1]), [{...detailRow,item:item === 'history.1' ? analysisItem : '2.2026-11-18.234A'}]));
    if (name === 'fundamental.json') return Response.json(analysis);
    return null;
  } });
  await flush();
  assert.equal(view.historyRenderings.at(-1).referenceRows[0].item, analysisItem);
  const detail = element('button');
  const classes = new Set();
  const record = { classList:{ toggle(name, open) { if (open) classes.add(name); else classes.delete(name); } } };
  detail.closest = selector => selector === '[data-member-history-details]' ? detail
    : selector === '#detection-table .history-record' ? record : null;
  view.content.append(detail);
  for (const open of [true,false]) {
    view.content.events.click({target:detail});
    assert.equal(classes.has('history-details-open'),open);
    assert.equal(detail.getAttribute('aria-expanded'),String(open));
    assert.equal(detail.textContent,open?'詳細を閉じる':'詳細を見る');
  }
  view.click();
  await flush();
  assert.equal(view.dialog().open,true);
  view.historyRegion.children[0].lastElementChild.events.click();
  await flush();
  assert.equal(view.dialog(),undefined);
  assert.equal(view.historyRenderings.at(-1).referenceRows[0].item, '2.2026-11-18.234A');
  assert.equal(view.requests.filter(request => request.url.searchParams.get('item')?.startsWith('dashboard.')).length, 1);
  const page2 = view.requests.find(request=>request.url.searchParams.get('item')==='history.2');
  assert.equal(page2.init.headers['x-cloud-generation'],initialToken);
  assert.equal(page2.init.headers['x-cloud-member-session'],initialSession);
});

test('history reference falls back independently only on explicit 404', async () => {
  const responses = [
    [new Response(null,{status:404}), /検出履歴の詳細を読み込めません/, true],
    [new Response(null,{status:403}), /アクセス権/, false],
    [new Response(null,{status:409}), /データが更新/, false],
    [Response.json({...historyReference(1),generation:nextToken}), /データが更新/, false],
    [Response.json(historyReference(2)), /検出履歴を読み込めません/, true],
    [Response.json(historyReference(1,[{...detailRow,item:'2.2026-11-18.234A'}])), /検出履歴を読み込めません/, true],
  ];
  for (const [response, message, dashboardRemains] of responses) {
    const view = analysisBrowser({read:(name,url)=>name==='reference.json'
      ? url.searchParams.get('item')==='history.1' ? response : Response.json(navigationView) : null});
    await flush();
    assert.equal(view.content.innerHTML, dashboardRemains ? 'synthetic-reference-slot' : '');
    assert.match((dashboardRemains ? view.historyState : view.nodes['member-state']).textContent, message);
    assert.equal(view.requests.some(request=>request.name==='dashboard.json'),false);
  }
});

test('old filters lazily resolve only matching rich pages and clear back to native history', async () => {
  const rows = Array.from({length:140},(_,offset)=>({
    ...detailRow,
    date:offset < 100 ? '2026-11-18' : '2026-11-10',
    symbol:String(1000 + offset),
    companyName:offset < 100 ? '銘柄' : '合成検索',
  })).map(({item,...row})=>row);
  const index = { names:['銘柄','合成検索'], rows:rows.map((row,offset)=>[row.date,row.symbol,offset < 100 ? 0 : 1]) };
  const view = browser({historyFilters:true, read:(name,url)=>{
    if (name === 'history.json') return Response.json({as_of:day,generation:initialToken,page:1,pages:2,rows:rows.slice(0,100)});
    if (name !== 'reference.json') return null;
    const item = url.searchParams.get('item');
    if (item === 'history.index') return Response.json({...navigationView,markup:JSON.stringify(index)});
    if (item === 'history.1') return Response.json(historyReference(1,rows.slice(0,100)));
    if (item === 'history.2') return Response.json(historyReference(2,rows.slice(100)));
    return Response.json(navigationView);
  }});
  await flush();
  const asked = item => view.requests.filter(c=>c.url.searchParams.get('item')===item);
  assert.equal(asked('history.index').length,0);
  assert.equal(asked('history.2').length,0);
  view.inputs.symbol.value = '合成検索';
  view.historyFilters.events.input({target:view.inputs.symbol});
  await flush();
  await flush();
  assert.match(view.historyNotice.textContent,/40件/);
  assert.equal(asked('history.index').length,1);
  assert.equal(asked('history.2').length,1);
  assert.equal(asked('history.index')[0].init.headers['x-cloud-generation'],initialToken);
  assert.match(view.historyResults.innerHTML,/>1100<.*>1119</);
  assert.doesNotMatch(view.historyResults.innerHTML,/>1120</);
  view.historyResults.lastElementChild.lastElementChild.events.click();
  await flush();
  assert.equal(asked('history.index').length,1);
  assert.match(view.historyResults.innerHTML,/>1120<.*>1139</);
  view.clearSearch.events.click();
  await flush();
  assert.equal(view.historyNotice.textContent,'');
  assert.match(view.historyResults.innerHTML,/>1000<.*>1099</);
  assert.equal(view.inputs.symbol.focused,true);
});

test('old history filters clear the protected view when the lazy index is denied or changes generation', async () => {
  const index = { names:['合成'], rows:[[detailRow.date,detailRow.symbol,0]] };
  for (const [getIndex,message] of [
    [()=>new Response(null,{status:403}),/アクセス権/],
    [()=>Response.json({...navigationView,generation:nextToken,markup:JSON.stringify(index)}),/データが更新/],
  ]) {
    const view = browser({historyFilters:true,read:(name,url)=>{
      if (name === 'history.json') return Response.json({as_of:day,generation:initialToken,page:1,pages:1,rows:[availableAnalysis]});
      if (name !== 'reference.json') return null;
      const item = url.searchParams.get('item');
      if (item === 'history.index') return getIndex();
      if (item === 'history.1') return Response.json(historyReference(1,[detailRow]));
      return Response.json(navigationView);
    }});
    await flush();
    view.inputs.order.value = 'oldest';
    view.historyFilters.events.change({target:view.inputs.order});
    await flush();
    assert.equal(view.nodes['member-content'].innerHTML,'');
    assert.match(view.nodes['member-state'].textContent,message);
    assert.equal(view.requests.some(request=>request.name==='dashboard.json'),false);
  }
});

test('fundamental dialog lazily uses the exact history page, session and generation', async () => {
  const view = analysisBrowser({ read: name => name === 'fundamental.json' ? Response.json(analysis) : null });
  await flush();
  assert.equal(view.requests.some(request => request.name === 'fundamental.json'), false);
  view.click();
  await flush();
  const fetched = view.requests.find(request => request.name === 'fundamental.json');
  assert.equal(fetched.url.searchParams.get('item'), analysisItem);
  assert.equal(fetched.init.headers['x-cloud-member-session'], initialSession);
  assert.equal(fetched.init.headers['x-cloud-generation'], initialToken);
  assert.equal(view.dialog().open, true);
  assert.match(view.dialog().innerHTML, /検証済み分析/);
  view.dialog().close();
  assert.equal(view.dialog(), undefined);
  assert.equal(view.button.focused, true);
  view.click();
  await flush();
  assert.equal(view.dialog().open, true);
  view.setTier('free');
  view.poll();
  await flush();
  assert.equal(view.dialog(), undefined);

  const free = analysisBrowser({ tier: 'free' });
  await flush();
  free.click();
  await flush();
  assert.equal(free.requests.some(request => request.name === 'fundamental.json'), false);
});

test('page or role change aborts an in-flight report and prevents a late response from opening it', async () => {
  for (const changed of ['page','role']) {
    let deliver;
    const pending = new Promise(resolve => { deliver = resolve; });
    const view = analysisBrowser({ read: name => name === 'fundamental.json' ? pending : null });
    await flush();
    view.click();
    await flush();
    const fetch = view.requests.find(request => request.name === 'fundamental.json');
    if (changed === 'page') view.historyRegion.children[0].lastElementChild.events.click();
    else { view.setTier('free'); view.poll(); }
    await flush();
    assert.equal(fetch.init.signal.aborted, true);
    deliver(Response.json(analysis));
    await flush();
    assert.equal(view.dialog(), undefined);
  }
});

test('404 removes an unavailable row action and a mismatched generation clears current member data', async () => {
  const missing = analysisBrowser({ read: name => name === 'fundamental.json' ? new Response(null,{status:404}) : null });
  await flush();
  missing.click();
  await flush();
  assert.equal(missing.button.isConnected, false);
  assert.equal(missing.dialog(), undefined);
  assert.equal(missing.content.innerHTML, 'synthetic-private-content');

  const newer = analysisBrowser({ read: name => name === 'fundamental.json'
    ? Response.json({ ...analysis,generation:nextToken }) : null });
  await flush();
  newer.click();
  await flush();
  assert.equal(newer.dialog(), undefined);
  assert.equal(newer.content.innerHTML, '');
  assert.match(newer.nodes['member-state'].textContent, /データが更新/);
});

test('free dashboard and paid direct pages never request Premium data or settings', async () => {
  const free = browser({ tier: 'free' });
  await flush();
  assert.deepEqual(free.requests.map(request => request.name), ['session', 'history.json', 'session']);
  assert.equal(free.nodes['member-content'].innerHTML, 'synthetic-closed-history');
  assert.equal(free.premiumLink.hidden, true);
  for (const page of ['analytics', 'settings']) {
    const locked = browser({ page, tier: 'free' });
    await flush();
    assert.deepEqual(locked.requests.map(request => request.name), ['session']);
    assert.equal(locked.nodes['member-content'].innerHTML, 'synthetic-premium-lock-' + page);
  }
});

test('confirmed Free access keeps the purchase action during a history outage', async () => {
  let historyStatus = 503;
  const view = browser({ tier: 'free', read: name => name === 'history.json' && historyStatus !== 200
    ? new Response(null, { status: historyStatus }) : null });
  assert.equal(view.nodes['member-content'].innerHTML, '');
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-premium-purchase');
  assert.match(view.nodes['member-state'].textContent, /履歴を読み込めません/);
  assert.equal(view.nodes['member-retry'].hidden, false);
  assert.deepEqual(view.requests.map(request => request.name), ['session', 'history.json', 'session']);

  historyStatus = 200;
  view.nodes['member-retry'].events.click();
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-closed-history');

  historyStatus = 403;
  view.nodes['member-content'].children[0].lastElementChild.events.click();
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, '');
});

test('changed tier clears the older Premium view before it can repaint', async () => {
  const view = browser();
  await flush();
  assert.equal(view.premiumLink.hidden, false);
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-private-content');
  view.setTier('free');
  view.poll();
  await flush();
  assert.equal(view.premiumLink.hidden, true);
  assert.equal(view.nodes['member-content'].innerHTML, '');
  const before = view.requests.length;
  view.nodes['member-retry'].events.click();
  await flush();
  assert.deepEqual(view.requests.slice(before).map(request => request.name), ['session', 'history.json', 'session']);
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-closed-history');
});

test('browser refuses mixed parallel responses even if their dates agree', async () => {
  const view = browser({ read: name => name === 'chart.json'
    ? Response.json({ generation: nextToken, as_of: day, rows: [] }) : null });
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, '');
  assert.match(view.nodes['member-state'].textContent, /データが更新/);
  assert.equal(view.nodes['member-retry'].hidden, false);
});

test('later pages send the last generation and rollback to page one after a source change', async () => {
  let change = false;
  const view = browser({ read: (name, url) => change && name === 'history.json' && url.searchParams.get('page') === '2'
    ? new Response(null, { status: 409 }) : null });
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-private-content');
  change = true;
  view.historyRegion.children[0].lastElementChild.events.click();
  await flush();
  const page2 = view.requests.find(request => request.url.searchParams.get('page') === '2');
  assert.equal(page2.init.headers['x-cloud-generation'], initialToken);
  assert.equal(page2.init.headers['x-cloud-member-session'], initialSession);
  assert.match(view.nodes['member-state'].textContent, /データが更新/);
  view.nodes['member-retry'].events.click();
  await flush();
  assert.equal(view.requests.filter(r => r.name === 'history.json').at(-1).url.searchParams.get('page'), '1');
  assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-private-content');
});

test('revocation aborts an in-flight private view and ignores a late response', async () => {
  let settle;
  const late = new Promise(resolve => { settle = resolve; });
  const view = browser({ read: name => name === 'chart.json' ? late : null });
  await flush();
  const call = view.requests.find(r => r.name === 'chart.json');
  assert.ok(call);
  view.setAccess(403);
  view.poll();
  await flush();
  assert.equal(call.init.signal.aborted, true);
  settle(Response.json({ generation: initialToken, as_of: day, rows: [] }));
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, '');
  assert.match(view.nodes['member-state'].textContent, /アクセス権/);
});

test('returning to the tab requires the same authorized session and hides revoked content', async () => {
  const view = browser();
  await flush();
  assert.equal(view.nodes['member-content'].hidden, false);
  view.hide();
  assert.equal(view.nodes['member-content'].hidden, true);
  view.setSession(nextSession);
  view.show();
  assert.equal(view.nodes['member-content'].hidden, true);
  await flush();
  assert.equal(view.nodes['member-content'].innerHTML, '');
  assert.match(view.nodes['member-state'].textContent, /アクセス権/);
});

test('member settings close before visibility and restored-page access rechecks settle', async () => {
  const view = browser();
  await flush();
  const dialog = view.settingsDialog;
  assert.equal(dialog.canOpen(),true);
  for (const transition of ['hide','show','restore','navigateAway']) {
    dialog.open=true;
    view[transition]();
    assert.equal(dialog.open,false,transition);
    assert.equal(view.nodes['member-content'].hidden,true,transition);
    assert.equal(dialog.canOpen(),false,transition);
    await flush();
  }
});

test('role loss clears settings and a delayed settings response cannot repaint them', async () => {
  let settle;
  const late = new Promise(resolve => { settle = resolve; });
  const view = browser({ page: 'settings', read: name => name === 'preferences' ? late : null });
  await flush();
  const preferences = view.requests.find(r => r.name === 'preferences');
  assert.equal(preferences.init.headers['x-cloud-member-session'], initialSession);
  assert.equal(view.nodes['member-content'].children.length, 1);
  view.setAccess(401);
  view.poll();
  await flush();
  settle(Response.json({ revision: 1, save_binding: 'synthetic', preferences: {}, view_preferences: {} }));
  await flush();
  assert.equal(preferences.init.signal.aborted, true);
  assert.equal(view.nodes['member-content'].children.length, 0);
  assert.match(view.nodes['member-state'].textContent, /アクセス権/);
});

test('expired login offers a user-clicked Discord link while role denial and outages offer safe retry', async () => {
  for (const status of [401, 403, 503]) {
    const view = browser();
    await flush();
    view.setAccess(status);
    view.poll();
    await flush();
    const link = view.nodes['member-state'].children.at(-1);
    assert.equal(view.nodes['member-content'].innerHTML, '');
    assert.equal(view.nodes['member-retry'].hidden, false);
    assert.equal(link?.href, status === 401 ? '/auth/login?return_to=%2Fweak_early_beta_latest.html' : undefined);
    view.setAccess(204);
    view.nodes['member-retry'].events.click();
    await flush();
    assert.equal(view.nodes['member-content'].innerHTML, 'synthetic-private-content');
    assert.equal(view.nodes['member-state'].children.length, 0);
  }
});
