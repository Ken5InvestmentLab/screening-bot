// The disclosure parser and issuer adapters come from Premium's 2026-11-24
// operating tree. This Cloud adapter owns the point-in-time and presentation
// boundaries and does not load the Premium claim or delivery process.
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { lookup as dnsLookup } from 'node:dns';
import { request as httpRequest } from 'node:http';
import { request as httpsRequest } from 'node:https';
import { BlockList, isIP } from 'node:net';
import { isDeepStrictEqual } from 'node:util';
import {
  buildInventory, officialUrl, publicationLabel, requiredDisclosureItems,
  validateContentEvidence, validateReflection,
} from './premium-disclosure-research/disclosure-audit.mjs';
import { classifyDisclosureTitle } from './premium-disclosure-research/disclosure-title.mjs';
import { createEvidenceReader, publicHttpDiscoveryUrl } from './premium-disclosure-research/evidence-cache.mjs';
import { createResearchDocumentExtractor } from './premium-disclosure-research/research-document.mjs';

const CANDIDATE_TITLE = /月別|販売速報|特許|新サービス|不正|資金|行使|解散|清算|基本合意|BPO|情報漏|保証|覚書|データセンター|事業戦略|AIクラウド/;
const LINK_LINE = /^\s*・?\s*\[([^\r\n]+)\]\((https:\/\/[^)\s]+)\)\s*$/u;
export const VERIFIED_ZERO_LINK_FIELD = '対象時点までの該当する開示はありません。';
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

const nonPublicAddresses = new BlockList();
for (const [address, prefix] of [
  ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8],
  ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24],
  ['192.0.2.0', 24], ['192.88.99.0', 24], ['192.168.0.0', 16],
  ['198.18.0.0', 15], ['198.51.100.0', 24], ['203.0.113.0', 24],
  ['224.0.0.0', 4], ['240.0.0.0', 4],
]) {
  nonPublicAddresses.addSubnet(address, prefix, 'ipv4');
}
for (const [address, prefix] of [['2001::', 23], ['2001:db8::', 32], ['2002::', 16], ['3fff::', 20]]) {
  nonPublicAddresses.addSubnet(address, prefix, 'ipv6');
}
const publicIPv6 = new BlockList();
publicIPv6.addSubnet('2000::', 3, 'ipv6');

function publicRequestUrl(value) {
  const url = new URL(value);
  const host = url.hostname.replace(/\.$/u, '');
  if (isIP(host.replace(/^\[|\]$/gu, '')) || !host.includes('.') || /\.(?:local|localhost|internal|home\.arpa)$/iu.test(host)) {
    throw new Error('official research requires a public hostname');
  }
  return url.protocol === 'http:' ? publicHttpDiscoveryUrl(url.href) : officialUrl(url.href);
}

function publicLookup(resolveHostname) {
  return (hostname, options, callback) => {
    // Return vetted addresses directly to the socket. There is no second DNS
    // resolution between the public-network check and the connection.
    resolveHostname(hostname, { all: true }, (error, addresses) => {
      if (error) return callback(error);
      if (!Array.isArray(addresses) || !addresses.length || addresses.some(({ address, family }) => {
        if (family === 4 && isIP(address) === 4) return nonPublicAddresses.check(address, 'ipv4');
        if (family === 6 && isIP(address) === 6) {
          return !publicIPv6.check(address, 'ipv6') || nonPublicAddresses.check(address, 'ipv6');
        }
        return true;
      })) return callback(new Error('official research DNS did not resolve exclusively to public addresses'));
      const selected = options.family ? addresses.filter(entry => entry.family === options.family) : addresses;
      if (!selected.length) return callback(new Error('official research DNS address family unavailable'));
      if (options.all) return callback(null, selected);
      return callback(null, selected[0].address, selected[0].family);
    });
  };
}

function createPublicFetcher(resolveHostname) {
  const lookup = publicLookup(resolveHostname);
  return async (url, options) => {
    const mayUseHttp = url.startsWith('http:');
    let current = url;
    for (let redirects = 0; redirects <= 5; redirects++) {
      current = publicRequestUrl(current);
      const useHttp = current.startsWith('http:');
      if (useHttp && !mayUseHttp) throw new Error('issuer source cannot redirect HTTPS to HTTP');
      const request = useHttp ? httpRequest : httpsRequest;
      const response = await new Promise((resolve, reject) => {
        const pending = request(current, {
          lookup, agent: false, signal: options.signal,
          headers: { 'User-Agent': 'cloud-fundamental-research', 'Accept-Encoding': 'identity', ...options.headers },
        }, resolve);
        pending.once('error', reject);
        pending.end();
      });
      if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
        response.destroy();
        if (!response.headers.location) throw new Error('official research redirect has no destination');
        current = new URL(response.headers.location, current).href;
        continue;
      }
      const chunks = [];
      for await (const chunk of response) chunks.push(chunk);
      return { status: response.statusCode, url: current, headers: response.headers, body: Buffer.concat(chunks) };
    }
    throw new Error('official research redirect limit');
  };
}

function createReaders(evidenceDirectory, fetcher) {
  const bytes = createEvidenceReader({
    dir: evidenceDirectory,
    fetcher: async (url, options) => fetcher(publicRequestUrl(url), options),
  });
  const text = async url => {
    const result = url.startsWith('http:') ? await bytes.httpDiscovery(url) : await bytes(url);
    const charset = result.contentType.match(/charset\s*=\s*["']?([\w-]+)/iu)?.[1] || 'utf-8';
    return { ...result, body: new TextDecoder(charset, { fatal: true }).decode(result.body) };
  };
  return { bytes, text };
}

function timestamp(value, label) {
  const pattern = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)$/u;
  const instant = Date.parse(value);
  if (typeof value !== 'string' || !pattern.test(value) || !Number.isFinite(instant) ||
      new Date(value.slice(0, 10) + 'T00:00:00Z').toISOString().slice(0, 10) !== value.slice(0, 10)) {
    throw new Error('Cloud research requires an exact ' + label + ' timestamp');
  }
  return instant;
}

function auditOptions({ claimId, symbolCode, analysisCutoff, receivedAt = analysisCutoff, sources }) {
  timestamp(analysisCutoff, 'analysis cutoff');
  return {
    claimId, symbolCode, sources, cutoffAt: analysisCutoff,
    receivedAtMs: timestamp(receivedAt, 'claim receipt'), classify: classifyDisclosureTitle,
  };
}

async function fetchInventory(options, readers) {
  const inventory = await buildInventory({ ...options, readBytes: readers.bytes }, readers.text);
  if (inventory.status !== 'verified') {
    const errors = inventory.observations.filter(item => item.status === 'failed').map(item => item.reason);
    throw new Error('official inventory unverified: ' + errors.join('; '));
  }
  return inventory;
}

function labelsFor(item) {
  try {
    const canonicalLabel = publicationLabel(item);
    return { canonicalLabel, cloudLabel: canonicalLabel.replace(/ JST\)$/u, ')') };
  } catch (error) {
    return { canonicalLabel: null, cloudLabel: null, publicationHold: error.message };
  }
}

function candidateItems(inventory) {
  const recent = inventory.items.filter(item =>
    !['scheduled-event', 'publication-index'].includes(item.recordKind) &&
    item.publication.latestMs >= inventory.windowStartMs)
    .sort((a, b) => b.publication.latestMs - a.publication.latestMs || a.id.localeCompare(b.id));
  return recent.filter((item, index) => index === 0 ||
    classifyDisclosureTitle(item.title) === 'fundamental' || CANDIDATE_TITLE.test(item.title));
}

function publicLinksForPremium(report, inventory) {
  const field = report.fields?.find(item => item.name === '開示リンク');
  if (!field || typeof field.value !== 'string' || !Array.isArray(report.disclosures)) {
    throw new Error('Cloud report requires a complete disclosure field and publication receipts');
  }
  if (field.value.trim() === VERIFIED_ZERO_LINK_FIELD) {
    if (candidateItems(inventory).length || report.disclosures.length ||
        !Array.isArray(report.disclosureEvidence) || report.disclosureEvidence.length ||
        typeof report.noMaterialDisclosureReason !== 'string' || !report.noMaterialDisclosureReason.trim()) {
      throw new Error('Cloud zero-disclosure wording requires verified zero official materials and no disclosure links');
    }
    return { report, publicUrls: [] };
  }
  const links = new Map();
  const publicIds = new Set();
  const canonicalField = field.value.split(/\r?\n/u).map(line => {
    if (!line.trim()) return line;
    const match = LINK_LINE.exec(line);
    if (!match) throw new Error('Cloud disclosure link is not a direct official Markdown link');
    const [, label, rawUrl] = match;
    const url = officialUrl(rawUrl);
    const item = inventory.items.find(entry => entry.urls.includes(url));
    const canonical = item && publicationLabel(item);
    if (!canonical || canonical.replace(/ JST\)$/u, ')') !== label || publicIds.has(item.id)) {
      throw new Error('Cloud public disclosure label, URL, or identity differs from the official inventory');
    }
    links.set(rawUrl, item);
    publicIds.add(item.id);
    return '[' + canonical + '](' + rawUrl + ')';
  }).join('\n');

  const seen = new Set();
  for (const receipt of report.disclosures) {
    const item = links.get(receipt.url);
    if (!item || seen.has(receipt.url) || receipt.contentReviewed !== true) {
      throw new Error('Cloud disclosure receipts do not match the verified public links');
    }
    const official = item.publication;
    if (official.precision === 'date'
      ? receipt.publishedAtPrecision !== 'date_only' || receipt.publishedAt !== official.dateJst
      : receipt.publishedAtPrecision === 'date_only' || Date.parse(receipt.publishedAt) !== official.earliestMs) {
      throw new Error('Cloud disclosure receipt publication time differs from the official record');
    }
    seen.add(receipt.url);
  }
  if (!links.size || links.size !== seen.size) throw new Error('Cloud public disclosures lack verified publication receipts');
  const fields = report.fields.map(item => item === field ? { ...field, value: canonicalField } : item);
  return { report: { ...report, fields }, publicUrls: [...links.keys()] };
}

// Dated Cloud claims use their immutable analysis cutoff. The transport observes
// evidence at its actual retrieval time and never treats a later fetch as
// proof that an untimed disclosure was publicly visible at the Cloud cutoff.
export function createCloudPremiumDisclosureAudit({
  evidenceDirectory, fetcher, pythonPath, resolveHostname = dnsLookup,
} = {}) {
  const readPublic = fetcher ?? createPublicFetcher(resolveHostname);
  let preparationReaders, validationReaders;
  const extract = createResearchDocumentExtractor({ pythonPath });

  return {
    async prepare(input) {
      const options = auditOptions(input);
      preparationReaders ??= createReaders(evidenceDirectory, readPublic);
      const inventory = await fetchInventory(options, preparationReaders);
      const candidates = candidateItems(inventory);
      const requiredIds = requiredDisclosureItems(inventory, options).map(item => item.id);
      const missingDocumentIds = candidates.filter(item => !item.url || item.documentUnavailable).map(item => item.id);
      if (missingDocumentIds.length) {
        throw new Error('official research material lacks an available direct original: ' + missingDocumentIds.join(', '));
      }

      const documents = [];
      for (const item of candidates) {
        const result = await preparationReaders.bytes(item.url);
        if (result.status !== 200 || !result.body.length) throw new Error('official research original unavailable: ' + item.id);
        const sha = sha256(result.body);
        const extension = result.body.subarray(0, 5).toString() === '%PDF-' ? '.pdf' : '.html';
        const file = path.resolve(input.documentDirectory, sha + extension);
        fs.mkdirSync(path.dirname(file), { recursive: true });
        if (fs.existsSync(file)) {
          if (sha256(fs.readFileSync(file)) !== sha) throw new Error('retained original hash mismatch');
        } else {
          const temp = file + '.tmp-' + randomUUID();
          try {
            fs.writeFileSync(temp, result.body, { flag: 'wx', mode: 0o600 });
            fs.renameSync(temp, file);
          } finally {
            if (fs.existsSync(temp)) fs.unlinkSync(temp);
          }
        }
        const derived = await extract({ result, file, readBytes: preparationReaders.bytes });
        documents.push({
          id: item.id, title: item.title, url: item.url, sha256: sha, file, ...derived,
          publication: item.publication, ...labelsFor(item), contentType: result.contentType,
          observedAt: result.observedAt, contentFormat: item.contentFormat,
          canonicalContentSha256: item.canonicalContentSha256,
        });
      }
      return { inventory, documents, requiredIds, missingDocumentIds };
    },

    async validate(input) {
      const options = auditOptions(input);
      const prepared = input.inventory;
      if (prepared?.status !== 'verified' || prepared.claimId !== options.claimId ||
          prepared.symbolCode !== options.symbolCode || prepared.cutoffAt !== options.cutoffAt ||
          prepared.receivedAtMs !== options.receivedAtMs || !isDeepStrictEqual(prepared.sources, options.sources) ||
          String(input.report?.symbolCode || '') !== options.symbolCode ||
          input.report?.analysisCutoff !== options.cutoffAt) {
        throw new Error('Cloud disclosure proof does not match the prepared claim, symbol, sources, or cutoff');
      }

      validationReaders ??= createReaders(evidenceDirectory, readPublic);
      const check = async readers => {
        const inventory = await fetchInventory(options, readers);
        const presentation = publicLinksForPremium(input.report, inventory);
        const proof = validateReflection(presentation.report, inventory, options);
        await validateContentEvidence(presentation.report, inventory, readers.bytes);
        return {
          requiredIds: proof.requiredIds, selectedIds: proof.selectedIds,
          publicUrls: presentation.publicUrls,
        };
      };
      try {
        return await check(validationReaders);
      } catch (error) {
        if (!error.message.startsWith('official publication time is missing')) throw error;
        return check(createReaders(evidenceDirectory, readPublic));
      }
    },

    restartPreparation() {
      preparationReaders = undefined;
    },

    restartValidation() {
      validationReaders = undefined;
    },
  };
}
