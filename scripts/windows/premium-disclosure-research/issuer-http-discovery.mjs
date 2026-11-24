// ISOLATED REVIEW PROPOSAL. No HTTP, CLI, state or delivery operations.
// Does not alter officialUrl() or allow HTTP disclosure links for posting.
import crypto from 'node:crypto';
import path from 'node:path';
import {compareHttpDiscoveryCanonicalSecureOriginal} from './http-pdf-content-review.mjs';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const plain=s=>s.replace(/<br\s*\/?\s*>/gi,' ').replace(/<[^>]*>/g,' ').replace(/&(?:nbsp|ensp);/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim();
const titleKey=s=>plain(s).normalize('NFKC').replace(/。$/,'').replace(/\s+/g,'');
function url(value,protocol){const u=new URL(value);if(u.protocol!==protocol||u.username||u.password||u.hash)throw Error('unsafe public source URL');return u;}
export function parsePublicIssuerDiscovery({body,sourceUrl,ownedSymbol,identityMarker,recordId='irNewsArea'}){
 const source=url(sourceUrl,'http:');if(!ownedSymbol||!identityMarker||!body.includes(identityMarker)||!/^[\w-]+$/.test(recordId))throw Error('issuer discovery identity missing');
 if(/rel=["']next["']|data-has-more=["']true["']/i.test(body))throw Error('discovery pagination incomplete');
 const opening=[...body.matchAll(new RegExp(`<ul\\b[^>]*\\bid=["']${recordId}["'][^>]*>`,'gi'))];
 const blocks=[...body.matchAll(new RegExp(`<ul\\b[^>]*\\bid=["']${recordId}["'][^>]*>([\\s\\S]*?)<\\/ul>`,'gi'))];
 if(!blocks.length||blocks.length!==opening.length)throw Error('incomplete issuer discovery inventory');
 return blocks.map(([raw])=>{
  const dates=[...raw.matchAll(/<dt\b[^>]*>\s*(20\d\d)\/(\d\d)\/(\d\d)\s*<\/dt>/gi)];
  if(dates.length!==1)throw Error('actual publication dt missing or ambiguous');
  const date=`${dates[0][1]}-${dates[0][2]}-${dates[0][3]}`;if(new Date(date+'T00:00:00Z').toISOString().slice(0,10)!==date)throw Error('invalid publication calendar date');
  const anchors=[...raw.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)];
  if(anchors.length>1)throw Error('ambiguous discovery document anchors');
  const title=plain(anchors[0]?.[2]||raw.match(/<dd\b[^>]*>([\s\S]*?)<\/dd>/i)?.[1]||'');if(!title)throw Error('discovery title missing');
  const originalUrl=anchors[0]?new URL(anchors[0][1],source).href:null;
  if(originalUrl){const u=url(originalUrl,'http:');if(u.hostname!==source.hostname)throw Error('unreviewed external discovery URL');}
  const scheduled=!originalUrl&&/アナリスト向け決算説明会のご案内/.test(title);
  return {symbolCode:ownedSymbol,date,title,url:null,originalUrl,documentUnavailable:!scheduled,recordKind:scheduled?'scheduled-event':undefined,recordKindEvidence:scheduled?{originalText:title}:undefined,rowKey:sha(JSON.stringify([sourceUrl,date,title,originalUrl])),discoveryEvidence:{sourceUrl,bodySha256:sha(body),publicationField:'dt',rawPublicationField:dates[0][0],transport:'http-untrusted-discovery-only'}};
 });
}
export function corroborateDiscoveryRows({rows,windowStartDate,cutoffDate,issuerOriginals,exchangeDocuments}){
 return rows.map(row=>{
  if(row.date<windowStartDate||row.date>cutoffDate||row.recordKind==='scheduled-event')return row;
  if(!row.originalUrl)throw Error('material-window issuer record lacks usable original');
  const issuer=issuerOriginals.get(row.originalUrl);if(!issuer||issuer.status!==200||issuer.url!==row.originalUrl||!Buffer.isBuffer(issuer.body)||issuer.body.subarray(0,5).toString()!=='%PDF-')throw Error('actual issuer original unavailable for same-document check');
  const issuerSha=sha(issuer.body);
  const matches=exchangeDocuments.filter(d=>{
   const u=url(d.url,'https:');if(!['www.release.tdnet.info','www2.jpx.co.jp'].includes(u.hostname))throw Error('unreviewed secure exchange host');
   if(d.symbolCode!==row.symbolCode||d.date!==row.date||titleKey(d.title)!==titleKey(row.title))return false;
   if(d.publicationField!=='kjTime'||d.place!=='東'||!/^\d\d:\d\d$/.test(d.time)||!Buffer.isBuffer(d.body)||d.body.subarray(0,5).toString()!=='%PDF-')throw Error('actual exchange publication/PDF evidence missing');
   if(url(d.sourceUrl,'https:').hostname!=='www.release.tdnet.info')throw Error('unreviewed exchange publication source');
   return sha(d.body)===issuerSha;
  });
  if(!matches.length)throw Error('no byte-identical secure exchange document for issuer record');
  if(new Set(matches.map(d=>d.time)).size!==1)throw Error('conflicting exact-document publication clocks');
  const d=matches[0];return {...row,url:d.url,documentUnavailable:false,date:d.date,time:d.time,zone:'Asia/Tokyo',evidence:`${d.date} ${d.time} JST; ${d.sourceUrl} kjTime; owned ${d.symbolCode} 東`,documentResolutionEvidence:{...row.discoveryEvidence,originalIssuerUrl:row.originalUrl,canonicalSecureUrl:d.url,issuerRawSha256:issuerSha,exchangeRawSha256:sha(d.body),matchedBy:'actual raw PDF bytes',exchangePublicationField:'kjTime',exchangePublicationSource:d.sourceUrl}};
 });
}
// Intended buildInventory branch: call AFTER its ordinary publicationReferences()
// parsed/validated the complete reviewed HTTPS TDnet pages. HTTP source text is
// discovery only; no row receives a clock from HTTP, PDF metadata or a title.
export async function buildHttpIssuerRows({body,spec,symbolCode,references,readBytes,windowStartMs,cutoffAt}){
 if(spec.symbolCode!==symbolCode||typeof readBytes?.httpDiscovery!=='function')throw Error('owned HTTP discovery reader missing');
 const rows=parsePublicIssuerDiscovery({body,sourceUrl:spec.url,ownedSymbol:symbolCode,identityMarker:spec.identityMarker,recordId:spec.recordId||'irNewsArea'});
 const windowStartDate=new Date(windowStartMs+9*3600000).toISOString().slice(0,10),cutoffDate=new Date(Date.parse(cutoffAt)+9*3600000).toISOString().slice(0,10);
 for(const row of rows){
  if(row.date<windowStartDate||row.date>cutoffDate||row.recordKind==='scheduled-event')continue;
  if(!row.originalUrl)throw Error('material-window issuer original link missing');
  const issuer=await readBytes.httpDiscovery(row.originalUrl);
  if(issuer.status!==200||issuer.url!==row.originalUrl||Buffer.from(issuer.body||[]).subarray(0,5).toString()!=='%PDF-')throw Error('actual HTTP issuer PDF unavailable for byte comparison');
  const issuerSha=sha(issuer.body),matches=[];
  for(const reference of references.documents.filter(r=>r.publication.dateJst===row.date&&titleKey(r.title)===titleKey(row.title))){
   const u=url(reference.url,'https:');if(!['www.release.tdnet.info','www2.jpx.co.jp'].includes(u.hostname))throw Error('unreviewed HTTPS exchange original');
   if(reference.publication.zoneBasis!=='domestic-official'||reference.publication.publicationField!=='kjTime'||!reference.publication.timeJst||url(reference.sourceUrl,'https:').hostname!=='www.release.tdnet.info')throw Error('ordinary TDnet publication evidence missing');
   const exchange=await readBytes(reference.url);if(exchange.status!==200||Buffer.from(exchange.body||[]).subarray(0,5).toString()!=='%PDF-')throw Error('secure exchange original unavailable');
   const exchangeSha=sha(exchange.body);
   if(exchangeSha===issuerSha)matches.push({...reference,identityMethod:'actual raw PDF bytes',issuerSha256:issuerSha,exchangeSha256:exchangeSha});
   else {
    const review=spec.sameDocumentContentReviews?.find(r=>r.issuerSha256===issuerSha&&r.exchangeSha256===exchangeSha&&r.issuerUrl===row.originalUrl&&r.canonicalSecureUrl===reference.url);
    if(review&&readBytes.cacheDirectory){
     const key={contentSha256:issuerSha,validatorVersion:'reviewed-http-content-pair-20261117-v1',key:sha(JSON.stringify({exchangeSha,review}))};
     let proof=readBytes.getVerification?.(key);
     if(!proof){proof=await compareHttpDiscoveryCanonicalSecureOriginal({scope:'http-discovery-canonical-secure-original-v1',issuerUrl:row.originalUrl,secureUrl:reference.url,issuerFile:path.join(readBytes.cacheDirectory,'bodies',issuerSha+'.bin'),secureFile:path.join(readBytes.cacheDirectory,'bodies',exchangeSha+'.bin'),symbolCode,issuerDate:row.date,issuerTitle:row.title.replace(/。$/,''),reference:{...reference,symbolCode,date:reference.publication.dateJst,time:reference.publication.timeJst,place:reference.publication.zoneEvidenceText?.match(/kjPlace=(\S+)/)?.[1],publicationField:reference.publication.publicationField},reviewedContentReview:review});readBytes.recordVerification?.({...key,value:proof});}
     matches.push({...reference,identityMethod:'complete legal page text and all-page visual review; layout variant, not raw byte identity',issuerSha256:issuerSha,exchangeSha256:exchangeSha,reviewedContentProof:proof});
    }
   }
  }
  if(!matches.length)throw Error('actual HTTP issuer original does not match secure TDnet bytes');
  if(new Set(matches.map(r=>r.publication.earliestMs)).size!==1)throw Error('conflicting secure same-document publication times');
  const reference=matches[0],proof={issuerUrl:row.originalUrl,exchangeUrl:reference.url,sourceUrl:reference.sourceUrl,issuerSha256:reference.issuerSha256,exchangeSha256:reference.exchangeSha256,matchedBy:reference.identityMethod,...(reference.reviewedContentProof?{reviewedContentProof:reference.reviewedContentProof}:{})};
  row.url=reference.url;row.documentUnavailable=false;row.exchangeMatchedPublication={...reference.publication,originalIssuerPublication:{dateJst:row.date,precision:'date',sourceUrl:spec.url,publicationField:'dt'},sameDocumentEvidence:proof};
  row.documentResolutionEvidence={...row.discoveryEvidence,...proof};row.evidence=row.discoveryEvidence.rawPublicationField;
 }
 const required=references.documents.filter(r=>r.publication.dateJst>=windowStartDate&&r.publication.dateJst<=cutoffDate);
 if(required.some(r=>!rows.some(row=>row.url===r.url)))throw Error('official HTTPS exchange material omitted from discovery inventory');
 return {rows,emptyProven:false};
}
