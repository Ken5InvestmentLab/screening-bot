"""Export a stopped Cloud checkpoint. No training, network, or production writes."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
import zipfile

from verify_cloud_dot_handoff_20261002 import verify, safe_name

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/cloud_full_search_v2_20261001'
OUT = ROOT / '.cache/cloud_dot_handoff_20261002'
ZIP = OUT / 'cloud-dot-handoff-20261002.zip'
REQUIRED = ['.cache/weak_early_beta/split_preflight_20261001/normalized_daily.csv',
            '.cache/cloud_cap_corrected_v2_20261001',
            '.cache/cloud_full_search_v2_20261001', 'research/cloud_full_search_20261001']
SECRETS = [re.compile(p) for p in (
    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'github_pat_[A-Za-z0-9_]{40,}',
    rb'AIza[A-Za-z0-9_-]{35}',
    rb'https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]{30,}',
    rb'(?i)["\x27]?(?:api_key|client_secret|access_token|refresh_token|password)["\x27]?\s*[:=]\s*["\x27][A-Za-z0-9_./+-]{20,}["\x27]',
)]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def prohibited(path):
    names = [x.lower() for x in path.parts]
    return any(x.startswith('.env') or 'credential' in x or x in ('id_rsa', 'id_ed25519')
               or x.endswith(('.pem', '.key', '.pfx', '.p12')) for x in names)


def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def checkpoint():
    stop = json.loads((CACHE / 'STOP_REQUESTED.json').read_text(encoding='utf-8'))
    if stop.get('reason') != 'user_dot_handoff' or not stop.get('manual_resume_required'):
        raise RuntimeError('handoff stop is not set')
    import msvcrt
    with (CACHE / 'worker.lock').open('a+b') as f:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    progress = json.loads((CACHE / 'progress.json').read_text(encoding='utf-8'))
    info = json.loads((CACHE / 'prepared.json').read_text(encoding='utf-8'))
    audit = json.loads((ROOT / 'research/cloud_full_search_20261001/independent_audit.json').read_text(encoding='utf-8'))
    receipts = [json.loads(f.read_text(encoding='utf-8')) for f in sorted((CACHE / 'fits').glob('*/*.json'))]
    return dict(stopped=True, stop=stop, progress=progress, completed_fits=len(receipts),
                screened_configs=len(list((CACHE / 'screen').glob('*.json'))), total_configs=864,
                total_screen_fits=3456, refined_configs=len(list((CACHE / 'refined').glob('*.json'))),
                exported_configs=len(list((CACHE / 'all_policy_metrics').glob('*.csv'))),
                independent_audit_receipts=audit['receipt_count'],
                independent_audit_model_families=len(audit['independent_model_replays']),
                independent_dev_arithmetic_checks=len(audit['dev_winner_reaggregations']),
                zero_retained_fits=[{'config':r['config']['id'], 'month':r['month']} for r in receipts if r['retained_rows']==0],
                incomplete_or_failed_files=[str(f.relative_to(CACHE)).replace('\\', '/') for f in CACHE.rglob('*')
                                           if f.is_file() and any(s in f.name.lower() for s in ('failed','error','.partial','.tmp'))],
                prepared_versions=info['versions'], production_unchanged=True, automation_status='PAUSED')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if ZIP.exists():
        raise FileExistsError('existing ZIP preserved; choose a new output before repackaging')
    state = checkpoint()
    head, branch = git('rev-parse', 'HEAD'), git('branch', '--show-current')
    if branch != 'research/weak-early-beta':
        raise RuntimeError('wrong branch')
    runtime = ROOT / '.cache/weak_early_beta/venv/Scripts/python.exe'
    code = "import json,sys,platform,importlib.metadata as m; print(json.dumps(dict(sys_version=sys.version,platform=platform.platform(),packages={d.metadata['Name']:d.version for d in m.distributions()})))"
    env = json.loads(subprocess.check_output([str(runtime), '-c', code]))
    write_json('ENVIRONMENT.json', env)
    write_json('CHECKPOINT.json', state)
    write_json('GIT.json', {'branch':branch, 'code_snapshot_commit':head, 'status':git('status','--short'),
                           'remote':'https://github.com/Ken5InvestmentLab/screening-bot.git'})
    write_json('SOURCE_CONTRACT.json', json.loads((CACHE/'prepared.json').read_text(encoding='utf-8')))
    packages = env['packages']
    (OUT/'requirements-windows-full.txt').write_text(''.join(f'{n}=={v}\n' for n,v in sorted(packages.items())),encoding='utf-8')
    needed = ('numpy','pandas','scikit-learn','xgboost','joblib','scipy','threadpoolctl','requests','yfinance','matplotlib')
    (OUT/'requirements-linux-core.txt').write_text(''.join(f'{n}=={packages[n]}\n' for n in needed),encoding='utf-8')
    (OUT/'README.md').write_text(
        '# Cloud dot引き継ぎデータ\n\n'
        f'コード保存時ブランチ: `{branch}`\n\nコードコミット: `{head}`\n\n'
        f'停止確認済み。{state["completed_fits"]} fit、一次比較{state["screened_configs"]}/864設定。'
        f'独立監査は{state["independent_audit_receipts"]} receiptまで。最新fit全部のモデル再予測監査は未完了。\n\n'
        '同梱のSTOP_REQUESTEDと失効leaseは意図的な停止票です。人の指示なしに解除しません。'
        'Windowsのmsvcrtロック、Scripts/python.exe、sys.versionのMSC文字列を含む完全一致により、Linuxでそのまま新fitを実行できません。'
        'Linux移植は別cache名前空間と移植・互換性監査が必要です。既存V2のreceipt/runtime/code hashを書き換えて通してはいけません。'
        '既存モデル・配列・予測は消さず読取専用の原本として保持してください。\n\n'
        '展開後、リポジトリ直下で `python3 research/verify_cloud_dot_handoff_20261002.py .` を実行すると、標準ライブラリだけで全ファイルのSHA-256を検証できます。'
        '同梱の過去未コミット差分は既にコードコミットへ保存済みの参考資料であり、再適用しません。'
        '最新のReleaseリンク・ZIP SHA・再開手順は同じGitHubブランチの `research/CLOUD_DOT_HANDOFF_20261002.md` を参照してください。\n',encoding='utf-8')
    sources = set()
    for name in REQUIRED:
        p = ROOT/name
        if not p.exists(): raise FileNotFoundError(name)
        sources.update([p] if p.is_file() else (f for f in p.rglob('*') if f.is_file()))
    contract = json.loads((CACHE/'prepared.json').read_text(encoding='utf-8'))
    sources.update(ROOT/k for k in contract['hashes'])
    extra = ['.cache/cloud_full_search_resume_20261001.json', 'weak_early_beta/__init__.py',
             'research/export_cloud_full_search_20261001.py','research/cloud_full_search_independent_audit_20261001.py',
             'research/render_cloud_full_search_20261001.py','research/package_cloud_dot_handoff_20261002.py',
             'research/verify_cloud_dot_handoff_20261002.py','research/CLOUD_CORPORATE_ACTION_AUDIT_20261001.md',
             'research/cloud_cap_comparison_20261001/RESULTS.md','research/comparisons/cloud_exit_20261001/report.md',
             'research/cloud_production_reconciliation_20261001/REPORT.md']
    sources.update(ROOT/k for k in extra if (ROOT/k).is_file())
    payload = [(p,p.relative_to(ROOT).as_posix()) for p in sorted(sources)]
    payload.extend((p,'handoff/'+p.name) for p in sorted(OUT.iterdir()) if p.is_file() and p.suffix not in ('.zip','.sha256'))
    excluded, rows, snapshots = [], [], []
    total = 0
    with zipfile.ZipFile(ZIP,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for p,name in payload:
            safe_name(name)
            if prohibited(Path(name)):
                excluded.append(name); continue
            if p.is_symlink(): raise ValueError('symlink excluded: '+name)
            before=p.stat(); h=hashlib.sha256(); tail=b''
            with p.open('rb') as f,z.open(name,'w',force_zip64=True) as dest:
                for block in iter(lambda:f.read(8*1024*1024),b''):
                    scan=tail+block
                    if any(rx.search(scan) for rx in SECRETS):
                        raise ValueError('possible credential detected in '+name)
                    tail=scan[-512:]; h.update(block); dest.write(block)
            after=p.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise RuntimeError('source changed during export: '+name)
            rows.append({'path':name,'bytes':after.st_size,'sha256':h.hexdigest()})
            snapshots.append((p,after.st_size,after.st_mtime_ns));total+=after.st_size
            if after.st_size>30_000_000:
                print(json.dumps({'packed':name,'source_bytes_done':total}),flush=True)
        hashes={r['path']:r['sha256'] for r in rows}
        for name,expected in contract['hashes'].items():
            if hashes.get(name)!=expected: raise ValueError('frozen input mismatch: '+name)
        for name,expected in contract['output_hashes'].items():
            if hashes.get('.cache/cloud_full_search_v2_20261001/'+name)!=expected:
                raise ValueError('prepared output mismatch: '+name)
        for f in (CACHE/'fits').glob('*/*.json'):
            receipt=json.loads(f.read_text(encoding='utf-8'))
            for extension,expected in receipt['files'].items():
                name=f.with_suffix('.'+extension).relative_to(ROOT).as_posix()
                if hashes.get(name)!=expected: raise ValueError('fit artifact mismatch: '+name)
        manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'branch':branch,
                  'code_snapshot_commit':head,'files':rows,'excluded_secret_paths':excluded,
                  'required_roots':REQUIRED,'fit_artifact_hash_checks':state['completed_fits']}
        text=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
        z.writestr('handoff/MANIFEST.json',text)
    for p,size,mtime in snapshots:
        s=p.stat()
        if (s.st_size,s.st_mtime_ns)!=(size,mtime): raise RuntimeError('source changed after export')
    print(json.dumps({'phase':'verify_all_zip_entries','zip_bytes':ZIP.stat().st_size}),flush=True)
    report=verify(ZIP)
    h=hashlib.sha256()
    with ZIP.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    report.update(zip_name=ZIP.name,zip_bytes=ZIP.stat().st_size,zip_sha256=h.hexdigest(),
                  fit_artifact_hash_checks=state['completed_fits'],frozen_contract_hashes_verified=True,
                  source_unchanged=True,excluded_secret_paths=excluded)
    write_json('MANIFEST.json',manifest)
    write_json('VERIFICATION.json',report)
    (OUT/(ZIP.name+'.sha256')).write_text(h.hexdigest()+'  '+ZIP.name+'\n',encoding='ascii')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
