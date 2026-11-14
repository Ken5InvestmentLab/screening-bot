// 既存CLOUD_DBの新A専用表だけを読む。認証後に呼び、旧設定表・台帳へは書かない。
export const DATASET_ID = 'A_BASE_FROZEN_2026_20261112_v1';
export const EXPECTED_SHA256 = '87d3ee71550d237a92b8147a0c164339734e81a724fc317d0c2b21e1b4cfc539';
export async function readResearchASnapshot(db:D1Database|undefined):Promise<any>{
 if(!db||typeof db.prepare!=='function')throw new Error('New A data unavailable');
 const header=await db.prepare('SELECT schema_version, content_sha256, header_json, row_count FROM new_a_research_snapshot_headers WHERE dataset_id = ?').bind(DATASET_ID).first<{schema_version:number,content_sha256:string,header_json:string,row_count:number}>();
 if(!header||header.schema_version!==1||header.content_sha256!==EXPECTED_SHA256||header.row_count!==197)throw new Error('New A data unavailable');
 const rows=await db.prepare('SELECT sequence, row_kind, row_json FROM new_a_research_snapshot_rows WHERE dataset_id = ? ORDER BY sequence').bind(DATASET_ID).all<{sequence:number,row_kind:string,row_json:string}>();
 if(!rows.success||rows.results.length!==197||rows.results.some((r,i)=>r.sequence!==i||!['closed','open'].includes(r.row_kind)))throw new Error('New A data unavailable');
 const h=JSON.parse(header.header_json),closed=rows.results.filter(r=>r.row_kind==='closed').map(r=>JSON.parse(r.row_json)),openAtEnd=rows.results.filter(r=>r.row_kind==='open').map(r=>JSON.parse(r.row_json));
 if(closed.length!==178||openAtEnd.length!==19)throw new Error('New A data unavailable');
 const snapshot={period:h.period,conditions:h.conditions,account:h.account,closed,openAtEnd,snapshot:h.snapshot};
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(snapshot))))).map(n=>n.toString(16).padStart(2,'0')).join('');
 if(digest!==EXPECTED_SHA256)throw new Error('New A data unavailable');
 return snapshot;
}
