"""No credentials or network: query-result protocol and private CLI boundary tests."""
import json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from weak_early_beta.new_a.publisher import parse_wrangler_query_results,RemoteD1Error,WranglerD1,is_read_only_select

def response(*rows):return json.dumps([{'success':True,'results':r,'meta':{'changes':0}} for r in rows],ensure_ascii=False)

class QueryResponse(unittest.TestCase):
 def parse(self,text,count=1,**kw):return parse_wrangler_query_results(text,count,**kw)
 def reject(self,text,category,count=1,**kw):
  with self.assertRaises(RemoteD1Error) as caught:self.parse(text,count,**kw)
  self.assertEqual(str(caught.exception),category);return caught.exception
 def test_single_result_preserves_utf8_and_nested_json_text(self):
  rows=[{'label':'合成のみ','payload':'[{"success":false}]'}]
  self.assertEqual(self.parse(response(rows)),[rows])
 def test_multiple_results_preserve_order_and_empty_write_result(self):
  self.assertEqual(self.parse(response([], [{'connection_test':1}], [{'revision':2}]),3),[[],[{'connection_test':1}],[{'revision':2}]])
 def test_empty_query_rows_are_valid(self):self.assertEqual(self.parse(response([])),[[]])
 def test_known_env_notices_bom_sgr_and_whitespace(self):
  text='\ufeff\x1b[90mUsing secrets defined in process.env\x1b[0m\r\nUsing secrets defined in .env\n'+response([{'connection_test':1}])+'\n'
  self.assertEqual(self.parse(text),[[{'connection_test':1}]])
 def test_known_proxy_notice_and_known_trailing_notice(self):
  self.assertEqual(self.parse("Proxy environment variables detected. We'll use your proxy for fetch requests.\n"+response([])+'\nUsing secrets defined in process.env\n'),[[]])
 def test_nonzero_cannot_be_overridden_by_success_json(self):
  error=self.reject(response([]),'remote_d1_operation_failed_reconcile_before_retry',returncode=1,stderr='SYNTHETIC_PRIVATE_MARKER')
  self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',str(error));self.assertEqual(error.returncode,1)
 def test_nonzero_authorization_code_preserved_without_raw_error(self):
  for body in ['{"error":{"code":7403,"text":"SYNTHETIC_PRIVATE_MARKER"}}','[code: 7403] SYNTHETIC_PRIVATE_MARKER']:
   with self.subTest(body=body):
    error=self.reject('', 'remote_d1_authorization_failed_reconcile_before_retry',returncode=1,stderr=body)
    self.assertEqual(error.provider_codes,(7403,));self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',str(error))
 def test_empty_or_whitespace_output_rejected(self):
  for text in ['', ' \r\n','\ufeff']:
   with self.subTest(text=text):self.reject(text,'remote_d1_response_empty_reconcile_before_retry')
 def test_notices_only_rejected(self):self.reject('Using secrets defined in .env\n','remote_d1_response_unrecognized_reconcile_before_retry')
 def test_unknown_prefix_is_not_scanned_for_embedded_success(self):
  for prefix in ['Error: SYNTHETIC_PRIVATE_MARKER\n','[broken JSON\n','arbitrary diagnostic\n']:
   with self.subTest(prefix=prefix):self.reject(prefix+response([]),'remote_d1_response_unrecognized_reconcile_before_retry')
 def test_unknown_trailing_output_or_second_document_rejected(self):
  for tail in ['\nError: failure','\n'+response([]),'\n{"success":true}']:
   with self.subTest(tail=tail):self.reject(response([])+tail,'remote_d1_response_unrecognized_reconcile_before_retry')
 def test_truncated_invalid_and_non_json_constants_rejected(self):
  for text in ['[', '[{"success":true}] trailing', '[{"success":true,"results":[{"v":NaN}]}]']:
   with self.subTest(text=text):self.reject(text,'remote_d1_response_unrecognized_reconcile_before_retry')
 def test_duplicate_success_key_rejected(self):self.reject('[{"success":false,"success":true,"results":[]}]','remote_d1_response_unrecognized_reconcile_before_retry')
 def test_error_object_at_zero_exit_is_not_success(self):
  error=self.reject('{"error":{"code":7403,"text":"SYNTHETIC_PRIVATE_MARKER"}}','remote_d1_authorization_failed_reconcile_before_retry')
  self.assertEqual(error.provider_codes,(7403,))
 def test_generic_error_object_at_zero_exit_rejected(self):self.reject('{"error":{"text":"SYNTHETIC_PRIVATE_MARKER"}}','remote_d1_operation_unconfirmed')
 def test_authorization_failure_in_result_array_is_classified(self):
  error=self.reject('[{"success":false,"results":[],"errors":[{"code":7403,"message":"SYNTHETIC_PRIVATE_MARKER"}]}]','remote_d1_authorization_failed_reconcile_before_retry')
  self.assertEqual(error.provider_codes,(7403,));self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',str(error))
 def test_single_object_and_empty_or_partial_result_list_rejected(self):
  for text,count in [('[]',1),(response([]),2),(response([],[]),1),('{"success":true,"results":[]}',1),('null',1)]:
   with self.subTest(text=text,count=count):self.reject(text,'remote_d1_query_result_count_mismatch_reconcile_before_retry',count)
 def test_failed_item_or_error_field_rejected(self):
  for item in [{'success':False,'results':[]},{'success':1,'results':[]},{'success':True,'results':[],'errors':[{'code':1}]},{'success':True,'results':[],'error':'failure'},'wrong']:
   with self.subTest(item=item):self.reject(json.dumps([item]),'remote_d1_operation_unconfirmed')
 def test_import_summary_never_masquerades_as_query_rows(self):
  summary=[{'success':True,'results':[{'Total queries executed':2,'Rows read':1,'Rows written':0}],'finalBookmark':'SYNTHETIC'}]
  self.reject(json.dumps(summary),'remote_d1_import_summary_not_query_results_reconcile_before_retry')
 def test_missing_or_wrong_results_shape_rejected(self):
  for item in [{'success':True},{'success':True,'results':None},{'success':True,'results':{}},{'success':True,'results':[1]}]:
   with self.subTest(item=item):self.reject(json.dumps([item]),'remote_d1_query_result_shape_invalid_reconcile_before_retry')

class PrivateTransport(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.repo=Path(self.tmp.name)
  cli=self.repo/'weak-early-beta-gate/node_modules/wrangler/bin/wrangler.js';cli.parent.mkdir(parents=True);cli.write_text('// fixture','utf8')
  self.root=self.repo/'.cache/weak_early_beta/new-a-private/sql';self.db=WranglerD1(self.repo,self.root,execute=True)
 def tearDown(self):self.tmp.cleanup()
 def fake(self,stdout,code=0):return SimpleNamespace(stdout=stdout,stderr='',returncode=code)
 def test_query_uses_private_bridge_without_sql_in_os_arguments(self):
  value="合成?;値'";seen=[]
  def run(args,**kw):
   seen.append(args);self.assertEqual(kw['cwd'],self.repo/'weak-early-beta-gate');self.assertTrue(kw['capture_output']);self.assertEqual(len(args),4)
   self.assertTrue(args[1].endswith('wrangler-query.cjs'));self.assertNotIn('--command',args);self.assertNotIn(value,' '.join(args))
   self.assertEqual(Path(args[-1]).read_text('utf8'),"SELECT '合成?;値''' AS label;")
   return self.fake('Using secrets defined in process.env\n'+response([{'label':value}]))
  with patch('weak_early_beta.new_a.publisher.subprocess.run',side_effect=run):self.assertEqual(self.db.query('SELECT ? AS label',(value,)),[{'label':value}])
  self.assertEqual(len(seen),1);self.assertEqual(list(self.root.glob('*.sql')),[])
 def test_batch_count_matches_each_requested_statement(self):
  with patch('weak_early_beta.new_a.publisher.subprocess.run',return_value=self.fake(response([{'a':1}],[{'b':2}]))):
   self.assertEqual(self.db.batch([('SELECT 1',()),('SELECT 2',())]),[[{'a':1}],[{'b':2}]])
 def test_no_partial_result_return_or_retry(self):
  with patch('weak_early_beta.new_a.publisher.subprocess.run',return_value=self.fake(response([]))) as run:
   with self.assertRaises(RemoteD1Error):self.db.batch([('SELECT 1',()),('SELECT 2',())])
   run.assert_called_once();self.assertEqual(list(self.root.glob('*.sql')),[])
 def test_nonzero_and_timeout_clean_private_file_without_retry(self):
  for outcome in [self.fake('',1),subprocess.TimeoutExpired(['SYNTHETIC'],120)]:
   with self.subTest(outcome=type(outcome).__name__):
    kwargs={'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome}
    with patch('weak_early_beta.new_a.publisher.subprocess.run',**kwargs) as run:
     with self.assertRaises((RemoteD1Error,subprocess.TimeoutExpired)):self.db.query('SELECT 1')
     run.assert_called_once();self.assertEqual(list(self.root.glob('*.sql')),[])
 def test_empty_batch_has_no_provider_request(self):
  with patch('weak_early_beta.new_a.publisher.subprocess.run',return_value=self.fake('[]')) as run:
   self.assertEqual(self.db.batch([]),[]);run.assert_not_called()
 def test_existing_sql_parameter_and_size_guards_remain(self):
  with patch('weak_early_beta.new_a.publisher.subprocess.run') as run:
   with self.assertRaisesRegex(ValueError,'parameters mismatch'):self.db.query('SELECT ?')
   with self.assertRaisesRegex(ValueError,'budget'):self.db.query('SELECT '+('x'*90001))
   run.assert_not_called()

class ReadOnlyRouting(unittest.TestCase):
 def test_only_single_comment_free_select_is_eligible(self):
  for sql in ['SELECT 1'," SELECT 'semi; quote'' value -- /*' AS note",'select "quoted;name" FROM table_name','SELECT [odd;name] FROM t']:
   with self.subTest(sql=sql):self.assertTrue(is_read_only_select(sql))
 def test_mutation_mixed_comments_and_unterminated_quotes_use_legacy(self):
  for sql in ['INSERT INTO t VALUES (1)','UPDATE t SET v=1','DELETE FROM t','SELECT 1; UPDATE t SET v=1','WITH x AS (SELECT 1) SELECT * FROM x','SELECT 1 -- comment','SELECT 1 /* comment */',"SELECT 'broken",'PRAGMA user_version=2','SELECT 1\0']:
   with self.subTest(sql=sql):self.assertFalse(is_read_only_select(sql))

if __name__=='__main__':unittest.main()
