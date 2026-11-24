const news = 'https://www.beatholdings.com/news';
const releases = 'https://beatholdings-api.jiexiongkhoo.workers.dev/api/releases';
const r2 = 'https://pub-caaba8498f194d2a9040f39213ad9632.r2.dev';
const legacy = 'https://qwvdeosnyngzgtnmmyog.supabase.co';

function japanesePdf(value) {
  if (typeof value !== 'string') throw Error('Beat Japanese release PDF is missing');
  const url = new URL(value);
  if (url.search || url.hash || url.username || url.password ||
      !((url.origin === r2 && /^\/(?:releases\/)?[^/]+\.pdf$/i.test(url.pathname)) ||
        (url.origin === legacy && /^\/storage\/v1\/object\/public\/timely-disclosures\/{1,2}[^/]+\.pdf$/i.test(url.pathname)))) {
    throw Error('unrecognized Beat Japanese release PDF host or path');
  }
  return url.href;
}

export async function readBeatReleases(body, spec, sourceUrl, read) {
  if (spec.kind !== 'issuer' || spec.symbolCode !== '9399' || sourceUrl !== releases ||
      !/^20\d\d-\d\d-\d\d$/.test(spec.coverageFrom || '') || spec.zoneEvidence) {
    throw Error('Beat release feed requires the reviewed issuer, API and date-only source');
  }
  const page = await read(news);
  if (page.status !== 200 || (page.url || news) !== news || !/<title\b[^>]*>News - Beat Holdings<\/title>/i.test(page.body)) {
    throw Error('Beat official news page binding is missing');
  }
  const chunks = [...page.body.matchAll(/<script\b[^>]*\bsrc=["'](\/_next\/static\/chunks\/pages\/news-[a-f0-9]+\.js)["'][^>]*>/g)];
  if (chunks.length !== 1) throw Error('Beat news-page client bundle is missing or ambiguous');
  const bundleUrl = new URL(chunks[0][1], news).href;
  const bundle = await read(bundleUrl);
  const fetchCall = 'fetch("' + releases + '")';
  const pieces = String(bundle.body || '').split(fetchCall);
  const response = pieces[0].match(/\b(?:let|const|var) (\w+)=await $/)?.[1];
  const decode = pieces[1]?.match(/^,(\w+)=await (\w+)\.json\(\);\w+\(\1\),\w+\(\1\);let \w+=\[\.\.\.new Set\(\1\.map\(/);
  const japaneseLink = /\bhref:\w+\.file\.JP,(?:(?!href:)[^{}]){0,240}children:\w+\("news\.pdfLinks\.japanese"\)/;
  if (bundle.status !== 200 || (bundle.url || bundleUrl) !== bundleUrl || pieces.length !== 2 ||
      !response || !decode || decode[2] !== response || !japaneseLink.test(bundle.body)) {
    throw Error('Beat official unpaginated release API or Japanese PDF binding is unverified');
  }
  const feed = JSON.parse(body);
  if (!Array.isArray(feed) || !feed.length) throw Error('Beat full release array is missing');
  const ids = new Set(), urls = new Set();
  let previousDate;
  const rows = feed.map(item => {
    const {id, date, title, file, category} = item || {};
    if (!Number.isSafeInteger(id) || id < 1 || ids.has(id) || !['TIMELY','NEWS','FINANCIAL'].includes(category) ||
        !/^20\d\d-\d\d-\d\d$/.test(date) || !Number.isFinite(Date.parse(date)) ||
        new Date(date).toISOString().slice(0,10) !== date || (previousDate && date > previousDate)) {
      throw Error('Beat release ID, category, order or date is invalid');
    }
    if (typeof title?.JP !== 'string' || !title.JP.trim() || typeof title.EN !== 'string' ||
        !Object.hasOwn(file || {},'EN') || !(file.EN === 0 || typeof file.EN === 'string') ||
        file.EN === file.JP) {
      throw Error('Beat Japanese release title or language selection is ambiguous');
    }
    const url = japanesePdf(file.JP);
    if (urls.has(url)) throw Error('duplicate Beat Japanese PDF');
    const dateToken = body.match(new RegExp('"date"\\s*:\\s*"' + date + '"'))?.[0];
    if (!dateToken) throw Error('Beat publication field missing in original JSON');
    ids.add(id); urls.add(url); previousDate = date;
    return {publisherId:String(id), date, title:title.JP.trim(), url, evidence:dateToken, rawPublicationField:date};
  });
  if (rows.at(-1).date >= spec.coverageFrom) throw Error('Beat official feed ends inside the required window');
  return {rows, emptyProven:false};
}
