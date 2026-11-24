import crypto from 'node:crypto';

// Source decoding only. Publication, inventory and delivery checks use the
// same rules as for the other official issuer formats.
const attributes = html => Object.fromEntries(
  [...html.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)]
    .map(([, key, doubleQuoted, singleQuoted]) => [key.toLowerCase(), doubleQuoted ?? singleQuoted]),
);
const sha256 = body => crypto.createHash('sha256').update(body).digest('hex');
export function dottedJsonRecordText(body, records) {
  const rows = [...body.matchAll(/\{(?:"(?:\\.|[^"\\])*"|[^{}"])*\}/g)].map(match => match[0]);
  if (!Array.isArray(records) || rows.length !== records.length ||
      rows.some((text, index) => JSON.stringify(JSON.parse(text)) !== JSON.stringify(records[index]))) {
    throw new Error('official dotted-date JSON must be a complete flat record array');
  }
  return rows;
}

export function parseIssuerAtom(body, sourceUrl, { plain, officialUrl }) {
  const feed = /<feed\b[^>]*\bxmlns=["']http:\/\/www\.w3\.org\/2005\/Atom["'][^>]*>/i;
  if (!feed.test(body) || !/<\/feed>\s*$/i.test(body) || /<!DOCTYPE|<!ENTITY|\brel\s*=\s*["']next["']/i.test(body)) {
    throw new Error('unsupported or incomplete official Atom feed');
  }
  const entries = [...body.matchAll(/<entry\b[^>]*>([\s\S]*?)<\/entry>/gi)];
  if (!entries.length || entries.length !== (body.match(/<entry\b/gi) || []).length) {
    throw new Error('missing or incomplete official Atom entries');
  }
  return entries.map(([, entry]) => {
    const metadata = entry.replace(/<(content|summary)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
    const getField = name => {
      const fields = [...metadata.matchAll(new RegExp('<' + name + '\\b[^>]*>([\\s\\S]*?)</' + name + '>', 'gi'))];
      if (fields.length !== 1) throw new Error('missing or ambiguous official Atom ' + name);
      return fields[0][1].trim().replace(/^<!\[CDATA\[([\s\S]*)\]\]>$/, '$1');
    };
    const title = plain(getField('title'));
    const publishedAt = getField('published');
    if (!title || !/^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$/.test(publishedAt)) {
      throw new Error('official Atom entry needs a title and zoned publication timestamp');
    }
    const links = [...metadata.matchAll(/<link\b([^>]*?)\/?>/gi)].map(([, raw]) => attributes(raw));
    const article = links.filter(link => link.rel === 'alternate' && link.type === 'text/html' && link.href);
    if (article.length !== 1) throw new Error('missing or ambiguous official Atom article link');
    return {
      title,
      publishedAt,
      rawPublicationField: publishedAt,
      url: officialUrl(article[0].href.replace(/&amp;/g, '&'), sourceUrl),
      evidence: '<published>' + publishedAt + '</published>',
    };
  });
}

export function parseIssuerBlogList(body, sourceUrl, { plain, officialUrl }) {
  const sections = [...body.matchAll(/<section\b([^>]*)>/gi)]
    .filter(([, raw]) => (attributes(raw).class || '').split(/\s+/).includes('BlogList'));
  if (sections.length !== 1) throw new Error('missing or ambiguous official BlogList section');
  const start = sections[0].index;
  const sectionTags = /<\/?section\b[^>]*>/gi;
  sectionTags.lastIndex = start;
  let depth = 0;
  let end;
  for (let tag; (tag = sectionTags.exec(body));) {
    depth += tag[0].startsWith('</') ? -1 : 1;
    if (depth === 0) {
      end = sectionTags.lastIndex;
      break;
    }
  }
  if (!end) throw new Error('official BlogList section is incomplete');
  const listing = body.slice(start, end);
  const cards = [...listing.matchAll(/<article\b([^>]*)>([\s\S]*?)<\/article>/gi)]
    .filter(([, raw]) => (attributes(raw).class || '').split(/\s+/).includes('BlogList-item'));
  if (!cards.length || cards.length !== (listing.match(/<article\b/gi) || []).length) {
    throw new Error('incomplete official BlogList records');
  }
  return cards.map(([, , card]) => {
    const heading = [...card.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)]
      .filter(([, raw]) => (attributes(raw).class || '').split(/\s+/).includes('BlogList-item-title'));
    const dates = [...card.matchAll(/<time\b([^>]*)>[^<]*<\/time>/gi)];
    if (heading.length !== 1 || dates.length !== 1) throw new Error('ambiguous official BlogList title or publication date');
    const title = plain(heading[0][2]);
    const date = attributes(dates[0][1]).datetime;
    const href = attributes(heading[0][1]).href;
    if (!title || !href || !/^20\d{2}-\d{2}-\d{2}$/.test(date || '')) {
      throw new Error('official BlogList entry lacks title, direct link or release date');
    }
    return { title, date, url: officialUrl(href.replace(/&amp;/g, '&'), sourceUrl), evidence: dates[0][0] };
  });
}

export async function readJpxPrPublication(body, spec, read, readBytes, { plain, officialUrl, publicationFromRow }) {
  const { nativePdfUrl, ifisListUrl, ifisPdfUrl, yahooPdfUrl, kabutanPdfUrl, jpxArchiveDate, documentId } = spec.prEvidence || {};
  if (Boolean(yahooPdfUrl) === Boolean(kabutanPdfUrl)) throw new Error('JPX PR requires one reviewed TDnet mirror');
  const native = officialUrl(nativePdfUrl);
  const mirrorPdf = officialUrl(kabutanPdfUrl || yahooPdfUrl);
  const ifisPdf = officialUrl(ifisPdfUrl);
  const ifisList = officialUrl(ifisListUrl);
  const nativeLocation = new URL(native);
  const source = new URL(spec.url);
  const expectedListing = kabutanPdfUrl
    ? `https://s.kabutan.jp/stocks/${spec.symbolCode}/news/`
    : `https://finance.yahoo.co.jp/quote/${spec.symbolCode}.T/disclosure`;
  const expectedKabutanPdf = `https://tdnet-pdf.kabutan.jp/${spec.date?.replaceAll('-', '')}/${documentId}.pdf`;
  if (!readBytes || source.origin + source.pathname !== expectedListing ||
      (kabutanPdfUrl && mirrorPdf !== expectedKabutanPdf) ||
      !/^1401\d{14}$/.test(documentId || '') ||
      nativeLocation.origin !== 'https://www2.jpx.co.jp' ||
      nativeLocation.pathname !== '/disc/' + spec.symbolCode + '0/' + documentId + '.pdf' ||
      jpxArchiveDate !== spec.date || new URL(ifisPdf).hostname !== 'kabuyoho-sls-disclose.ifis.co.jp' ||
      !new URL(ifisPdf).pathname.endsWith('/' + documentId + '.pdf')) {
    throw new Error('JPX PR requires a reviewed issuer/document binding and official archive original');
  }
  const mirrorRows = kabutanPdfUrl
    ? [...body.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)]
      .filter(([, attr]) => attributes(attr).href === mirrorPdf)
      .map(([, , card]) => card)
    : [...body.matchAll(/<article\b[^>]*>([\s\S]*?)<\/article>/gi)]
      .map(([, card]) => card)
      .filter(card => card.includes('href="' + mirrorPdf + '"'));
  const category = kabutanPdfUrl
    ? /<span\b[^>]*\bnews_category-disclosure\b[^>]*>\s*開示\s*<\/span>/i
    : />TDnet<\/li>/i;
  if (mirrorRows.length !== 1 || !category.test(mirrorRows[0])) throw new Error('TDnet publisher mirror row is missing or ambiguous');
  const titleTag = kabutanPdfUrl ? /<div\b[^>]*>([\s\S]*?)<\/div>/i : /<h3\b[^>]*>([\s\S]*?)<\/h3>/i;
  const title = plain(mirrorRows[0].match(titleTag)?.[1] || '');
  const rawTime = attributes(mirrorRows[0].match(/<time\b([^>]*)>/i)?.[1] || '').datetime;
  const time = kabutanPdfUrl
    ? rawTime?.replace(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) \+0900$/, '$1T$2+09:00')
    : rawTime;
  if (!title || !time?.startsWith(jpxArchiveDate + 'T') || !time.endsWith('+09:00')) throw new Error('TDnet publisher mirror lacks actual zoned publication metadata');
  const ifis = await read(ifisList);
  if (ifis.status !== 200 || !ifis.body || new URL(ifis.url || ifisList).hostname !== new URL(ifisList).hostname) {
    throw new Error('independent TDnet distributor listing unavailable');
  }
  const rows = [...ifis.body.matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/gi)]
    .map(([, record]) => record).filter(record => record.includes('pid=' + documentId));
  if (rows.length !== 1 || !rows[0].includes('PR情報')) throw new Error('independent TDnet PR record is missing or ambiguous');
  const ifisTitle = plain(rows[0].match(/<dd\b[^>]*>([\s\S]*?)<\/dd>/i)?.[1] || '');
  const ifisClock = plain(rows[0].match(/<span\b[^>]*class=["']time["'][^>]*>([\s\S]*?)<\/span>/i)?.[1] || '');
  const digits = ifisClock.match(/^(20\d{2})年(\d{1,2})月(\d{1,2})日\s+(\d{2}:\d{2})$/);
  const wanted = digits && digits[1] + '-' + digits[2].padStart(2, '0') + '-' + digits[3].padStart(2, '0') + 'T' + digits[4];
  if (!wanted || time.slice(0, 16) !== wanted || ifisTitle.normalize('NFKC') !== title.normalize('NFKC')) {
    throw new Error('TDnet distributor publication field or title disagrees with the mirror');
  }
  const bytes = await Promise.all([native, mirrorPdf, ifisPdf].map(url => readBytes(url)));
  if (bytes.some(result => result.status !== 200 || Buffer.from(result.body || []).subarray(0, 5).toString() !== '%PDF-')) {
    throw new Error('JPX PR identity check requires all three reachable original PDFs');
  }
  const hashes = bytes.map(result => sha256(Buffer.from(result.body)));
  if (new Set(hashes).size !== 1) throw new Error('TDnet PR copies do not match the official JPX original');
  const row = { title, publishedAt: time, url: native, evidence: rawTime, rawPublicationField: rawTime };
  const publication = publicationFromRow(row, spec.url);
  return [{
    ...row,
    exchangeMatchedPublication: {
      ...publication,
      evidenceKind: 'tdnet-pr-distribution',
      publicationField: 'time[datetime]',
      clockCorroboration: {
        jpxArchiveDate,
        jpxUrl: native,
        mirrorUrl: mirrorPdf,
        distributorUrl: ifisPdf,
        distributorListing: ifisList,
        distributorField: ifisClock,
        distributorListingSha256: sha256(ifis.body),
        documentSha256: hashes[0],
      },
    },
  }];
}
