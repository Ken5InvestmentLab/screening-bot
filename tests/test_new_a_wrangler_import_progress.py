"""Installed non-TTY file-import framing, synthetic acknowledgement only."""
import json,unittest
from weak_early_beta.new_a.publisher import parse_wrangler_import_ack,parse_wrangler_query_results,RemoteD1Error

def acknowledgement(count=1):
 return json.dumps([{'success':True,'finalBookmark':'SYNTHETIC_BOOKMARK','meta':{'rows_read':0,'rows_written':1},'results':[{'Total queries executed':count,'Rows read':0,'Rows written':1}]}])
PREFIX='├ Checking if file needs uploading\n│\n├ 🌀 Uploading synthetic-import.sql\n│ 🌀 Uploading complete.\n│\n'
class ImportProgressTests(unittest.TestCase):
 def test_installed_file_import_prefix_preserves_ack_semantics(self):self.assertEqual(parse_wrangler_import_ack(PREFIX+acknowledgement(),1),[[]])
 def test_cached_upload_still_requires_a_valid_full_receipt(self):self.assertEqual(parse_wrangler_import_ack('├ Checking if file needs uploading\n│\n'+acknowledgement(2),2),[[],[]])
 def test_plain_success_remains_compatible(self):self.assertEqual(parse_wrangler_import_ack(acknowledgement(),1),[[]])
 def test_query_path_never_accepts_import_progress(self):
  with self.assertRaises(RemoteD1Error):parse_wrangler_query_results(PREFIX+acknowledgement(),1)
 def test_arbitrary_prefix_suffix_or_multiple_documents_rejected(self):
  for text in ['UNKNOWN\n'+PREFIX+acknowledgement(),PREFIX+acknowledgement()+'\nUNKNOWN',PREFIX+acknowledgement()+acknowledgement()]:
   with self.subTest(text=text):
    with self.assertRaises(RemoteD1Error):parse_wrangler_import_ack(text,1)
 def test_missing_or_reordered_progress_rejected(self):
  for prefix in ['│\n','├ 🌀 Uploading synthetic.sql\n','├ Checking if file needs uploading\n│\n├ 🌀 Uploading synthetic.sql\n','├ Checking if file needs uploading\n├ Checking if file needs uploading\n│\n']:
   with self.subTest(prefix=prefix):
    with self.assertRaises(RemoteD1Error):parse_wrangler_import_ack(prefix+acknowledgement(),1)
 def test_wrong_count_or_receipt_shape_never_confirmed(self):
  for value in [acknowledgement(2),'[]','{}',json.dumps([{'success':True,'results':[]}])]:
   with self.assertRaises(RemoteD1Error):parse_wrangler_import_ack(PREFIX+value,1)
 def test_nonzero_and_authorization_errors_do_not_become_success(self):
  with self.assertRaisesRegex(RemoteD1Error,'operation_failed'):parse_wrangler_import_ack(PREFIX+acknowledgement(),1,returncode=1)
  with self.assertRaisesRegex(RemoteD1Error,'authorization_failed'):parse_wrangler_import_ack(PREFIX+acknowledgement(),1,returncode=1,stderr='[code: 7403]')
 def test_json_error_at_zero_exit_is_not_an_acknowledgement(self):
  with self.assertRaisesRegex(RemoteD1Error,'authorization_failed'):parse_wrangler_import_ack('├ Checking if file needs uploading\n│\n'+json.dumps({'error':{'code':7403}}),1)
 def test_color_and_existing_notices_only_are_compatible(self):self.assertEqual(parse_wrangler_import_ack('Using secrets defined in process.env\n'+ '\x1b[90m'+PREFIX+'\x1b[0m'+acknowledgement(),1),[[]])
 def test_unsupported_controls_and_empty_output_rejected(self):
  for text in ['', '\x1b[2K'+PREFIX+acknowledgement()]:
   with self.assertRaises(RemoteD1Error):parse_wrangler_import_ack(text,1)
if __name__=='__main__':unittest.main()
