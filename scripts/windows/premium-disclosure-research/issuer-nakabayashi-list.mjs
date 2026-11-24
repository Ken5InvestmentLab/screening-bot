// Nakabayashi's annual IR archive exposes each publication as a nested div.
// Its IR landing page contains only the newest five entries.
export function parseNakabayashiIrArchive(body, spec, sourceUrl, {plain, officialUrl}) {
  const url = new URL(sourceUrl);
  const year = url.pathname.match(/^\/news\/(20\d{2})\/ir\/?$/)?.[1];
  if (spec.symbolCode !== '7987' || spec.kind !== 'issuer' || url.origin !== 'https://www.nakabayashi.co.jp' ||
      !year || url.search || url.hash || !spec.coverageFrom?.startsWith(year + '-') || !spec.coverageThrough?.startsWith(year + '-')) {
    throw Error('Nakabayashi IR archive requires its official year, issuer and coverage');
  }
  const html = body.replace(/<!--[\s\S]*?-->|<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  if (/\brel\s*=\s*["']next["']|data-has-more\s*=\s*["']true["']/i.test(html)) throw Error('Nakabayashi IR archive pagination is incomplete');
  const divTags = /<\/?div\b[^>]*>/gi;
  const scope = [...html.matchAll(divTags)].filter(m => /\bid\s*=\s*["']news-list["']/i.test(m[0]));
  if (scope.length !== 1) throw Error('Nakabayashi IR archive scope is missing or ambiguous');

  divTags.lastIndex = scope[0].index + scope[0][0].length;
  const start = divTags.lastIndex, cards = [];
  let depth = 1, cardStart;
  for (let tag; (tag = divTags.exec(html));) {
    if (tag[0][1] === '/') {
      depth--;
      if (depth === 0) break;
      if (depth === 1) cards.push(html.slice(cardStart, divTags.lastIndex));
    } else {
      if (depth === 1) {
        if (!/\bclass\s*=\s*["']news-item["']/i.test(tag[0])) throw Error('unrecognized Nakabayashi archive item');
        cardStart = tag.index;
      } else if (depth !== 2 || !/\bclass\s*=\s*["']news-ttl["']/i.test(tag[0])) {
        throw Error('unrecognized nested Nakabayashi news row');
      }
      depth++;
    }
  }
  const listing = html.slice(start, divTags.lastIndex);
  if (depth !== 0 || !cards.length || (listing.match(/<span\s+class=["']date["']>/gi) || []).length !== cards.length ||
      (listing.match(/<a\b[^>]*href=["'][^"']*\.pdf["']/gi) || []).length !== cards.length ||
      /<a\b[^>]*(?:href=["'][^"']*[?&]page=|class=["'][^"']*\b(?:next|pagination)\b)/i.test(listing)) {
    throw Error('Nakabayashi IR archive contains an incomplete or unsupported listing');
  }
  const rows = cards.map(card => {
    const dates = [...card.matchAll(/<span\s+class=["']date["']>([^<]+)<\/span>/gi)];
    const titles = [...card.matchAll(/<span\s+class=["']ttl["']>\s*<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)];
    if (dates.length !== 1 || titles.length !== 1 || (card.match(/<a\b/gi) || []).length !== 1 ||
        !/<span\s+class=["']cate cate-ir["']>IR<\/span>/i.test(card)) throw Error('Nakabayashi IR date, category or title missing or ambiguous');
    const rawDate = dates[0][1].trim(), date = rawDate.replaceAll('.', '-');
    if (!/^20\d{2}\.\d{2}\.\d{2}$/.test(rawDate) || !date.startsWith(year + '-') ||
        !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) throw Error('invalid Nakabayashi publication date');
    const title = plain(titles[0][2]);
    const docUrl = officialUrl(titles[0][1], sourceUrl);
    const target = new URL(docUrl);
    if (!title || target.origin !== url.origin || !/^\/_files\/News\/[^?#]+\.pdf$/i.test(target.pathname) || target.search || target.hash) {
      throw Error('Nakabayashi official news row has no verified title and primary PDF');
    }
    return {date, title, url:docUrl, evidence:dates[0][0], rawPublicationField:rawDate};
  });
  if (new Set(rows.map(row => row.url)).size !== rows.length || rows.some((row, i) => i > 0 && row.date > rows[i-1].date) ||
      rows.at(-1).date > spec.coverageFrom) throw Error('Nakabayashi IR archive coverage, order or document identity is incomplete');
  return {rows, emptyProven:false};
}
