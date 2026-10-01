"""Render metadata-only Cloud research dashboard; never fit or select models."""
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT/'research/cloud_full_search_20261001'
CACHE = ROOT/'.cache/cloud_full_search_v2_20261001'

def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def render():
    info = read(CACHE/'prepared.json')
    records = []
    for stage in ('screen', 'refined'):
        for path in sorted((CACHE/stage).glob('*.json')):
            record = read(path)
            if record['contract'] != info['hashes']:
                raise RuntimeError('mixed dashboard source contracts')
            records.append({'stage': stage, 'config': record['config'], 'best': record['best'], 'qualifying': record['qualifying']})
    final = read(CACHE/'final.json')
    audit = read(HERE/'independent_audit.json', {})
    if final and len(audit.get('final_trade_reaggregations', [])) != len(final['candidates']):
        raise RuntimeError('final dashboard requires final independent trade audit')
    source = {'records': records, 'final': final}
    screen_count = sum(r['stage']=='screen' for r in records)
    refine_count = sum(r['stage']=='refined' for r in records)
    fit_count = len(list((CACHE/'fits').glob('*/*.json')))
    updated = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(source, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    stage = read(CACHE/'progress.json', {}).get('phase', '準備中')
    audit_count = audit.get('receipt_count', 0)
    audit_winners = len(audit.get('dev_winner_reaggregations', []))
    status = '計算完了・採用未確認' if final else '探索途中・採用未確認'
    html = f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cloud 全面探索ダッシュボード</title><style>
:root{{color-scheme:light;--ink:#183046;--muted:#536878;--accent:#007f78;--line:#dce7e9}}
*{{box-sizing:border-box}}body{{margin:0;background:#f3f7f8;color:var(--ink);font:15px/1.65 system-ui,"Meiryo",sans-serif}}
main{{max-width:1280px;margin:auto;padding:32px 24px}}h1{{font-size:30px;margin:10px 0}}h2{{font-size:21px;margin-top:30px}}p{{margin:10px 0}}a{{color:#006d78}}small,.muted{{color:var(--muted)}}
.status{{display:inline-block;background:#fff2cf;border:1px solid #e6cb7b;border-radius:8px;padding:6px 14px;font-weight:700}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}}.card,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:20px}}
.card strong{{font-size:27px;display:block}}.card span{{color:var(--muted)}}.notice{{border-left:4px solid #d6a343;padding:10px 16px;background:#fff9e9}}
.filters{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}}label{{display:flex;flex-direction:column;gap:4px}}select{{font:inherit;border:1px solid #bbcdd3;border-radius:6px;padding:8px;background:white;color:var(--ink)}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}th{{background:#edf5f5}}th:first-child,td:first-child{{text-align:left}}.setting{{white-space:normal;min-width:240px;max-width:330px}}.good{{color:#00786d}}.bad{{color:#a33d35}}details{{max-width:330px;font-size:12px;white-space:normal}}summary{{cursor:pointer}}
.chart{{display:grid;gap:10px}}.barrow{{display:grid;grid-template-columns:minmax(210px,1fr) 2fr 70px;gap:10px;align-items:center}}.track{{background:#e6eeee;border-radius:4px;height:14px;overflow:hidden}}.fill{{height:100%;background:#007f78}}.negative{{background:#c26959}}progress{{width:100%;accent-color:var(--accent)}}footer{{margin-top:30px;color:var(--muted);font-size:13px}}
@media(max-width:720px){{main{{padding:20px 12px}}h1{{font-size:24px}}.cards{{grid-template-columns:repeat(2,1fr)}}.card,section{{padding:14px}}.barrow{{grid-template-columns:1fr 70px}}.barrow .track{{grid-column:1;grid-row:auto}}.barrow .value{{grid-column:2}}}}
</style><main><span class="status">{status}</span><h1>Cloud 全面探索</h1>
<p>良い条件を探すための研究記録。現行Cloudの価格上限・売却日・通知設定は変更していません。</p><small>保存時点：{escape(updated)} ／ 段階：{escape(stage)}</small>
<div class="cards"><div class="card"><strong>{screen_count} / 864</strong><span>4か月比較を完了した設定</span><progress value="{screen_count}" max="864"></progress></div><div class="card"><strong>{fit_count:,}</strong><span>保存済み月次学習</span></div><div class="card"><strong>{refine_count} / 最大12</strong><span>24か月再評価済み設定</span></div><div class="card"><strong>{audit_count:,} / {audit_winners}</strong><span>監査済み学習記録 / 損益候補</span></div></div>
<div class="notice">途中の首位は最善条件の確定ではありません。第一段階は2023年3・9月、2024年3・9月の比較です。2025年は新候補の固定後に検証しますが、前回研究で閲覧済み。2026年も閲覧済みの参考評価です。</div>
<h2>開発候補を比較</h2><section><p>各設定で品質基準を通過した政策・出口のうち、事前固定の順位指標が最高のものを表示します。基準：40件以上、各年15件以上、上位3利益を除いた平均がプラス、中央値0以上、大敗率30%以下、0.2%コスト後の平均がプラス。</p>
<div class="filters"><label>段階<select id="stage"><option value="screen">4か月の選抜</option><option value="refined">24か月の再評価</option></select></label><label>価格上限<select id="cap"><option value="all">すべて</option><option value="1000">1,000円以下</option><option value="1500">1,500円以下</option><option value="2000">2,000円以下</option><option value="3000">3,000円以下</option><option value="5000">5,000円以下</option><option value="0">上限なし</option></select></label><label>並べ替え<select id="sort"><option value="utility">事前固定の順位指標</option><option value="mean_pct">平均利益</option><option value="win_pct">勝率</option><option value="top3_ex_mean_pct">上位3利益除外後の平均</option></select></label></div>
<p id="scope" class="muted"></p><div class="scroll"><table><thead><tr><th>学習設定・検出条件</th><th>売却</th><th>件数</th><th>勝率</th><th>平均</th><th>中央値</th><th>大敗率</th><th>上位3除外平均</th><th>必要資金</th><th>順位指標</th></tr></thead><tbody id="results"></tbody></table></div>
<h2>平均と利益集中</h2><p class="muted">品質基準を通過した候補のみ。平均と上位3利益除外後の平均の差が大きいほど、大勝ちへの依存が強くなります。</p><div id="chart" class="chart"></div></section>
<h2>固定した候補の年別検証</h2><section id="validation"></section>
<h2>現行公開値との関係</h2><section><p>現行公開実績の参考水準：固有銘柄248件、平均5.4942%、勝率49.1935%、中央値0%、大敗率29.0323%。過去に固定された別集合の成績で、上の開発4か月と直接対応する比較値ではありません。</p><p>最終検証では同入力の現行V7と公開参考値の両方を示します。補正後の研究ベースラインだけを超えた候補は採用済みと扱いません。</p><p>損益は翌営業日始値で実100株を買い、保有中の分割・併合後の株数を使います。勝率は利益プラスの件数÷評価件数（0%を含む）、大敗は-10%以下。予定価格の欠落、隔離価格、端株精算未対応、約定困難登録は除外。必要資金は同日売却代金を購入前に使わない保守的な概算です。</p></section>
<footer><a href="PROTOCOL.md">事前固定手順</a> · <a href="PROGRESS.md">進捗記録</a> · <a href="independent_audit.json">監査の範囲</a> · <a href="../cloud_comparison_dashboard_20261001/index.html">前回の比較</a><p>有限の段階探索であり、数学的な全条件の最適を証明しません。実約定、配当、税、過去の銘柄母集団・企業行動の完全性は再現していません。</p></footer>
<script type="application/json" id="data">{payload}</script><script src="search-dashboard.js"></script></main></html>'''
    (HERE/'dashboard.html').write_text(html, encoding='utf-8')
    receipt = {'updated_at_utc': updated, 'cache': CACHE.relative_to(ROOT).as_posix(), 'screened_configs': screen_count,
               'refined_configs': refine_count, 'completed_fits': fit_count, 'final_present': bool(final),
               'generator_sha256': digest(Path(__file__)), 'dashboard_sha256': digest(HERE/'dashboard.html'),
               'javascript_sha256': digest(HERE/'search-dashboard.js'), 'prepared_manifest_sha256': digest(CACHE/'prepared.json'),
               'scope': 'Metadata-only rendering. No new model fits, candidate selection, or production changes.'}
    (HERE/'DASHBOARD_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))

if __name__=='__main__': render()
