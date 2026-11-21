import type { ReadyPointer } from './new-a-member-services';
import { plannedHoldingExit } from './new-a-market-calendar';

type SessionDatabase = Pick<D1Database, 'withSession'>;
type Part = { index: number; bytes: number; sha256: string };
type Variant = { item: string; bytes: number; sha256: string; parts: Part[] };
type Index = { schema: string; source: ReadyPointer; variants: Variant[] };

const schema = 'NEW_A_MEMBER_REFERENCE_V2';
const dataItems = new Set(['data.dashboard', 'data.analytics', ...[
  'defensive', 'medium', 'return_priority',
].map(preset => 'data.chart.' + preset)]);
const hash = /^[a-f0-9]{64}$/;
const maxMarker = 64 * 1024;
const maxVariant = 512 * 1024;
const maxHistoryIndex = 1024 * 1024;
const maxPart = 48 * 1024;
const readyIndex = 10_000;
const maxHistoryPages = 200;
const historyIndex = 'history.index';
const historyItem = /^history\.([1-9]\d{0,2})$/;
const encoder = new TextEncoder();
const permitted = new Set(['dashboard', 'analytics'].flatMap(page =>
  ['defensive', 'medium', 'return_priority'].map(preset => page + '.' + preset)));
// Keep the published dashboard presets aligned with the finite simulation.
const holdingSessions = new Map([
  ['dashboard.defensive', 5],
  ['dashboard.medium', 5],
  ['dashboard.return_priority', 8],
]);
const holdingsTable = '<table class="scenario-table" data-finite-table="holdings">';
const holdingDates = /(<td data-label="仮想買付日">)(\d{4}-\d{2}-\d{2})(<\/td><td data-label="仮想決済予定日">)未確認(?=<\/td><\/tr>)/g;

function withHoldingExitDates(markup: string, item: string, asOf: string): string {
  const sessions = holdingSessions.get(item);
  if (sessions === undefined) return markup;
  const start = markup.indexOf(holdingsTable);
  if (start === -1 || markup.lastIndexOf(holdingsTable) !== start) return markup;
  const end = markup.indexOf('</tbody></table>', start + holdingsTable.length);
  if (end === -1) return markup;
  const table = markup.slice(start, end).replace(holdingDates, (original, open, entry, nextCell) => {
    const planned = plannedHoldingExit(entry, asOf, sessions);
    return planned === null ? original : open + entry + nextCell + planned;
  });
  return markup.slice(0, start) + table + markup.slice(end);
}

export function isMemberReferenceItem(value: string): boolean {
  const page = historyItem.exec(value);
  return permitted.has(value) || value === historyIndex || (page !== null && Number(page[1]) <= maxHistoryPages);
}

type ReferenceView = 'full' | 'overview' | 'daily';
const analyticsPart = /^analytics\.(overview|daily)\.(defensive|medium|return_priority)$/;
const dailyTable = '<table class="scenario-table" data-finite-table="daily">';
const dailyBodyStart = '</thead><tbody>';
const dailyBodyEnd = '</tbody></table></div></div><button id="new-a-daily-more"';
const dailyTemplate = '<template id="new-a-reference-daily-values">';
const equityChart = /<div class="cloud-chart" id="new-a-daily-chart"><svg class="scenario-chart cloud-equity-chart"[^>]*>[\s\S]*?<\/svg>/;
const equityDates = /<text x="132" y="284" class="axis-label">(\d{4}-\d{2}-\d{2})<\/text><text x="826" y="284" text-anchor="end" class="axis-label">(\d{4}-\d{2}-\d{2})<\/text>(?=<\/svg>)/;
const tradingDay = /^\d{4}-\d{2}-\d{2}$/;

function withEquityDates(overview: string, dailyJson: string): string {
  return overview.replace(equityChart, chart => {
    const endpoints = equityDates.exec(chart);
    if (!endpoints) return chart;
    let daily;
    try {
      ({ daily } = JSON.parse(dailyJson));
    } catch {
      return chart;
    }
    if (!Array.isArray(daily)) return chart;
    // The saved SVG spaces only the finite equity points. Use those same trading days.
    const dates = daily.filter(row => Array.isArray(row) && Number.isFinite(row[3])).map(row => row[0]);
    if (dates[0] !== endpoints[1] || dates.at(-1) !== endpoints[2]
      || !dates.every((day, index) => typeof day === 'string' && tradingDay.test(day)
        && (index === 0 || day > dates[index - 1]))) return chart;
    const last = dates.length - 1;
    const positions = new Set([0, 1, 2, 3, 4].map(quarter => Math.round(last * quarter / 4)));
    const labels = Array.from(positions, index => {
      const x = (132 + index / Math.max(1, last) * 694).toFixed(2);
      return '<line x1="' + x + '" x2="' + x + '" y1="242" y2="248" stroke="var(--line)"/>'
        + '<text x="' + x + '" y="284" text-anchor="middle" class="axis-label" data-equity-date'
        + ' style="font-size:calc(clamp(16px,calc(34px - 1.4vw),27px) * var(--text-scale))">'
        + dates[index] + '</text>';
    }).join('');
    return chart.replace(equityDates, labels);
  });
}

export function parseMemberReferenceRequest(item: string): { item: string; view: ReferenceView } | null {
  const part = analyticsPart.exec(item);
  if (part && part[0] === item) {
    return { item: 'analytics.' + part[2], view: part[1] === 'daily' ? 'daily' : 'overview' };
  }
  return isMemberReferenceItem(item) ? { item, view: 'full' } : null;
}

export function isMemberAnalyticsReference(item: string): boolean {
  return analyticsPart.exec(item)?.[0] === item;
}

function freeDailyValues(text: string): string | null {
  let daily: unknown;
  try {
    daily = JSON.parse(text)?.daily;
  } catch {
    return null;
  }
  if (!Array.isArray(daily) || !daily.every(row => Array.isArray(row) && row.length === 6
    && typeof row[0] === 'string' && tradingDay.test(row[0])
    && row.slice(1, 4).every(value => value === null || Number.isFinite(value))
    && (row[4] === null || Number.isSafeInteger(row[4]) && row[4] >= 0)
    && typeof row[5] === 'boolean')) return null;
  return JSON.stringify({ daily });
}

export function memberReferenceMarkup(markup: string, view: ReferenceView, free = false): string | null {
  if (view === 'full') return free ? null : markup;
  // Read from the already verified canonical markup so earlier generations work without a republish.
  const table = markup.indexOf(dailyTable);
  const start = table === -1 ? -1 : markup.indexOf(dailyBodyStart, table + dailyTable.length);
  const end = start === -1 ? -1 : markup.indexOf(dailyBodyEnd, start + dailyBodyStart.length);
  const template = markup.lastIndexOf(dailyTemplate);
  const hasDaily = end !== -1 && template >= end + dailyBodyEnd.length && markup.endsWith('</template>');
  if (!hasDaily) return !free && view === 'overview' ? markup : null;
  const dailyJson = markup.slice(template + dailyTemplate.length, -'</template>'.length);
  if (!free && view === 'daily') return markup.slice(template);
  const overview = markup.slice(0, start + dailyBodyStart.length) + markup.slice(end, template);
  if (!free) return withEquityDates(overview, dailyJson);
  const checkedDaily = freeDailyValues(dailyJson);
  if (checkedDaily === null) return null;
  if (view === 'daily') return dailyTemplate + checkedDaily + '</template>';
  // The aggregate view shares its canonical renderer with Premium. The Free
  // response has no settings/export actions, or other embedded data templates.
  if (/<(?:template|script)\b|data-finite-table="holdings"|data-member-fundamental\b|data-symbol\s*=/i.test(overview)) return null;
  return withEquityDates(overview
    .replace(/<details class="cloud-kpi-detail"><summary>適用中の設定<\/summary>[\s\S]*?<\/details>/, '')
    .replace(/<section class="panel" aria-labelledby="analytics-export">[\s\S]*?<\/section>/, ''), checkedDaily);
}

function identity(source: ReadyPointer) {
  return JSON.stringify({
    status: source.status, dataset_id: source.dataset_id, revision: source.revision,
    as_of: source.as_of, source_version: source.source_version,
  });
}

async function sha256(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
}

function valid(condition: unknown): asserts condition {
  if (!condition) throw Error('invalid_member_reference');
}

function validDescriptor(input: Pick<Part, 'bytes' | 'sha256'>, limit: number): boolean {
  return Number.isInteger(input.bytes) && input.bytes > 0 && input.bytes <= limit && hash.test(input.sha256);
}

async function checkBytes(value: string, descriptor: Pick<Part, 'bytes' | 'sha256'>, limit: number) {
  valid(typeof value === 'string' && validDescriptor(descriptor, limit));
  const bytes = encoder.encode(value);
  valid(bytes.byteLength === descriptor.bytes && await sha256(bytes) === descriptor.sha256);
}

export function createMemberReferenceReader(db: SessionDatabase | undefined) {
  return async (source: ReadyPointer, item: string): Promise<string | null> => {
    if (!db || (!isMemberReferenceItem(item) && !dataItems.has(item))) return null;
    const boundIdentity = identity(source) + '\n' + schema;
    const session = db.withSession('first-primary');
    const selected = await session.prepare(`
      SELECT m.digest, m.json, ready.json AS ready FROM private_projection_manifest m
      JOIN private_projection_part ready ON ready.identity=m.identity AND ready.kind='analytics' AND ready.idx=?
      JOIN private_projection_ready published ON published.singleton=1 AND published.identity=?
      WHERE m.identity=? AND length(CAST(m.json AS BLOB)) <= ? AND length(CAST(ready.json AS BLOB)) <= 128
    `).bind(readyIndex, identity(source), boundIdentity, maxMarker).first<{ digest: string; json: string; ready: string }>();
    if (!selected) return null;
    valid(hash.test(selected.digest) && selected.ready === JSON.stringify({ digest: selected.digest }));
    valid(await sha256(encoder.encode(selected.json)) === selected.digest);
    const manifest = JSON.parse(selected.json) as Index;
    const fixedItems = [...permitted, ...dataItems];
    valid(manifest.schema === schema && identity(manifest.source) === identity(source)
      && Array.isArray(manifest.variants) && manifest.variants.length >= fixedItems.length
      && manifest.variants.length <= fixedItems.length + maxHistoryPages + 1);
    const keys = new Set(manifest.variants.map(value => value.item));
    valid(keys.size === manifest.variants.length && fixedItems.every(key => keys.has(key))
      && [...keys].every(key => isMemberReferenceItem(key) || dataItems.has(key)));
    const historyPages = keys.size - fixedItems.length - Number(keys.has(historyIndex));
    for (let page = 1; page <= historyPages; page++) valid(keys.has('history.' + page));
    const variant = manifest.variants.find(value => value.item === item);
    const variantLimit = item === historyIndex ? maxHistoryIndex : maxVariant;
    valid(variant && validDescriptor(variant, variantLimit) && Array.isArray(variant.parts)
      && variant.parts.length > 0 && variant.parts.length <= 96);
    const first = variant.parts[0].index;
    valid(Number.isInteger(first) && first >= 0 && first + variant.parts.length <= readyIndex
      && variant.parts.every((part, offset) => part.index === first + offset && validDescriptor(part, maxPart)));
    const { results } = await session.prepare(`
      SELECT idx, json FROM private_projection_part WHERE identity=? AND kind='analytics'
      AND idx BETWEEN ? AND ? AND length(CAST(json AS BLOB)) <= ? ORDER BY idx
    `).bind(boundIdentity, first, first + variant.parts.length - 1, maxPart).all<{ idx: number; json: string }>();
    valid(results.length === variant.parts.length);
    const chunks = await Promise.all(results.map(async (row, offset) => {
      const part = variant.parts[offset];
      valid(row.idx === part.index);
      await checkBytes(row.json, part, maxPart);
      const chunk = JSON.parse(row.json) as { markup: string };
      valid(typeof chunk.markup === 'string');
      return chunk.markup;
    }));
    const markup = chunks.join('');
    await checkBytes(markup, variant, variantLimit);
    return withHoldingExitDates(markup, item, source.as_of);
  };
}
