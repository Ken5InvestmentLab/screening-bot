#!/usr/bin/env node

// Discord poster for claim-matched, point-in-time beta snapshots.
// The production Premium Worker intentionally rejects stale reports when a
// newer disclosure exists. This sidecar keeps the analysis cutoff explicit
// and posts only a claim-matched report for the isolated beta worker state.
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { isDeepStrictEqual } from 'node:util';

const repoRoot = path.resolve(import.meta.dirname, '..', '..');
const reportPath = resolveArg('--input', path.join(repoRoot, 'weak_early_beta', 'fundamental_worker', 'out', 'premium_reports.json'));
const statePath = resolveArg('--state', path.join(repoRoot, 'weak_early_beta', 'fundamental_worker', 'state', 'premium_alert_state.json'));
const envPath = path.join(repoRoot, '.env');
const GUILD_ID = '1479418833352785944';
const FUNDAMENTAL_CHANNEL_ID = '1550876675884060702';
const REQUIRED_FIELDS = ['材料インパクト', '事業概要', '足元材料', 'ファンダ要点', '注意点', '開示リンク', 'Sources'];

const env = { ...readDotEnv(envPath), ...process.env };
const webhook = String(env.WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL || '').trim();
const saveOnly = process.argv.includes('--save-only');

const reportData = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
const reports = Array.isArray(reportData) ? reportData : reportData.reports;
if (!Array.isArray(reports) || reports.length !== 1) throw new Error('historical poster requires exactly one report');
const report = reports[0];
const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
const claim = state.claims?.[report.alertId];
if (!claim) throw new Error(`no active beta claim for ${report.alertId}`);
if (state.posted?.[report.alertId]) throw new Error(`already posted: ${report.alertId}`);
if (String(claim.symbolCode) !== String(report.symbolCode)) throw new Error('report/claim symbol mismatch');

const signalDate = String(report.signalDate || claim.signalDate || '').slice(0, 10);
const cutoff = String(report.analysisCutoff || '').trim();
const explicitAnalysisCutoff = String(claim.analysisCutoff || '').trim();
const forwardAnalysis = claim.signalType === 'WEAK_EARLY_BETA' && Boolean(explicitAnalysisCutoff);
const claimCutoff = forwardAnalysis ? explicitAnalysisCutoff : String(claim.receivedAt || '').trim();
const endOfDayCutoff = `${signalDate}T23:59:59+09:00`;
let analysisInstant;
if (forwardAnalysis) {
  if (report.auditStatus !== 'pass') throw new Error("forward snapshot requires auditStatus='pass'");
  if (String(report.analysisCutoff || '') !== String(claim.analysisCutoff || '')) {
    throw new Error('HTML snapshot analysisCutoff must match claim.analysisCutoff');
  }
  analysisInstant = exactTimestamp(cutoff, 'analysisCutoff');
  if (claim.signalDate && signalDate !== String(claim.signalDate).slice(0, 10)) {
    throw new Error('report/claim signal date mismatch');
  }
} else if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$/.test(cutoff) ||
           !cutoff.startsWith(signalDate) ||
           (cutoff !== claimCutoff && cutoff !== endOfDayCutoff)) {
  throw new Error('analysisCutoff must match claim.receivedAt or signal_date 23:59:59+09:00');
}
if (saveOnly && cutoff !== claimCutoff) {
  throw new Error('HTML snapshot analysisCutoff must match claim.receivedAt');
}
const allText = JSON.stringify(report);
if (!forwardAnalysis) {
  for (const date of allText.match(/\b20\d{2}-\d{2}-\d{2}\b/g) || []) {
    if (date > signalDate) throw new Error(`post-signal date found in historical report: ${date}`);
  }
  const compactCutoff = signalDate.replace(/-/g, '');
  for (const match of allText.matchAll(/disclosure\/(20\d{6})\//g)) {
    if (match[1] > compactCutoff) throw new Error(`post-signal compact date found in historical report: ${match[1]}`);
  }
  for (const match of allText.matchAll(/\/(20\d{6})\.pdf(?:[\"')]|$)/g)) {
    if (match[1] > compactCutoff) throw new Error(`post-signal compact date found in historical report: ${match[1]}`);
  }
}

const fields = new Map((report.fields || []).map((field) => [String(field.name || '').trim(), String(field.value || '').trim()]));
for (const name of REQUIRED_FIELDS) {
  if (!fields.get(name)) throw new Error(`missing report field: ${name}`);
}
const impact = fields.get('材料インパクト');
if (!/^(?:ポジティブ材料|ネガティブ材料|様子見|混在\/要確認)[：:]/.test(impact)) {
  throw new Error('材料インパクト must begin with a supported label and summary');
}
if (!fields.get('Sources').includes('https://')) throw new Error('Sources must contain a URL');
if (cutoff === claimCutoff) {
  const disclosureLines = fields.get('開示リンク').split(/\r?\n/).filter(line => line.trim());
  const disclosureUrls = new Set();
  const publicationReceipts = new Map();
  if (forwardAnalysis) {
    if (!Array.isArray(report.disclosures)) throw new Error('forward analysis requires selected disclosure publication receipts');
    const cutoffDay = jstDate(analysisInstant.milliseconds);
    for (const disclosure of report.disclosures) {
      if (disclosure?.contentReviewed !== true) throw new Error('selected forward disclosure requires contentReviewed');
      const publishedAt = String(disclosure?.publishedAt || '').trim();
      const dateOnly = disclosure?.publishedAtPrecision === 'date_only';
      let publicationDay;
      if (dateOnly) {
        publicationDay = /^\d{4}-\d{2}-\d{2}$/.test(publishedAt)
          ? jstDate(exactTimestamp(`${publishedAt}T00:00:00+09:00`, 'disclosure publishedAt').milliseconds)
          : jstDate(exactTimestamp(publishedAt, 'disclosure publishedAt').milliseconds);
        if (publicationDay >= cutoffDay) throw new Error('date-only disclosure must predate the analysis-start JST date');
      } else if (exactTimestamp(publishedAt, 'disclosure publishedAt').nanoseconds > analysisInstant.nanoseconds) {
        throw new Error(`post-cutoff disclosure found: ${publishedAt}`);
      }
      publicationReceipts.set(String(disclosure?.url || '').trim(), { dateOnly, publicationDay });
    }
  }
  for (const line of disclosureLines) {
    const datedLink = line.match(/^\s*・?\s*\[(\d{4}-\d{2}-\d{2})\s+.+\]\((https:\/\/[^)]+)\)\s*$/);
    if (forwardAnalysis && datedLink) {
      disclosureUrls.add(datedLink[2]);
      const publication = publicationReceipts.get(datedLink[2]);
      if (publication?.dateOnly) {
        if (datedLink[1] !== publication.publicationDay) throw new Error('date-only disclosure link date must match its publication receipt');
        continue;
      }
    }
    const pattern = forwardAnalysis
      ? /^\s*・?\s*\[(\d{4}-\d{2}-\d{2})\s+.+\((\d{2}):(\d{2})(?::(\d{2})(\.\d{1,9})?)?\)\]\(https:\/\/[^)]+\)\s*$/
      : /^\s*・?\s*\[(\d{4}-\d{2}-\d{2})\s+.+\((\d{2}):(\d{2})\)\]\(https:\/\/[^)]+\)\s*$/;
    const match = line.match(pattern);
    if (!match || Number(match[2]) > 23 || Number(match[3]) > 59) {
      throw new Error('forward disclosure links require a dated title and publication time');
    }
    const publishedAt = `${match[1]}T${match[2]}:${match[3]}:${match[4] || '00'}${match[5] || ''}+09:00`;
    if (forwardAnalysis ? exactTimestamp(publishedAt, 'disclosure publishedAt').nanoseconds > analysisInstant.nanoseconds : publishedAt > cutoff) {
      throw new Error(`post-cutoff disclosure found: ${publishedAt}`);
    }
  }
  if (forwardAnalysis) {
    const receiptUrls = new Set(publicationReceipts.keys());
    if (receiptUrls.size !== disclosureUrls.size || [...disclosureUrls].some(url => !receiptUrls.has(url))) {
      throw new Error('forward disclosure links must match selected publication receipts');
    }
  }
}
if (/(買い推奨|売り推奨|目標株価|追加採点|買うべき|売るべき|利確|損切り)/.test(allText)) {
  throw new Error('report contains prohibited investment-advice wording');
}

const title = `${report.symbolName || claim.symbolName} (${report.symbolCode || claim.symbolCode}) | TradingView チャート`;
const embedFields = REQUIRED_FIELDS.map((name) => ({
  name,
  value: truncate(['開示リンク', 'Sources'].includes(name) ? bulletize(fields.get(name)) : fields.get(name), 1024),
  inline: false,
}));
const payload = {
  username: '天底極致 -Cloud- | ファンダ分析',
  allowed_mentions: { parse: [] },
  embeds: [{
    title,
    url: report.url || claim.tradingViewUrl,
    color: 0xF9A825,
    timestamp: new Date().toISOString(),
    fields: embedFields,
    footer: { text: 'Premium fundamental snapshot / Not investment advice' },
  }],
};

if (process.argv.includes('--dry-run')) {
  console.log(JSON.stringify({ ok: true, dryRun: true, alertId: report.alertId, analysisCutoff: cutoff }));
  process.exit(0);
}

if (saveOnly) {
  state.completed ??= {};
  const existing = state.completed[report.alertId];
  if (existing && !isDeepStrictEqual(existing.report, report)) {
    throw new Error(`a different HTML snapshot already exists: ${report.alertId}`);
  }
  if (!existing) {
    state.completed[report.alertId] = {
      completedAt: new Date().toISOString(),
      delivery: 'html',
      analysisCutoff: cutoff,
      ...(forwardAnalysis ? { analysisBasis: 'analysis_start' } : {}),
      report,
    };
    const temporary = `${statePath}.tmp`;
    fs.writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
    fs.renameSync(temporary, statePath);
  }
  // Keep claim ownership until the runner successfully imports and renders HTML.
  console.log(JSON.stringify({ ok: true, alertId: report.alertId, saved: true, posted: false }));
  process.exit(0);
}

if (!webhook) throw new Error('WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL is missing');
const postUrl = new URL(webhook);
postUrl.searchParams.set('wait', 'true');
const response = await fetch(postUrl, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(payload),
});
if (!response.ok) throw new Error(`Discord webhook failed: HTTP ${response.status} ${await response.text()}`);
const message = await response.json();
const discordMessageUrl = `https://discord.com/channels/${GUILD_ID}/${FUNDAMENTAL_CHANNEL_ID}/${message.id}`;
state.posted ??= {};
state.failed ??= {};
state.pendingLogEvents ??= [];
state.posted[report.alertId] = {
  postedAt: new Date().toISOString(),
  symbolCode: String(report.symbolCode || claim.symbolCode),
  symbolName: String(report.symbolName || claim.symbolName || ''),
  title,
  url: String(report.url || claim.tradingViewUrl || ''),
  discordMessageUrl,
  sourceCount: (JSON.stringify(payload).match(/https?:\/\//g) || []).length,
  analysisCutoff: cutoff,
};
delete state.claims[report.alertId];
delete state.failed[report.alertId];
fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
console.log(JSON.stringify({ ok: true, alertId: report.alertId, discordMessageUrl }, null, 2));

function readDotEnv(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const result = {};
  for (const raw of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const index = line.indexOf('=');
    if (index <= 0) continue;
    let value = line.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    result[line.slice(0, index).trim()] = value;
  }
  return result;
}

function resolveArg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? path.resolve(process.argv[index + 1]) : fallback;
}

function bulletize(value) {
  return String(value || '').split(/\r?\n/).map((line) => line.trim() ? `・${line.replace(/^・/, '')}` : '').join('\n');
}

function truncate(value, max) {
  const text = String(value || '');
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

function exactTimestamp(value, label) {
  const match = String(value).match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})$/);
  const milliseconds = Date.parse(value);
  if (!match || !Number.isFinite(milliseconds)) throw new Error(`${label} must be a valid ISO timestamp with seconds and timezone`);
  const seconds = Date.parse(`${match[1]}${match[3]}`);
  const zone = match[3];
  const offset = zone === 'Z' ? 0 : (zone[0] === '+' ? 1 : -1) * (Number(zone.slice(1, 3)) * 60 + Number(zone.slice(4, 6)));
  if (new Date(seconds + offset * 60_000).toISOString().slice(0, 19) !== match[1]) {
    throw new Error(`${label} must be a valid calendar timestamp`);
  }
  return { milliseconds, nanoseconds: BigInt(seconds) * 1_000_000n + BigInt((match[2] || '').padEnd(9, '0')) };
}

function jstDate(milliseconds) {
  return new Date(milliseconds + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}
