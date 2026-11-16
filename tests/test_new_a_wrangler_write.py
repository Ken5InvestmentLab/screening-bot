"""Synthetic import receipts and temporary SQLite only. No CLI/network/credentials."""
import copy,json,sqlite3,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from weak_early_beta.new_a import publisher as p
from weak_early_beta.new_a.files import encode,atomic_write

def ack(count=1,**overrides):
 item={'success':True,'results':[{'Total queries executed':count,'Rows read':0,'Rows written':0,'Database size (MB)':'0.01'}],'finalBookmark':'LOCAL_SYNTHETIC_ONLY','meta':{'rows_read':0,'rows_written':0}}
 item.update(overrides);return json.dumps([item])

class ImportResponse(unittest.TestCase):
 def test_one_and_many_statements_return_ack_without_fabricated_rows(self):
  for n in [1,8]:self.assertEqual(p.parse_wrangler_import_ack(ack(n),n),[[] for _ in range(n)])
 def test_only_existing_notice_allowlist_is_accepted(self):
  self.assertEqual(p.parse_wrangler_import_ack('\ufeff\x1b[90mUsing secrets defined in process.env\x1b[0m\n'+ack()+'\nUsing secrets defined in .env',1),[[]])
 def test_nonzero_exit_always_fails_even_with_valid_ack(self):
  with self.assertRaisesRegex(p.RemoteD1Error,'operation_failed'):p.parse_wrangler_import_ack(ack(),1,returncode=1)
 def test_7403_is_classified_without_raw_output(self):
  with self.assertRaises(p.RemoteD1Error) as caught:p.parse_wrangler_import_ack('',1,returncode=1,stderr='[code: 7403] SYNTHETIC_PRIVATE')
  self.assertEqual(caught.exception.provider_codes,(7403,));self.assertNotIn('SYNTHETIC_PRIVATE',str(caught.exception))
 def test_zero_exit_error_is_rejected(self):
  with self.assertRaisesRegex(p.RemoteD1Error,'authorization'):p.parse_wrangler_import_ack('{"error":{"code":7403}}',1)
 def test_empty_truncated_unknown_prefix_trailing_and_duplicate_keys_fail(self):
  for text in ['', '[', 'unknown\n'+ack(),ack()+'\nunknown',ack()+ack(),'[{"success":true,"success":false}]']:
   with self.subTest(text=text),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(text,1)
 def test_query_response_cannot_ack_an_import(self):
  with self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack('[{"success":true,"results":[]}]',1)
 def test_partial_extra_and_wrong_count_imports_fail(self):
  for text in ['[]',ack(0),ack(2),ack(1.0),ack(True),json.dumps(json.loads(ack())*2)]:
   with self.subTest(text=text),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(text,1)
 def test_missing_or_invalid_bookmark_fails(self):
  for v in [None,'',123,'   ']:
   with self.subTest(v=v),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(ack(finalBookmark=v),1)
 def test_failed_or_nonboolean_success_fails(self):
  for v in [False,1,None]:
   with self.subTest(v=v),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(ack(success=v),1)
 def test_error_fields_override_success(self):
  for kw in [{'error':'failure'},{'errors':[{'code':7403}]}]:
   with self.subTest(kw=kw),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(ack(**kw),1)
 def test_totals_must_be_single_mapping_and_match_metadata(self):
  base=json.loads(ack())[0]
  for field,value in [('results',[]),('results',[{},{}]),('results',[1]),('meta',None),('meta',{'rows_read':1,'rows_written':0}),('meta',{'rows_read':0,'rows_written':False})]:
   item=copy.deepcopy(base);item[field]=value
   with self.subTest(field=field,value=value),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(json.dumps([item]),1)
 def test_negative_boolean_or_missing_row_totals_fail(self):
  for value in [-1,True,None]:
   item=json.loads(ack())[0];item['results'][0]['Rows written']=value;item['meta']['rows_written']=value
   with self.subTest(value=value),self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(json.dumps([item]),1)
 def test_nonpositive_expected_count_never_acknowledged(self):
  with self.assertRaises(p.RemoteD1Error):p.parse_wrangler_import_ack(ack(0),0)

class ImportTransport(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.repo=Path(self.tmp.name)
  cli=self.repo/'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js';cli.parent.mkdir(parents=True);cli.write_text('// never executed','utf8')
  self.directory=self.repo/'.cache/weak_early_beta/new-a-private/sql';self.db=p.WranglerD1(self.repo,self.directory,execute=True)
 def tearDown(self):self.tmp.cleanup()
 def test_file_transport_order_input_flags_timeout_and_utf8_remain(self):
  secret_free_value="synthetic 日本?; quote' RETURNING -- /*"
  def fake(args,**kw):
   self.assertEqual(args[:7],['node',str(self.db.cli),'d1','execute','CLOUD_DB','--remote','--file']);self.assertEqual(args[-2:],['--yes','--json'])
   self.assertNotIn(secret_free_value,' '.join(args));self.assertNotIn('--command',args)
   self.assertEqual(kw,dict(cwd=self.repo/'weak-early-beta-gate',capture_output=True,text=True,encoding='utf8',timeout=120))
   self.assertEqual(Path(args[7]).read_text('utf8'),"INSERT INTO t VALUES ("+p.literal(secret_free_value)+");\nUPDATE t SET v=2;")
   return SimpleNamespace(stdout='Using secrets defined in process.env\n'+ack(2),stderr='',returncode=0)
  with patch.object(p.subprocess,'run',side_effect=fake) as run:self.assertEqual(self.db.batch([('INSERT INTO t VALUES (?)',(secret_free_value,)),('UPDATE t SET v=2',())]),[[],[]]);run.assert_called_once()
  self.assertEqual(list(self.directory.glob('*.sql')),[])
 def test_returning_mixed_read_write_and_extra_statements_stop_before_execution(self):
  for sql in ['UPDATE t SET v=2 RETURNING v','INSERT INTO t VALUES(1);DELETE FROM t','UPDATE t SET v=2 -- comment',"UPDATE t SET v='broken",'PRAGMA user_version=2','SELECT 1; UPDATE t SET v=2']:
   with self.subTest(sql=sql),patch.object(p.subprocess,'run') as run:
    with self.assertRaises(ValueError):self.db.query(sql)
    run.assert_not_called()
  with patch.object(p.subprocess,'run') as run:
   with self.assertRaises(ValueError):self.db.batch([('SELECT 1',()),('DELETE FROM t',())])
   run.assert_not_called()
 def test_statement_and_batch_size_budgets_preserved_before_execution(self):
  with patch.object(p.subprocess,'run') as run:
   for statements in [[('UPDATE t SET v=?',('x'*90000,))],[('UPDATE t SET v=?',('x'*65000,))]*17]:
    with self.assertRaisesRegex(ValueError,'budget'):self.db.batch(statements)
   run.assert_not_called()
 def test_partial_ack_nonzero_timeout_are_never_retried_and_files_are_cleaned(self):
  outcomes=[SimpleNamespace(stdout=ack(1),stderr='',returncode=0),SimpleNamespace(stdout=ack(2),stderr='',returncode=1),subprocess.TimeoutExpired(['SYNTHETIC'],120)]
  for outcome in outcomes:
   kw={'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome}
   with self.subTest(kind=type(outcome).__name__),patch.object(p.subprocess,'run',**kw) as run:
    with self.assertRaises((p.RemoteD1Error,subprocess.TimeoutExpired)):self.db.batch([('DELETE FROM t',()),('DELETE FROM u',())])
    run.assert_called_once();self.assertEqual(list(self.directory.glob('*.sql')),[])

class SQLiteImportModel:
 """Model documented whole-file rollback; not a claim about a real remote write."""
 def __init__(self,repo):
  self.db=sqlite3.connect(repo/'synthetic.sqlite',isolation_level=None);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA foreign_keys=ON')
  schema=Path(__file__).resolve().parents[1]/'weak-early-beta-gate/schema/new-a-private.sql';self.db.executescript(schema.read_text('utf8'))
  self.imports=0;self.calls=0;self.fail_import=None;self.fail_statement=0;self.timeout_after_commit=False;self.before_import=None;self.after_import=None
 def run(self,args,**kw):
  self.calls+=1
  if '--file' not in args:
   if not args[1].endswith('wrangler-query.cjs'):raise AssertionError('unexpected process prohibited')
   sql=Path(args[-1]).read_text('utf8');rows=[dict(row) for row in self.db.execute(sql).fetchall()]
   return SimpleNamespace(stdout=json.dumps([{'success':True,'results':rows,'meta':{}}]),stderr='',returncode=0)
  self.imports+=1;sql=Path(args[args.index('--file')+1]).read_text('utf8');statements=[];buffer=''
  for char in sql:
   buffer+=char
   if char==';' and sqlite3.complete_statement(buffer):statements.append(buffer);buffer=''
  if buffer.strip():raise AssertionError('incomplete model SQL')
  if self.before_import:callback=self.before_import;self.before_import=None;callback()
  self.db.execute('BEGIN')
  try:
   for i,statement in enumerate(statements):
    self.db.execute(statement)
    if self.imports==self.fail_import and i==self.fail_statement:raise sqlite3.OperationalError('SYNTHETIC_INJECTED_FAILURE')
   self.db.execute('COMMIT')
  except sqlite3.Error:
   self.db.execute('ROLLBACK');return SimpleNamespace(stdout='',stderr='synthetic import failure',returncode=1)
  if self.after_import:callback=self.after_import;self.after_import=None;callback()
  if self.timeout_after_commit:self.timeout_after_commit=False;raise subprocess.TimeoutExpired(['SYNTHETIC'],120)
  return SimpleNamespace(stdout='Using secrets defined in process.env\n'+ack(len(statements)),stderr='',returncode=0)

class PublicationOnLocalImport(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  cli=self.root/'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js';cli.parent.mkdir(parents=True);cli.write_text('// never executed','utf8')
  self.model=SQLiteImportModel(self.root);self.db=p.WranglerD1(self.root,self.root/'.cache/weak_early_beta/new-a-private/sql',execute=True);self.db.external=False
  self.patcher=patch.object(p.subprocess,'run',side_effect=self.model.run);self.patcher.start()
  self.folder=self.bundle('a');self.second=self.bundle('c')
 def tearDown(self):self.patcher.stop();self.model.db.close();self.tmp.cleanup()
 def bundle(self,suffix):
  folder=self.root/('bundle-'+suffix);folder.mkdir();cols={}
  for kind in ['episodes','intents','watches','presentation','current_daily','quotes']:
   raw=encode([{'synthetic':suffix}]);name=kind+'-000.json';(folder/name).write_text(raw,'utf8')
   cols[kind]=[dict(name=name,sha256=p.hash_text(raw),bytes=len(raw.encode()),rows=1)]
  manifest=dict(schema='A_BROWSER_PRIVATE_INPUT_V1',audience='EXISTING_CLOUD_OWNER_ONLY',strategy='A_BASE',source_version=suffix*64,collections={k:v for k,v in cols.items() if k!='quotes'},quotes=cols['quotes'],as_of='SYNTHETIC_SESSION',daily_snapshot_sha256='b'*64)
  self.save_manifest(folder,manifest);return folder
 def save_manifest(self,folder,manifest):
  raw=encode(manifest);(folder/'manifest.json').write_text(raw,'utf8');atomic_write(folder/'receipt.json',{'manifest_sha256':p.hash_text(raw)})
 def counts(self):return [self.model.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['new_a_private_datasets','new_a_private_parts']]
 def test_publish_immutable_parts_ready_then_pointer_and_replay_without_duplicates(self):
  first=p.publish_bundle(self.db,self.folder,expected_revision=0);counts=self.counts();imports=self.model.imports
  again=p.publish_bundle(self.db,self.folder,expected_revision=1)
  self.assertEqual(first['revision'],1);self.assertTrue(again['same_dataset_replay']);self.assertEqual(self.counts(),counts);self.assertEqual(self.model.imports,imports);self.assertEqual(p.pointer(self.db)['status'],'READY')
 def test_two_file_statements_rollback_together_on_mid_file_error(self):
  self.model.db.execute('CREATE TABLE synthetic(v INTEGER PRIMARY KEY)');self.model.fail_import=1;self.model.fail_statement=1
  with self.assertRaises(p.RemoteD1Error):self.db.batch([('INSERT INTO synthetic VALUES(1)',()),('INSERT INTO synthetic VALUES(2)',())])
  self.assertEqual(self.model.db.execute('SELECT count(*) FROM synthetic').fetchone()[0],0);self.assertEqual(self.model.imports,1)
 def test_failed_part_batch_leaves_staging_and_old_pointer_and_explicit_retry_is_safe(self):
  first=p.publish_bundle(self.db,self.folder,expected_revision=0);old=p.pointer(self.db);self.model.fail_import=self.model.imports+2;self.model.fail_statement=2
  with self.assertRaises(p.RemoteD1Error):p.stage_bundle(self.db,self.second,expected_revision=1)
  self.assertEqual(p.pointer(self.db),old);self.assertEqual(self.model.db.execute("SELECT count(*) FROM new_a_private_datasets WHERE status='STAGING'").fetchone()[0],1)
  self.model.fail_import=None;prepared=p.stage_bundle(self.db,self.second,expected_revision=1);counts=self.counts();again=p.stage_bundle(self.db,self.second,expected_revision=1)
  self.assertEqual(prepared['dataset_id'],again['dataset_id']);self.assertEqual(counts,self.counts());self.assertEqual(p.pointer(self.db)['dataset_id'],first['dataset_id'])
 def test_later_batch_failure_preserves_prior_parts_without_publication_then_explicit_resume(self):
  manifest=json.loads((self.folder/'manifest.json').read_text('utf8'))
  for i in range(1,4):
   name='quotes-%03d.json'%i;raw=encode([{'synthetic':i}]);(self.folder/name).write_text(raw,'utf8')
   manifest['quotes'].append(dict(name=name,sha256=p.hash_text(raw),bytes=len(raw.encode()),rows=1))
  self.save_manifest(self.folder,manifest);self.model.fail_import=3
  with self.assertRaises(p.RemoteD1Error):p.stage_bundle(self.db,self.folder,expected_revision=0)
  self.assertEqual(self.counts(),[1,8]);self.assertIsNone(p.pointer(self.db))
  self.assertEqual(self.model.db.execute('SELECT status FROM new_a_private_datasets').fetchone()[0],'STAGING')
  self.model.fail_import=None;prepared=p.stage_bundle(self.db,self.folder,expected_revision=0)
  self.assertEqual(self.counts(),[1,9]);self.assertIsNone(p.pointer(self.db))
  p.activate_prepared(self.db,prepared,expected_revision=0);self.assertEqual(p.pointer(self.db)['revision'],1)
 def test_corrupt_stored_part_never_becomes_ready_or_active(self):
  self.model.after_import=lambda:self.model.db.execute("CREATE TRIGGER corrupt AFTER INSERT ON new_a_private_parts BEGIN UPDATE new_a_private_parts SET payload_json='[]' WHERE dataset_id=NEW.dataset_id AND name=NEW.name; END")
  with self.assertRaisesRegex(ValueError,'part mismatch'):p.stage_bundle(self.db,self.folder,expected_revision=0)
  self.assertIsNone(p.pointer(self.db));self.assertEqual(self.model.db.execute('SELECT status FROM new_a_private_datasets').fetchone()[0],'STAGING')
 def test_pointer_not_changed_when_ready_update_fails(self):
  self.model.fail_import=3;self.model.fail_statement=0
  with self.assertRaises(p.RemoteD1Error):p.publish_bundle(self.db,self.folder,expected_revision=0)
  self.assertIsNone(p.pointer(self.db))
 def test_compare_and_swap_race_does_not_overwrite_other_dataset(self):
  a=p.stage_bundle(self.db,self.folder,expected_revision=0);b=p.stage_bundle(self.db,self.second,expected_revision=0)
  self.model.before_import=lambda:self.model.db.execute("INSERT INTO new_a_active_pointer VALUES('owner',?,1,'SYNTHETIC')",(b['dataset_id'],))
  with self.assertRaisesRegex(ValueError,'conflict'):p.activate_prepared(self.db,a,expected_revision=0)
  self.assertEqual(p.pointer(self.db)['dataset_id'],b['dataset_id']);self.assertEqual(p.pointer(self.db)['revision'],1)
 def test_update_cas_zero_rows_fails_readback_without_overwriting_new_revision(self):
  p.publish_bundle(self.db,self.folder,expected_revision=0);prepared=p.stage_bundle(self.db,self.second,expected_revision=1)
  self.model.before_import=lambda:self.model.db.execute('UPDATE new_a_active_pointer SET revision=revision+1')
  with self.assertRaisesRegex(ValueError,'conflict'):p.activate_prepared(self.db,prepared,expected_revision=1)
  self.assertEqual(p.pointer(self.db)['revision'],2);self.assertNotEqual(p.pointer(self.db)['dataset_id'],prepared['dataset_id'])
 def test_wrong_revision_even_for_same_target_never_yields_success(self):
  p.publish_bundle(self.db,self.folder,expected_revision=0);prepared=p.stage_bundle(self.db,self.second,expected_revision=1)
  self.model.after_import=lambda:self.model.db.execute('UPDATE new_a_active_pointer SET revision=revision+1')
  with self.assertRaisesRegex(ValueError,'conflict'):p.activate_prepared(self.db,prepared,expected_revision=1)
  self.assertEqual(p.pointer(self.db)['revision'],3)
 def test_commit_then_timeout_is_uncertain_no_retry_then_explicit_reconcile_is_idempotent(self):
  prepared=p.stage_bundle(self.db,self.folder,expected_revision=0);before=self.model.imports;self.model.timeout_after_commit=True
  with self.assertRaises(subprocess.TimeoutExpired):p.activate_prepared(self.db,prepared,expected_revision=0)
  self.assertEqual(self.model.imports,before+1);self.assertEqual(p.pointer(self.db)['revision'],1)
  receipt=p.activate_prepared(self.db,prepared,expected_revision=0);self.assertTrue(receipt['same_dataset_replay']);self.assertEqual(self.model.imports,before+1);self.assertEqual(p.pointer(self.db)['revision'],1)
 def test_bad_ack_after_commit_has_no_automatic_replay(self):
  prepared=p.stage_bundle(self.db,self.folder,expected_revision=0);actual=self.model.run
  def partial(args,**kw):
   result=actual(args,**kw)
   if '--file' in args:result.stdout=ack(0)
   return result
  before=self.model.imports
  with patch.object(p.subprocess,'run',side_effect=partial),self.assertRaises(p.RemoteD1Error):p.activate_prepared(self.db,prepared,expected_revision=0)
  self.assertEqual(self.model.imports,before+1);self.assertEqual(p.pointer(self.db)['revision'],1)
 def test_rollback_reads_exact_revision_and_preserves_immutable_records(self):
  first=p.publish_bundle(self.db,self.folder,expected_revision=0);p.publish_bundle(self.db,self.second,expected_revision=1);counts=self.counts()
  result=p.rollback_pointer(self.db,first['dataset_id'],2);self.assertEqual(result['revision'],3);self.assertEqual(self.counts(),counts)
  before=self.model.imports
  with self.assertRaisesRegex(ValueError,'conflict'):p.rollback_pointer(self.db,first['dataset_id'],2)
  self.assertEqual(self.model.imports,before);self.assertEqual(p.pointer(self.db)['revision'],3)
 def test_rollback_post_read_race_fails_instead_of_returning_wrong_revision(self):
  first=p.publish_bundle(self.db,self.folder,expected_revision=0);p.publish_bundle(self.db,self.second,expected_revision=1)
  self.model.after_import=lambda:self.model.db.execute('UPDATE new_a_active_pointer SET revision=revision+1')
  with self.assertRaisesRegex(ValueError,'readback'):p.rollback_pointer(self.db,first['dataset_id'],2)
  self.assertEqual(p.pointer(self.db)['revision'],4)
 def test_rollback_invalid_revision_rejected_before_any_database_operation(self):
  for revision in [0,-1,True,'2']:
   before=self.model.calls
   with self.subTest(revision=revision),self.assertRaisesRegex(ValueError,'explicit'):p.rollback_pointer(self.db,'SYNTHETIC',revision)
   self.assertEqual(self.model.calls,before)

if __name__=='__main__':unittest.main()
