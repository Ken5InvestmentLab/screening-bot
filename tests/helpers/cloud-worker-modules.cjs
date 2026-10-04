const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const sourceRoot = path.resolve(__dirname, '../../weak-early-beta-gate/src');
const ts = require('../../weak-early-beta-gate/node_modules/typescript/lib/typescript.js');
exports.modules = function ({ fetchMock, cryptoMock = webcrypto, clock } = {}) {
  const cache = new Map();
  function load(name, parent = sourceRoot) {
    const filename = path.resolve(parent, `${name.replace(/\.ts$/, '')}.ts`);
    if (!filename.startsWith(sourceRoot + path.sep)) throw new Error('outside_test_source');
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} }; cache.set(filename, module);
    let source = fs.readFileSync(filename, 'utf8');
    if (filename.endsWith('shared-report-gate.ts')) source += '\nexport const __test = {createSession};';
    const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
    vm.runInNewContext(code, { module, exports: module.exports, require: name => load(name, path.dirname(filename)),
      Request, Response, Headers, URL, URLSearchParams, AbortSignal, TextEncoder, TextDecoder, Uint8Array,
      crypto: cryptoMock, atob, btoa, Date: clock ? class extends Date {
        constructor(...args) { super(...(args.length ? args : [clock.now])); }
        static now() { return clock.now; }
      } : Date, setTimeout, clearTimeout,
      fetch: fetchMock || (() => { throw new Error('network_forbidden'); }), console: { error() {}, warn() {}, log() {} },
    }, { filename });
    return module.exports;
  }
  return { load };
};
