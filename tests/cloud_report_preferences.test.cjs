const test = require('node:test');
const assert = require('node:assert/strict');
const prefs = require('../reports/weak-early-beta-interactions.js');

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
