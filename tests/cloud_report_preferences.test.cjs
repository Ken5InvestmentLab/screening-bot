const test = require('node:test');
const assert = require('node:assert/strict');
const prefs = require('../reports/weak-early-beta-interactions.js');
const fs = require('node:fs');
const vm = require('node:vm');

test('explicit unlimited and arbitrary positive two-decimal caps without rounding', () => {
  assert.equal(prefs.parseCap(null), null);
  assert.equal(prefs.parseCap('1234.56'), 1234.56);
  assert.equal(prefs.parseCap(1500), 1500);
  assert.deepEqual(prefs.PRESETS, [1000, 2000, 3000, 5000]);
  for (const invalid of ['', '0', 0, '-1', '1.234', '1e3', Infinity, NaN, true, undefined]) {
    assert.throws(() => prefs.parseCap(invalid));
  }
});

test('inclusive cap and unknown nominal close behavior are explicit', () => {
  assert.equal(prefs.matchesCap(1000, 'true', 1000), true);
  assert.equal(prefs.matchesCap(1000.01, true, 1000), false);
  assert.equal(prefs.matchesCap(999, false, 1000), false);
  assert.equal(prefs.matchesCap('', true, 1000), false);
  assert.equal(prefs.matchesCap(null, false, null), true);
});

test('every arbitrary cap chooses the last inclusive aggregate boundary', () => {
  const payload = { priceBreakpoints: [500.01, 1000, 1234.56, 6000] };
  const key = (cap, exitKey = 'd5_close') => prefs.variantKey(payload, { priceCapYen: cap, exitKey });
  assert.equal(key(500), 'd5_close:empty');
  assert.equal(key(1000), 'd5_close:1000');
  assert.equal(key(1234.55), 'd5_close:1000');
  assert.equal(key(1234.56, 'd6_open'), 'd6_open:1234.56');
  assert.equal(key(999999), 'd5_close:6000');
  assert.equal(key(null), 'd5_close:all');
});

test('CSV preserves missing prices, decimals and quotes without formula injection', () => {
  const csv = prefs.csv([{ name: '=HYPERLINK("x")', price: null, pl: -123.45 },
    { name: 'A,"B"', price: 1234.56, pl: 0 }], ['name', 'price', 'pl']);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"\'=HYPERLINK(""x"")","","-123.45"'));
  assert.ok(csv.includes('"A,""B""","1234.56","0"'));
});

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const flush = () => new Promise((resolve) => setImmediate(resolve));

// Run the shipped browser handlers, not a second implementation of their state
// machine. Only the browser boundary is simulated; the async variant completion,
// filter, endpoint, save and CSV paths below are the actual application code.
function browserFixture({ emptyHistory = false } = {}) {
  const elements = new Map();
  const downloads = [];
  const blobs = new Map();
  const storage = new Map();
  const requests = [];
  const queuedDecodes = new Map();
  const variants = {};
  const serverRead = deferred();
  let nextSave = null;
  class Element {
    constructor(id = '') {
      this.id = id; this.value = ''; this.dataset = {}; this.hidden = false;
      this.disabled = false; this.handlers = new Map(); this.attributes = {};
      this.innerHTML = ''; this.textContent = ''; this.children = [];
      if (id) elements.set(id, this);
    }
    addEventListener(type, handler) { this.handlers.set(type, handler); }
    // Deliberately dispatch even when disabled: the handler must independently
    // guard downloads/saves against keyboard or scripted event dispatch.
    dispatch(type) { return this.handlers.get(type)?.({ target: this }); }
    append(...children) {
      for (const child of children) {
        if (child.id) elements.set(child.id, child);
        child.parentElement = this;
        this.children.push(child);
      }
    }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    querySelectorAll() { return []; }
    querySelector() { return null; }
    closest() { return null; }
    focus() {}
    remove() {}
    click() {
      if (this.download) downloads.push({ filename: this.download, csv: blobs.get(this.href).parts.join('') });
      else return this.dispatch('click');
    }
  }
  for (const id of ['cloud-price-preset', 'cloud-price-custom', 'cloud-price-custom-field',
    'cloud-exit-endpoint', 'cloud-settings-save', 'cloud-settings-status',
    'cloud-analytics-data', 'cloud-analytics-content', 'cloud-export-csv',
    'cloud-history-export-csv', 'cloud-preferences', 'search-result-count', 'symbol-filter']) new Element(id);
  const rows = (emptyHistory ? [] : [
    { symbol: 'LOW1111', signalActualClose: '222.22', entryOpen: '220', d5Close: '242', d6Open: '244' },
    { symbol: 'HIGH9999', signalActualClose: '731.29', entryOpen: '730', d5Close: '803', d6Open: '810' },
  ]).map((values) => {
    const row = new Element();
    row.dataset = { ...values, signalPriceVerified: 'true', date: '2025-01-06',
      selectors: 'mode-a', entryDate: '2025-01-07', d6EntryDate: '2025-01-07',
      d6EntryOpen: values.entryOpen, d5Date: '2025-01-14', d6Date: '2025-01-15',
      d5Return: '0.1', d6Return: '0.11', d6Status: 'verified' };
    return row;
  });
  const emptyMessage = new Element();
  emptyMessage.textContent = '検出履歴がありません';
  const tableRows = emptyHistory ? [emptyMessage] : rows;
  const endpointCells = ['d5_close', 'd6_open'].map((exitKey) => {
    const element = new Element(); element.dataset.exitKey = exitKey; return element;
  });
  const payload = { priceBreakpoints: emptyHistory ? [] : [222.22, 731.29], variants: {} };
  for (const exit of ['d5_close', 'd6_open']) {
    for (const [bound, count] of [['empty', 0], ['222.22', 1], ['731.29', 2], ['all', 2]]) {
      const key = `${exit}:${bound}`;
      variants[key] = { html: `view:${key}`, metrics: [{ period: 'all', n: emptyHistory ? 0 : count }], monthlyMetrics: [] };
      payload.variants[key] = { gzip: Buffer.from(key).toString('base64') };
    }
  }
  elements.get('cloud-analytics-data').textContent = JSON.stringify(payload);
  elements.get('cloud-analytics-content').innerHTML = 'view:d5_close:731.29';
  class Blob {
    constructor(parts) { this.parts = parts; }
    stream() { return { pipeThrough: () => ({ key: Buffer.from(this.parts[0]).toString() }) }; }
  }
  class Response {
    constructor(stream) { this.key = stream.key; }
    json() { return queuedDecodes.get(this.key)?.shift()?.promise || Promise.resolve(variants[this.key]); }
  }
  const document = {
    documentElement: new Element(), body: new Element(),
    getElementById: (id) => elements.get(id) || null,
    querySelectorAll: (selector) => selector === '#detection-table tbody tr' ? tableRows
      : selector === '#detection-table tbody tr[data-date]' ? rows
      : selector === '[data-exit-key]' ? endpointCells : [],
    querySelector: () => null, addEventListener: () => {},
    createElement: () => new Element(), createTextNode: (textContent) => ({ textContent }),
  };
  class BrowserURL extends URL {
    static createObjectURL(blob) { const key = `blob:${blobs.size}`; blobs.set(key, blob); return key; }
    static revokeObjectURL() {}
  }
  const context = vm.createContext({
    document, Element, window: { location: { search: '' } }, Blob, Response,
    DecompressionStream: class {}, URL: BrowserURL, URLSearchParams,
    atob: (value) => Buffer.from(value, 'base64').toString('binary'),
    setTimeout: () => {}, console,
    localStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
    fetch: (url, options = {}) => {
      requests.push({ url, options });
      if (options.method === 'PUT') return nextSave?.promise || Promise.resolve({ ok: true });
      return serverRead.promise;
    },
  });
  vm.runInContext(fs.readFileSync(require.resolve('../reports/weak-early-beta-interactions.js'), 'utf8'), context);
  return {
    elements, downloads, storage, requests, rows, emptyMessage, endpointCells, variants, serverRead,
    get: (id) => elements.get(id),
    delay(key) { const item = deferred(); queuedDecodes.set(key, [...(queuedDecodes.get(key) || []), item]); return item; },
    delaySave() { nextSave = deferred(); return nextSave; },
    select(cap, exit = 'd5_close') {
      elements.get('cloud-price-preset').value = cap === null ? 'unlimited' : 'custom';
      elements.get('cloud-price-custom').value = String(cap ?? '');
      elements.get('cloud-exit-endpoint').value = exit;
      return elements.get('cloud-exit-endpoint').dispatch('change');
    },
    snapshot() {
      return { html: elements.get('cloud-analytics-content').innerHTML,
        symbols: rows.filter((row) => !row.hidden).map((row) => row.dataset.symbol),
        endpoints: endpointCells.filter((element) => !element.hidden).map((element) => element.dataset.exitKey) };
    },
    async exportBoth() {
      await elements.get('cloud-export-csv').dispatch('click');
      await elements.get('cloud-history-export-csv').dispatch('click');
      return downloads.slice(-2);
    },
  };
}

test('pending cap change blocks both CSVs and save, then commits one consistent population', async () => {
  const page = browserFixture(); await flush();
  const before = page.snapshot();
  const load = page.delay('d5_close:222.22');
  const change = page.select(500);
  assert.deepEqual(page.snapshot(), before);
  for (const id of ['cloud-export-csv', 'cloud-history-export-csv', 'cloud-settings-save']) assert.equal(page.get(id).disabled, true);
  await page.exportBoth(); await page.get('cloud-settings-save').dispatch('click');
  assert.equal(page.downloads.length, 0);
  assert.equal(page.requests.filter((request) => request.options.method === 'PUT').length, 0);
  assert.equal(page.storage.size, 0);
  load.resolve(page.variants['d5_close:222.22']); await change;
  assert.deepEqual(page.snapshot(), { html: 'view:d5_close:222.22', symbols: ['LOW1111'], endpoints: ['d5_close'] });
  const [aggregate, history] = await page.exportBoth();
  assert.match(aggregate.csv, /"d5_close","500","all","1"/);
  assert.match(history.csv, /LOW1111/); assert.doesNotMatch(history.csv, /HIGH9999|731.29/);
  assert.equal(JSON.parse(page.storage.get('cloudReportPreferences:v1')).priceCapYen, 500);
});

test('decompression failure restores controls and exports the complete previous D5 view', async () => {
  const page = browserFixture(); await flush(); await page.select(500);
  const before = page.snapshot();
  const load = page.delay('d6_open:731.29');
  const change = page.select(1000, 'd6_open');
  load.reject(new Error('bad gzip')); await change;
  assert.deepEqual(page.snapshot(), before);
  assert.equal(page.get('cloud-price-custom').value, '500');
  assert.equal(page.get('cloud-exit-endpoint').value, 'd5_close');
  assert.equal(page.get('cloud-settings-status').dataset.state, 'error');
  for (const id of ['cloud-export-csv', 'cloud-history-export-csv', 'cloud-settings-save']) assert.equal(page.get(id).disabled, false);
  const [aggregate, history] = await page.exportBoth();
  assert.match(aggregate.csv, /"d5_close","500","all","1"/);
  assert.match(history.csv, /検出から5営業日後 終値/);
  assert.doesNotMatch(history.csv, /HIGH9999|検出から6営業日後 始値/);
  assert.equal(JSON.parse(page.storage.get('cloudReportPreferences:v1')).exitKey, 'd5_close');
  await page.get('cloud-settings-save').dispatch('click');
  const saved = JSON.parse(page.requests.find((request) => request.options.method === 'PUT').options.body);
  assert.equal(saved.max_price, 500); assert.equal(saved.exit_endpoint, 'd5_close');
});

test('rapid changes commit only the newest choice despite older completion and rejection', async () => {
  const page = browserFixture(); await flush();
  const first = page.delay('d6_open:222.22'), second = page.delay('d5_close:222.22'), latest = page.delay('d6_open:all');
  const one = page.select(500, 'd6_open'), two = page.select(500), three = page.select(null, 'd6_open');
  second.resolve(page.variants['d5_close:222.22']); await two;
  assert.equal(page.get('cloud-history-export-csv').disabled, true);
  assert.equal(page.snapshot().html, 'view:d5_close:731.29');
  latest.resolve(page.variants['d6_open:all']); await three;
  const complete = page.snapshot();
  first.reject(new Error('stale gzip failure')); await one;
  assert.deepEqual(page.snapshot(), complete);
  assert.deepEqual(complete, { html: 'view:d6_open:all', symbols: ['LOW1111', 'HIGH9999'], endpoints: ['d6_open'] });
  assert.equal(page.get('cloud-exit-endpoint').value, 'd6_open');
  assert.equal(page.get('cloud-price-preset').value, 'unlimited');
  const [aggregate, history] = await page.exportBoth();
  assert.match(aggregate.csv, /"d6_open","上限なし","all","2"/);
  assert.match(history.csv, /検出から6営業日後 始値/);
  assert.match(history.csv, /HIGH9999/);
});

test('invalid newer input cancels pending application and cannot save unapplied controls', async () => {
  const page = browserFixture(); await flush();
  const load = page.delay('d6_open:222.22');
  const valid = page.select(500, 'd6_open');
  await page.select('1.234', 'd6_open');
  load.resolve(page.variants['d6_open:222.22']); await valid;
  assert.deepEqual(page.snapshot(), { html: 'view:d5_close:731.29', symbols: ['LOW1111', 'HIGH9999'], endpoints: ['d5_close'] });
  const [aggregate, history] = await page.exportBoth();
  assert.match(aggregate.csv, /"d5_close","1000","all","2"/);
  assert.match(history.csv, /検出から5営業日後 終値/);
  await page.get('cloud-settings-save').dispatch('click');
  assert.equal(page.requests.filter((request) => request.options.method === 'PUT').length, 0);
});

test('save uses the applied snapshot and never rolls back an edit made during its request', async () => {
  const page = browserFixture(); await flush(); await page.select(500);
  const save = page.delaySave();
  const saving = page.get('cloud-settings-save').dispatch('click');
  await page.select(null, 'd6_open');
  save.resolve({ ok: true }); await saving;
  const sent = JSON.parse(page.requests.find((request) => request.options.method === 'PUT').options.body);
  assert.equal(sent.max_price, 500); assert.equal(sent.exit_endpoint, 'd5_close');
  assert.equal(page.snapshot().html, 'view:d6_open:all');
  assert.match(page.get('cloud-settings-status').textContent, /前の設定は保存済み/);
  const [aggregate] = await page.exportBoth();
  assert.match(aggregate.csv, /"d6_open","上限なし","all","2"/);
});

test('late server preferences do not replace a user choice still being decoded', async () => {
  const page = browserFixture(); await flush();
  const load = page.delay('d6_open:222.22');
  const change = page.select(500, 'd6_open');
  page.serverRead.resolve({ ok: true, json: async () => ({ preferences: { max_price: null, exit_endpoint: 'd5_close' }, membership: { status: 'paid' } }) });
  await flush();
  assert.equal(page.get('cloud-exit-endpoint').value, 'd6_open');
  assert.equal(page.get('cloud-history-export-csv').disabled, true);
  load.resolve(page.variants['d6_open:222.22']); await change;
  assert.equal(page.snapshot().html, 'view:d6_open:222.22');
  const [aggregate] = await page.exportBoth();
  assert.match(aggregate.csv, /"d6_open","500","all","1"/);
});

test('saving the initial view prevents a late server read from replacing that snapshot', async () => {
  const page = browserFixture(); await flush();
  const save = page.delaySave();
  const saving = page.get('cloud-settings-save').dispatch('click');
  page.serverRead.resolve({ ok: true, json: async () => ({ preferences: { max_price: null, exit_endpoint: 'd6_open' }, membership: { status: 'paid' } }) });
  await flush();
  save.resolve({ ok: true }); await saving;
  assert.equal(page.snapshot().html, 'view:d5_close:731.29');
  assert.equal(page.get('cloud-price-preset').value, '1000');
  const sent = JSON.parse(page.requests.find((request) => request.options.method === 'PUT').options.body);
  assert.equal(sent.max_price, 1000); assert.equal(sent.exit_endpoint, 'd5_close');
});

test('an empty free history with unlimited cap stays zero and exports only CSV headers', async () => {
  const page = browserFixture({ emptyHistory: true }); await flush();
  await page.select(null);
  assert.equal(page.get('search-result-count').textContent, '0件を表示');
  assert.deepEqual(page.snapshot().symbols, []);
  assert.equal(page.emptyMessage.hidden, false);
  const [aggregate, history] = await page.exportBoth();
  assert.match(aggregate.csv, /"d5_close","上限なし","all","0"/);
  assert.equal(history.csv.split('\r\n').length, 1);
  assert.ok(history.csv.startsWith('\uFEFF"検出日","銘柄コード"'));
  assert.doesNotMatch(history.csv, /検出から5営業日後 終値/);
  page.get('symbol-filter').value = 'anything';
  await page.get('symbol-filter').dispatch('input');
  assert.equal(page.get('search-result-count').textContent, '0件を表示');
  assert.equal(page.emptyMessage.hidden, false);
});
