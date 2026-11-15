"""新A専用private領域の入出力。秘密・価格を標準出力へ出さない。"""
import hashlib,json,os,re,tempfile
from pathlib import Path
def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()
def file_sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def atomic_write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.pending',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf8') as f:f.write(encode(value)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
def private_root(repo):return Path(repo).resolve()/'.cache/weak_early_beta/new-a-private'
def verify_bootstrap(root):
 root=Path(root).resolve();manifest=read(root/'bootstrap/manifest.json')
 if manifest.get('schema')!='NEW_A_PRIVATE_BOOTSTRAP_V1' or manifest.get('strategy')!='A_BASE':raise ValueError('bootstrap contract unavailable')
 files={}
 for name,item in manifest['files'].items():
  declared=Path(item['path']);p=(declared if declared.is_absolute() else root/'bootstrap'/declared).resolve()
  external=declared.is_absolute() and item.get('external_read_only') is True and name in {'seed','calendar','history_input','presentation','quotes'} and p.suffix in ['.json','.sqlite']
  if (not external and not p.is_relative_to(root/'bootstrap')) or not re.fullmatch('[a-f0-9]{64}',item['sha256']) or file_sha(p)!=item['sha256']:raise ValueError('bootstrap bytes changed')
  files[name]=p
 required={'seed','calendar','history_input','presentation','quotes'}
 if not required.issubset(files):raise ValueError('bootstrap inputs incomplete')
 return manifest,files
