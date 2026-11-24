// Isolated proposal. Parent integrates/reviews this with disclosure-audit.mjs.
// No network, files, credentials or delivery state are accessed by this module.
export async function expandIssuerIrRecords(rows, spec, symbolCode, read, readBytes, helpers) {
  const policies = (spec.issuerIrDateOnlyPolicies || []).filter(p => p.format === 'issuer-ir-record-v1');
  if (!policies.length) return rows;
  const { publicationFromRow, corroboratePublication, publicationReferences, officialUrl, digest, plain, calendar } = helpers;
  if (spec.kind !== 'issuer' || spec.symbolCode !== symbolCode || typeof read !== 'function' || typeof readBytes !== 'function') throw new Error('company IR record classification requires an owned official issuer and original bytes');
  const sourceUrl = officialUrl(spec.url);
  const seenPolicies = new Set();
  for (const policy of policies) {
    if (!policy.categoryMarker || !policy.title || !policy.documentUrl || officialUrl(policy.categoryUrl) !== sourceUrl) throw new Error('incomplete company IR record policy');
    calendar(policy.publicationDate);
    const key = JSON.stringify([officialUrl(policy.documentUrl), policy.publicationDate, policy.title]);
    if (seenPolicies.has(key)) throw new Error('duplicate company IR record policy');
    seenPolicies.add(key);
    const matches = rows.filter(row => row.url && officialUrl(row.url) === officialUrl(policy.documentUrl) && row.date === policy.publicationDate && row.title === policy.title);
    if (matches.length !== 1) throw new Error('company IR exact dated publication row is missing or ambiguous');
  }
  const source = await read(sourceUrl);
  const sourceBytes = await readBytes(sourceUrl);
  if (source.status !== 200 || !source.body || sourceBytes.status !== 200 || !sourceBytes.body || new URL(source.url || sourceUrl).hostname !== new URL(sourceUrl).hostname || new URL(sourceBytes.url || sourceUrl).hostname !== new URL(sourceUrl).hostname || !spec.identityMarker || !source.body.includes(spec.identityMarker)) throw new Error('company IR record source identity or original unavailable');
  const categorySha256 = digest(sourceBytes.body);
  const scans = new Map();
  async function scan(date) {
    if (scans.has(date)) return scans.get(date);
    const compact = date.replaceAll('-', '');
    const first = `https://www.release.tdnet.info/inbs/I_list_001_${compact}.html`;
    const queue = [first], seen = new Set(queue), pages = [], documents = [];
    while (queue.length) {
      const url = queue.shift();
      const response = await read(url);
      if (response.status !== 200 || !response.body || new URL(response.url || url).hostname !== 'www.release.tdnet.info' || !response.body.includes('適時開示情報閲覧サービス')) throw new Error('company IR record needs complete official TDnet retrieval');
      const head = response.body.match(/<div\b[^>]*id=["']kaiji-date-1["'][^>]*>\s*(20\d{2})年(\d{1,2})月(\d{1,2})日\s*<\/div>/);
      if (!head || `${head[1]}-${head[2].padStart(2, '0')}-${head[3].padStart(2, '0')}` !== date) throw new Error('company IR record exchange coverage date mismatch');
      if (!/class=["'][^"']*\bkjCode\b/.test(response.body) && !response.body.includes('該当する情報はありません')) throw new Error('company IR record exchange rows or official empty evidence missing');
      for (const match of response.body.matchAll(new RegExp(`I_list_\\d{3}_${compact}\\.html`, 'g'))) {
        const next = new URL(match[0], url).href;
        if (!seen.has(next)) {
          if (seen.size >= 100) throw new Error('company IR record exchange pagination limit');
          seen.add(next); queue.push(next);
        }
      }
      const proof = { kind: 'exchange', symbolCode, format: 'tdnet-table-v1', url, date, identityMarker: '適時開示情報閲覧サービス' };
      const parsed = await publicationReferences({ publicationSources: [proof] }, symbolCode, async () => response);
      documents.push(...parsed.documents);
      pages.push({ url, date, sha256: digest(response.body), observedAt: response.observedAt, rowCount: parsed.documents.length });
    }
    // Every owned same-day original must be available, including when none matches.
    for (const reference of documents) {
      const bytes = await readBytes(reference.url);
      if (bytes.status !== 200 || !bytes.body || Buffer.from(bytes.body).subarray(0, 5).toString() !== '%PDF-') throw new Error('company IR record owned exchange original unavailable');
    }
    const result = { documents, pages };
    scans.set(date, result);
    return result;
  }
  const output = [];
  for (const row of rows) {
    const policy = policies.find(p => row.url && officialUrl(p.documentUrl) === officialUrl(row.url) && p.publicationDate === row.date && p.title === row.title);
    if (!policy) { output.push(row); continue; }
    if (!source.body.includes(policy.categoryMarker) || !plain(source.body).includes(plain(row.evidence || row.raw || '')) || !plain(row.evidence || row.raw || '')) throw new Error('company IR actual category/publication evidence missing');
    const original = await readBytes(row.url);
    if (original.status !== 200 || !original.body || new URL(original.url || row.url).hostname !== new URL(row.url).hostname) throw new Error('company IR record original document unavailable or redirected');
    const bytes = Buffer.from(original.body), isPdf = bytes.subarray(0, 5).toString() === '%PDF-';
    const publication = publicationFromRow(row, spec.url, spec.zoneEvidence);
    // A genuinely verified publication clock must never be downgraded to date-only.
    if (publication.timeJst) { output.push(row); continue; }
    const references = await scan(policy.publicationDate);
    if (!isPdf && references.documents.length && !(spec.listedPdfResolution || []).some(p => officialUrl(p.listingUrl) === officialUrl(row.url) && p.publicationDate === row.date)) throw new Error('company IR HTML record has owned TDnet originals; exact PDF resolution required');
    const resolutionCopy = { ...row };
    const matched = await corroboratePublication(resolutionCopy, publication, references, readBytes, spec);
    if (matched.timeJst) {
      output.push({ ...row, exchangeMatchedPublication: { ...matched, evidenceKind: 'tdnet-publication' } });
      continue;
    }
    if (!isPdf && references.documents.length) throw new Error('company IR HTML did not establish identical owned TDnet original');
    output.push({ ...row, issuerIrEvidence: {
      dateJst: policy.publicationDate,
      categoryUrl: sourceUrl,
      categoryMarker: policy.categoryMarker,
      categorySha256,
      documentUrl: row.url,
      documentSha256: digest(bytes),
      recordTitle: row.title,
      publicationFieldEvidence: row.evidence || row.raw,
      recordFormat: 'issuer-ir-record-v1',
      exchangeScan: { status: 'verified-no-identical-document', symbolCode, date: policy.publicationDate, pages: references.pages }
    } });
  }
  return output;
}
