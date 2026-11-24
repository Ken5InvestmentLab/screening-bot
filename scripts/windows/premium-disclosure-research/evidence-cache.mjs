import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
const HASH = /^[a-f0-9]{64}$/;
const sleepDefault = ms => new Promise(resolve => setTimeout(resolve, ms));

function publicUrl(value, httpDiscovery=false) {
  const u = new URL(value);
  if ((u.protocol !== 'https:' && !(httpDiscovery && u.protocol==='http:')) || u.username || u.password || [...u.searchParams.keys()].some(k => /token|authorization|api[_-]?key|signature|password|secret|credential|subscription-key|x-amz-/i.test(k))) throw new Error('evidence cache accepts only public HTTPS URLs without credentials');
  u.hash = ''; u.searchParams.sort(); return u.href;
}
export function publicHttpDiscoveryUrl(value){const u=new URL(value);if(u.protocol!=='http:')throw Error('HTTP issuer discovery requires an actual public HTTP URL');return publicUrl(value,true);}
function replaceFile(from, to) {
  // Windows can transiently reject an atomic replacement while another process
  // reads the target. Retry only these exact paths; never unlink the old target.
  // This synchronous bound also supports the synchronous derived-result API.
  for (let attempt = 0; ; attempt++) {
    try { fs.renameSync(from, to); return; }
    catch (error) {
      if (!['EPERM', 'EACCES', 'EBUSY'].includes(error.code) || attempt >= 9) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 20);
    }
  }
}
function atomicJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp-${process.pid}-${crypto.randomUUID()}`;
  let fd;
  try { fd = fs.openSync(tmp, 'wx', 0o600); fs.writeFileSync(fd, JSON.stringify(value)); fs.fsyncSync(fd); fs.closeSync(fd); fd = undefined; replaceFile(tmp, file); }
  finally { if (fd !== undefined) fs.closeSync(fd); if (fs.existsSync(tmp)) fs.unlinkSync(tmp); }
}
function readJson(file) { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (error) { if (error.code === 'ENOENT' || error instanceof SyntaxError) return null; throw error; } }
function boundedPositive(value, fallback, maximum = 64) { const n = value ?? fallback; if (!Number.isInteger(n) || n < 1 || n > maximum) throw new Error('invalid evidence concurrency bound'); return n; }
function queue(globalLimit, hostLimit) {
  let active = 0; const hosts = new Map(), pending = [];
  const pump = () => {
    while (active < globalLimit) {
      const i = pending.findIndex(p => (hosts.get(p.host) || 0) < hostLimit); if (i < 0) break;
      const { host, resolve } = pending.splice(i, 1)[0]; active++; hosts.set(host, (hosts.get(host) || 0) + 1);
      let released = false; resolve(() => { if (released) return; released = true; active--; hosts.set(host, hosts.get(host) - 1); pump(); });
    }
  };
  return async (url, action) => { const release = await new Promise(resolve => { pending.push({ host: new URL(url).hostname, resolve }); pump(); }); try { return await action(); } finally { release(); } };
}
async function responseBytes(response, requestedUrl) {
  if (!response || !Number.isInteger(response.status)) throw new Error('invalid evidence HTTP response');
  const header = name => typeof response.headers?.get === 'function' ? response.headers.get(name) : Object.entries(response.headers || {}).find(([k]) => k.toLowerCase() === name)?.[1];
  const body = typeof response.arrayBuffer === 'function' ? Buffer.from(await response.arrayBuffer()) : Buffer.from(response.body || []);
  return { status: response.status, url: publicUrl(response.url || requestedUrl,requestedUrl.startsWith('http:')), body, contentType: response.contentType || header('content-type') || '', etag: response.etag || header('etag') || null, lastModified: response.lastModified || header('last-modified') || null, retryAfter: response.retryAfter || header('retry-after') || null, transport: response.transport || 'fetch' };
}

/** Public-source cache. A NEW reader always observes the source before reuse.
 * `Last-Modified` is only an HTTP cache validator, never a publication timestamp.
 * Within one reader the first successful observation is shared. `revalidate:true`
 * forces another observation; `revalidate:false` explicitly permits offline reuse.
 */
export function createEvidenceReader({ dir, fetcher = globalThis.fetch, globalConcurrency = 4, perHostConcurrency = 2, maxRetries = 2, retryBaseMs = 250, maxRetryDelayMs = 30000, timeoutMs = 15000, lockWaitMs = 5000, sleep = sleepDefault, now = () => new Date(), hashBody = sha256 } = {}) {
  if (!dir || typeof fetcher !== 'function' || !Number.isInteger(maxRetries) || maxRetries < 0 || maxRetries > 5) throw new Error('invalid evidence reader configuration');
  const root = path.resolve(dir), run = queue(boundedPositive(globalConcurrency, 4), boundedPositive(perHostConcurrency, 2));
  const bodyDir = path.join(root, 'bodies'), urlDir = path.join(root, 'urls'), derivedDir = path.join(root, 'verifications');
  for (const p of [bodyDir, urlDir, derivedDir]) fs.mkdirSync(p, { recursive: true });
  const observations = new Map(), inFlight = new Map(), verifiedBodies = new Map();
  const stats = { requests: 0, conditionalRequests: 0, downloaded: 0, revalidated304: 0, memoryHits: 0, singleFlightHits: 0, integrityHashes: 0, downloadHashes: 0, corruptEntries: 0, retries: 0, derivedHits: 0 };
  const at = () => { const d = now(); const v = d instanceof Date ? d : new Date(d); if (!Number.isFinite(+v)) throw new Error('invalid cache clock'); return v.toISOString(); };
  const bodyFile = hash => { if (!HASH.test(hash || '')) throw new Error('invalid evidence content digest'); return path.join(bodyDir, `${hash}.bin`); };
  function trustedBody(hash) {
    if (!HASH.test(hash || '')) return null;
    const file = bodyFile(hash); let stat; try { stat = fs.statSync(file); } catch (e) { if (e.code === 'ENOENT') return null; throw e; }
    const stamp = `${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`, old = verifiedBodies.get(hash);
    if (old?.stamp === stamp) return old.body;
    const body = fs.readFileSync(file); stats.integrityHashes++;
    if (hashBody(body) !== hash) { stats.corruptEntries++; verifiedBodies.delete(hash); return null; }
    verifiedBodies.set(hash, { stamp, body }); return body;
  }
  function saveBody(body, hash) {
    const file = bodyFile(hash), existing = trustedBody(hash);
    if (!existing) {
      const tmp = `${file}.tmp-${process.pid}-${crypto.randomUUID()}`; let fd;
      try { fd = fs.openSync(tmp, 'wx', 0o600); fs.writeFileSync(fd, body); fs.fsyncSync(fd); fs.closeSync(fd); fd = undefined; replaceFile(tmp, file); }
      finally { if (fd !== undefined) fs.closeSync(fd); if (fs.existsSync(tmp)) fs.unlinkSync(tmp); }
      const stat = fs.statSync(file); verifiedBodies.set(hash, { stamp: `${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`, body });
    }
  }
  function cached(url) {
    const meta = readJson(path.join(urlDir, `${sha256(url)}.json`));
    if (!meta || meta.version !== 1 || meta.requestedUrl !== url || !HASH.test(meta.contentSha256 || '') || !Number.isFinite(Date.parse(meta.observedAt))) return null;
    try { publicUrl(meta.url,url.startsWith('http:')); } catch { return null; }
    const body = trustedBody(meta.contentSha256); return body && body.length === meta.byteLength ? { meta, body } : null;
  }
  async function saveMeta(url, value) {
    const file = path.join(urlDir, `${sha256(url)}.json`), lock = `${file}.lock`, token = crypto.randomUUID(), started = performance.now(); let fd;
    while (true) { try { fd = fs.openSync(lock, 'wx', 0o600); break; } catch (e) { if (e.code !== 'EEXIST') throw e; if (performance.now() - started >= lockWaitMs) throw new Error('evidence metadata lock timeout; preserve lock and reconcile'); await sleep(10); } }
    try {
      fs.writeFileSync(fd, token); fs.closeSync(fd); fd = undefined;
      const current = readJson(file);
      if (!current || !Number.isFinite(Date.parse(current.observedAt)) || Date.parse(current.observedAt) <= Date.parse(value.observedAt)) atomicJson(file, value);
    } finally { if (fd !== undefined) fs.closeSync(fd); if (fs.readFileSync(lock, 'utf8') !== token) throw new Error('evidence metadata lock ownership changed'); fs.unlinkSync(lock); }
  }
  async function request(url, headers) {
    for (let attempt = 0; ; attempt++) {
      const response = await run(url, async () => { stats.requests++; if (Object.keys(headers).length) stats.conditionalRequests++; return responseBytes(await fetcher(url, { headers, signal: AbortSignal.timeout(timeoutMs) }), url); });
      if ((response.status !== 429 && !(response.status >= 500 && response.status <= 599)) || attempt >= maxRetries) return response;
      let delay = retryBaseMs * 2 ** attempt;
      if (response.retryAfter) { const seconds = Number(response.retryAfter); delay = Number.isFinite(seconds) ? Math.max(0, seconds * 1000) : Math.max(0, Date.parse(response.retryAfter) - Date.parse(at())); if (!Number.isFinite(delay)) delay = retryBaseMs * 2 ** attempt; }
      // Never retry earlier than Retry-After to fit the local wait budget.
      if (delay > maxRetryDelayMs) return response;
      stats.retries++; await sleep(delay);
    }
  }
  async function observe(url, offlineAllowed) {
    let old = cached(url);
    if (old && offlineAllowed) return { status: 200, url: old.meta.url, body: old.body, observedAt: old.meta.observedAt, contentType: old.meta.contentType, contentSha256: old.meta.contentSha256, etag: old.meta.etag, lastModified: old.meta.lastModified, cache: 'explicit-offline-reuse', networkStatus: null };
    const headers = {}; if (old?.meta.etag) headers['If-None-Match'] = old.meta.etag; else if (old?.meta.lastModified) headers['If-Modified-Since'] = old.meta.lastModified;
    let response = await request(url, headers), observedAt = at();
    if (response.status === 304 && !old) { response = await request(url, {}); observedAt = at(); }
    if (response.status === 304) {
      if (!old || !trustedBody(old.meta.contentSha256)) throw new Error('304 response without intact cached evidence');
      if (response.url !== old.meta.url) throw new Error('304 final URL differs from the verified cached source identity; reverify the official source');
      stats.revalidated304++; const meta = { ...old.meta, observedAt, etag: response.etag || old.meta.etag, lastModified: response.lastModified || old.meta.lastModified };
      await saveMeta(url, meta); return { status: 200, url: meta.url, body: old.body, observedAt, contentType: meta.contentType, contentSha256: meta.contentSha256, etag: meta.etag, lastModified: meta.lastModified, transport: response.transport, cache: 'revalidated', networkStatus: 304 };
    }
    if (response.status !== 200) return { ...response, observedAt, contentSha256: null, cache: 'not-stored', networkStatus: response.status };
    stats.downloaded++; stats.downloadHashes++; const contentSha256 = hashBody(response.body);
    if (!HASH.test(contentSha256)) throw new Error('invalid computed evidence digest');
    saveBody(response.body, contentSha256);
    const meta = { version: 1, requestedUrl: url, url: response.url, contentSha256, byteLength: response.body.length, contentType: response.contentType, etag: response.etag, lastModified: response.lastModified, observedAt };
    await saveMeta(url, meta); return { ...response, observedAt, contentSha256, cache: old?.meta.contentSha256 === contentSha256 ? 'downloaded-identical' : 'downloaded', networkStatus: 200 };
  }
  async function read(value, { revalidate, httpDiscovery=false } = {}) {
    const url = httpDiscovery?publicHttpDiscoveryUrl(value):publicUrl(value); let promise = inFlight.get(url);
    if (promise) stats.singleFlightHits++;
    else if (revalidate !== true && observations.has(url)) { stats.memoryHits++; promise = Promise.resolve(observations.get(url)); }
    else { promise = observe(url, revalidate === false); inFlight.set(url, promise); try { const result = await promise; if (result.status === 200) observations.set(url, result); return { ...result, body: Buffer.from(result.body) }; } finally { inFlight.delete(url); } }
    const result = await promise; return { ...result, body: Buffer.from(result.body) };
  }
  function derivedLocation({ contentSha256, validatorVersion, key = 'default' }) {
    bodyFile(contentSha256); if (typeof validatorVersion !== 'string' || !validatorVersion.trim() || validatorVersion.length > 512 || typeof key !== 'string' || key.length > 2048) throw new Error('derived evidence requires a validator version and key');
    return { file: path.join(derivedDir, contentSha256, `${sha256(JSON.stringify([validatorVersion, key]))}.json`), contentSha256, validatorVersion, key };
  }
  read.httpDiscovery=(value,options={})=>read(value,{...options,httpDiscovery:true});
  read.cacheDirectory=root;
  read.getRetainedBody = hash => trustedBody(hash);
  read.recordVerification = options => {
    const ref = derivedLocation(options); if (!trustedBody(ref.contentSha256)) throw new Error('cannot verify missing/corrupt cached original');
    const json = JSON.stringify(options.value); if (json === undefined) throw new Error('derived verification value must be JSON');
    atomicJson(ref.file, { version: 1, contentSha256: ref.contentSha256, validatorVersion: ref.validatorVersion, key: ref.key, recordedAt: at(), value: JSON.parse(json), valueSha256: sha256(json) }); return options.value;
  };
  read.getVerification = options => {
    const ref = derivedLocation(options); if (!trustedBody(ref.contentSha256)) return null;
    const item = readJson(ref.file); if (!item || item.version !== 1 || item.contentSha256 !== ref.contentSha256 || item.validatorVersion !== ref.validatorVersion || item.key !== ref.key || item.value === undefined || sha256(JSON.stringify(item.value)) !== item.valueSha256) return null;
    stats.derivedHits++; return item.value;
  };
  read.getStats = () => ({ ...stats });
  read.clearMemory = () => { observations.clear(); };
  read.read = read;
  return read;
}
