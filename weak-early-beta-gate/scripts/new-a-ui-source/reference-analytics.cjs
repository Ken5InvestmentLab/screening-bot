'use strict';

const assert = require('node:assert/strict');

const PAGE_SIZE = 50;
const exportPanel = '<section class="panel" aria-labelledby="analytics-export">';
const aggregateExports = exportPanel
  + '<h2 id="analytics-export">CSV</h2><div class="cloud-meta">'
  + '<button id="new-a-export-summary" class="settings-secondary" type="button">集計</button>'
  + '<button id="new-a-export-daily" class="settings-secondary" type="button">日次</button>'
  + '</div></section>';

function equityChart(result, finite) {
  const points = result.daily.filter(day => Number.isFinite(day.equity_diagnostic));
  if (!points.length) return '<p>日次値なし</p>';

  const values = points.map(day => day.equity_diagnostic);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const x = index => 132 + index / Math.max(1, points.length - 1) * 694;
  const y = value => high === low ? 145 : 240 - (value - low) / (high - low) * 190;
  const line = values.map((value, index) => {
    return (index ? 'L' : 'M') + x(index).toFixed(2) + ' ' + y(value).toFixed(2);
  }).join(' ');
  const label = result.resolved ? '純資産（円）' : '純資産の診断値（円）';
  const axisTick = (value, position) =>
    '<text x="122" y="' + position + '" text-anchor="end" class="axis-label">' + finite.number(value) + '</text>';
  const ticks = high === low ? axisTick(high, 151) : axisTick(high, 55) + axisTick(low, 246);

  return '<svg class="scenario-chart cloud-equity-chart" viewBox="0 0 870 308" role="img" aria-label="'
    + label + 'の日次推移"><title>' + label + 'の日次推移</title>'
    + '<text x="132" y="25" class="axis-label">' + label + '</text>'
    + '<path d="M132 49H826M132 242H826" fill="none" stroke="var(--line)"/>' + ticks
    + '<path class="equity-line" d="' + line + '" style="stroke:var(--blue)"/>'
    + '<circle cx="' + x(values.length - 1) + '" cy="' + y(values.at(-1)) + '" r="4" fill="var(--blue)"/>'
    + '<text x="132" y="284" class="axis-label">' + finite.esc(points[0].date) + '</text>'
    + '<text x="826" y="284" text-anchor="end" class="axis-label">' + finite.esc(points.at(-1).date) + '</text></svg>';
}

function setPlaceholder(markup, id, content) {
  const placeholder = '<div id="' + id + '"></div>';
  const chartPlaceholder = '<div class="cloud-chart" id="' + id + '"></div>';
  const target = markup.includes(chartPlaceholder) ? chartPlaceholder : placeholder;
  assert(markup.includes(target), 'Missing reference analytics container: ' + id);
  return markup.replace(target, target.slice(0, -6) + content + '</div>');
}

function analyticsReferenceMarkup({ result, preferences, latestYear }, finite) {
  const columns = [
    ['date', '日付'],
    ['cash', '現金', finite.yen],
    ['holdings_value', '保有評価', finite.yen],
    ['equity_diagnostic', result.resolved ? '純資産' : '純資産（診断値）', finite.yen],
    ['positions', '保有数', finite.number],
    ['unresolved', '状態', value => value ? '保留' : '確定'],
  ];
  const daily = result.daily.map(day => columns.map(([key]) => key === 'unresolved' ? Boolean(day[key]) : day[key] ?? null));
  const metrics = result.metrics;
  const summary = [
    ['運用レベル', finite.TRIAL_PRESETS[result.trial_policy?.id] ?? ''],
    ['開始日', result.period?.[0] ?? ''],
    ['終了日', result.period?.[1] ?? ''],
    ['状態', result.resolved ? '確定' : '保留'],
    ['元本', metrics.initialCash ?? null],
    ['期末純資産', metrics.endEquity ?? null],
    ['純損益', metrics.netProfit ?? null],
    ['確定損益', metrics.realizedProfit ?? null],
    ['評価損益', metrics.unrealizedProfit ?? null],
    ['決済済み', metrics.closed ?? null],
    ['勝率（%）', metrics.winRate == null ? null : metrics.winRate * 100],
    ['最大下落率（%）', metrics.maxDrawdown == null ? null : metrics.maxDrawdown * 100],
  ];
  const payload = JSON.stringify({ daily, summary }).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const dailyData = '<template id="new-a-reference-daily-values">' + payload + '</template>';

  let markup = finite.render({ result, preferences, latest_year: latestYear });
  markup = setPlaceholder(markup, 'new-a-daily-chart', equityChart(result, finite));
  if (latestYear) markup = setPlaceholder(markup, 'new-a-latest-year-chart', equityChart(latestYear, finite));
  markup = setPlaceholder(markup, 'new-a-daily-table', finite.table(columns, result.daily.slice(0, PAGE_SIZE), 'daily'));
  if (daily.length <= PAGE_SIZE) markup = markup.replace('id="new-a-daily-more"', 'id="new-a-daily-more" hidden');

  const exportIndex = markup.indexOf(exportPanel);
  assert(exportIndex !== -1, 'Missing reference analytics CSV section');
  return markup.slice(0, exportIndex) + aggregateExports + dailyData;
}

module.exports = { analyticsReferenceMarkup };
