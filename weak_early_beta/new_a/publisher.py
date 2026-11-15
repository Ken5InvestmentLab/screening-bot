"""immutable parts→検証→READY→atomic pointer。通常Wrangler認証だけを使う。"""
import copy,datetime,hashlib,json,re,sqlite3,subprocess,tempfile
from pathlib import Path
from .files import encode,read,atomic_write
def hash_text(value):return hashlib.sha256(value.encode()).hexdigest()
def literal(value):
 if value is None:return 'NULL'
 if isinstance(value,(int,float)):return str(value)
 return "'"+str(value).replace("'","''")+"'"
class LocalD1:
 def __init__(self,path,schema):
  Path(path).parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,isolation_level=None);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA foreign_keys=ON');self.db.executescript(Path(schema).read_text(encoding='utf8'));self.external=False
 def query(self,sql,values=()):
  cursor=self.db.execute(sql,values);return [dict(r) for r in cursor.fetchall()] if cursor.description else []
 def batch(self,statements):return [self.query(sql,values) for sql,values in statements]
 def close(self):self.db.close()
class WranglerD1:
 def __init__(self,repo,private_directory,*,execute=False,node='node'):
  if not execute:raise ValueError('remote publication not authorized in preparation')
  self.repo=Path(repo).resolve();self.directory=Path(private_directory).resolve();self.node=node;self.external=True
  if not self.directory.is_relative_to(self.repo/'.cache/weak_early_beta/new-a-private'):raise ValueError('private SQL directory required')
  self.cli=self.repo/'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js'
  if not self.cli.is_file():raise ValueError('existing Wrangler unavailable')
  self.directory.mkdir(parents=True,exist_ok=True)
 def query(self,sql,values=()):return self.batch([(sql,values)])[0]
 def batch(self,statements):
  compiled=[]
  for sql,values in statements:
   segments=sql.split('?')
   if len(segments)!=len(values)+1:raise ValueError('SQL parameters mismatch')
   sql=''.join(segment+(literal(values[i]) if i<len(values) else '') for i,segment in enumerate(segments))
   if len(sql.encode())>90000:raise ValueError('D1 SQL statement budget exceeded')
   compiled.append(sql.rstrip(';'))
  sql=';\n'.join(compiled)+';'
  if len(sql.encode())>1024*1024:raise ValueError('D1 SQL batch budget exceeded')
  # 値を引数/履歴へ入れずprivate fileから渡し、stdout/stderrはチャット/CIへ出さない。
  with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',suffix='.sql',dir=self.directory,delete=False) as f:f.write(sql);name=f.name
  try:
   result=subprocess.run([self.node,str(self.cli),'d1','execute','CLOUD_DB','--remote','--file',name,'--yes','--json'],cwd=self.repo/'weak-early-beta-gate',capture_output=True,text=True,encoding='utf8',timeout=120)
   if result.returncode:raise RuntimeError('remote_d1_operation_failed_reconcile_before_retry')
   try:data=json.loads(result.stdout)
   except Exception:raise RuntimeError('remote_d1_response_unrecognized_reconcile_before_retry') from None
   if not isinstance(data,list) or any(item.get('success') is not True for item in data):raise RuntimeError('remote_d1_operation_unconfirmed')
   return [item.get('results',[]) for item in data]
  finally:Path(name).unlink(missing_ok=True)
 def close(self):pass
def descriptors(manifest):return [*manifest['quotes'],*[d for values in manifest['collections'].values() for d in values]]
def validate_manifest(manifest,*,prepared=False):
 if manifest.get('schema')!='A_BROWSER_PRIVATE_INPUT_V1' or manifest.get('audience')!='EXISTING_CLOUD_OWNER_ONLY' or manifest.get('strategy')!='A_BASE' or not re.fullmatch('[a-f0-9]{64}',manifest.get('source_version','')):raise ValueError('private manifest contract invalid')
 kinds={'episodes','intents','watches','presentation','current_daily'}
 if set(manifest.get('collections',{}))!=kinds or not isinstance(manifest.get('quotes'),list) or any(not isinstance(v,list) for v in manifest['collections'].values()):raise ValueError('private manifest collections invalid')
 values=descriptors(manifest)
 if len(values)>512 or len({d.get('name') for d in values})!=len(values):raise ValueError('private manifest count invalid')
 for d in values:
  if not re.fullmatch(r'(episodes|intents|watches|presentation|current_daily|quotes)-\d{3}\.json',str(d.get('name',''))) or not isinstance(d.get('bytes'),int) or not 2<=d['bytes']<=65536 or not isinstance(d.get('rows'),int) or d['rows']<0 or not re.fullmatch('[a-f0-9]{64}',str(d.get('sha256',''))):raise ValueError('private descriptor invalid')
  if 'dataset_id' in d and (prepared or not re.fullmatch('a-[a-f0-9]{24}',str(d['dataset_id']))):raise ValueError('private descriptor storage invalid')
 return manifest
def logical_manifest(manifest):
 m=copy.deepcopy(manifest)
 for d in descriptors(m):d.pop('dataset_id',None)
 return m
def pointer(db):
 rows=db.query("SELECT p.dataset_id,p.revision,d.source_version,d.manifest_sha256,d.manifest_json,d.status FROM new_a_active_pointer p JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id WHERE p.pointer_key='owner'")
 return rows[0] if rows else None
def verify_dataset(db,dataset_id):
 rows=db.query('SELECT * FROM new_a_private_datasets WHERE dataset_id=?',(dataset_id,))
 if not rows:raise ValueError('dataset unavailable')
 row=rows[0];m=validate_manifest(json.loads(row['manifest_json']))
 if hash_text(row['manifest_json'])!=row['manifest_sha256'] or m['source_version']!=row['source_version']:raise ValueError('manifest mismatch')
 seen=set();loaded={};groups={}
 for d in descriptors(m):groups.setdefault(d.get('dataset_id',dataset_id),[]).append(d['name'])
 for storage,names in groups.items():
  if storage!=dataset_id:
   parent=db.query('SELECT status FROM new_a_private_datasets WHERE dataset_id=?',(storage,))
   if not parent or parent[0]['status']!='READY':raise ValueError('shared part dataset not ready')
  for offset in range(0,len(names),8):
   batch=names[offset:offset+8];marks=','.join('?' for _ in batch)
   for part in db.query('SELECT name,payload_json,sha256,byte_length FROM new_a_private_parts WHERE dataset_id=? AND name IN ('+marks+')',(storage,*batch)):loaded[(storage,part['name'])]=part
 for d in descriptors(m):
  if d['name'] in seen or not re.fullmatch(r'(episodes|intents|watches|presentation|current_daily|quotes)-\d{3}\.json',d['name']):raise ValueError('private part identity invalid')
  seen.add(d['name']);storage=d.get('dataset_id',dataset_id)
  part=loaded.get((storage,d['name']))
  if not part:raise ValueError('private part absent')
  raw=part['payload_json']
  if hash_text(raw)!=d['sha256'] or part['sha256']!=d['sha256'] or len(raw.encode())!=d['bytes'] or part['byte_length']!=d['bytes'] or len(json.loads(raw))!=d['rows']:raise ValueError('private part mismatch')
 return row,m
def stage_bundle(db,folder,*,expected_revision=None,now=None):
 folder=Path(folder);incoming=(folder/'manifest.json').read_text(encoding='utf8');manifest=validate_manifest(json.loads(incoming),prepared=True);receipt=read(folder/'receipt.json')
 if hash_text(incoming)!=receipt['manifest_sha256'] or manifest.get('strategy')!='A_BASE' or manifest.get('audience')!='EXISTING_CLOUD_OWNER_ONLY':raise ValueError('bundle receipt mismatch')
 active=pointer(db);prior_revision=active['revision'] if active else 0
 if expected_revision is not None and expected_revision!=prior_revision:raise ValueError('active pointer revision conflict')
 if active:
  _,previous=verify_dataset(db,active['dataset_id'])
  if logical_manifest(previous)==logical_manifest(manifest):return preparation_receipt(active,previous,prior_revision,True)
 else:previous=None
 existing={d['name']:d for d in descriptors(previous)} if previous else {}
 for d in descriptors(manifest):
  p=folder/d['name'];raw=p.read_text(encoding='utf8')
  if hash_text(raw)!=d['sha256'] or len(raw.encode())!=d['bytes'] or len(json.loads(raw))!=d['rows'] or d['bytes']>65536:raise ValueError('prepared part mismatch')
  old=existing.get(d['name'])
  if old and (old['sha256'],old['bytes'],old['rows'])==(d['sha256'],d['bytes'],d['rows']):d['dataset_id']=old.get('dataset_id',active['dataset_id'])
 text=encode(manifest);manifest_sha=hash_text(text);dataset_id='a-'+manifest_sha[:24];now=now or datetime.datetime.now(datetime.timezone.utc).isoformat()
 # SQLリテラル化後も100KB公式上限の内側に収める。投入前に全件検査する。
 if len((literal(text)+dataset_id).encode())>88000:raise ValueError('manifest SQL budget exceeded')
 for d in descriptors(manifest):
  if 'dataset_id' not in d and len(literal((folder/d['name']).read_text(encoding='utf8')).encode())>88000:raise ValueError('part SQL budget exceeded')
 db.query('INSERT INTO new_a_private_datasets VALUES (?,?,?,?,?,?) ON CONFLICT(dataset_id) DO NOTHING',(dataset_id,manifest['source_version'],text,manifest_sha,'STAGING',now))
 prior=db.query('SELECT manifest_sha256 FROM new_a_private_datasets WHERE dataset_id=?',(dataset_id,))
 if not prior or prior[0]['manifest_sha256']!=manifest_sha:raise ValueError('immutable dataset conflict')
 statements=[]
 for d in descriptors(manifest):
  if 'dataset_id' in d:continue
  raw=(folder/d['name']).read_text(encoding='utf8');statements.append(('INSERT INTO new_a_private_parts VALUES (?,?,?,?,?) ON CONFLICT(dataset_id,name) DO NOTHING',(dataset_id,d['name'],raw,d['sha256'],d['bytes'])))
 for offset in range(0,len(statements),8):db.batch(statements[offset:offset+8])
 verify_dataset(db,dataset_id)
 db.query("UPDATE new_a_private_datasets SET status='READY' WHERE dataset_id=?",(dataset_id,))
 row,stored=verify_dataset(db,dataset_id)
 if row['status']!='READY':raise ValueError('prepared dataset not READY')
 if pointer(db)!=active:raise ValueError('active pointer changed during preparation; reconcile')
 return preparation_receipt(row,stored,prior_revision,False)

def preparation_receipt(row,manifest,revision,already_active):
 value={'schema':'NEW_A_PREPARED_DATASET_V1','dataset_id':row['dataset_id'],'source_version':manifest['source_version'],'manifest_sha256':row['manifest_sha256'],'snapshot_sha256':manifest['daily_snapshot_sha256'],'as_of':manifest['as_of'],'expected_revision':revision,'ready_readback_verified':True,'already_active':already_active,'pointer_changed':False,'published':False,'notifications_sent':0}
 value['receipt_sha256']=hash_text(encode(value));return value

def activate_prepared(db,prepared,*,expected_revision,now=None):
 unsigned={k:v for k,v in prepared.items() if k!='receipt_sha256'}
 if prepared.get('schema')!='NEW_A_PREPARED_DATASET_V1' or prepared.get('published') is not False or prepared.get('pointer_changed') is not False or prepared.get('receipt_sha256')!=hash_text(encode(unsigned)):raise ValueError('prepared receipt invalid')
 if type(expected_revision) is not int or expected_revision<0 or prepared.get('expected_revision')!=expected_revision:raise ValueError('explicit prepared revision required')
 row,manifest=verify_dataset(db,prepared['dataset_id'])
 if row['status']!='READY' or row['manifest_sha256']!=prepared['manifest_sha256'] or manifest['source_version']!=prepared['source_version'] or manifest['daily_snapshot_sha256']!=prepared['snapshot_sha256']:raise ValueError('prepared dataset changed')
 current=pointer(db);prior_revision=current['revision'] if current else 0
 if current and current['dataset_id']==row['dataset_id'] and prior_revision in (expected_revision,expected_revision+1):return publication_receipt(current,manifest,prior_revision,True,db.external)
 if prior_revision!=expected_revision:raise ValueError('active pointer revision conflict')
 now=now or datetime.datetime.now(datetime.timezone.utc).isoformat();dataset_id=row['dataset_id']
 if prior_revision==0:switched=db.query("INSERT INTO new_a_active_pointer VALUES ('owner',?,1,?) ON CONFLICT(pointer_key) DO NOTHING RETURNING revision",(dataset_id,now))
 else:switched=db.query("UPDATE new_a_active_pointer SET dataset_id=?,revision=revision+1,updated_at=? WHERE pointer_key='owner' AND revision=? RETURNING revision",(dataset_id,now,prior_revision))
 current=pointer(db)
 if not switched and (not current or current['dataset_id']!=dataset_id or current['revision']!=expected_revision+1):raise ValueError('active pointer conflict after staging; reconcile')
 if not current or current['dataset_id']!=dataset_id or current['status']!='READY':raise ValueError('active dataset readback mismatch')
 verify_dataset(db,dataset_id);return publication_receipt(current,manifest,current['revision'],False,db.external)

def publish_bundle(db,folder,*,expected_revision=None,now=None):
 prepared=stage_bundle(db,folder,expected_revision=expected_revision,now=now)
 return activate_prepared(db,prepared,expected_revision=prepared['expected_revision'],now=now)

def publication_receipt(active,manifest,revision,duplicate,external):
 return {'schema':'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1','published':external,'local_d1_emulation':not external,'dataset_id':active['dataset_id'],'revision':revision,'source_version':manifest['source_version'],'manifest_sha256':active['manifest_sha256'],'snapshot_sha256':manifest['daily_snapshot_sha256'],'as_of':manifest['as_of'],'active_readback_verified':True,'same_dataset_replay':duplicate,'existing_owner_gate_verified':False,'notifications_sent':0}
def rollback_pointer(db,target_dataset_id,expected_revision):
 row,m=verify_dataset(db,target_dataset_id)
 if row['status']!='READY':raise ValueError('rollback target not verified ready')
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();changed=db.query("UPDATE new_a_active_pointer SET dataset_id=?,revision=revision+1,updated_at=? WHERE pointer_key='owner' AND revision=? RETURNING revision",(target_dataset_id,now,expected_revision))
 if not changed:raise ValueError('rollback pointer conflict')
 current=pointer(db)
 if current['dataset_id']!=target_dataset_id:raise ValueError('rollback readback failed')
 return publication_receipt(current,m,current['revision'],False,db.external)
