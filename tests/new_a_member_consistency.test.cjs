const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const ts = require('../weak-early-beta-gate/node_modules/typescript');

const gate = path.resolve(__dirname, '../weak-early-beta-gate');
const servicesSource = fs.readFileSync(path.join(gate, 'src/new-a-member-services.ts'), 'utf8');
const servicesModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(servicesSource, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText, {
  module: servicesModule,
  exports: servicesModule.exports,
  require: name => {
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
const initialToken = 'a'.repeat(64);
const nextToken = 'b'.repeat(64);
const initialSession = 'c'.repeat(64);
const nextSession = 'd'.repeat(64);
const flush = () => new Promise(resolve => setImmediate(resolve));
function element() {
  let content = '';
  return {
    hidden: false,
    innerHTML: '',
    children: [],
    get textContent() { return content; },
    set textContent(value) { content = value; this.children = []; },
    events: {},
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.innerHTML = ''; this.children = children; },
    setAttribute() {},
    addEventListener(type, handler) { this.events[type] = handler; },
  };
}
function browser(options = {}) {
  let access = 204;
  let tier = options.tier ?? 'premium';
  let session = initialSession;
  let interval;
  const requests = [];
  const nodes = Object.fromEntries(['state', 'retry', 'content', 'preset'].map(key => ['member-' + key, element()]));
  const premiumLink = { hidden: true };
  const document = {
    body: { dataset: { page: options.page ?? 'home' } },
    visibilityState: 'visible',
    events: {},
    getElementById(id) { return nodes[id]; },
    querySelectorAll(selector) { return selector === '[data-member-premium-nav]' ? [premiumLink] : []; },
    createElement: element,
    addEventListener(type, handler) { this.events[type] = handler; },
  };
  const context = {
    document,
    location: { pathname: '/weak_early_beta_latest.html' },
    AbortSignal,
    AbortController,
    addEventListener() {},
    structuredClone,
    setInterval(handler) { interval = handler; },
    NewAMemberPresentation: {
      view: ({ access }) => access === 'premium' ? 'synthetic-private-content' : 'synthetic-closed-history',
      lockedPage: mode => 'synthetic-premium-lock-' + mode,
      freeHome: () => 'synthetic-premium-purchase',
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
      return Response.json({ as_of: day, generation: initialToken, rows: [], presets: [], pages: 3 });
    },
  };
  vm.createContext(context);
  if (options.page === 'settings') vm.runInContext(settings, context);
  vm.runInContext(loader, context);
  return {
    document, requests, nodes, premiumLink,
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
  view.nodes['member-content'].children[0].children[1].events.click();
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
  view.nodes['member-content'].children[0].children[1].events.click();
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
