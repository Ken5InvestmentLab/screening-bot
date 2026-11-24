import { createHash } from 'node:crypto';
import { intranceArchive, intranceNavigation, resolveIntranceDocument } from './issuer-intrance-archive.mjs';

const archives = {
  'ys-ir-topics-v1': {
    code: '2694', root: 'https://ys-holdings.co.jp/ir-information/',
    title: 'IRに関するお知らせ', issuer: '焼肉坂井ホールディングス',
    container: 'ul', className: 'topics-list', card: 'li',
  },
  'delta-ir-news-v1': {
    code: '4598', root: 'https://www.delta-flypharma.co.jp/ir/news/',
    title: 'IRニュース一覧', issuer: 'Delta-Fly Pharma株式会社',
    container: 'div', className: 'article-box', card: 'div',
  },
};

function attribute(tag, key) {
  return tag.match(new RegExp('\\s' + key + '\\s*=\\s*(["\'])(.*?)\\1', 'i'))?.[2] || '';
}

function hasClass(tag, name) {
  return attribute(tag, 'class').split(/\s+/).includes(name);
}

// Find the corresponding end tag even when the archive uses nested div columns.
function elementAt(html, start, tag) {
  const tokens = new RegExp('<(/?)' + tag + '\\b[^>]*>', 'gi');
  tokens.lastIndex = start;
  let depth = 0, innerStart;
  for (let match; (match = tokens.exec(html));) {
    if (innerStart === undefined) innerStart = tokens.lastIndex;
    depth += match[1] ? -1 : 1;
    if (depth === 0) return { inner: html.slice(innerStart, match.index), end: tokens.lastIndex };
  }
  throw new Error('issuer archive element is incomplete');
}

function archiveCards(body, archive) {
  const openings = [...body.matchAll(new RegExp('<' + archive.container + '\\b[^>]*>', 'gi'))]
    .filter(match => hasClass(match[0], archive.className));
  if (openings.length !== 1) throw new Error('issuer archive list is missing or ambiguous');
  let inner = elementAt(body, openings[0].index, archive.container).inner.trim();
  // The 4598 list ends with its numbered navigation inside the article box.
  inner = inner.replace(/<nav\b[^>]*>[\s\S]*?<\/nav>\s*$/i, '').trim();
  const cards = [];
  while (inner) {
    const start = inner.match(new RegExp('^<' + archive.card + '\\b[^>]*>', 'i'))?.[0];
    const required = archive.code === '4598' ? ['article-item', 'columns'] : [archive.cardClass || 'topics-item'];
    if (!start || !required.every(name => hasClass(start, name))) throw new Error('unrecognized issuer archive record');
    const element = elementAt(inner, 0, archive.card);
    cards.push(element.inner);
    inner = inner.slice(element.end).trim();
  }
  if (!cards.length) throw new Error('issuer archive listing contains no reviewed records');
  return cards;
}

function parseRecord(card, archive, pageUrl, { plain, officialUrl, calendar }) {
  const anchors = [...card.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)];
  if (anchors.length !== 1 || !attribute(anchors[0][1], 'href')) throw new Error('issuer archive document link missing or ambiguous');
  const url = officialUrl(attribute(anchors[0][1], 'href').replaceAll('&amp;', '&'), pageUrl);
  if (new URL(url).origin !== new URL(archive.root).origin) throw new Error('unreviewed issuer archive document origin');
  let date, title, evidence;
  if (archive.card === 'li') {
    const times = [...card.matchAll(/<time\b([^>]*)>([^<]+)<\/time>/gi)];
    const headings = [...card.matchAll(/<p\b([^>]*)>([\s\S]*?)<\/p>/gi)]
      .filter(match => archive.code === '3237' || hasClass(match[1], 'topics-item_details'));
    if (times.length !== 1 || headings.length !== 1) throw new Error('issuer archive dated heading missing or ambiguous');
    date = attribute(times[0][1], 'datetime');
    if (plain(times[0][2]).replaceAll('.', '-') !== date) throw new Error('issuer archive visible and machine dates conflict');
    title = plain(headings[0][2]);
    evidence = times[0][0];
  } else {
    const columns = [...card.matchAll(/<div\b([^>]*)>([\s\S]*?)<\/div>/gi)];
    if (columns.length !== 2 || !hasClass(columns[0][1], 'is-narrow') ||
        !hasClass(columns[0][1], 'column') || !hasClass(columns[1][1], 'column') ||
        !columns[1][2].includes(anchors[0][0])) throw new Error('issuer archive publication columns changed');
    const match = plain(columns[0][2]).match(/^\[(20\d\d\.\d\d\.\d\d)\]$/);
    if (!match) throw new Error('issuer archive bracketed publication date missing or ambiguous');
    date = match[1].replaceAll('.', '-');
    evidence = match[0];
    title = plain(anchors[0][2]);
  }
  calendar(date);
  if (!title) throw new Error('issuer archive publication title missing');
  return { title, date, url, evidence };
}

function nextPage(body, archive, currentPage, officialUrl) {
  const nav = archive.code === '3237' ? [intranceNavigation(body, { hasClass, elementAt })] :
    [...body.matchAll(/<nav\b([^>]*)>([\s\S]*?)<\/nav>/gi)].filter(match => hasClass(match[1], 'pagination')).map(match => match[2]);
  if (nav.length !== 1) throw new Error('issuer archive numbered page navigation missing or ambiguous');
  const expected = (page) => page === 1 ? archive.root : archive.root + 'page/' + page + '/';
  const links = new Set();
  for (const match of nav[0].matchAll(/<a\b[^>]*>/gi)) {
    const href = attribute(match[0], 'href');
    if (!href) throw new Error('issuer archive navigation link missing');
    const url = officialUrl(href.replaceAll('&amp;', '&'), expected(currentPage));
    const page = url === archive.root ? 1 : Number(new URL(url).pathname.match(/\/page\/(\d+)\/$/)?.[1]);
    if (!Number.isSafeInteger(page) || page < 1 || url !== expected(page)) throw new Error('unreviewed issuer archive navigation target');
    links.add(page);
  }
  const active = [...nav[0].matchAll(/<span\b([^>]*)>/gi)].filter(match =>
    hasClass(match[1], 'is-current') || attribute(match[1], 'aria-current') === 'page');
  if (active.length !== 1) throw new Error('issuer archive current page missing or ambiguous');
  const activeText = elementAt(nav[0], active[0].index, 'span').inner.replace(/<[^>]*>/g, ' ').trim();
  if (Number(activeText.match(/\b(\d+)\s*$/)?.[1]) !== currentPage) throw new Error('issuer archive current page mismatch');
  if (links.has(currentPage + 1)) return expected(currentPage + 1);
  if ([...links].some(page => page > currentPage)) throw new Error('issuer archive page sequence is incomplete');
  return null;
}

async function resolveYsDocument(row, read, plain, officialUrl) {
  const response = await read(row.url);
  if (response.status !== 200 || !response.body || officialUrl(response.url || row.url) !== row.url) throw new Error('issuer IR detail unavailable or redirected');
  const headings = [...response.body.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)];
  const sections = [...response.body.matchAll(/<div\b[^>]*>/gi)].filter(match => hasClass(match[0], 'entry-body'));
  if (headings.filter(match => plain(match[1]) === row.title).length !== 1 || sections.length !== 1) throw new Error('issuer IR detail heading or body changed');
  const section = elementAt(response.body, sections[0].index, 'div').inner;
  const anchors = [...section.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)];
  if (anchors.length !== 1 || plain(anchors[0][2]) !== row.title || !attribute(anchors[0][1], 'href')) throw new Error('issuer IR detail attached document is missing or ambiguous');
  const href = officialUrl(attribute(anchors[0][1], 'href').replaceAll('&amp;', '&'), row.url);
  if (new URL(href).origin !== new URL(row.url).origin || !new URL(href).pathname.endsWith('.pdf')) throw new Error('issuer IR detail attached document is outside reviewed format');
  const listingUrl = row.url;
  row.originalListingUrl = listingUrl;
  row.documentResolutionEvidence = { listingUrl, listingSha256: createHash('sha256').update(response.body).digest('hex'), actualHref: href };
  row.url = href;
}

export async function readIssuerArchive({ body, spec, symbolCode, url, read, windowStartMs, plain, officialUrl, calendar, observedAt }) {
  const archive = spec.format === 'intrance-ir-archive-v1' ? intranceArchive(url) : archives[spec.format];
  if (!archive || archive.code !== symbolCode || spec.kind !== 'issuer' || url !== archive.root || spec.url !== url ||
      !Number.isFinite(windowStartMs)) throw new Error('unreviewed issuer archive identity or coverage');
  const rows = [], pages = [], documents = new Set();
  let pageUrl = url, pageBody = body, seenAt = observedAt, previousDate;
  for (let page = 1; page <= 100; page++) {
    const pageTitle = plain(pageBody.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1]);
    if (!pageTitle.includes(archive.title) || !pageTitle.includes(archive.issuer)) throw new Error('issuer archive title or identity changed');
    const cards = archiveCards(pageBody, archive);
    const next = nextPage(pageBody, archive, page, officialUrl);
    for (const card of cards) {
      const row = parseRecord(card, archive, pageUrl, { plain, officialUrl, calendar });
      if (previousDate && row.date > previousDate) throw new Error('issuer archive publication order changed');
      if (archive.code === '2694' && calendar(row.date) + 15 * 3600000 - 1 >= windowStartMs) {
        await resolveYsDocument(row, read, plain, officialUrl);
      }
      if (archive.code === '3237' && calendar(row.date) + 15 * 3600000 - 1 >= windowStartMs) {
        await resolveIntranceDocument(row, read, { plain, officialUrl, elementAt, hasClass, attribute });
      }
      if (documents.has(row.url)) throw new Error('duplicate issuer archive document or repeated page');
      documents.add(row.url);
      rows.push(row);
      previousDate = row.date;
    }
    pages.push({ url: pageUrl, observedAt: seenAt, rowCount: cards.length, sha256: createHash('sha256').update(pageBody).digest('hex') });
    // A missing next link cannot prove that the established archive covers the window.
    if (calendar(previousDate) + 15 * 3600000 - 1 < windowStartMs) return { rows, pages };
    if (!next) throw new Error('issuer archive ends inside the required publication window');
    const response = await read(next);
    if (response.status !== 200 || !response.body || officialUrl(response.url || next) !== next) throw new Error('issuer archive next page unavailable or redirected');
    pageUrl = next;
    pageBody = response.body;
    seenAt = response.observedAt;
  }
  throw new Error('issuer archive page limit reached before coverage boundary');
}
