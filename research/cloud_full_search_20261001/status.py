"""Small progress receipt; reads metadata, never models or production writers."""
import json
from pathlib import Path
from datetime import datetime, timezone
import hashlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT/'.cache/cloud_full_search_v2_20261001'

def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

def render():
    fits = sorted((CACHE/'fits').glob('*/*.json'))
    screen = sorted((CACHE/'screen').glob('*.json'))
    refined = sorted((CACHE/'refined').glob('*.json'))
    latest = max(fits, key=lambda p: p.stat().st_mtime) if fits else None
    value = dict(updated_at_utc=datetime.now(timezone.utc).isoformat(), status='IN_PROGRESS',
                 production_unchanged=True, prepared=bool(read(CACHE/'prepared.json')),
                 parity=read(CACHE/'parity.json'), completed_fits=len(fits), screened_configs=len(screen),
                 total_configs=864, refined_configs=len(refined),
                 latest_fit=read(latest) if latest else None, progress=read(CACHE/'progress.json'),
                 usage_lease=read(CACHE/'usage_lease.json'), final=read(CACHE/'final.json'))
    if value['final']: value['status']='COMPLETE'
    if value['latest_fit']: value['latest_fit'].pop('contract', None)
    (HERE/'PROGRESS.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    parity = (value['parity'] or {}).get('status', '未完了')
    phase = (value['progress'] or {}).get('phase', '準備・本番処理一致確認')
    lines = ['# Cloud 全面探索の進捗', '', f"更新（UTC）: {value['updated_at_utc']}", '',
             f'状態: **{value["status"]}**。本番条件の変更なし。', '',
             f'- 入力準備: {"完了" if value["prepared"] else "処理中"}',
             f'- 同一入力での本番再計算: {parity}',
             f'- 現在の段階: {phase}', f'- 完了fit: {len(fits)}',
             f'- 4月の開発比較を完了した学習設定: {len(screen)} / 864',
             f'- 全24月・検出政策の再評価完了: {len(refined)}', '',
             '途中経過から最善条件や採用可否を断定しません。選抜手順と限界は [PROTOCOL.md](PROTOCOL.md) に記載しています。', '',
             '再現コマンド（リポジトリ直下、PowerShell）:', '', '```powershell',
             "& '.cache/weak_early_beta/venv/Scripts/python.exe' -B -m unittest discover -s research/cloud_full_search_20261001 -p test_search.py -v",
             "& '.cache/weak_early_beta/venv/Scripts/python.exe' -B research/cloud_full_search_20261001/prepare.py",
             "& '.cache/weak_early_beta/venv/Scripts/python.exe' -B research/cloud_full_search_20261001/parity.py",
             "& '.cache/weak_early_beta/venv/Scripts/python.exe' -B research/cloud_full_search_20261001/search.py --max-fits 8 --max-seconds 480",
             "py -3 -B research/cloud_full_search_20261001/status.py", '```', '',
             '準備・再計算・探索前に使用量を確認して15分のusage leaseを保存します。leaseが無い/期限切れ/STOP_REQUESTEDなら新しいfitを開始しません。']
    (HERE/'PROGRESS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('latest_fit','final')}, ensure_ascii=False))

if __name__ == '__main__': render()
