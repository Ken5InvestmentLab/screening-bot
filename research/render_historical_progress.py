"""Render a compact, local progress dashboard for the Cloud history backfill."""

from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "weak_early_beta/fundamental_worker/out/historical_backfill_manifest.json"
STATE = Path(__file__).with_name("historical_progress_state.json")
OUTPUT = Path(__file__).with_name("historical_progress_dashboard.html")


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def row(identity: str, detail: str, status: str) -> str:
    return (
        '<tr><th scope="row">'
        + escape(identity)
        + '</th><td>'
        + escape(detail)
        + '</td><td><span class="pill">'
        + escape(status)
        + "</span></td></tr>"
    )


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    records = manifest["records"]
    total = int(manifest["total_identities"])
    completed = sum(item["status"] == "complete" for item in records)
    pending = total - completed
    published = int(state["published_complete"])
    percent = 100 * completed / total if total else 0
    year_totals = Counter(item["signal_date"][:4] for item in records)
    year_complete = Counter(item["signal_date"][:4] for item in records if item["status"] == "complete")
    excluded = set(state.get("known_holds", []))
    active_ids = {item["identity"] for item in state.get("active", [])}
    active_pending = {item["identity"] for item in records if item["status"] != "complete" and item["identity"] in active_ids}
    active_items = [item for item in state.get("active", []) if item["identity"] in active_pending]
    next_records = [item for item in records if item["status"] != "complete" and item["identity"] not in excluded | active_ids][:8]
    stage_counts = Counter(item["status"] for item in active_items)
    later = pending - len(active_pending)
    active_rows = "".join(row(item["identity"], item["detail"], item["status"]) for item in active_items)
    next_rows = "".join(row(item["identity"], item.get("company_name", ""), "未着手") for item in next_records)
    year_rows = "".join(
        f'<tr><th scope="row">{escape(year)}</th><td>{year_complete[year]} / {year_totals[year]}</td>'
        f'<td><div class="year-track"><div class="year-fill" style="width:{100 * year_complete[year] / year_totals[year]:.1f}%"></div></div></td></tr>'
        for year in sorted(year_totals)
    )
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    root_url = "https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/"
    page = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Cloud 過去ファンダ分析・進捗</title>
<style>
  :root {{ color-scheme: light dark; font-family: system-ui, 'Yu Gothic', sans-serif; }}
  body {{ max-width: 1080px; margin: auto; padding: 28px 20px 44px; background: #f5f7fb; color: #17233a; }}
  h1 {{ margin: 0 0 5px; font-size: clamp(1.35rem, 3vw, 2rem); }}
  h2 {{ margin: 0 0 12px; font-size: 1.08rem; }}
  p {{ margin: 0; }}
  .muted {{ color: #5b697e; }}
  .top {{ display: flex; align-items: baseline; justify-content: space-between; gap: 14px; flex-wrap: wrap; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 23px 0 18px; }}
  .stat, section {{ background: #fff; border: 1px solid #dce3ee; border-radius: 14px; padding: 16px; }}
  .stat .value {{ display: block; font-size: clamp(1.4rem, 3vw, 2rem); font-weight: 700; font-variant-numeric: tabular-nums; }}
  .stat .label {{ color: #5b697e; font-size: .88rem; }}
  .layout {{ display: grid; grid-template-columns: 1.25fr 1fr; gap: 14px; }}
  section {{ margin-bottom: 14px; min-width: 0; }}
  .track, .year-track {{ height: 12px; border-radius: 999px; background: #e5eaf2; overflow: hidden; }}
  .fill, .year-fill {{ height: 100%; border-radius: inherit; background: #2464bb; }}
  .track {{ margin: 11px 0 8px; height: 16px; }}
  .year-track {{ min-width: 75px; }}
  .progress-copy {{ display: flex; justify-content: space-between; gap: 12px; font-variant-numeric: tabular-nums; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
  th, td {{ text-align: left; padding: 9px 5px; border-bottom: 1px solid #e8edf4; vertical-align: top; }}
  th {{ white-space: nowrap; font-weight: 600; }}
  tr:last-child th, tr:last-child td {{ border-bottom: none; }}
  .pill {{ display: inline-block; background: #e9f1ff; color: #174f9a; padding: 3px 8px; border-radius: 999px; white-space: nowrap; }}
  .meta {{ display: grid; gap: 8px; font-size: .9rem; }}
  .meta strong {{ display: inline-block; min-width: 115px; }}
  a {{ color: #1658aa; }}
  .note {{ margin-top: 8px; font-size: .86rem; }}
  .flow {{ text-align: center; }}
  .flow-node {{ border-radius: 12px; background: #edf3fd; padding: 12px; min-width: 0; }}
  .flow-node strong {{ display: block; font-size: 1.35rem; font-variant-numeric: tabular-nums; }}
  .flow-node small {{ display: block; color: #5b697e; }}
  .flow-row {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; max-width: 640px; margin: auto; }}
  .flow-arrow {{ line-height: 1; color: #5b697e; margin: 6px 0; font-size: 1.2rem; }}
  .flow-stages {{ display: flex; gap: 8px; align-items: center; justify-content: center; flex-wrap: wrap; margin-top: 14px; }}
  .flow-stages .flow-node {{ flex: 1 1 150px; max-width: 205px; }}
  .flow-stages .flow-arrow {{ transform: rotate(-90deg); margin: 0; }}
  @media (max-width: 760px) {{ .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .layout {{ grid-template-columns: 1fr; }} }}
  @media (max-width: 430px) {{ body {{ padding: 18px 12px; }} .stats {{ gap: 8px; }} .stat, section {{ padding: 12px; }} table {{ font-size: .82rem; }} th, td {{ padding: 7px 3px; }} .flow-stages .flow-node {{ flex-basis: 100%; max-width: none; }} .flow-stages .flow-arrow {{ transform: none; }} }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #101827; color: #e7edfa; }} .stat, section {{ background: #19253a; border-color: #31405b; }} .muted, .stat .label, .flow-node small {{ color: #b4c0d4; }} .track, .year-track {{ background: #34435e; }} .fill, .year-fill {{ background: #69a4ff; }} th, td {{ border-color: #31405b; }} .pill {{ background: #264576; color: #d4e7ff; }} .flow-node {{ background: #243855; }} a {{ color: #91bbff; }} }}
</style>
</head>
<body>
<div class="top"><div><h1>Cloud 過去ファンダ分析</h1><p class="muted">研究ブランチの履歴分析と beta Web 公開</p></div><p class="muted">更新 {escape(now)}</p></div>
<div class="stats" aria-label="進捗の要約">
  <div class="stat"><span class="value">{completed} / {total}</span><span class="label">分析完了</span></div>
  <div class="stat"><span class="value">{pending}</span><span class="label">未完了</span></div>
  <div class="stat"><span class="value">{published}</span><span class="label">Web公開済み</span></div>
  <div class="stat"><span class="value">{len(active_items)}</span><span class="label">進行中</span></div>
</div>
<section aria-label="全体進捗"><div class="progress-copy"><strong>全体進捗</strong><strong>{percent:.1f}%</strong></div><div class="track" role="progressbar" aria-label="分析完了率" aria-valuemin="0" aria-valuemax="{total}" aria-valuenow="{completed}"><div class="fill" style="width:{percent:.1f}%"></div></div><p class="muted note">公式IR / TDnet / JPX の本文を、各検出日16:15 JSTまでの情報として確認。</p></section>
<section class="flow" aria-label="件数の流れ">
  <h2>いまどこまで進んだか</h2>
  <div class="flow-node" style="max-width:210px;margin:auto"><strong>{total}件</strong><small>分析対象</small></div>
  <div class="flow-arrow" aria-hidden="true">↓</div>
  <div class="flow-row"><div class="flow-node"><strong>{completed}件</strong><small>分析完了</small></div><div class="flow-node"><strong>{pending}件</strong><small>未完了</small></div></div>
  <div class="flow-arrow" aria-hidden="true">↓</div>
  <div class="flow-row"><div class="flow-node"><strong>{len(active_pending)}件</strong><small>今回の調査対象</small></div><div class="flow-node"><strong>{later}件</strong><small>後続・保留</small></div></div>
  <div class="flow-stages" aria-label="今回の調査対象の段階"><div class="flow-node"><strong>{stage_counts['資料確認中']}件</strong><small>一次資料を調査中</small></div><div class="flow-arrow" aria-hidden="true">↓</div><div class="flow-node"><strong>{stage_counts['資料確認済み']}件</strong><small>一次資料確認済み</small></div><div class="flow-arrow" aria-hidden="true">↓</div><div class="flow-node"><strong>{stage_counts['候補作成中']}件</strong><small>Luna候補作成中</small></div><div class="flow-arrow" aria-hidden="true">↓</div><div class="flow-node"><strong>{stage_counts['監査完了']}件</strong><small>独立監査完了</small></div></div>
</section>
<div class="layout"><div>
  <section><h2>いま進めている銘柄</h2><table><thead><tr><th>検出日・コード</th><th>銘柄</th><th>状態</th></tr></thead><tbody>{active_rows}</tbody></table></section>
  <section><h2>次の未完了</h2><table><thead><tr><th>検出日・コード</th><th>銘柄</th><th>状態</th></tr></thead><tbody>{next_rows}</tbody></table></section>
</div><div>
  <section><h2>年別の完了状況</h2><table><thead><tr><th>年</th><th>完了 / 対象</th><th>進捗</th></tr></thead><tbody>{year_rows}</tbody></table></section>
  <section><h2>公開・検証</h2><div class="meta"><p><strong>次回反映</strong>{escape(state['release_plan'])}</p><p><strong>公開tag</strong>{escape(state['last_deploy_tag'])}</p><p><strong>公開状況</strong>{escape(state['deploy_status'])}</p><p><strong>リモートHEAD</strong><code>{escape(state['remote_head'])[:12]}</code></p><p><strong>Cloud</strong><a href="{root_url}">公開レポート</a></p><p><strong>Discord履歴投稿</strong>0件</p></div></section>
  <section><h2>既知の保留</h2><p class="muted">{escape(' / '.join(state.get('known_holds', [])))}</p><p class="muted note">確認済みの不足証拠を同じ方法で再探索しません。</p></section>
</div></div>
</body></html>
"""
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"{OUTPUT} | complete={completed}/{total} | published={published}")


if __name__ == "__main__":
    main()
