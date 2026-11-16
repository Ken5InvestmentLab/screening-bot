import contextlib,io,json,unittest
from weak_early_beta.progress import recorded_phase
class DelayedProgress(unittest.TestCase):
 def test_arguments_and_return_identity_are_unchanged(self):
  value=object();arguments=[]
  @recorded_phase('synthetic-normalization')
  def original(a,*,b):arguments.append((a,b));return value
  output=io.StringIO()
  with contextlib.redirect_stderr(output):actual=original(value,b=value)
  self.assertIs(actual,value);self.assertEqual(arguments,[(value,value)]);rows=[json.loads(v) for v in output.getvalue().splitlines()];self.assertEqual([r['event'] for r in rows],['started','finished']);self.assertTrue(all(set(r)=={'identity','stage','event','elapsed_seconds','cpu_seconds'} for r in rows))
 def test_exact_exception_preserved_without_argument_or_secret_output(self):
  exception=ValueError('SYNTHETIC SECRET MUST NOT BE LOGGED')
  @recorded_phase('synthetic-normalization')
  def original(value):raise exception
  output=io.StringIO()
  with contextlib.redirect_stderr(output),self.assertRaises(ValueError) as caught:original('SYNTHETIC PRIVATE VALUE')
  self.assertIs(caught.exception,exception);self.assertNotIn('SECRET',output.getvalue());self.assertNotIn('PRIVATE VALUE',output.getvalue());self.assertEqual([json.loads(v)['event'] for v in output.getvalue().splitlines()],['started','failed'])
if __name__=='__main__':unittest.main()
