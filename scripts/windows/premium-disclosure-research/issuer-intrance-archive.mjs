import { createHash } from 'node:crypto';

export function intranceArchive(root) {
  const categories = new Map([
    ['https://intrance.jp/ir/ir-arc/irnews/', 'IRニュース'],
    ['https://intrance.jp/ir/ir-arc/irlibrary/', 'IRライブラリ'],
  ]);
  const title = categories.get(root);
  return title && {
    code: '3237', root, title, issuer: '株式会社イントランス',
    container: 'ul', className: 'common-wrap__ir', card: 'li',
    cardClass: 'common-wrap__ir-item',
  };
}

export function intranceNavigation(body, { hasClass, elementAt }) {
  const tags = [...body.matchAll(/<div\b[^>]*>/gi)].filter(match => hasClass(match[0], 'wp-pagenavi'));
  if (tags.length !== 1) throw new Error('issuer archive page navigation missing or ambiguous');
  return elementAt(body, tags[0].index, 'div').inner;
}

export async function resolveIntranceDocument(row, read, { plain, officialUrl, elementAt, hasClass, attribute }) {
  const landing = await read(row.url);
  if (landing.status !== 200 || !landing.body || officialUrl(landing.url || row.url) !== row.url) throw new Error('Intrance IR article unavailable or redirected');
  const headings = [...landing.body.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)];
  const sections = [...landing.body.matchAll(/<div\b[^>]*>/gi)].filter(match => hasClass(match[0], 'detail-content'));
  if (headings.filter(match => plain(match[1]) === row.title).length !== 1 || sections.length !== 1) throw new Error('Intrance IR article title or attachment container changed');
  const html = elementAt(landing.body, sections[0].index, 'div').inner;
  const anchors = [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)];
  if (anchors.length !== 2 || !anchors.some(match => hasClass(match[1], 'pdfemb-viewer')) ||
      !anchors.some(match => hasClass(match[1], 'c-btn__02--down'))) throw new Error('unreviewed Intrance article attachment roles');
  const links = anchors.map(match => officialUrl(attribute(match[1], 'href'), row.url));
  const href = links[0];
  if (links[1] !== href || new URL(href).origin !== 'https://intrance.jp' || !/^\/wp-content\/uploads\/[^?#]+\.pdf$/i.test(new URL(href).pathname)) throw new Error('Intrance article attachments ambiguous or off-site');
  row.originalListingUrl = row.url;
  row.documentResolutionEvidence = { listingUrl: row.url, listingSha256: createHash('sha256').update(landing.body).digest('hex'), actualHref: href };
  row.url = href;
}
