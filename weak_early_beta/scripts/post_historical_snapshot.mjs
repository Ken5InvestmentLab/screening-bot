#!/usr/bin/env node

// Research-only Discord poster for historical snapshots.
// The production Premium Worker intentionally rejects stale reports when a
// newer disclosure exists. This sidecar keeps a detection-date cutoff explicit
// and posts only a claim-matched report for the isolated beta worker state.
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const repoRoot = path.resolve(import.meta.dirname, '..', '..');
const reportPath = resolveArg('--input', path.join(repoRoot, 'weak_early_beta', 'fundamental_worker', 'out', 'premium_reports.json'));
const statePath = resolveArg('--state', path.join(repoRoot, 'weak_early_beta', 'fundamental_worker', 'state', 'premium_alert_state.json'));
const envPath = path.join(repoRoot, '.env');
const GUILD_ID = '1479418833352785944';
const FUNDAMENTAL_CHANNEL_ID = '1550876675884060702';
const REQUIRED_FIELDS = ['材料インパクト', '事業概要', '足元材料', 'ファンダ要点', '注意点', '開示リンク', 'Sources'];

const env = { ...readDotEnv(envPath), ...process.env };
const webhook = String(env.WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL || '').trim();
if (!webhook) throw new Error('WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL is missing');

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
if (!/^\d{4}-\d{2}-\d{2}T23:59:59\+09:00$/.test(cutoff) || !cutoff.startsWith(signalDate)) {
  throw new Error('analysisCutoff must be signal_date 23:59:59+09:00');
}
const allText = JSON.stringify(report);
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

const fields = new Map((report.fields || []).map((field) => [String(field.name || '').trim(), String(field.value || '').trim()]));
for (const name of REQUIRED_FIELDS) {
  if (!fields.get(name)) throw new Error(`missing report field: ${name}`);
}
const impact = fields.get('材料インパクト');
if (!/^(?:ポジティブ材料|ネガティブ材料|様子見|混在\/要確認)[：:]/.test(impact)) {
  throw new Error('材料インパクト must begin with a supported label and summary');
}
if (!fields.get('Sources').includes('https://')) throw new Error('Sources must contain a URL');
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
  components: [{
    type: 1,
    components: [{
      type: 2,
      style: 2,
      custom_id: `premium_scan:${report.symbolCode || claim.symbolCode}`,
      label: `🔍 ${report.symbolCode || claim.symbolCode} をスキャンする`,
    }],
  }],
};

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
  historicalSnapshotCutoff: cutoff,
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
