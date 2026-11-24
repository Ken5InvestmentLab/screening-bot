// ISOLATED proposal. No HTTP/state/post. Never import into general pdfDocumentIdentity.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {execFile} from 'node:child_process';
import {withPdfResource} from './research-document.mjs';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const exactTitle=s=>String(s).normalize('NFKC').replace(/\s+/gu,'');
function publicUrl(value,protocol){const u=new URL(value);if(u.protocol!==protocol||u.username||u.password||u.hash)throw Error('unsafe comparison source');return u;}

export async function compareHttpDiscoveryCanonicalSecureOriginal({
  scope,issuerUrl,secureUrl,issuerFile,secureFile,symbolCode,
  issuerDate,issuerTitle,reference,reviewedContentReview,
},{pythonPath=path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),helperPath=path.join(import.meta.dirname,'http-pdf-content-compare.py'),execFileImpl=execFile}={}){
  if(scope!=='http-discovery-canonical-secure-original-v1')throw Error('HTTP discovery scope required');
  publicUrl(issuerUrl,'http:');
  const secure=publicUrl(secureUrl,'https:');
  if(!['www.release.tdnet.info','www2.jpx.co.jp'].includes(secure.hostname))throw Error('canonical exchange host required');
  if(!/^\d{4}$/.test(symbolCode)||reference?.symbolCode!==symbolCode||reference.url!==secureUrl||
     reference.date!==issuerDate||exactTitle(reference.title)!==exactTitle(issuerTitle)||
     reference.publicationField!=='kjTime'||reference.place!=='東'||!/^\d{2}:\d{2}$/.test(reference.time)||
     publicUrl(reference.sourceUrl,'https:').hostname!=='www.release.tdnet.info')throw Error('exact owned TDnet publication reference required');
  const actualTime=reference.time.split(':').map(Number);
  if(actualTime[0]>23||actualTime[1]>59||!/^20\d{2}-\d{2}-\d{2}$/.test(issuerDate)||new Date(issuerDate+'T00:00:00Z').toISOString().slice(0,10)!==issuerDate)throw Error('invalid real publication calendar/time');
  const issuerRaw=fs.readFileSync(issuerFile),secureRaw=fs.readFileSync(secureFile);
  if(!issuerRaw.subarray(0,5).equals(Buffer.from('%PDF-'))||!secureRaw.subarray(0,5).equals(Buffer.from('%PDF-')))throw Error('PDF originals required');
  const issuerSha256=sha(issuerRaw),secureSha256=sha(secureRaw);
  const output=await withPdfResource(()=>new Promise((resolve,reject)=>execFileImpl(pythonPath,[helperPath,path.resolve(issuerFile),path.resolve(secureFile)],{windowsHide:true,timeout:90000,maxBuffer:2*1024*1024,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(error,stdout)=>error?reject(Error('offline PDF comparison unavailable')):resolve(stdout))));
  const result=JSON.parse(output);
  if(result.error||result.method!=='layout-reencoded-complete-page-text-v1'||result.publicationInferred!==false||!result.completePageTextEqual||!result.pageCountEqual||result.issuer?.rawSha256!==issuerSha256||result.secure?.rawSha256!==secureSha256)throw Error('complete PDF page text comparison failed');
  // Text cannot establish unchanged graphics, vector drawings or overlays. Every
  // differing-byte fallback therefore requires all-page visual review bound to
  // the exact two raw hashes AND current complete text/page count.
  if(result.notRawByteIdentity&&(reviewedContentReview?.issuerSha256!==issuerSha256||reviewedContentReview?.exchangeSha256!==secureSha256||reviewedContentReview?.fullTextSha256!==result.fullTextSha256||reviewedContentReview?.pageCount!==result.issuer.pages.length||reviewedContentReview?.reviewedAllPages!==true||reviewedContentReview?.activeContentAbsent!==true||reviewedContentReview?.visualConclusion!=='same-legal-content-layout-variant'||typeof reviewedContentReview?.evidence!=='string'||reviewedContentReview.evidence.trim().length<30))throw Error('layout variant needs all-page reviewed exact-hash pair evidence');
  return {scope,matchedBy:result.method,notRawByteIdentity:result.notRawByteIdentity,
    issuerUrl,canonicalSecureUrl:secureUrl,issuerSha256,secureSha256,
    pageComparison:result,reviewedContentReview:result.notRawByteIdentity?reviewedContentReview:null,
    publicationInferred:false,publicationAppliesTo:'canonical-secure-original-only',
    exchangePublicationSource:reference.sourceUrl,exchangePublicationField:'kjTime'};
}
