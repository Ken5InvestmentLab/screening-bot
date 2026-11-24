import fs from 'node:fs';import path from 'node:path';import os from 'node:os';import crypto from 'node:crypto';import {execFile} from 'node:child_process';
import {isDeepStrictEqual} from 'node:util';
import {atomicJson} from './atomic-json.mjs';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function htmlDecoder(result,body){
  const declared=result.contentType?.match(/charset\s*=\s*["']?([\w-]+)/i)?.[1];
  const head=body.subarray(0,8192).toString('latin1');
  const meta=/html/i.test(result.contentType||'')||/^\s*<(?:!doctype\s+html|html|head|meta)\b/i.test(head)?head.match(/<meta\b[^>]*\bcharset\s*=\s*["']?\s*([\w-]+)/i)?.[1]:null;
  const bom=body[0]===0xff&&body[1]===0xfe?'utf-16le':body[0]===0xfe&&body[1]===0xff?'utf-16be':null;
  return new TextDecoder(declared||meta||bom||'utf-8',{fatal:true});
}
let sharedPdfActive=0;const sharedPdfPending=[];
export async function withPdfResource(fn){if(sharedPdfActive>=2)await new Promise(resolve=>sharedPdfPending.push(resolve));sharedPdfActive++;try{return await fn();}finally{sharedPdfActive--;sharedPdfPending.shift()?.();}}
export function createResearchDocumentExtractor({pythonPath=path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),helperPath=path.join(import.meta.dirname,'pdf-evidence.py'),execFileImpl=execFile,maxConcurrency=2}={}) {
  if(!Number.isInteger(maxConcurrency)||maxConcurrency<1||maxConcurrency>4)throw Error('PDF extraction concurrency must be 1-4');
  let active=0,versionPromise;const pending=[],inFlight=new Map();
  const run=(args)=>new Promise((resolve,reject)=>execFileImpl(pythonPath,args,{windowsHide:true,timeout:90000,maxBuffer:16*1024*1024,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}},(error,stdout)=>error?reject(Error('existing PDF extraction failed; retain this symbol checkpoint for review')):resolve(stdout)));
  async function bounded(fn){if(active>=maxConcurrency)await new Promise(resolve=>pending.push(resolve));active++;try{return await withPdfResource(fn);}finally{active--;pending.shift()?.();}}
  async function extractionInputs(result) {
    if(result.status!==200||!result.body)throw Error('research document unavailable');
    const body=Buffer.isBuffer(result.body)?result.body:Buffer.from(result.body),contentSha256=result.contentSha256||sha(body),isPdf=body.subarray(0,5).toString()==='%PDF-';
    const decoder=isPdf?null:htmlDecoder(result,body);
    let version=isPdf?'':`literal-html-charset-20261117-v2:${decoder.encoding}`;
    if(isPdf){
      if(!fs.existsSync(pythonPath)||!fs.existsSync(helperPath))throw Error('existing pypdf runtime/helper unavailable; retain raw PDF for manual review; do not install a runtime');
      versionPromise??=run(['-c','import pypdf; print(pypdf.__version__)']).then(s=>s.trim());
      version=`pypdf-${await versionPromise}-${sha(fs.readFileSync(helperPath))}`;
    }
    const key={contentSha256,validatorVersion:version,key:'body-text-and-supplementary-metadata'};
    return {body,contentSha256,isPdf,decoder,version,key};
  }
  async function extractResearchDocument({result,file,readBytes}) {
    const {body,contentSha256,isPdf,decoder,version,key}=await extractionInputs(result);
    let value=readBytes?.getVerification?.(key);
    if(!value){const id=JSON.stringify(key);let work=inFlight.get(id);if(!work){work=bounded(async()=>{
      const parsed=isPdf?JSON.parse(await run([helperPath,path.resolve(file)])):{pages:null,text:decoder.decode(body),auxiliaryPdfMetadata:null};
      if(typeof parsed.text!=='string')throw Error('PDF extraction returned no text record');
      const derived={...parsed,sourceSha256:contentSha256,extractorVersion:version,contentRead:false,publicationInferred:false,requiresVisualReview:isPdf&&parsed.text.replace(/\s/g,'').length<30};
      if(result.contentSha256&&readBytes?.recordVerification)readBytes.recordVerification({...key,value:derived});return derived;
    });inFlight.set(id,work);work.finally(()=>inFlight.delete(id)).catch(()=>{});}value=await work;}
    const textFile=file+'.txt',metadataFile=file+'.extraction.json';fs.writeFileSync(textFile,value.text,'utf8');atomicJson(metadataFile,{...value,text:undefined,textFile});
    return{textFile,metadataFile,pages:value.pages,contentRead:false,publicationInferred:false,requiresVisualReview:value.requiresVisualReview,extractorVersion:version,sourceSha256:contentSha256,auxiliaryPdfMetadata:value.auxiliaryPdfMetadata};
  }
  extractResearchDocument.matchesRetained = async ({result,file,readBytes,record}) => {
    const {key, version, contentSha256} = await extractionInputs(result);
    if (record.extractorVersion !== version || record.sourceSha256 !== contentSha256) return false;
    const cached = readBytes.getVerification?.(key);
    if (cached?.sourceSha256 !== contentSha256 || cached.extractorVersion !== version ||
        typeof cached.text !== 'string' || cached.contentRead !== false || cached.publicationInferred !== false) return false;
    const textFile = file + '.txt', metadataFile = file + '.extraction.json';
    if (record.textFile !== textFile || record.metadataFile !== metadataFile || record.pages !== cached.pages ||
        record.requiresVisualReview !== cached.requiresVisualReview ||
        !isDeepStrictEqual(record.auxiliaryPdfMetadata, cached.auxiliaryPdfMetadata)) return false;
    const {text, ...metadata} = cached;
    try {
      return fs.readFileSync(textFile).equals(Buffer.from(text, 'utf8')) &&
        isDeepStrictEqual(JSON.parse(fs.readFileSync(metadataFile, 'utf8')), {...metadata, textFile});
    } catch {
      // An unreadable or incomplete artifact goes through normal extraction.
      return false;
    }
  };
  return extractResearchDocument;
}
