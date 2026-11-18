"""既存本人認証の初回受入記録。設定を変更/秘密を取得する機能は持たない。"""
from pathlib import Path
from .files import file_sha
def validate_activation(value,repo,*,dependency_reader=None,worker_reader=None):
 if value.get('schema')!='NEW_A_OWNER_ACTIVATION_V1' or value.get('active') is not True or value.get('external_actions_approved') is not True or value.get('strategy')!='A_BASE':raise ValueError('new-A activation not approved')
 evidence=value.get('owner_acceptance',{})
 if evidence.get('continuing_acceptance') is not None:
  from .continuing_acceptance import validate_evidence
  validate_evidence(evidence,repo,dependency_reader=dependency_reader,worker_reader=worker_reader)
 elif any(evidence.get(k) is not True for k in ['actual_owner_allowed','anonymous_denied','nonowner_denied','private_direct_paths_denied','existing_auth_unchanged']):raise ValueError('actual owner acceptance incomplete')
 for path,h in evidence.get('auth_source_hashes',{}).items():
  p=(Path(repo)/path).resolve()
  if not p.is_relative_to(Path(repo).resolve()) or p.suffix not in ['.ts','.mjs'] or file_sha(p)!=h:raise ValueError('accepted owner wrapper changed')
 if not evidence.get('auth_source_hashes'):raise ValueError('owner wrapper hash proof absent')
 return value
