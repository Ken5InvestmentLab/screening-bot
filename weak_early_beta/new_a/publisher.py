"""immutable parts→検証→READY→atomic pointer。通常Wrangler認証だけを使う。"""
import copy,datetime,hashlib,json,os,re,sqlite3,subprocess,tempfile
from pathlib import Path
from .files import encode,read,atomic_write
def hash_text(value):return hashlib.sha256(value.encode()).hexdigest()
def literal(value):
 if value is None:return 'NULL'
 if isinstance(value,(int,float)):return str(value)
 return "'"+str(value).replace("'","''")+"'"

class RemoteD1Error(RuntimeError):
 """Fixed categories and numeric provider codes only; never include SQL or output."""
 def __init__(self,category,*,provider_codes=(),returncode=None):
  self.provider_codes=tuple(provider_codes);self.returncode=returncode
  super().__init__(category)

def is_read_only_select(statement):
 """Conservative routing only: one SELECT, no comments or outside-string ';'."""
 text=statement.strip()
 if not re.match(r'SELECT\b',text,re.I) or '\0' in text:return False
 quote=None;i=0
 while i<len(text):
  char=text[i]
  if quote:
   if char==quote:
    if i+1<len(text) and text[i+1]==quote:i+=1
    else:quote=None
  elif char in "'\"`":quote=char
  elif char=='[':quote=']'
  elif char==';' or text[i:i+2] in ['--','/*']:return False
  i+=1
 return quote is None

_CLI_NOTICES={
 'Using secrets defined in process.env',
 'Using secrets defined in .env',
 "Proxy environment variables detected. We'll use your proxy for fetch requests.",
}

def _decode_wrangler_output(stdout,*,returncode=0,stderr='',import_progress=False):
 """Decode one document with only the existing allowlisted CLI notices."""
 def reject(category,codes=()):
  raise RemoteD1Error(category,provider_codes=codes,returncode=returncode)
 if returncode:
  codes=sorted({int(value) for pair in re.findall(r'\[code:\s*(\d+)\]|"code"\s*:\s*(\d+)',(stdout or '')+'\n'+(stderr or '')) for value in pair if value})
  reject('remote_d1_authorization_failed_reconcile_before_retry' if 7403 in codes else 'remote_d1_operation_failed_reconcile_before_retry',codes)
 if not isinstance(stdout,str) or not stdout.strip('\ufeff \t\r\n'):
  reject('remote_d1_response_empty_reconcile_before_retry')
 text=re.sub(r'\x1b\[[0-9;]*m','',stdout).lstrip('\ufeff')
 lines=text.splitlines(keepends=True)
 progress=[]
 while lines:
  line=lines[0].strip()
  if not line or line in _CLI_NOTICES:lines.pop(0);continue
  token=None
  if import_progress:
   # Wrangler 4.135.0 spinnerWhile writes non-TTY progress directly even
   # when its normal logger is suppressed by --json. Only its known file
   # import protocol is accepted; query results and arbitrary prose are not.
   if line=='├ Checking if file needs uploading':token='check'
   elif line=='│':token='separator'
   elif re.fullmatch(r'├ 🌀 Uploading [^\s\x00-\x1f\x7f\[\]{}]{1,512}',line):token='upload'
   elif line=='│ 🌀 Uploading complete.':token='done'
  if token is None:break
  progress.append(token);lines.pop(0)
 if progress and progress not in [['check','separator'],['check','separator','upload','done','separator']]:
  reject('remote_d1_response_unrecognized_reconcile_before_retry')
 text=''.join(lines).lstrip()
 def unique_object(pairs):
  value={}
  for key,item in pairs:
   if key in value:raise ValueError('duplicate JSON key')
   value[key]=item
  return value
 def invalid_constant(_):raise ValueError('non-JSON constant')
 try:
  data,end=json.JSONDecoder(object_pairs_hook=unique_object,parse_constant=invalid_constant).raw_decode(text)
  if any(line.strip() and line.strip() not in _CLI_NOTICES for line in text[end:].splitlines()):raise ValueError('unexpected trailing output')
 except (ValueError,TypeError):
  reject('remote_d1_response_unrecognized_reconcile_before_retry')
 if isinstance(data,dict) and data.get('error'):
  # The CLI's JSON failure envelope is not a successful result, even at exit 0.
  codes=sorted({int(value) for pair in re.findall(r'"code"\s*:\s*(\d+)|\[code:\s*(\d+)\]',json.dumps(data['error'])) for value in pair if value})
  reject('remote_d1_authorization_failed_reconcile_before_retry' if 7403 in codes else 'remote_d1_operation_unconfirmed',codes)
 return data

def _require_success(item,returncode):
 if not isinstance(item,dict):raise RemoteD1Error('remote_d1_operation_unconfirmed',returncode=returncode)
 if item.get('success') is not True or item.get('error') or item.get('errors'):
  detail=json.dumps({'error':item.get('error'),'errors':item.get('errors')})
  codes=sorted({int(value) for pair in re.findall(r'"code"\s*:\s*(\d+)|\[code:\s*(\d+)\]',detail) for value in pair if value})
  raise RemoteD1Error('remote_d1_authorization_failed_reconcile_before_retry' if 7403 in codes else 'remote_d1_operation_unconfirmed',provider_codes=codes,returncode=returncode)

def parse_wrangler_query_results(stdout,expected_count,*,returncode=0,stderr='',require_primary=False):
 """Accept query rows only; an import receipt cannot supply RETURNING rows."""
 data=_decode_wrangler_output(stdout,returncode=returncode,stderr=stderr)
 def reject(category):raise RemoteD1Error(category,returncode=returncode)
 if not isinstance(data,list) or len(data)!=expected_count:
  reject('remote_d1_query_result_count_mismatch_reconcile_before_retry')
 for item in data:
  _require_success(item,returncode)
  if 'finalBookmark' in item:
   reject('remote_d1_import_summary_not_query_results_reconcile_before_retry')
  if not isinstance(item.get('results'),list) or any(not isinstance(row,dict) for row in item['results']):
   reject('remote_d1_query_result_shape_invalid_reconcile_before_retry')
  if require_primary:
   meta=item.get('meta')
   if not isinstance(meta,dict) or meta.get('served_by_primary') is not True:
    reject('remote_d1_primary_read_unconfirmed')
 return [item['results'] for item in data]

def parse_wrangler_import_ack(stdout,expected_count,*,returncode=0,stderr=''):
 """Validate file-import completion, never manufacture SQL result rows."""
 data=_decode_wrangler_output(stdout,returncode=returncode,stderr=stderr,import_progress=True)
 def reject():raise RemoteD1Error('remote_d1_import_unconfirmed_reconcile_before_retry',returncode=returncode)
 if not isinstance(data,list) or len(data)!=1:reject()
 item=data[0];_require_success(item,returncode)
 rows=item.get('results');meta=item.get('meta');bookmark=item.get('finalBookmark')
 if not isinstance(bookmark,str) or not bookmark.strip() or not isinstance(meta,dict) or not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):reject()
 total=rows[0].get('Total queries executed')
 if type(total) is not int or total!=expected_count or expected_count<1:reject()
 for label,key in [('Rows read','rows_read'),('Rows written','rows_written')]:
  value=rows[0].get(label)
  if type(value) is not int or value<0 or type(meta.get(key)) is not int or meta[key]!=value:reject()
 return [[] for _ in range(expected_count)]

def _import_statement_allowed(sql):
 """Restrict imports to the publisher's single DML statements without row output."""
 if not re.match(r'(INSERT|UPDATE|DELETE)\b',sql.strip(),re.I) or '\0' in sql:return False
 # Removing quoted content allows harmless literals and quoted identifiers.
 unquoted=re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[(?:\]\]|[^\]])*\]",' ',sql)
 return not re.search(r"[;'\"`\[\]]|--|/\*|\bRETURNING\b",unquoted,re.I)

_OWNER_BINDING='CLOUD_DB'
_MEMBER_BINDING='CLOUD_MEMBER_DB'
_MEMBER_DATABASE_ID='72edf9bf-b033-463b-a053-ff259db17cb5'
_CLOUDFLARE_API='https://api.cloudflare.com/client/v4'


def _canonical_member_config(repo):
 """Match the standalone read bridge's production-only binding checks."""
 path=repo/'weak-early-beta-gate/wrangler.jsonc'
 try:
  if path.resolve(strict=True)!=path or not path.is_file():raise ValueError
  config=read(path)
 except (OSError,ValueError):
  raise ValueError('canonical member D1 config required') from None
 databases=config.get('d1_databases') if isinstance(config,dict) else None
 if (not isinstance(databases,list) or any(not isinstance(db,dict) for db in databases)
     or config.get('name')!='tentei-kyokuchi-cloud' or config.get('preview_urls') is not False):
  raise ValueError('canonical member D1 config required')
 matches=[db for db in databases if db.get('binding')==_MEMBER_BINDING
          or db.get('database_name')==_MEMBER_BINDING or db.get('database_id')==_MEMBER_DATABASE_ID]
 owners=[db for db in databases if db.get('binding')==_OWNER_BINDING]
 environments=config.get('env')
 preview=environments.get('preview') if isinstance(environments,dict) else None
 if (len(matches)!=1 or len(owners)!=1 or owners[0].get('database_id')!='e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb'
     or owners[0].get('database_name')!='tentei-cloud-settings'
     or any(db.get('preview_database_id')==_MEMBER_DATABASE_ID for db in databases)
     or not isinstance(preview,dict) or preview.get('d1_databases')!=[]):
  raise ValueError('canonical member D1 config required')
 member=matches[0]
 if (member.get('binding')!=_MEMBER_BINDING or member.get('database_name')!='tentei-cloud-member-view'
     or member.get('database_id')!=_MEMBER_DATABASE_ID or member.get('remote') is not False
     or member.get('migrations_dir')!='member-migrations'
     or 'preview_database_id' in member or 'database_internal_env' in member):
  raise ValueError('canonical member D1 config required')
 return path


class LocalD1:
 def __init__(self,path,schema):
  Path(path).parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,isolation_level=None);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA foreign_keys=ON');self.db.executescript(Path(schema).read_text(encoding='utf8'));self.external=False
 def query(self,sql,values=()):
  cursor=self.db.execute(sql,values);return [dict(r) for r in cursor.fetchall()] if cursor.description else []
 def batch(self,statements):return [self.query(sql,values) for sql,values in statements]
 def close(self):self.db.close()
class WranglerD1:
 def __init__(self,repo,private_directory,*,execute=False,node='node',binding=_OWNER_BINDING,require_primary=False):
  if not execute:raise ValueError('remote publication not authorized in preparation')
  if binding not in (_OWNER_BINDING,_MEMBER_BINDING):raise ValueError('unsupported D1 binding')
  self.repo=Path(repo).resolve();self.directory=Path(private_directory).resolve();self.node=node;self.external=True
  self.binding=binding;self.require_primary=binding==_MEMBER_BINDING or require_primary
  if not self.directory.is_relative_to(self.repo/'.cache/weak_early_beta/new-a-private'):raise ValueError('private SQL directory required')
  self.cli=self.repo/'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js'
  if not self.cli.is_file():raise ValueError('existing Wrangler unavailable')
  if self.binding==_MEMBER_BINDING:_canonical_member_config(self.repo)
  self.directory.mkdir(parents=True,exist_ok=True)
 def query(self,sql,values=()):return self.batch([(sql,values)])[0]
 def batch(self,statements):
  if not statements:return []
  compiled=[]
  for sql,values in statements:
   segments=sql.split('?')
   if len(segments)!=len(values)+1:raise ValueError('SQL parameters mismatch')
   sql=''.join(segment+(literal(values[i]) if i<len(values) else '') for i,segment in enumerate(segments))
   if len(sql.encode())>90000:raise ValueError('D1 SQL statement budget exceeded')
   compiled.append(sql.rstrip(';'))
  sql=';\n'.join(compiled)+';'
  if len(sql.encode())>1024*1024:raise ValueError('D1 SQL batch budget exceeded')
  read_only=bool(compiled) and all(is_read_only_select(statement) for statement in compiled)
  if not read_only and not all(_import_statement_allowed(statement) for statement in compiled):raise ValueError('D1 import requires single DML statements without RETURNING')
  options=dict(cwd=self.repo/'weak-early-beta-gate',capture_output=True,text=True,encoding='utf8',timeout=120)
  member_arguments=[]
  if self.binding==_MEMBER_BINDING:
   config=_canonical_member_config(self.repo)
   member_arguments=['--config',str(config),'--env=']
   options['env']={**os.environ,'CLOUDFLARE_API_BASE_URL':_CLOUDFLARE_API}
  # 値を引数/履歴へ入れずprivate fileから渡し、stdout/stderrはチャット/CIへ出さない。
  with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',suffix='.sql',dir=self.directory,delete=False) as f:f.write(sql);name=f.name
  try:
   if read_only:
    bridge=Path(__file__).with_name('wrangler-query.cjs')
    command=[self.node,str(bridge),str(self.cli),name]
    if member_arguments:command.append(self.binding)
    result=subprocess.run(command,**options)
    return parse_wrangler_query_results(result.stdout,len(statements),returncode=result.returncode,stderr=result.stderr,require_primary=self.require_primary)
   # Keep the existing file-import transport, statement order, limits and timeout.
   result=subprocess.run([self.node,str(self.cli),'d1','execute',self.binding,'--remote','--file',name,'--yes','--json',*member_arguments],**options)
   return parse_wrangler_import_ack(result.stdout,len(statements),returncode=result.returncode,stderr=result.stderr)
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
 if prior_revision==0:db.query("INSERT INTO new_a_active_pointer VALUES ('owner',?,1,?) ON CONFLICT(pointer_key) DO NOTHING",(dataset_id,now))
 else:db.query("UPDATE new_a_active_pointer SET dataset_id=?,revision=revision+1,updated_at=? WHERE pointer_key='owner' AND revision=?",(dataset_id,now,prior_revision))
 current=pointer(db)
 if not current or current['dataset_id']!=dataset_id or current['revision']!=expected_revision+1:raise ValueError('active pointer conflict after staging; reconcile')
 if not current or current['dataset_id']!=dataset_id or current['status']!='READY':raise ValueError('active dataset readback mismatch')
 verify_dataset(db,dataset_id);return publication_receipt(current,manifest,current['revision'],False,db.external)

def publish_bundle(db,folder,*,expected_revision=None,now=None):
 prepared=stage_bundle(db,folder,expected_revision=expected_revision,now=now)
 return activate_prepared(db,prepared,expected_revision=prepared['expected_revision'],now=now)

def publication_receipt(active,manifest,revision,duplicate,external):
 return {'schema':'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1','published':external,'local_d1_emulation':not external,'dataset_id':active['dataset_id'],'revision':revision,'source_version':manifest['source_version'],'manifest_sha256':active['manifest_sha256'],'snapshot_sha256':manifest['daily_snapshot_sha256'],'as_of':manifest['as_of'],'active_readback_verified':True,'same_dataset_replay':duplicate,'existing_owner_gate_verified':False,'notifications_sent':0}
def rollback_pointer(db,target_dataset_id,expected_revision):
 if type(expected_revision) is not int or expected_revision<1:raise ValueError('explicit rollback revision required')
 row,m=verify_dataset(db,target_dataset_id)
 if row['status']!='READY':raise ValueError('rollback target not verified ready')
 before=pointer(db)
 if not before or before['revision']!=expected_revision:raise ValueError('rollback pointer conflict')
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();db.query("UPDATE new_a_active_pointer SET dataset_id=?,revision=revision+1,updated_at=? WHERE pointer_key='owner' AND revision=?",(target_dataset_id,now,expected_revision))
 current=pointer(db)
 if not current or current['dataset_id']!=target_dataset_id or current['revision']!=expected_revision+1 or current['status']!='READY':raise ValueError('rollback readback failed; reconcile')
 verify_dataset(db,target_dataset_id)
 return publication_receipt(current,m,current['revision'],False,db.external)
