import { createHash } from 'node:crypto';
// Isolated proposal only. Parent must review, integrate, test and version it.
// Actual observed source: issuer HTML data-sb-listview plus category-script.b3s.js.
export function parseSoftBankList(body, spec, sourceUrl) {
  const url = new URL(sourceUrl);
  if (spec.symbolCode !== '9434' || spec.kind !== 'issuer' ||
      url.protocol !== 'https:' || url.hostname !== 'www.softbank.jp' ||
      url.pathname !== '/scsystem/api/CreateJson/' ||
      url.searchParams.get('category') !== 'corp' ||
      !['sbkk_press', 'ir_news'].includes(url.searchParams.get('sub_category')) ||
      url.searchParams.get('corp_category') !== '' ||
      url.searchParams.get('language') !== 'ja-JP' ||
      !/^20\d{2}$/.test(url.searchParams.get('year') || '')) {
    throw new Error('SoftBank official list is not bound to the reviewed issuer/API scope');
  }
  const expectedKeys = ['category', 'corp_category', 'language', 'sub_category', 'year'];
  const actualKeys = [...url.searchParams.keys()].sort();
  if (JSON.stringify(actualKeys) !== JSON.stringify(expectedKeys)) {
    throw new Error('SoftBank official list API has unreviewed query/pagination parameters');
  }
  const value = JSON.parse(body);
  if (!value || !Array.isArray(value.data) || !Number.isSafeInteger(value.total_count) ||
      value.total_count < 0 || value.hasMore === true || value.has_more === true ||
      value.next || value.next_page || value.nextPage) {
    throw new Error('SoftBank official list count/pagination is missing or incomplete');
  }
  const rows = [];
  const months = new Set();
  for (const block of value.data) {
    if (!block || !/^20\d{2}(?:0[1-9]|1[0-2])$/.test(block.month || '') ||
        !block.month.startsWith(url.searchParams.get('year')) ||
        !Array.isArray(block.list) || months.has(block.month)) {
      throw new Error('SoftBank official list month grouping is missing, duplicate or outside the requested year');
    }
    months.add(block.month);
    for (const raw of block.list) {
      if (!raw || !/^20\d{2}\d{4}$/.test(raw.date || '') ||
          raw.date.slice(0, 6) !== block.month || typeof raw.display_date !== 'string' ||
          typeof raw.title !== 'string' || !raw.title.trim() ||
          typeof raw.url !== 'string' || !raw.url.trim()) {
        throw new Error('SoftBank official publication/title/URL row is missing or malformed');
      }
      const y = Number(raw.date.slice(0, 4)), m = Number(raw.date.slice(4, 6)), d = Number(raw.date.slice(6, 8));
      const instant = new Date(Date.UTC(y, m - 1, d));
      if (instant.getUTCFullYear() !== y || instant.getUTCMonth() !== m - 1 || instant.getUTCDate() !== d ||
          raw.display_date !== `${y}年${m}月${d}日`) {
        throw new Error('SoftBank official date and display_date are invalid or contradictory');
      }
      const target = new URL(raw.url, sourceUrl);
      if (target.protocol !== 'https:' || target.username || target.password) {
        throw new Error('SoftBank official row has an unsafe disclosure URL');
      }
      const publicationIndex=target.hostname==='www.softbank.jp'&&/^\/corp\/ir\/documents\/presentations\/fy20\d{2}\/$/.test(target.pathname)&&target.hash==='#result-'+raw.date&&raw.category==='決算'&&Array.isArray(raw.category_search)&&raw.category_search.includes('決算')&&/決算短信・各種資料\s*掲載$/.test(raw.title.trim());
      rows.push({ title: raw.title.trim(), url: target.href,
        ...(publicationIndex?{recordKind:'publication-index',recordKindEvidence:{sourceSchema:'softbank-list-v1',actualRecord:raw,reason:'dated financial-library index; substantive documents require separate body evidence'}}:{}),
        date: `${raw.date.slice(0, 4)}-${raw.date.slice(4, 6)}-${raw.date.slice(6, 8)}`,
        evidence: JSON.stringify(raw), rawPublicationField: raw.date });
    }
  }
  if (rows.length !== value.total_count) throw new Error('SoftBank official total_count differs from actual complete row count');
  return rows;
}

// Read the actual publication field from the identical official article.
// The update clock and document/server metadata are intentionally unused.
export function parseSoftBankArticlePublication(body, row) {
  const url = new URL(row.url);
  if (url.protocol !== 'https:' || url.hostname !== 'www.softbank.jp' ||
      !/^\/corp\/news\/press\/sbkk\/20\d{2}\/\d{8}_\d+\/$/.test(url.pathname)) {
    throw new Error('SoftBank publication article is not an owned issuer press page');
  }
  const objects = [];
  function visit(value) {
    if (Array.isArray(value)) { value.forEach(visit); return; }
    if (!value || typeof value !== 'object') throw new Error('Malformed official JSON-LD value');
    objects.push(value);
    if (value['@graph']) visit(value['@graph']);
  }
  for (const match of body.matchAll(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    visit(JSON.parse(match[1]));
  }
  const articles = objects.filter(value => value['@type'] === 'NewsArticle' && value.url === url.href);
  if (articles.length !== 1) throw new Error('Exact official NewsArticle publication record is missing or ambiguous');
  const article = articles[0];
  const normalize = value => String(value || '').normalize('NFKC').replace(/\s+/g, '');
  const organization = value => value && value['@type'] === 'Organization' &&
    value['@id'] === 'https://www.softbank.jp/#organization' && value.url === 'https://www.softbank.jp/' &&
    Array.isArray(value.name) && value.name.some(name => name['@language'] === 'ja' && name['@value'] === 'ソフトバンク株式会社');
  if (article['@context'] !== 'https://schema.org' || article.inLanguage !== 'ja' ||
      normalize(article.headline) !== normalize(row.title) ||
      !organization(article.author) || !organization(article.publisher) ||
      article['@id'] !== url.href + '#news-article' ||
      article.mainEntityOfPage?.['@id'] !== url.href + '#web-page') {
    throw new Error('Official article publication identity/title does not match the issuer list row');
  }
  const publishedAt = article.datePublished;
  if (typeof publishedAt !== 'string' ||
      !/^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(publishedAt) ||
      !Number.isFinite(Date.parse(publishedAt))) {
    throw new Error('Official article datePublished lacks an actual valid explicit publication timezone');
  }
  const dateJst = new Date(Date.parse(publishedAt) + 9 * 3600000).toISOString().slice(0, 10);
  if (dateJst !== row.date) throw new Error('Official article publication date contradicts the exact issuer list date');
  return { publishedAt, publicationField: 'NewsArticle.datePublished',
    evidenceUrl: url.href,
    evidence: JSON.stringify({ url: article.url, headline: article.headline, datePublished: article.datePublished,
      author: article.author, publisher: article.publisher }) };
}

export function canonicalSoftBankArticle(body, row) {
  const publication = parseSoftBankArticlePublication(body, row);
  const mains = [...body.matchAll(/<main\b[^>]*>[\s\S]*?<\/main>/gi)];
  if (mains.length !== 1) throw new Error('Official issuer article main body is missing or ambiguous');
  const mainHtml = mains[0][0].replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/\s+/g, ' ').trim();
  const content = { scope: 'exact owned NewsArticle publication identity and complete main HTML, excluding scripts/comments; volatile site header/dateModified excluded',
    url: row.url, publication: JSON.parse(publication.evidence), mainHtml };
  const sha256 = createHash('sha256').update(JSON.stringify(content)).digest('hex');
  return { content, sha256, publication };
}
