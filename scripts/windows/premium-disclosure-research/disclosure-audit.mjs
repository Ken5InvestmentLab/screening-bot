import crypto from 'node:crypto';
import {expandIssuerIrRecords} from './issuer-ir-record.mjs';
import {parseSoftBankList,canonicalSoftBankArticle} from './issuer-softbank-list.mjs';
import {buildHttpIssuerRows} from './issuer-http-discovery.mjs';
import {readIssuerArchive} from './issuer-paginated-archives.mjs';
import {parseNakabayashiIrArchive} from './issuer-nakabayashi-list.mjs';
import {readBeatReleases} from './issuer-beat-releases.mjs';
import {dottedJsonRecordText, parseIssuerAtom, parseIssuerBlogList, readJpxPrPublication} from './issuer-feed-rows.mjs';

const DAY = 86400000;
const DISCLOSURE_LINK = /\[([^\r\n]+?)\]\((https?:\/\/[^)\s]+)\)/g;
export function disclosureFieldChunks(value,limit=1024) {
  const chunks=[];let current='';
  for(const line of String(value||'').split(/\r?\n/)) {
    if(line.length>limit)throw new Error('one verified disclosure link exceeds the Discord field limit');
    if(current&&current.length+1+line.length>limit){chunks.push(current);current=line;}else current+=(current?'\n':'')+line;
  }
  if(current||!chunks.length)chunks.push(current);return chunks;
}
export function renderedDisclosureUrls(fields) {
  return new Set((fields||[]).filter(f=>f.name==='開示リンク'||/^開示リンク（続き\d+）$/.test(f.name)).flatMap(f=>[...String(f.value||'').matchAll(DISCLOSURE_LINK)].map(m=>officialUrl(m[2]))));
}

export function canonicalDisclosureLabels(value, inventory) {
  return String(value || '').replace(DISCLOSURE_LINK, (original, _label, url) => {
    const directUrl = officialUrl(url);
    const item = inventory.items.find(entry => entry.urls.includes(directUrl));
    return item ? `[${publicationLabel(item)}](${url})` : original;
  });
}
// Exact PDF body identity except for a narrow set of resave metadata. These
// metadata values NEVER establish a publication time. Creation dates, document
// IDs, page objects, streams, attachments and all other bytes remain significant.
export function pdfDocumentIdentity(bytes) {
  const raw=Buffer.from(bytes).toString('latin1');
  if(!raw.startsWith('%PDF-'))throw new Error('PDF identity requires original PDF bytes');
  const infoIds=new Set([...raw.matchAll(/\/Info\s+(\d+)\s+(\d+)\s+R\b/g)].map(m=>m[1]+' '+m[2]));
  const canonical=raw.replace(/\b(\d+)\s+(\d+)\s+obj\b([\s\S]*?)\bendobj\b/g,(whole,id,generation,body)=>{
    const streamAt=body.indexOf('stream'),dictionary=streamAt<0?body:body.slice(0,streamAt);let result=whole;
    if(infoIds.has(id+' '+generation)&&streamAt<0)result=result.replace(/\/ModDate\s*\(D:\d{14}(?:[+-]\d{2}'\d{2}'|Z)?\)/g,'/ModDate(RESAVE-METADATA)');
    if(/\/Type\s*\/Metadata\b/.test(dictionary)&&/\/Subtype\s*\/XML\b/.test(dictionary)&&!dictionary.includes('/Filter')&&whole.includes('http://ns.adobe.com/xap/1.0/')) {
      result=result.replace(/<(xmp:ModifyDate|xmp:MetadataDate)>[^<]*<\/\1>/g,(_,tag)=>`<${tag}>RESAVE-METADATA</${tag}>`).replace(/<xmpMM:InstanceID>uuid:[0-9a-f-]+<\/xmpMM:InstanceID>/gi,'<xmpMM:InstanceID>RESAVE-INSTANCE</xmpMM:InstanceID>');
    }
    if(/\/Type\s*\/XRef\b/.test(dictionary))result=result.replace(/\/ID\s*\[\s*<([0-9a-f]+)>\s*<[0-9a-f]+>\s*\]/gi,'/ID[<$1><RESAVE-INSTANCE>]');
    return result;
  });
  return digest(Buffer.from(canonical,'latin1'));
}
function videoIssuerBinding(rule, spec, symbolCode) {
  if (!rule.issuerIrBinding) return null;
  const {channelId, issuerIrUrl} = rule.issuerIrBinding;
  const proof = spec.zoneEvidence;
  const issuerUrl = new URL(officialUrl(issuerIrUrl));
  const feed = new URL(officialUrl(spec.url));
  if (spec.kind !== 'issuer' || spec.format !== 'eir-announcements-v1' || spec.symbolCode !== symbolCode ||
      feed.hostname !== 'ssl4.eir-parts.net' || feed.pathname !== '/V4Public/eir/' + symbolCode + '/ja/announcement/announcement_0.js' ||
      !/^UC[A-Za-z0-9_-]{22}$/.test(channelId || '') || proof?.basis !== 'domestic-official' ||
      proof.symbolCode !== symbolCode || !proof.issuerBindingQuote?.includes(symbolCode) ||
      new URL(officialUrl(proof.issuerBindingUrl)).origin !== issuerUrl.origin ||
      issuerUrl.search || issuerUrl.hash || issuerUrl.pathname === '/') {
    throw new Error('official video issuer feed, channel or IR origin binding is invalid');
  }
  return {symbolCode, channelId, issuerIrUrl: issuerUrl.href, eirSourceUrl: feed.href};
}

export function officialVideoPage(body,declaredUrl,symbolCode,expectedChannelName,issuerIrBinding=null) {
  const u=new URL(officialUrl(declaredUrl)),id=u.hostname==='youtu.be'?u.pathname.slice(1):u.hostname==='www.youtube.com'&&u.pathname==='/watch'?u.searchParams.get('v'):null;
  if(!/^[\w-]{11}$/.test(id||''))throw new Error('unsupported official video document identity');
  let data=null;
  for(const marker of ['var ytInitialPlayerResponse =','ytInitialPlayerResponse =']) {
    const at=body.indexOf(marker);if(at<0)continue;const start=body.indexOf('{',at);let depth=0,quoted=false,escape=false;
    for(let i=start;i<body.length;i++){const ch=body[i];if(escape){escape=false;continue;}if(ch==='\\'&&quoted){escape=true;continue;}if(ch==='"'){quoted=!quoted;continue;}if(!quoted){if(ch==='{')depth++;if(ch==='}'&&--depth===0){data=JSON.parse(body.slice(start,i+1));break;}}}if(data)break;
  }
  const detail=data?.videoDetails,m=data?.microformat?.playerMicroformatRenderer;
  if(data?.playabilityStatus?.status!=='OK'||detail?.videoId!==id||m?.ownerChannelName!==expectedChannelName)throw new Error('official video page identity, availability or issuer binding failed');
  if (issuerIrBinding) {
    const {channelId, issuerIrUrl} = issuerIrBinding;
    const links = String(detail.shortDescription || '').split(/\s+/);
    if (issuerIrBinding.symbolCode !== symbolCode || !expectedChannelName || detail.channelId !== channelId ||
        m.externalChannelId !== channelId || !links.includes(issuerIrUrl) || !detail.title) {
      throw new Error('official video channel ID or issuer IR backlink differs');
    }
  } else if (!detail.title?.includes(symbolCode) && !detail.shortDescription?.includes(symbolCode)) {
    throw new Error('official video page identity, availability or issuer binding failed');
  }
  const date=m.publishDate;if(!/^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)$/.test(date||''))throw new Error('official video publication metadata has no explicit timestamp/timezone');
  const metaDates=[...body.matchAll(/<meta\b[^>]*itemprop=["']datePublished["'][^>]*content=["']([^"']+)["'][^>]*>/g)].map(m=>m[1]);
  if(metaDates.some(value=>value!==date))throw new Error('official video publication metadata conflicts');
  const content={videoId:id,title:detail.title,description:detail.shortDescription,ownerChannelName:m.ownerChannelName,publishedAt:date,uploadDate:m.uploadDate||null};
  if(issuerIrBinding)content.issuerIrBinding=issuerIrBinding;
  return {content,sha256:digest(JSON.stringify(content))};
}
const digest = text => crypto.createHash('sha256').update(text).digest('hex');
async function retainedPdfIdentity(result,readBytes) {
  const contentSha256=result.contentSha256||digest(result.body),key={contentSha256,validatorVersion:'pdf-resave-identity-20261116-v1',key:'all-other-bytes-significant'};
  const prior=readBytes.getVerification?.(key);if(typeof prior==='string'&&/^[a-f0-9]{64}$/.test(prior))return prior;
  const identity=pdfDocumentIdentity(result.body);if(result.contentSha256&&readBytes.recordVerification)readBytes.recordVerification({...key,value:identity});return identity;
}
const plain = text => String(text || '').replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
export function officialUrl(value, base) {
  const u = new URL(value, base);
  if (u.protocol !== 'https:' || u.username || u.password) throw new Error('official evidence requires an HTTPS URL without credentials');
  if ([...u.searchParams.keys()].some(k=>/token|authorization|api[_-]?key|signature|password|secret|credential|subscription-key|x-amz-/i.test(k))) throw new Error('credential-bearing URLs cannot be official public evidence');
  u.hash = ''; u.searchParams.sort(); return u.href;
}
function calendar(value) {
  const m = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) throw new Error('official publication date requires an explicit YYYY-MM-DD year');
  const [,y,mo,d]=m, t=Date.UTC(+y,+mo-1,+d), check=new Date(t);
  if (check.toISOString().slice(0,10)!==value) throw new Error('invalid official publication calendar date');
  return t;
}
export function publication({ date, time, zone, evidenceUrl, evidenceText, zoneEvidenceText }) {
  officialUrl(evidenceUrl);
  calendar(date);
  if (!evidenceText) throw new Error('publication needs original date/time evidence, not a filename or document-ID inference');
  if (!time) return { dateJst: date, timeJst: null, precision: 'date', earliestMs: calendar(date)-9*3600000, latestMs: calendar(date)+15*3600000-1, evidenceUrl, evidenceText };
  if (!/^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(time)) throw new Error('invalid official publication time');
  const offsets = { 'Asia/Tokyo': '+09:00', JST: '+09:00', UTC: '+00:00', Z: '+00:00' };
  const offset = offsets[zone] || (/^[+-](?:0\d|1[0-4]):[0-5]\d$/.test(zone || '') ? zone : null);
  if (!offset || !zoneEvidenceText) throw new Error('official time zone is ambiguous; do not infer JST/UTC');
  const t=Date.parse(`${date}T${time.length===5?time+':00':time}${offset}`);
  if (!Number.isFinite(t)) throw new Error('invalid official timestamp offset');
  const jst=new Date(t+9*3600000).toISOString();
  return { dateJst:jst.slice(0,10),timeJst:jst.slice(11,16),precision:'minute',earliestMs:t,latestMs:t,evidenceUrl,evidenceText,zoneEvidenceText,sourceZone:zone };
}
export function publicationLabel(item) {
  const p=item.publication;
  if (!p.timeJst && p.evidenceKind==='issuer-ir-date-only') {
    const e=p.issuerIrEvidence;
    if(item.sourceKind!=='issuer'||p.precision!=='date'||!e||e.dateJst!==p.dateJst||e.documentUrl!==item.url||!e.categorySha256||!e.documentSha256||e.exchangeScan?.status!=='verified-no-identical-document'||!e.exchangeScan.pages?.length)throw new Error('company IR date-only classification is unverified');
    return `${p.dateJst} ${item.title}(会社IR資料・公表日)`;
  }
  if (!p.timeJst) throw new Error('official publication time is missing; resolve using the original publication field or an official same-document route before posting');
  return `${p.dateJst} ${item.title}(${p.timeJst} JST)`;
}
async function expandIssuerIrMaterials(rows,spec,symbolCode,read,readBytes) {
  if(!spec.issuerIrDateOnlyPolicies)return rows;
  if(spec.kind!=='issuer'||!Array.isArray(spec.issuerIrDateOnlyPolicies)||!readBytes)throw new Error('company IR classification requires an official issuer and actual documents');
  const output=[];
  for(const row of rows) {
    const policy=spec.issuerIrDateOnlyPolicies.find(p=>officialUrl(p.categoryUrl)===row.url&&p.publicationDate===row.date);
    if(!policy){output.push(row);continue;}
    if(policy.format!=='issuer-ir-library-v1'||!policy.categoryMarker||!policy.fiscalHeading||!policy.materialHeading||!Number.isInteger(policy.expectedDocumentCount)||policy.expectedDocumentCount<1)throw new Error('incomplete company IR category schema');
    if(new URL(row.url).hostname!==new URL(spec.url).hostname)throw new Error('company IR library is not on the verified issuer host');
    const category=await readBytes(row.url);if(category.status!==200||new URL(category.url||row.url).hostname!==new URL(spec.url).hostname)throw new Error('official company IR library unavailable');
    const body=Buffer.from(category.body).toString('utf8').replace(/<!--[\s\S]*?-->/g,'');if(!body.includes(policy.categoryMarker))throw new Error('company IR category identity missing');
    const candidates=[...body.matchAll(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi)].map(m=>m[0]).filter(r=>plain(r).includes(policy.fiscalHeading)&&plain(r).includes(policy.materialHeading));
    if(candidates.length!==1)throw new Error('company IR fiscal/material row missing or ambiguous');
    const documents=[...candidates[0].matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)].map(m=>({url:officialUrl(m[1],row.url),title:plain(m[2])}));
    if(documents.length!==policy.expectedDocumentCount||new Set(documents.map(d=>d.url)).size!==documents.length||documents.some(d=>new URL(d.url).hostname!==new URL(spec.url).hostname||!new URL(d.url).pathname.endsWith('.pdf')||!d.title))throw new Error('company IR document set missing/ambiguous');
    const date=policy.publicationDate;
    const proof={kind:'exchange',symbolCode,format:'tdnet-table-v1',url:`https://www.release.tdnet.info/inbs/I_list_001_${date.replaceAll('-','')}.html`,date,identityMarker:'適時開示情報閲覧サービス',followPagination:true};
    const {documents:references,observations:pages}=await publicationReferences({publicationSources:[proof]},symbolCode,read);
    for(const doc of documents){const bytes=await readBytes(doc.url);if(bytes.status!==200||Buffer.from(bytes.body).subarray(0,5).toString()!=='%PDF-')throw new Error('company IR actual PDF unavailable');
      const derived={...row,url:doc.url,title:`${row.title} — ${doc.title}`,publisherId:undefined,rowKey:`${date}|${row.url}|${doc.url}`,originalListingUrl:row.url,documentResolutionEvidence:{listingUrl:row.url,listingSha256:digest(category.body),actualHref:doc.url}};
      const p=publicationFromRow(row,spec.url,spec.zoneEvidence),matched=await corroboratePublication(derived,p,{documents:references},readBytes);
      if(matched.timeJst){derived.exchangeMatchedPublication={...matched,evidenceKind:'tdnet-publication'};}
      else derived.issuerIrEvidence={dateJst:date,categoryUrl:row.url,categoryMarker:policy.categoryMarker,categorySha256:digest(category.body),fiscalHeading:policy.fiscalHeading,materialHeading:policy.materialHeading,documentUrl:doc.url,documentSha256:digest(bytes.body),exchangeScan:{status:'verified-no-identical-document',symbolCode,date,pages}};
      output.push(derived);
    }
  }
  return output;
}
function publicationFromRow(row, sourceUrl, zoneProof) {
  const evidence=plain(row.evidence || row.raw || '');
  let date=row.date,time=row.time,zone=row.zone;
  if (row.publishedAt) {
    const publicationField=String(row.publishedAt).trim().replace(/^(\d{4})\/(\d{2})\/(\d{2})(?=[ T]|$)/,'$1-$2-$3').replace(/^(\d{4}-\d{2}-\d{2}) /,'$1T');
    const m=publicationField.match(/^(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$/);
    if (!m) throw new Error('unrecognized official publishedAt');
    if (m[3] && zone) {
      const offsets={JST:'+09:00','Asia/Tokyo':'+09:00',UTC:'+00:00',Z:'+00:00'};
      if ((offsets[zone]||zone)!==(offsets[m[3]]||m[3])) {
        const visible=row.date&&row.time ? Date.parse(`${row.date}T${row.time.length===5?row.time+':00':row.time}${offsets[zone]||zone}`) : NaN;
        if (!Number.isFinite(visible)||visible!==Date.parse(row.publishedAt)) throw new Error('conflicting official timezone declarations');
      }
    }
    [,date,time]=m; zone=m[3] || zone;
  }
  const zoneEvidenceText = zone ? (row.zoneEvidenceText || (row.publishedAt?.match(/(?:Z|[+-]\d{2}:\d{2})$/) ? row.publishedAt : evidence.includes(zone) ? evidence : null)) : zoneProof?.quote;
  const p=publication({date,time,zone:zone||zoneProof?.zone,evidenceUrl:sourceUrl,evidenceText:evidence,zoneEvidenceText});
  if (row.rawPublicationField) p.rawPublicationField=row.rawPublicationField;
  else if (row.publishedAt) p.rawPublicationField=String(row.publishedAt);
  if (!zone && zoneProof) p.zoneEvidence={...zoneProof};
  if(!zone && zoneProof?.basis==='domestic-official' && p.timeJst==='00:00') {
    const untimed=publication({date:p.dateJst,evidenceUrl:sourceUrl,evidenceText:evidence});
    return {...p,...untimed,originalMetadataTime:'00:00',timeJst:null,timeVerification:'unconfirmed midnight metadata; same-document official corroboration required'};
  }
  return p;
}
function htmlRows(body, spec, url, {checkPagination=true}={}) {
  let scope=body;
  if(spec.scopeElement) {
    const {tag,id,className}=spec.scopeElement;
    if(!['div','ul','dl','section','article','main'].includes(tag)||(!id&&!className)||!(/^[\w-]+$/).test(id||className))throw new Error('invalid reviewed HTML scope element');
    const candidates=[...body.matchAll(new RegExp(`<${tag}\\b[^>]*>`,'gi'))].filter(m=>id?m[0].match(new RegExp(`\\bid=["']${id}["']`)):m[0].match(new RegExp(`\\bclass=["'][^"']*\\b${className}\\b[^"']*["']`)));
    if(candidates.length!==1)throw new Error('reviewed HTML scope element missing or non-unique');
    const start=candidates[0].index,re=new RegExp(`<\\/?${tag}\\b[^>]*>`,'gi');re.lastIndex=start;let depth=0,end=-1;
    for(let m;(m=re.exec(body));){depth+=m[0].startsWith('</')?-1:1;if(depth===0){end=re.lastIndex;break;}}
    if(end<0)throw new Error('reviewed HTML scope element is incomplete');scope=body.slice(start,end);
  }
  if (spec.scopeStart || spec.scopeEnd) {
    if (!spec.scopeStart || !spec.scopeEnd || body.split(spec.scopeStart).length!==2 || body.split(spec.scopeEnd).length!==2) throw new Error('listing scope markers are missing or non-unique');
    const a=body.indexOf(spec.scopeStart)+spec.scopeStart.length,b=body.indexOf(spec.scopeEnd);
    if (b<=a) throw new Error('invalid listing scope'); scope=body.slice(a,b);
  }
  if (checkPagination && /rel\s*=\s*["']next["']|data-has-more\s*=\s*["']true["']/i.test(body)) throw new Error('listing pagination is incomplete; include the complete covered official list');
  if (!['tr','li','article','a','dt-dd'].includes(spec.recordTag)) throw new Error('unsupported official HTML record adapter');
  const rows=[], re=spec.recordTag==='dt-dd'?/<dt\b[^>]*>[\s\S]*?<\/dt>\s*<dd\b[^>]*>[\s\S]*?<\/dd>/gi:new RegExp(`<${spec.recordTag}\\b[^>]*>([\\s\\S]*?)<\\/${spec.recordTag}>`,'gi');
  const field=(raw,selector)=>{
    if(!selector||!['td','th','dt','dd','span','em','time','div','p'].includes(selector.tag)||(selector.className&&!/^[\w-]+$/.test(selector.className)))throw new Error('unsupported reviewed publication/title field');
    const attributePattern = selector.className ? `(?=[^>]*\\bclass=["'][^"']*\\b${selector.className}\\b[^"']*["'])` : '';
    const fragments=[...raw.matchAll(new RegExp(`<${selector.tag}\\b${attributePattern}[^>]*>([\\s\\S]*?)<\\/${selector.tag}>`,'gi'))];
    if(fragments.length!==1)throw new Error('official publication/title field missing or ambiguous');return fragments[0][0];
  };
  for (const m of scope.matchAll(re)) {
    const raw=m[0],text=plain(raw),links=[...raw.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)];
    if (!links.length) continue;
    const metadataFragment=spec.publicationField?field(raw,spec.publicationField):raw.replace(/<a\b[^>]*>[\s\S]*?<\/a>/gi,''),metadata=plain(metadataFragment);
    const dates=[...metadata.matchAll(/(20\d{2})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})日?/g)].map(m=>`${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`);
    const dateTimes=[...metadataFragment.matchAll(/<time\b[^>]*datetime=["']([^"']+)["']/gi)].map(m=>m[1]);
    const times=[...metadata.matchAll(/\b([01]?\d|2[0-3]):([0-5]\d)\b/g)].map(m=>`${m[1].padStart(2,'0')}:${m[2]}`);
    if (dateTimes.length>1 || (!dateTimes.length && (new Set(dates).size!==1 || new Set(times).size>1))) throw new Error('official row publication date/time is missing or ambiguous');
    const zone=metadata.match(/\b(JST|UTC)\b/)?.[1];
    for (const link of links) {
      const title=plain(spec.titleField?field(raw,spec.titleField):link[2]); if (!title) throw new Error('official disclosure anchor title is missing');
      const originalUrl = new URL(link[1].replace(/&amp;/g,'&'),url);
      const archivedHttp = spec.kind==='issuer' && spec.archiveLegacyHttpOutsideWindow===true && originalUrl.protocol==='http:';
      const contentUrl = archivedHttp ? null : officialUrl(originalUrl.href);
      if (archivedHttp) officialUrl(originalUrl.href.replace(/^http:/,'https:')); // Check URL safety without fetching a fabricated HTTPS alias.
      if(spec.rowIdentity && spec.rowIdentity!=='publication-url-title')throw new Error('unsupported reviewed official row identity');
      rows.push({url:contentUrl,title,publisherId:raw.match(/data-disclosure-id=["']([^"']+)["']/i)?.[1],
        ...(spec.rowIdentity || archivedHttp ? {rowKey:digest(JSON.stringify([contentUrl || originalUrl.href,dateTimes[0]||dates[0],title]))} : {}),
        date:dates[0],time:times[0],zone,publishedAt:dateTimes[0],evidence:text,
        ...(archivedHttp ? {originalUrl:originalUrl.href,documentUnavailable:true,archivedHttp:true} : {})});
    }
  }
  return {rows,emptyProven:Boolean(spec.emptyMarker&&scope.includes(spec.emptyMarker))};
}

async function readGeostarLibrary(body, spec, url, read, windowStart) {
  if (spec.kind!=='issuer' || spec.symbolCode!=='5282' ||
      !/^https:\/\/www\.geostr\.co\.jp\/ir\/library\/(?:balance_sheet|briefing|disclosure|securities)\/$/.test(url)) {
    throw Error('unreviewed GeoStar IR library identity');
  }
  const layout = {...spec,scopeElement:{tag:'div',className:'page-wrapper'},recordTag:'a',
    publicationField:{tag:'span',className:'page-balance__date'},titleField:{tag:'p',className:'page-balance__text'}};
  const parse = (page, pageUrl) => {
    if (!page.includes(spec.identityMarker) || /data-has-more\s*=\s*["']true["']/i.test(page)) throw Error('GeoStar IR library identity or completeness changed');
    const result = htmlRows(page,layout,pageUrl,{checkPagination:false}).rows;
    if (result.some((row,i) => i>0 && row.date > result[i-1].date) ||
        !result.length || calendar(result.at(-1).date)+15*3600000-1>=windowStart) {
      throw Error('GeoStar IR library list order or 45-day coverage changed');
    }
    return result;
  };
  const rows = parse(body, url);
  const matches = [...body.matchAll(/<link\b(?=[^>]*\brel=["']next["'])(?=[^>]*\bhref=["']([^"']+)["'])[^>]*>/gi)];
  const nextMarkers = [...body.matchAll(/<[^>]+\brel\s*=\s*["']next["'][^>]*>/gi)];
  if (matches.length>1 || nextMarkers.length!==matches.length) throw Error('GeoStar library next page is ambiguous');
  if (!matches.length) return {rows,nextPage:null};
  const nextUrl = officialUrl(matches[0][1],url);
  if(nextUrl!==url+'page/2/') throw Error('GeoStar library next page changed');
  const next = await read(nextUrl);
  if(next.status!==200 || officialUrl(next.url||nextUrl)!==nextUrl) throw Error('GeoStar library next page could not be checked');
  // WordPress emits this link on the static IR template. Retain proof that
  // the numbered page actually shows the identical disclosure list.
  const fingerprint = entries => digest(JSON.stringify(entries.map(row=>[row.date,row.url,row.title])));
  if(fingerprint(parse(next.body,nextUrl))!==fingerprint(rows)) throw Error('GeoStar library next page contains a distinct listing');
  return {rows,nextPage:{url:nextUrl,sha256:digest(next.body),observedAt:next.observedAt}};
}
// XJ GetList2 HTML is a three-column table. The publication cell is metadata;
// fiscal dates and meeting times in the separate title cell are never metadata.
function issuerXmlRows(body,spec,url) {
  if(/<!DOCTYPE|<!ENTITY/i.test(body)||!/<data\b/.test(body)||!/<\/data>\s*$/.test(body))throw new Error('unsupported or incomplete official XML envelope');
  const blocks=[...body.matchAll(/<XmlAnnouncementItem\b[^>]*>([\s\S]*?)<\/XmlAnnouncementItem>/g)];
  if(blocks.length!==[...body.matchAll(/<XmlAnnouncementItem\b/g)].length)throw new Error('official XML item is incomplete');
  const field=(raw,name)=>{const matches=[...raw.matchAll(new RegExp(`<${name}\\b[^>]*>([\\s\\S]*?)<\\/${name}>`,'g'))];if(matches.length>1)throw new Error('ambiguous official XML field '+name);return matches[0]?matches[0][1].replace(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/,'$1').trim():'';};
  const count=field(body.replace(/<item>[\s\S]*?<\/item>/g,''),'item_count');
  if(count ? !/^\d+$/.test(count)||Number(count)!==blocks.length : !spec.reviewedUncountedFeed)throw new Error('official XML count is missing or incomplete');
  const header=body.match(/<header>([\s\S]*?)<\/header>/)?.[1]||'',owned=field(header,'customer_code');
  if(owned&&owned!==spec.symbolCode)throw new Error('official XML issuer code mismatch');
  return blocks.map(([,raw])=>{
    const date=field(raw,'date'),title=plain(field(raw,'title')),guid=field(raw,'guid'),link=field(raw,'link');
    if(!date||!title)throw new Error('official XML publication/title missing');
    const absolute=link?new URL(link,url).href:null,unavailable=!absolute||absolute.startsWith('http:');
    if(absolute&&unavailable)officialUrl(absolute.replace(/^http:/,'https:'));
    const contentUrl=unavailable?null:officialUrl(absolute);
    return {publisherId:guid||undefined,...(!guid?{rowKey:digest(JSON.stringify([absolute,date,title]))}:{}),title,url:contentUrl,publishedAt:date,evidence:date,rawPublicationField:date,...(unavailable?{documentUnavailable:true,...(absolute?{originalUrl:absolute}:{})}:{})};
  });
}
function xjRows(body, spec, url) {
  const rows=[];
  for (const [raw] of body.matchAll(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi)) {
    if (/<th\b/i.test(raw)) continue;
    const cells=[...raw.matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map(m=>m[1]);
    if (cells.length!==3) throw new Error('unsupported XJ disclosure row: expected publication/title/links cells');
    const timestamp=plain(cells[0]);
    const m=timestamp.match(/^(20\d{2})\/(\d{2})\/(\d{2})\s+([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$/);
    if (!m) throw new Error('XJ publication cell has missing/invalid date or time');
    const title=plain(cells[1]);
    if (!title) throw new Error('XJ formal disclosure title is missing');
    const links=[...cells[2].matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)];
    const primary=links.filter(m=>plain(m[2])==='PDF-GENERAL');
    if (primary.length!==1 || links.some(m=>!['PDF-GENERAL','PDF-SUMMARY','XBRL-GENERAL-ZIP','XBRL-SUMMARY-ZIP'].includes(plain(m[2])))) throw new Error('unsupported XJ document attachment role; verify complete source layout');
    rows.push({url:officialUrl(primary[0][1],url),title,date:`${m[1]}-${m[2]}-${m[3]}`,time:`${m[4]}:${m[5]}:${m[6]}`,evidence:timestamp,rawPublicationField:timestamp});
  }
  return {rows,emptyProven:false};
}
function xjJsonRows(body, url) {
  const value=JSON.parse(body);
  if (!Array.isArray(value.items) || !/^\d+$/.test(String(value.length)) || Number(value.length)!==value.items.length || value.hasMore===true) throw new Error('incomplete or unsupported XJ JSON item inventory');
  return value.items.map(item=>{
    const m=String(item.publishDate||'').match(/^(20\d{2})\/(\d{2})\/(\d{2})\s+([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$/);
    if (!m || !item.title || !Array.isArray(item.files)) throw new Error('XJ JSON item missing publication/title/files');
    const primary=item.files.filter(f=>f.type==='PDF-GENERAL');
    if(primary.length!==1 || item.files.some(f=>!['PDF-GENERAL','PDF-SUMMARY','XBRL-GENERAL-ZIP','XBRL-SUMMARY-ZIP'].includes(f.type))) throw new Error('unsupported XJ JSON attachment role');
    return {url:officialUrl(primary[0].url,url),title:item.title,date:`${m[1]}-${m[2]}-${m[3]}`,time:`${m[4]}:${m[5]}:${m[6]}`,evidence:item.publishDate,rawPublicationField:item.publishDate};
  });
}
function jsonRows(body,spec,url) {
  if (spec.jsonpCallback) {
    if (!/^(?:window\.)?[A-Za-z_$][A-Za-z0-9_$]*$/.test(spec.jsonpCallback)) throw new Error('invalid official JSONP callback');
    const prefix=spec.jsonpCallback+'(';
    const text=body.replace(/^(?:\s*\/\/[^\r\n]*(?:\r?\n|$))*/, '').trim();
    if(!text.startsWith(prefix) || !/\)\s*;?$/.test(text)) throw new Error('official JSONP envelope does not match the configured callback');
    body=text.slice(prefix.length).replace(/\)\s*;?$/,'');
  }
  let value=JSON.parse(body);
  if(spec.format==='eir-announcements-v1') {
    if(!Array.isArray(value.header)||!value.header.some(h=>h.customer_code===spec.symbolCode)||!Array.isArray(value.item)||Number(value.item_count)!==value.item.length)throw new Error('official EIR identity/item count mismatch');
  }
  if (value.hasMore===true) throw new Error('official JSON pagination is incomplete');
  for (const key of (spec.recordsPath||'').split('.').filter(Boolean)) value=value?.[key];
  if (!Array.isArray(value)) throw new Error('official JSON records path is not an array');
  const keys={title:'title',url:'url',publisherId:'id',date:'date',time:'time',zone:'timezone',publishedAt:'publishedAt',...spec.keys};
  const dotted=spec.jsonPublicationDateFormat==='YYYY.MM.DD';
  if (spec.jsonPublicationDateFormat!==undefined&&(!dotted||spec.format!=='json-records-v1'||spec.recordsPath)) throw new Error('unsupported official JSON publication date format');
  const recordText=dotted?dottedJsonRecordText(body,value):null;
  return value.map((raw,index)=>{
    const row={evidence:recordText?.[index]??JSON.stringify(raw)};for (const [to,from] of Object.entries(keys)) row[to]=raw[from];
    if(dotted){
      if(typeof row.date!=='string'||!/^20\d{2}\.\d{2}\.\d{2}$/.test(row.date)||row.publishedAt||row.time||row.zone)throw new Error('invalid official dotted publication date');
      row.rawPublicationField=row.date;
      row.date=row.date.replaceAll('.','-');
    }
    if (!row.title) throw new Error('official JSON record lacks title/URL');
    if(spec.format==='eir-announcements-v1'&&raw.news_type==='calendar'&&['calendar','calendar1'].includes(raw.sub_type)&&/^calendar_\d+$/.test(String(row.publisherId))&&raw.type==='space'&&raw.link===''&&(!raw.attachment_count||raw.attachment_count==='0')&&(!raw.attachment||raw.attachment.length===0)) {
      row.recordKind='scheduled-event';row.recordKindEvidence={news_type:raw.news_type,sub_type:raw.sub_type,guid:row.publisherId,type:raw.type,link:raw.link};
    }
    if (!row.url) {
      if(spec.format!=='eir-announcements-v1'||raw.type!=='space'||!row.publisherId||raw.link!=='')throw new Error('official JSON record lacks title/URL');
      row.documentUnavailable=true;row.url=null; // Valid issuer text-only record, retained, never a fabricated direct link.
    } else {
      const candidate=new URL(row.url,url);
      const archivedHttp = spec.kind==='issuer' && spec.archiveLegacyHttpOutsideWindow===true && candidate.protocol==='http:';
      if((spec.format==='eir-announcements-v1' || archivedHttp) && candidate.protocol==='http:') {
        const validation=new URL(candidate);validation.protocol='https:';officialUrl(validation.href); // Validate credential safety without inventing a reachable HTTPS alias.
        row.originalUrl=candidate.href;row.url=null;row.documentUnavailable=true;
        if (archivedHttp) {
          row.archivedHttp=true;
          if (!row.publisherId) row.rowKey=digest(JSON.stringify([candidate.href,row.publishedAt||row.date,row.title]));
        }
      } else row.url=officialUrl(row.url,url);
    }
    return row;
  });
}
export function cachedReader(fetcher) {
  const cache=new Map();return async url=>{
    if (!cache.has(url)) cache.set(url,Promise.resolve().then(()=>fetcher(url)));
    return cache.get(url);
  };
}

async function readPaginatedTdnetReference(proof,symbolCode,read) {
  calendar(proof.date);
  const date=proof.date.replaceAll('-','');
  const start=officialUrl(proof.url);
  if(start!=='https://www.release.tdnet.info/inbs/I_list_001_'+date+'.html')throw new Error('official TDnet pagination requires the reviewed same-date first page');
  const scope=new RegExp('^https://www\\.release\\.tdnet\\.info/inbs/I_list_(\\d{3})_'+date+'\\.html$');
  const queue=[start],seen=new Set(queue),ordinals=new Set(),documents=[],observations=[];
  let minimumPages=1;
  while(queue.length) {
    const url=queue.shift(),response=await read(url);
    if(response.status!==200||!response.body||officialUrl(response.url||url)!==url||!response.body.includes('適時開示情報閲覧サービス'))throw new Error('same-day scan needs complete official TDnet retrieval: '+url);
    const body=response.body.replace(/<!--[\s\S]*?-->|<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
    const ordinal=Number(url.match(scope)[1]);
    if(!/class=["'][^"']*\bkjCode\b/.test(body)&&(ordinal!==1||!body.includes('該当する情報はありません')))throw new Error('official TDnet exchange response has no verified rows/empty evidence');
    const result=await publicationReferences({publicationSources:[{...proof,url,followPagination:false}]},symbolCode,async()=>({...response,body}));
    documents.push(...result.documents);
    // Hash the acquired text before stripping markup for row/navigation parsing.
    observations.push({...result.observations[0],sha256:digest(response.body)});
    ordinals.add(ordinal);
    if(ordinal===1) {
      const summary=body.match(/<div\b[^>]*class=["'][^"']*\bkaijiSum\b[^"']*["'][^>]*>([\s\S]*?)<\/div>/i);
      const range=summary&&plain(summary[1]).match(/^1\s*[～〜]\s*([\d,]+)件\s*\/\s*全([\d,]+)件$/);
      if(range)minimumPages=Math.ceil(Number(range[2].replaceAll(',',''))/Number(range[1].replaceAll(',','')));
    }
    for(const [control] of body.matchAll(/<(?:a|div|button)\b[^>]*>/gi)) {
      const href=control.match(/\bhref\s*=\s*(["'])(.*?)\1/i)?.[2];
      const button=control.match(/\bonclick\s*=\s*(["'])\s*pager(?:Link)?\(\s*(["'])([^"']+)\2\s*\)\s*;?\s*\1/i)?.[3];
      const target=button||href;
      if(!target||!/I_list_\d{3}_\d{8}\.html/.test(target))continue;
      const next=officialUrl(target,url);
      if(!scope.test(next)||Number(next.match(scope)[1])<1)throw new Error('official TDnet pagination target outside the reviewed same-date source');
      if(seen.has(next))continue;
      if(seen.size>=100)throw new Error('official TDnet pagination limit');
      seen.add(next);
      queue.push(next);
    }
  }
  if(ordinals.size<minimumPages||Math.max(...ordinals)!==ordinals.size)throw new Error('official TDnet pagination does not cover the listed same-date pages');
  return {documents,observations};
}

async function publicationReferences(spec,symbolCode,read) {
  const documents=[],observations=[];
  for(const proof of spec.publicationSources||[]) {
    if(proof.kind!=='exchange'||proof.format!=='tdnet-table-v1'||proof.symbolCode!==symbolCode)throw new Error('publication corroboration must be an official exchange adapter bound to the owned symbol');
    if(proof.followPagination!==undefined&&typeof proof.followPagination!=='boolean')throw new Error('invalid official TDnet pagination setting');
    if(proof.followPagination) {
      const result=await readPaginatedTdnetReference(proof,symbolCode,read);
      documents.push(...result.documents);
      observations.push(...result.observations);
      continue;
    }
    const url=officialUrl(proof.url),response=await read(url);
    if(response.status!==200||!response.body||new URL(response.url||url).hostname!==new URL(url).hostname||!proof.identityMarker||!response.body.includes(proof.identityMarker))throw new Error('official publication reference fetch/identity failed');
    const dateMatch=response.body.match(/<div\b[^>]*id=["']kaiji-date-1["'][^>]*>\s*(20\d{2})年(\d{1,2})月(\d{1,2})日\s*<\/div>/);
    if(!dateMatch)throw new Error('TDnet page publication date header missing');
    const date=`${dateMatch[1]}-${dateMatch[2].padStart(2,'0')}-${dateMatch[3].padStart(2,'0')}`;calendar(date);
    if(proof.date&&proof.date!==date)throw new Error('TDnet exchange coverage date mismatch: TDnet publication page date differs from reviewed reference');
    const cell=(row,name)=>row.match(new RegExp(`<td\\b[^>]*class=["'][^"']*\\b${name}\\b[^"']*["'][^>]*>([\\s\\S]*?)<\\/td>`,'i'))?.[1];
    let count=0;
    for(const [row]of response.body.matchAll(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi)) {
      if(plain(cell(row,'kjCode'))!==symbolCode+'0')continue;
      const time=plain(cell(row,'kjTime')),market=plain(cell(row,'kjPlace')),titleCell=cell(row,'kjTitle')||'',link=titleCell.match(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/i);
      if(!['東','東名','東福'].includes(market)||!link||!/^\d\d:\d\d$/.test(time))throw new Error('owned TDnet publication row is incomplete or not the reviewed domestic TSE field');
      const p=publication({date,time,zone:'Asia/Tokyo',zoneEvidenceText:`Domestic TSE kjTime; kjCode=${symbolCode}0; kjPlace=${market}`,evidenceUrl:url,evidenceText:plain(row)});
      p.zoneBasis='domestic-official';p.publicationField='kjTime';
      documents.push({url:officialUrl(link[1],url),title:plain(link[2]),publication:p,sourceUrl:url});count++;
    }
    observations.push({url,date,status:'verified',symbolCode,rowCount:count,sha256:digest(response.body),observedAt:response.observedAt});
  }
  return {documents,observations};
}
async function corroboratePublication(row,p,references,readBytes,spec={}) {
  const sameDay=references.documents.filter(r=>r.publication.dateJst===p.dateJst);
  if(p.timeJst||!row.url||!sameDay.length)return p;
  if(!readBytes)throw new Error('same-document publication verification requires actual original bytes');
  let issuer=await readBytes(row.url);
  const resolution=spec.listedPdfResolution?.find(r=>officialUrl(r.listingUrl)===row.url && r.publicationDate===p.dateJst);
  if(resolution&&issuer.status===200&&Buffer.from(issuer.body).subarray(0,5).toString()!=='%PDF-') {
    const html=Buffer.from(issuer.body).toString('utf8').replace(/<!--[\s\S]*?-->/g,''),links=[...html.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>/gi)].map(m=>officialUrl(m[1].replace(/&amp;/g,'&'),row.url)).filter(u=>u.endsWith('.pdf')&&u.includes(resolution.hrefContains));
    const unique=[...new Set(links)];if(unique.length!==1)throw new Error('reviewed original PDF link is missing or ambiguous on the official detail page');
    row.originalListingUrl=row.url;row.documentResolutionEvidence={listingUrl:row.url,listingSha256:digest(issuer.body),actualHref:unique[0]};row.url=unique[0];issuer=await readBytes(row.url);
  }
  if(issuer.status!==200||Buffer.from(issuer.body).subarray(0,5).toString()!=='%PDF-')return {...p,timeVerification:'issuer record does not yet resolve to a reachable original PDF'};
  const sha256=issuer.contentSha256||digest(issuer.body),matches=[];let identity;
  for(const reference of sameDay) {
    const result=await readBytes(reference.url);
    if(result.status!==200)throw new Error('official publication corroboration PDF unavailable');
    if(Buffer.from(result.body).subarray(0,5).toString()==='%PDF-') {
      const exchangeSha256=result.contentSha256||digest(result.body);let matched=exchangeSha256===sha256;
      if(!matched){identity??=await retainedPdfIdentity(issuer,readBytes);matched=await retainedPdfIdentity(result,readBytes)===identity;}
      if(matched)matches.push({...reference,exchangeSha256,identityMethod:exchangeSha256===sha256?'actual PDF bytes':'all PDF bytes except narrowly identified resave metadata',documentIdentitySha256:exchangeSha256===sha256?sha256:identity});
    }
  }
  if(!matches.length)return {...p,timeVerification:'no byte-identical document in the reviewed official publication references'};
  if(new Set(matches.map(m=>m.publication.earliestMs)).size!==1)throw new Error('conflicting official times for the byte-identical original');
  const match=matches[0];
  return {...match.publication,originalIssuerPublication:p,sameDocumentEvidence:{issuerUrl:row.url,exchangeUrl:match.url,exchangeTitle:match.title,sourceUrl:match.sourceUrl,sha256,exchangeSha256:match.exchangeSha256,documentIdentitySha256:match.documentIdentitySha256,matchedBy:match.identityMethod}};
}
export async function buildInventory({claimId,symbolCode,receivedAtMs,cutoffAt,sources,readBytes},read) {
  if (!claimId || !/^[0-9A-Z]{4,5}$/i.test(symbolCode||'')) throw new Error('inventory needs claimId and symbolCode');
  const cutoff=Date.parse(cutoffAt);
  if (!/T.*(?:Z|[+-]\d\d:\d\d)$/.test(cutoffAt||'') || !Number.isFinite(cutoff) || !receivedAtMs || cutoff<receivedAtMs) throw new Error('invalid inventory cutoff/receivedAt');
  if (!Array.isArray(sources) || !sources.length || !sources.some(s=>s.kind==='issuer')) throw new Error('a verified official issuer disclosure list is required');
  // Reject credential-bearing configuration before it can enter an artifact or diagnostic.
  const sourceUrl=s=>{if(s.format!=='issuer-http-tdnet-v1')return officialUrl(s.url);const u=new URL(s.url);if(s.kind!=='issuer'||u.protocol!=='http:'||!s.identityMarker||!s.publicationSources?.length)throw Error('HTTP issuer discovery requires actual issuer identity and secure official exchange originals');const secure=new URL(u);secure.protocol='https:';officialUrl(secure.href);return u.href;};
  for(const source of sources) {sourceUrl(source);for(const proof of source.publicationSources||[])officialUrl(proof.url);if(source.zoneEvidence){officialUrl(source.zoneEvidence.url);if(source.zoneEvidence.issuerBindingUrl)officialUrl(source.zoneEvidence.issuerBindingUrl);}}
  const windowStart=receivedAtMs-45*DAY,items=new Map(),observations=[];
  for (const spec of sources) {
    const observation={kind:spec.kind,url:spec.url,status:'failed'};observations.push(observation);
    try {
      if (!['issuer','exchange'].includes(spec.kind)) throw new Error('third-party list is not official issuer/exchange evidence');
      if(spec.symbolCode!==symbolCode) throw new Error('official source is not bound to the owned symbolCode');
      const url=sourceUrl(spec);
      const exchangeSupplement=spec.format==='tdnet-supplement-v1';
      const jpxPrSupplement=spec.format==='jpx-pr-publication-v1';
      if(exchangeSupplement){
        if(spec.kind!=='exchange'||spec.coverageRole!=='publication-supplement'||spec.coverageComplete!==true||new URL(url).hostname!=='www.release.tdnet.info'||!/^\/inbs\/I_list_\d{3}_\d{8}\.html$/.test(new URL(url).pathname)||spec.coverageFrom!==spec.date||spec.coverageThrough!==spec.date)throw new Error('invalid official TDnet supplemental scope');
        calendar(spec.date);if(calendar(spec.date)-9*3600000>cutoff)throw new Error('future official TDnet supplemental date');
      }else if(jpxPrSupplement){
        if (spec.kind!=='exchange'||spec.coverageRole!=='publication-supplement'||spec.coverageComplete!==true||spec.coverageFrom!==spec.date||spec.coverageThrough!==spec.date||calendar(spec.date)-9*3600000>cutoff) throw new Error('invalid JPX PR supplemental scope');
      }else if (spec.coverageComplete!==true || calendar(spec.coverageFrom)-9*3600000>windowStart || calendar(spec.coverageThrough)+15*3600000-1<cutoff) throw new Error('official list coverage does not cover 45 days before receipt through cutoff');
      const result=await read(url);
      if (result.status!==200 || !result.body) throw new Error(`official source fetch failed HTTP ${result.status||0}`);
      const finalUrl=spec.format==='issuer-http-tdnet-v1'?sourceUrl({...spec,url:result.url||url}):officialUrl(result.url||url);
      if (new URL(finalUrl).hostname!==new URL(url).hostname) throw new Error('official list redirected to a different host; reverify source identity');
      if (!spec.identityMarker || !result.body.includes(spec.identityMarker)) throw new Error('official listing identity marker missing (blocked/login/unsupported page)');
      let zoneProof=spec.zoneEvidence;
      if (zoneProof) {
        const z=await read(officialUrl(zoneProof.url));
        if (new URL(zoneProof.url).hostname!==new URL(url).hostname || z.status!==200 || !zoneProof.quote || !z.body.includes(zoneProof.quote)) throw new Error('official timezone evidence is unverified');
        const domestic=zoneProof.basis==='domestic-official' && zoneProof.zone==='Asia/Tokyo' && zoneProof.country==='JP' && zoneProof.symbolCode===symbolCode && zoneProof.publicationField && zoneProof.quote.includes(zoneProof.publicationField);
        if (zoneProof.basis==='domestic-official' && !domestic) throw new Error('domestic official timezone evidence lacks owned identity/publication field');
        if (domestic) {
          if (!zoneProof.issuerBindingUrl || !zoneProof.issuerBindingQuote || !(zoneProof.issuerBindingQuote.includes(new URL(url).hostname) || zoneProof.issuerBindingQuote.includes(symbolCode))) throw new Error('domestic official timezone requires verified issuer-to-source binding');
          const bindingUrl=officialUrl(zoneProof.issuerBindingUrl),binding=await read(bindingUrl);
          if(binding.status!==200 || new URL(binding.url||bindingUrl).hostname!==new URL(bindingUrl).hostname || !binding.body.includes(zoneProof.issuerBindingQuote)) throw new Error('domestic official issuer-to-source binding is unverified');
        }
        if (!domestic && !zoneProof.quote.includes(zoneProof.zone) && !(zoneProof.zone==='Asia/Tokyo' && /日本時間|JST|Japan Standard Time/.test(zoneProof.quote))) throw new Error('timezone quote does not establish the declared zone');
      }
      let rows,emptyProven;
      if(spec.format==='issuer-http-tdnet-v1'){
        const refs=await publicationReferences(spec,symbolCode,read);
        ({rows,emptyProven}=await buildHttpIssuerRows({body:result.body,spec,symbolCode,references:refs,readBytes,windowStartMs:windowStart,cutoffAt}));
        observation.httpDiscoveryOnly=true;observation.secureExchangeCorroboration=true;
      }
      else if(exchangeSupplement){
        const referenced=await publicationReferences({publicationSources:[{kind:'exchange',format:'tdnet-table-v1',symbolCode,url,date:spec.date,identityMarker:spec.identityMarker,followPagination:spec.followPagination}]},symbolCode,page=>page===url?result:read(page));
        if(spec.followPagination)observation.exchangePages=referenced.observations;
        rows=referenced.documents.map(d=>({url:d.url,title:d.title,date:d.publication.dateJst,time:d.publication.timeJst,zone:'Asia/Tokyo',zoneEvidenceText:d.publication.zoneEvidenceText,evidence:d.publication.evidenceText,rawPublicationField:d.publication.timeJst,exchangeMatchedPublication:{...d.publication,evidenceKind:'tdnet-publication'}}));
        emptyProven=/class=["'][^"']*\bkjCode\b/.test(result.body)||result.body.includes('該当する情報はありません');
      }
      else if(jpxPrSupplement){
        rows=await readJpxPrPublication(result.body,spec,read,readBytes,{plain,officialUrl,publicationFromRow});
        emptyProven=false;
      }
      else if (spec.format==='issuer-xml-v1') {rows=issuerXmlRows(result.body,spec,url);emptyProven=false;}
      else if (spec.format==='issuer-atom-v1') {
        rows=parseIssuerAtom(result.body,url,{plain,officialUrl});
        if (!rows.some(row=>Date.parse(row.publishedAt)<=windowStart)) throw new Error('official Atom feed ends inside the required publication window');
        emptyProven=false;
      }
      else if (spec.format==='issuer-bloglist-v1') {
        rows=parseIssuerBlogList(result.body,url,{plain,officialUrl});
        if (!rows.some(row=>calendar(row.date)+15*3600000-1<windowStart)) throw new Error('official BlogList ends inside the required publication window');
        emptyProven=false;
      }
      else if (spec.format==='ys-ir-topics-v1' || spec.format==='delta-ir-news-v1' || spec.format==='intrance-ir-archive-v1') {
        const archive = await readIssuerArchive({
          body:result.body, spec, symbolCode, url, read, windowStartMs:windowStart,
          plain, officialUrl, calendar, observedAt:result.observedAt
        });
        rows = archive.rows;
        observation.archivePages = archive.pages;
        emptyProven = false;
      }
      else if (spec.format==='geostar-library-v1') {
        const library = await readGeostarLibrary(result.body,spec,url,read,windowStart);
        rows = library.rows;
        observation.duplicateNextPage = library.nextPage;
        emptyProven = false;
      }
      else if (spec.format==='nakabayashi-ir-archive-v1') {
        ({rows,emptyProven}=parseNakabayashiIrArchive(result.body,spec,url,{plain,officialUrl}));
      }
      else if (spec.format==='beat-releases-v1') {
        ({rows,emptyProven}=await readBeatReleases(result.body,spec,url,read));
      }
      else if (spec.format==='xj-json-v1') { rows=xjJsonRows(result.body,url); emptyProven=true; }
      else if (spec.format==='xj-table-v1') ({rows,emptyProven}=xjRows(result.body,spec,url));
      else if (spec.format==='html-records-v1') ({rows,emptyProven}=htmlRows(result.body,spec,url));
      else if (spec.format==='softbank-list-v1') {rows=parseSoftBankList(result.body,spec,url);emptyProven=true;}
      else if(['json-records-v1','eir-announcements-v1'].includes(spec.format)) {rows=jsonRows(result.body,spec,url);emptyProven=true;}
      else throw new Error('unsupported official-list format; never treat parse failure as zero');
      if (!rows.length && !emptyProven) throw new Error('zero rows without explicit official empty evidence');
      if(spec.rowIdentity!==undefined&&spec.rowIdentity!=='publication-url-title')throw new Error('unsupported official publication row identity');
      if(spec.rowIdentity==='publication-url-title')for(const row of rows)if(!row.publisherId&&!row.rowKey&&row.url)row.rowKey=digest(JSON.stringify([row.url,row.date||row.publishedAt,plain(row.title)]));
      const references=await publicationReferences(spec,symbolCode,read);
      if(references.observations.length)observation.publicationReferences=references.observations;
      let included=0;
      if((spec.issuerIrDateOnlyPolicies||[]).some(p=>!['issuer-ir-library-v1','issuer-ir-record-v1'].includes(p.format)))throw new Error('unsupported company IR classification policy');
      const libraryPolicies=(spec.issuerIrDateOnlyPolicies||[]).filter(p=>p.format==='issuer-ir-library-v1');
      const librarySpec={...spec,issuerIrDateOnlyPolicies:libraryPolicies.length?libraryPolicies:undefined};
      const libraryRows=await expandIssuerIrMaterials(rows,librarySpec,symbolCode,read,readBytes);
      const classifiedRows=await expandIssuerIrRecords(libraryRows,spec,symbolCode,read,readBytes,{publicationFromRow,corroboratePublication,publicationReferences,officialUrl,digest,plain,calendar});
      for(const row of classifiedRows) {
        if(row.publisherId!==undefined&&row.publisherId!==null && typeof row.publisherId!=='string' && !(typeof row.publisherId==='number'&&Number.isSafeInteger(row.publisherId))) throw new Error('official publisher ID is not a stable string/safe integer');
        // HTTP is a discovery catalogue, never the publication-clock proof.
        // Current documents already carry the exact HTTPS TDnet publication;
        // old/unavailable catalogue rows remain explicitly unpublishable.
        let original=spec.format==='issuer-http-tdnet-v1'?(row.exchangeMatchedPublication||{dateJst:row.date,timeJst:null,precision:'date',earliestMs:calendar(row.date)-9*3600000,latestMs:calendar(row.date)+15*3600000-1,evidenceKind:'http-discovery-only',discoveryEvidence:row.discoveryEvidence}):publicationFromRow(row,url,zoneProof);
        const articleRule=spec.officialArticlePublications?.find(rule=>officialUrl(rule.url)===row.url);
        if(articleRule){
          if(symbolCode!=='9434'||articleRule.format!=='softbank-news-article-v1'||!readBytes)throw new Error('unreviewed official article publication schema');
          const article=await readBytes(row.url);if(article.status!==200||officialUrl(article.url||row.url)!==row.url)throw new Error('official publication article unavailable or redirected');
          const parsed=canonicalSoftBankArticle(Buffer.from(article.body).toString('utf8'),row);
          const precise=publicationFromRow({title:row.title,publishedAt:parsed.publication.publishedAt,evidence:parsed.publication.evidence},row.url);
          if(precise.dateJst!==original.dateJst)throw new Error('official article publication/list date conflict');
          original={...precise,originalIssuerPublication:original,rawPublicationField:parsed.publication.publishedAt,publicationField:parsed.publication.publicationField,explicitTimezone:true};
          row.contentFormat='official-article-page-v1';row.canonicalContentSha256=parsed.sha256;
        }
        const videoRule=spec.officialVideoPublications?.find(rule=>officialUrl(rule.url)===row.url);
        if(videoRule) {
          if(!readBytes)throw new Error('official video metadata requires actual page retrieval');const video=await readBytes(row.url);if(video.status!==200)throw new Error('official video page unavailable');
          const binding=videoIssuerBinding(videoRule,spec,symbolCode);
          const parsed=officialVideoPage(Buffer.from(video.body).toString('utf8'),row.url,symbolCode,videoRule.expectedChannelName,binding);
          const precise=publicationFromRow({title:row.title,publishedAt:parsed.content.publishedAt,evidence:`playerMicroformatRenderer.publishDate=${parsed.content.publishedAt}; videoId=${parsed.content.videoId}`},row.url);
          if(precise.dateJst!==original.dateJst)throw new Error('official video JST publication date differs from issuer listing');
          original={...precise,originalIssuerPublication:original,rawPublicationField:parsed.content.publishedAt,publicationField:'playerMicroformatRenderer.publishDate',explicitTimezone:true};row.contentFormat='official-video-page-v1';row.canonicalContentSha256=parsed.sha256;row.videoMetadata=parsed.content;row.expectedChannelName=videoRule.expectedChannelName;
        }
        if (row.archivedHttp && original.latestMs>=windowStart) throw new Error('unavailable HTTP original is inside the required official coverage window');
        let p=await corroboratePublication(row,original,references,readBytes,spec);
        if(row.exchangeMatchedPublication)p=row.exchangeMatchedPublication;
        else if(row.issuerIrEvidence&&!p.timeJst)p={...p,evidenceKind:'issuer-ir-date-only',issuerIrEvidence:row.issuerIrEvidence};
        const id=row.publisherId ? `official:${new URL(url).hostname}:${symbolCode}:${row.publisherId}` : row.rowKey ? `official-row:${new URL(url).hostname}:${symbolCode}:${row.rowKey}` : `official-url:${row.url}`;
        const item={id,url:row.url,urls:row.url?[row.url]:[],title:plain(row.title),symbolCode,publication:p,sourceUrl:url,sourceKind:spec.kind,...(row.contentFormat?{contentFormat:row.contentFormat,canonicalContentSha256:row.canonicalContentSha256,videoMetadata:row.videoMetadata,expectedChannelName:row.expectedChannelName}:{}),...(row.documentResolutionEvidence?{originalListingUrl:row.originalListingUrl,documentResolutionEvidence:row.documentResolutionEvidence}:{}),...(row.documentUnavailable?{documentUnavailable:true}:{}),...(row.originalUrl?{originalUrl:row.originalUrl}:{}),...(row.recordKind?{recordKind:row.recordKind,recordKindEvidence:row.recordKindEvidence}:{})};
        // A date-only release has no fabricated midnight publication time. Same-day
        // inclusion needs proof it was actually visible by this observation cutoff.
        if (p.earliestMs>cutoff) continue;
        if (p.precision==='date' && p.latestMs>cutoff && (!result.observedAt || Date.parse(result.observedAt)>cutoff || !Number.isFinite(Date.parse(result.observedAt)))) throw new Error('date-only disclosure has no verified visibility by cutoff; verify or defer');
        const prior=items.get(id);
        if (prior && (prior.title!==item.title || prior.publication.dateJst!==p.dateJst || (prior.publication.timeJst && p.timeJst && prior.publication.timeJst!==p.timeJst))) throw new Error('conflicting official publication/title for the same stable ID');
        if(prior) {
          if(!prior.urls.includes(row.url))prior.urls.push(row.url);
          // A second official route may establish the missing time only for the
          // identical stable document identity/date/title. Preserve both proofs.
          if (!prior.publication.timeJst && p.timeJst) { prior.publicationAlternatives ||= []; prior.publicationAlternatives.push(prior.publication); prior.publication=p; }
        } else items.set(id,item);
        included++;
      }
      observation.status=rows.length?'ok':'empty';observation.rowCount=rows.length;observation.observedCount=included;observation.sha256=digest(result.body);observation.transport=result.transport||'fetch';
    } catch(error) {observation.reason=error.message;}
  }
  return {version:1,claimId,symbolCode,receivedAtMs,cutoffAt,windowStartMs:windowStart,sources,observations,
    status:observations.every(o=>['ok','empty'].includes(o.status))?'verified':'unverified',items:[...items.values()]};
}
function fields(report,name) {return String((report.fields||[]).find(f=>f.name===name)?.value||'');}
export function requiredDisclosureItems(inventory, { receivedAtMs, classify }) {
  const recent = inventory.items.filter(item => !['scheduled-event','publication-index'].includes(item.recordKind)
    && item.publication.latestMs >= receivedAtMs - 45 * DAY && classify(item.title) === 'fundamental')
    .sort((a, b) => b.publication.earliestMs - a.publication.earliestMs);
  const newest = recent[0];
  if (!newest) return [];
  return recent.filter(item => item.publication.dateJst === newest.publication.dateJst
    && (item.publication.timeJst === newest.publication.timeJst || !item.publication.timeJst || !newest.publication.timeJst));
}
export function validateReflection(report,inventory,{claimId,receivedAtMs,classify}) {
  if(inventory.status!=='verified') throw new Error('official inventory unverified: '+inventory.observations.filter(s=>s.status==='failed').map(s=>s.reason).join('; '));
  if(inventory.claimId!==claimId || inventory.symbolCode!==String(report.symbolCode) || inventory.receivedAtMs>receivedAtMs) throw new Error('official inventory owner/symbol/receipt mismatch');
  const evidence=report.disclosureEvidence;
  if(!Array.isArray(evidence)) throw new Error('report needs disclosureEvidence ID-to-analysis mapping, even for a verified zero inventory');
  const must=requiredDisclosureItems(inventory,{receivedAtMs,classify});
  const byId=new Map(inventory.items.map(i=>[i.id,i])); const selected=new Set();
  const labels=new Map();
  for(const e of evidence) {
    const item=byId.get(e.id);if(!item || selected.has(e.id))throw new Error('unknown/duplicate official disclosure ID in analysis mapping');selected.add(e.id);
    if(!Array.isArray(e.reflections)||!e.reflections.length)throw new Error(`official disclosure ${item.id} has no analytical reflection`);
    for(const r of e.reflections) {
      if(!['足元材料','ファンダ要点','注意点'].includes(r.field) || typeof r.text!=='string' || r.text.trim().length<12 || !fields(report,r.field).includes(r.text))throw new Error(`official disclosure ${item.id} reflection missing from analytical field`);
    }
    if(e.contentRead!==true || !e.contentSha256 || !/^[a-f0-9]{64}$/.test(e.contentSha256) || !e.contentEvidence?.trim())throw new Error(`official disclosure ${item.id} needs content-read evidence/hash`);
  }
  const missing=must.filter(i=>!selected.has(i.id));if(missing.length)throw new Error('missing important official disclosure IDs: '+missing.map(i=>i.id).join(', '));
  for(const index of inventory.items.filter(i=>i.recordKind==='publication-index'&&i.publication.latestMs>=receivedAtMs-45*DAY)){
    if(index.recordKindEvidence?.sourceSchema!=='softbank-list-v1'||!inventory.items.some(i=>!['scheduled-event','publication-index'].includes(i.recordKind)&&i.publication.dateJst===index.publication.dateJst&&classify(i.title)==='fundamental'&&selected.has(i.id)))throw new Error('financial library publication index lacks substantive same-date document evidence');
  }
  const linkText=fields(report,'開示リンク');const links=[...linkText.matchAll(DISCLOSURE_LINK)];
  for(const [,label,url] of links) {
    const normalized=officialUrl(url),item=inventory.items.find(i=>i.urls.includes(normalized));
    if(!item || !selected.has(item.id))throw new Error('disclosure link lacks matching official ID and analytical evidence');
    if(label.normalize('NFKC')!==publicationLabel(item).normalize('NFKC'))throw new Error(`official publication label mismatch for ${item.id}; expected ${publicationLabel(item)}`);
    labels.set(normalized,publicationLabel(item));
  }
  if(report.disclosureLinkPolicy!==undefined&&report.disclosureLinkPolicy!=='key-materials-v1')throw new Error('unsupported public disclosure link policy');
  if(report.disclosureLinkPolicy==='key-materials-v1'){if(!links.length||links.length>4)throw new Error('key material links require one to four verified primary links');}
  else for(const id of selected)if(!links.some(([,label,url])=>byId.get(id).urls.includes(officialUrl(url))))throw new Error(`official disclosure ${id} is not linked in report`);
  for(const e of report.supplementalBodyEvidence||[]){
    const contentUrl=officialUrl(e.contentUrl),sourceUrl=officialUrl(e.sourceUrl);
    if(e.publicationClaim!==false||e.contentRead!==true||!/^[a-f0-9]{64}$/.test(e.contentSha256||'')||!e.contentEvidence?.trim()||new URL(contentUrl).hostname!==new URL(sourceUrl).hostname||!inventory.sources.some(s=>s.url===sourceUrl)||!Array.isArray(e.reflections)||!e.reflections.length)throw new Error('unverified supplemental official body evidence');
    for(const r of e.reflections)if(!['足元材料','ファンダ要点','注意点'].includes(r.field)||typeof r.text!=='string'||r.text.trim().length<12||!fields(report,r.field).includes(r.text))throw new Error('supplemental body reflection missing from analytical field');
  }
  return {labels,requiredIds:must.map(i=>i.id),selectedIds:[...selected]};
}

function requireMatchingEvidenceBytes(response, expectedSha, prefix, field, index) {
  const observedSha = response.status === 200 ? response.contentSha256 || digest(response.body) : null;
  if (response.status === 200 && observedSha === expectedSha) return;

  // Evidence IDs can contain full URLs. The report field and index identify the original without logging them.
  const shortSha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) ? value.slice(0, 12) : 'unavailable';
  const status = Number.isInteger(response.status) && response.status >= 100 && response.status <= 599 ? response.status : 'unknown';
  const cause = response.status === 200 ? 'sha256-mismatch' : 'http-status';
  throw new Error(`${prefix} for ${field}[${index}]: ${cause}, HTTP ${status}, expectedSha256=${shortSha(expectedSha)}, observedSha256=${shortSha(observedSha)}`);
}

function avixArticleBytes(body, url, postId) {
  // latin1 is a one-to-one view of raw bytes. Apart from the 13 hex digits every byte remains significant.
  const html = Buffer.from(body).toString('latin1');
  const canonicals = html.match(/<link\b[^>]*\brel=["']canonical["'][^>]*>/gi) || [];
  const bodies = html.match(/<body\b[^>]*>/gi) || [];
  const bodyClasses = bodies[0]?.match(/\bclass="([^"]+)"/)?.[1].split(/\s+/) || [];
  if (canonicals.length !== 1 || canonicals[0].match(/\bhref="([^"]+)"/)?.[1] !== url ||
      bodies.length !== 1 || !bodyClasses.includes('single-news') || !bodyClasses.includes('postid-' + postId)) {
    throw new Error('supplemental official article identity differs');
  }
  const styles = [...html.matchAll(/<style\b[^>]*>[\s\S]*?<\/style>/gi)]
    .filter(([tag]) => tag.startsWith('<style id="wp-block-library-inline-css">'));
  const marker = /\/\*wp_block_styles_on_demand_placeholder:([a-f0-9]{13})\*\//g;
  if (styles.length !== 1 || (html.match(/wp_block_styles_on_demand_placeholder:/g) || []).length !== 1 ||
      !styles[0][0].match(marker)) {
    throw new Error('supplemental official article WordPress style marker missing or ambiguous');
  }
  return html.replace(marker, '/*wp_block_styles_on_demand_placeholder:_____________*/');
}

function verifyAvixSupplementalBody(evidence, inventory, response, readBytes) {
  const url = officialUrl(evidence.contentUrl);
  const postId = /^https:\/\/avix\.co\.jp\/news\/(?:notice|product)\/([1-9]\d*)\/$/.exec(url)?.[1];
  if (inventory.symbolCode !== '7836' || !postId || response.url !== url ||
      !/^text\/html(?:\s*;|$)/i.test(response.contentType || '') ||
      !inventory.sources?.some(source => source.kind === 'issuer' && source.url === evidence.sourceUrl &&
        new URL(source.url).origin === 'https://avix.co.jp')) {
    throw new Error('supplemental official article issuer, URL or format differs');
  }
  const original = readBytes.getRetainedBody?.(evidence.contentSha256);
  if (!original) throw new Error('supplemental official article original raw body unavailable');
  if (avixArticleBytes(original, url, postId) !== avixArticleBytes(response.body, url, postId)) {
    throw new Error('supplemental official body changed/unavailable: article differs outside its WordPress style placeholder');
  }
}

function pixtaArticleBytes(body, url) {
  const html = Buffer.from(body).toString('latin1');
  const identity = [...html.matchAll(/<meta name="twitter:url" content="([^"]+)"\s*\/?>/g)];
  const token = /(<meta name="csrf-token" content=")[A-Za-z0-9+/_=-]{88}("\s*\/?>)/g;
  if (identity.length !== 1 || identity[0][1] !== url ||
      [...html.matchAll(/name="csrf-token"/g)].length !== 1 ||
      [...html.matchAll(token)].length !== 1) throw Error('Pixta official article identity or single Rails token marker differs');
  return html.replace(token, '$1[per-response token]$2');
}

function verifyPixtaArticleBody(evidence, item, inventory, response, readBytes, url) {
  if (inventory.symbolCode !== '3416' || item.sourceKind !== 'issuer' || item.sourceUrl !== 'https://pixta.co.jp/news' ||
      !/^https:\/\/pixta\.co\.jp\/news\/[1-9]\d*$/.test(url) || response.url !== url || response.status !== 200 ||
      !/^text\/html(?:\s*;|$)/i.test(response.contentType || '')) throw Error('Pixta official article response or issuer scope differs');
  const original = readBytes.getRetainedBody?.(evidence.contentSha256);
  if (!original || pixtaArticleBytes(original,url) !== pixtaArticleBytes(response.body,url)) {
    throw Error('Pixta official article differs outside its per-response Rails token');
  }
  if (!plain(Buffer.from(response.body).toString('utf8')).includes(plain(evidence.contentEvidence))) {
    throw Error('Pixta official article quotation missing');
  }
}

export async function validateContentEvidence(report,inventory,readBytes) {
  for (const [index, e] of (report.supplementalBodyEvidence || []).entries()) {
    const r = await readBytes(officialUrl(e.contentUrl));
    if (r.status === 200 && e.contentFormat === 'avix-wordpress-style-placeholder-v1') {
      verifyAvixSupplementalBody(e, inventory, r, readBytes);
    } else {
      requireMatchingEvidenceBytes(r, e.contentSha256, 'supplemental official body changed/unavailable', 'supplementalBodyEvidence', index);
    }
    if (!/^%PDF-/.test(Buffer.from(r.body).subarray(0, 5).toString()) && !plain(Buffer.from(r.body).toString('utf8')).includes(plain(e.contentEvidence))) throw new Error('supplemental official body quote missing');
  }
  for(const [index,e] of (report.disclosureEvidence||[]).entries()) {
    const item=inventory.items.find(i=>i.id===e.id);if(!item)throw new Error('unknown content evidence ID');
    const contentUrl=officialUrl(e.contentUrl||item.url);if(!item.urls.includes(contentUrl))throw new Error('content URL does not belong to the official disclosure ID');
    const result=await readBytes(contentUrl);
    if(item.contentFormat==='official-article-page-v1'){
      if(result.status!==200||e.contentFormat!==item.contentFormat)throw new Error('official article content scope/availability mismatch');
      const parsed=canonicalSoftBankArticle(Buffer.from(result.body).toString('utf8'),{url:contentUrl,title:item.title,date:item.publication.dateJst});
      if(e.contentScope!==parsed.content.scope||parsed.sha256!==e.contentSha256||parsed.sha256!==item.canonicalContentSha256||!plain(parsed.content.mainHtml).includes(plain(e.contentEvidence)))throw new Error('official article stable body changed or evidence quote missing');
      continue;
    }
    if(item.contentFormat==='official-video-page-v1') {
      if(result.status!==200||e.contentFormat!==item.contentFormat||e.contentScope!=='official video page title, description and publication metadata')throw new Error('official video page evidence scope/availability mismatch');
      const parsed=officialVideoPage(Buffer.from(result.body).toString('utf8'),contentUrl,inventory.symbolCode,item.expectedChannelName,item.videoMetadata?.issuerIrBinding);
      if(parsed.sha256!==e.contentSha256||parsed.sha256!==item.canonicalContentSha256||!JSON.stringify(parsed.content).includes(e.contentEvidence))throw new Error('official video page stable content changed or evidence quote missing');
      continue;
    }
    if(e.contentFormat==='pixta-rails-csrf-v1') {
      verifyPixtaArticleBody(e,item,inventory,result,readBytes,contentUrl);
      continue;
    }
    requireMatchingEvidenceBytes(result, e.contentSha256, 'official disclosure content changed/unavailable', 'disclosureEvidence', index);
    const retained={contentSha256:e.contentSha256,validatorVersion:'content-reflection-20261116-v2',key:digest(JSON.stringify([contentUrl,e.contentEvidence,e.contentFormat||null,e.contentScope||null]))};
    if(result.contentSha256&&readBytes.getVerification?.(retained)?.matched===true)continue;
    // Text/HTML quotes are mechanically checked. PDF reading remains the existing evidence-grounded research duty.
    if(!/^%PDF-/.test(Buffer.from(result.body).subarray(0,5).toString()) && !plain(Buffer.from(result.body).toString('utf8')).includes(plain(e.contentEvidence)))throw new Error(`official content evidence quote not found for ${item.id}`);
    if(result.contentSha256&&readBytes.recordVerification)readBytes.recordVerification({...retained,value:{matched:true,scope:'byte identity and literal HTML quotation; semantic PDF reading is separate'}});
  }
}
