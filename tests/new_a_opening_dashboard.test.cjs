const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const asset = '../weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-opening.js';
const code = fs.readFileSync(require.resolve(asset), 'utf8');
const library = { exports: {} };
vm.runInNewContext(code, { module: library });
const { marketClock, validResult } = library.exports;

class Element {
  constructor() { this.children = []; this.textContent = ''; this.hidden = true; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
}

function fixture() {
  const date = '2026-11-19';
  let now = Date.parse(date + 'T00:01:02Z');
  class FixtureDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  }
  const target = new EventTarget(), window = new EventTarget();
  const elements = new Map();
  const doc = Object.assign(target, {
    hidden: false,
    createElement: () => new Element(),
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new Element());
      return elements.get(id);
    },
  });
  let timerSequence = 0;
  const timers = new Map();
  const responses = [], calls = [];
  const context = vm.createContext({
    Date: FixtureDate, AbortController,
    document: doc, addEventListener: window.addEventListener.bind(window),
    removeEventListener: window.removeEventListener.bind(window),
    setTimeout(fn, delay) { timers.set(++timerSequence, { fn, delay }); return timerSequence; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url, init) {
      calls.push({ url, init });
      const next = responses.shift();
      assert.ok(next);
      return Promise.resolve({ ok: next.status === 200, status: next.status, json: () => next.body });
    },
  });
  vm.runInContext(code, context);
  return {
    date, doc, context, calls, responses, poller: context.AOwnerOpening,
    panel: doc.getElementById('cloud-opening'),
    cards: doc.getElementById('cloud-opening-cards'),
    status: doc.getElementById('cloud-opening-status'),
    tick(ms) {
      now += ms;
      for (const [id, item] of timers) {
        if (item.delay === 60000) { timers.delete(id); item.fn(); break; }
      }
    },
  };
}

const flush = () => new Promise(resolve => setImmediate(resolve));
const candidate = { symbol: '1234', candidate_date: '2026-11-17', status: 'AWAITING_FIRST_TRADE' };
function ready(date, revision, row) {
  return { target_date: date, state: 'ready', revision, updated_at: date + 'T00:01:01Z', rows: [row] };
}

test('opening card updates in place from waiting to trade and disappears when daily data supersedes it', async () => {
  const f = fixture();
  f.context.AOwnerPageData = { rows: [{ symbol: '1234', candidateDate: candidate.candidate_date, companyName: '試験銘柄' }] };
  f.responses.push({ status: 200, body: ready(f.date, 1, candidate) });
  f.poller.start(() => assert.fail('not denied'));
  await flush();
  assert.equal(f.panel.hidden, false);
  assert.equal(f.cards.children[0].children[0].textContent, '試験銘柄 1234');
  assert.match(f.cards.children[0].children[1].textContent, /初約定待ち/);
  assert.equal(f.calls[0].url, '/api/cloud/new-a-finite/opening-observation');
  assert.equal(f.calls[0].init.cache, 'no-store');

  const verified = { ...candidate, status: 'PROVISIONAL_ELIGIBLE', trade_at: f.date + 'T00:00:23Z', actual_price_yen: 1200.5 };
  f.responses.push({ status: 200, body: ready(f.date, 2, verified) });
  f.tick(60000);
  await flush();
  assert.match(f.cards.children[0].children[1].textContent, /仮判定/);
  assert.match(f.cards.children[0].children[2].textContent, /1,200.5円 · 09:00:23 JST/);

  f.responses.push({ status: 503 });
  f.tick(60000);
  await flush();
  assert.equal(f.panel.hidden, false);
  assert.match(f.status.textContent, /最新情報を確認できませんでした/);

  f.responses.push({ status: 200, body: { state: 'empty', target_date: f.date } });
  f.tick(60000);
  await flush();
  assert.equal(f.panel.hidden, true);
  assert.deepEqual(f.cards.children, []);
});

test('hidden tabs pause network and a role denial erases earlier cards and stops polling', async () => {
  const f = fixture();
  let denied = 0;
  f.responses.push({ status: 200, body: ready(f.date, 1, candidate) });
  f.poller.start(() => { denied++; });
  await flush();
  f.doc.hidden = true;
  f.doc.dispatchEvent(new Event('visibilitychange'));
  f.tick(60000);
  assert.equal(f.calls.length, 1);

  f.responses.push({ status: 403 });
  f.doc.hidden = false;
  f.doc.dispatchEvent(new Event('visibilitychange'));
  await flush();
  assert.equal(denied, 1);
  assert.equal(f.panel.hidden, true);
  assert.deepEqual(f.cards.children, []);
  f.tick(60000);
  assert.equal(f.calls.length, 2);
});

test('opening panel uses Tokyo dates and rejects malformed, future-day or unsupported results', () => {
  assert.deepEqual({ ...marketClock(new Date('2026-11-19T00:01:00Z')) }, { date: '2026-11-19', poll: true });
  assert.deepEqual({ ...marketClock(new Date('2026-11-19T15:01:00Z')) }, { date: '2026-11-20', poll: false });
  assert.equal(marketClock(new Date('2026-11-21T00:01:00Z')).poll, false);
  assert.equal(validResult(ready('2026-11-19', 1, candidate), '2026-11-20'), false);
  assert.equal(validResult(ready('2026-11-19', 1, { ...candidate, status: 'FILLED' }), '2026-11-19'), false);
  assert.equal(validResult(ready('2026-11-19', 1, { ...candidate, actual_price_yen: 1000 }), '2026-11-19'), false);
});
