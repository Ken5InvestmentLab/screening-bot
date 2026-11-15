// Immutable private datasets. Called only after existing owner and fresh-role checks.
export interface NewAStatement { bind(...values: (string|number|null)[]): NewAStatement; first<T = Record<string,unknown>>(): Promise<T|null>; }
export interface NewADatabase { prepare(sql:string): NewAStatement; }
export interface PartDescriptor {name:string;sha256:string;bytes:number;rows:number;dataset_id?:string;}
export interface PrivateManifest {schema:string;audience:string;source_version:string;input_header:Record<string,unknown>;collections:Record<string,PartDescriptor[]>;quotes:PartDescriptor[];dataset_id?:string;[key:string]:unknown;}
export const DATASET_ID=/^a-[a-f0-9]{20,64}$/;
export const PART_NAME=/^(episodes|intents|watches|quotes|presentation|current_daily)-\d{3}\.json$/;
const hex=/^[a-f0-9]{64}$/;
export async function digest(value:string):Promise<string>{const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value));return Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');}
export function validateManifest(value:unknown):PrivateManifest{
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('manifest_schema');
 const m=value as PrivateManifest;
 if(m.schema!=='A_BROWSER_PRIVATE_INPUT_V1'||m.audience!=='EXISTING_CLOUD_OWNER_ONLY'||!hex.test(m.source_version)||!m.input_header||m.input_header.source_version!==m.source_version||!m.collections||!Array.isArray(m.quotes))throw Error('manifest_schema');
 const all:PartDescriptor[]=[...m.quotes];for(const kind of ['episodes','intents','watches','presentation','current_daily']){if(!Array.isArray(m.collections[kind]))throw Error('manifest_collections');all.push(...m.collections[kind]);}
 if(!all.length||all.length>512||new Set(all.map(d=>d.name)).size!==all.length||all.some(d=>!PART_NAME.test(d.name)||!hex.test(d.sha256)||d.dataset_id!==undefined&&!DATASET_ID.test(d.dataset_id)||!Number.isSafeInteger(d.bytes)||d.bytes<2||d.bytes>196608||!Number.isSafeInteger(d.rows)||d.rows<0))throw Error('manifest_bounds');
 for(const [kind,ds]of Object.entries(m.collections))if(!['episodes','intents','watches','presentation','current_daily'].includes(kind)||ds.some(d=>!d.name.startsWith(kind+'-')))throw Error('manifest_kind');
 if(m.quotes.some(d=>!d.name.startsWith('quotes-')))throw Error('manifest_kind');
 return m;
}
export async function readActiveManifest(db:NewADatabase):Promise<PrivateManifest>{
 const row=await db.prepare("SELECT d.dataset_id,d.source_version,d.manifest_json,d.manifest_sha256 FROM new_a_active_pointer p JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id WHERE p.pointer_key='owner' AND d.status='READY'").bind().first<{dataset_id:string;source_version:string;manifest_json:string;manifest_sha256:string}>();
 if(!row||!DATASET_ID.test(row.dataset_id)||!hex.test(row.manifest_sha256)||await digest(row.manifest_json)!==row.manifest_sha256)throw Error('active_dataset_unavailable');
 const manifest=validateManifest(JSON.parse(row.manifest_json));if(manifest.source_version!==row.source_version)throw Error('source_version_mismatch');
 return {...manifest,dataset_id:row.dataset_id};
}
export async function readPrivatePart(db:NewADatabase,datasetId:string,name:string):Promise<string|null>{
 if(!DATASET_ID.test(datasetId)||!PART_NAME.test(name))return null;
 const row=await db.prepare("SELECT p.payload_json,p.sha256,p.byte_length FROM new_a_private_parts p JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id WHERE p.dataset_id=? AND p.name=? AND d.status='READY'").bind(datasetId,name).first<{payload_json:string;sha256:string;byte_length:number}>();
 if(!row)return null;if(!hex.test(row.sha256)||row.byte_length<2||row.byte_length>196608||new TextEncoder().encode(row.payload_json).byteLength!==row.byte_length||await digest(row.payload_json)!==row.sha256)throw Error('private_part_integrity');
 return row.payload_json;
}
