"""Standalone user-friendly HTML report for the Weak+Early beta."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from .config import (
    BETA_IDENTITY,
    COMBINED_SELECTOR_IDS,
    ENDPOINT_LABEL,
    SELECTOR_ORDER,
    selector_info,
)
from .metrics import build_metrics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "weak_early_beta_latest.html"
DEFAULT_METRICS = ROOT / "weak_early_beta" / "state" / "metrics.csv"


def _pct(value, signed: bool = False) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):+,.2f}%" if signed else f"{float(value):,.2f}%"


def _yen(value) -> str:
    if pd.isna(value):
        return "—"
    return f"¥{float(value):+,.0f}"


def _price(value) -> str:
    if pd.isna(value):
        return "—"
    return f"¥{float(value):,.0f}"


def _date(value) -> str:
    return "—" if pd.isna(value) or not str(value).strip() else f"{pd.Timestamp(value):%Y-%m-%d}"


def _overall_rows(metrics: pd.DataFrame) -> str:
    if metrics.empty:
        return '<tr><td colspan="18">集計対象がありません</td></tr>'
    total_period = max(metrics["period"].astype(str), key=len)
    rows = []
    total = metrics[
        metrics["period"].eq(total_period) & metrics["selector_id"].isin(SELECTOR_ORDER)
    ].sort_values(
        ["cash_pl_100_yen", "mean_pct"], ascending=False, kind="mergesort"
    )
    for rank, (_, row) in enumerate(total.iterrows(), start=1):
        rows.append(
            "<tr>"
            f"<td>{rank}位</td><th>{html.escape(row['selector_name'])}</th>"
            f"<td>{int(row['n'])}</td><td>{int(row['pending'])}</td>"
            f"<td>{_pct(row['mean_pct'], True)}</td><td>{_pct(row['median_pct'], True)}</td>"
            f"<td>{_pct(row['win_pct'])}</td><td>{_pct(row['plus10_pct'])}</td>"
            f"<td>{_pct(row['plus20_pct'])}</td><td>{_pct(row['minus10_pct'])}</td>"
            f"<td>{_pct(row['minus20_pct'])}</td><td>{_pct(row['max_up_pct'], True)}</td>"
            f"<td>{_pct(row['max_down_pct'], True)}</td><td>{_pct(row['top3_ex_mean_pct'], True)}</td>"
            f"<td>{_yen(row['cash_pl_100_yen'])}</td><td>{_price(row['required_capital_yen'])}</td>"
            f"<td>{_pct(row['capital_return_pct'], True)}</td><td>{_pct(row['simple_annualized_pct'], True)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _yearly_rows(metrics: pd.DataFrame) -> str:
    rows = []
    if metrics.empty:
        return '<tr><td colspan="15">集計対象がありません</td></tr>'
    total_period = max(metrics["period"].astype(str), key=len)
    yearly = metrics[
        ~metrics["period"].eq(total_period) & metrics["selector_id"].isin(SELECTOR_ORDER)
    ]
    for period, group in yearly.groupby("period", sort=True):
        ranked = group.sort_values(
            ["cash_pl_100_yen", "mean_pct"], ascending=False, kind="mergesort"
        )
        for rank, row in enumerate(ranked.itertuples(), start=1):
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(period))}</td><td>{rank}位</td><th>{html.escape(row.selector_name)}</th>"
                f"<td>{row.n}</td><td>{_pct(row.mean_pct, True)}</td>"
                f"<td>{_pct(row.median_pct, True)}</td><td>{_pct(row.win_pct)}</td>"
                f"<td>{_pct(row.plus10_pct)}</td><td>{_pct(row.plus20_pct)}</td>"
                f"<td>{_pct(row.minus10_pct)}</td><td>{_pct(row.minus20_pct)}</td>"
                f"<td>{_yen(row.cash_pl_100_yen)}</td><td>{_price(row.required_capital_yen)}</td>"
                f"<td>{_pct(row.capital_return_pct, True)}</td><td>{_pct(row.simple_annualized_pct, True)}</td>"
                "</tr>"
            )
    return "".join(rows)


def _combined_rows(metrics: pd.DataFrame) -> str:
    combined = metrics[metrics["selector_id"].isin(COMBINED_SELECTOR_IDS)].copy()
    if combined.empty:
        return '<tr><td colspan="17">集計対象がありません</td></tr>'
    total_period = max(metrics["period"].astype(str), key=len)
    order = {period: index for index, period in enumerate(sorted(combined["period"].astype(str).unique()))}
    order[total_period] = 999
    combined["_order"] = combined["period"].map(order)
    combined["_mode_order"] = combined["selector_id"].map(
        {selector_id: index for index, selector_id in enumerate(COMBINED_SELECTOR_IDS)}
    )
    rows = []
    for row in combined.sort_values(["_order", "_mode_order"]).itertuples():
        label = f"{row.period} 合計" if str(row.period) == total_period else str(row.period)
        rows.append(
            "<tr>"
            f"<th>{html.escape(label)}</th><th>{html.escape(row.selector_name)}</th>"
            f"<td>{row.n}</td><td>{row.pending}</td>"
            f"<td>{_pct(row.mean_pct, True)}</td><td>{_pct(row.median_pct, True)}</td>"
            f"<td>{_pct(row.win_pct)}</td><td>{_pct(row.plus10_pct)}</td>"
            f"<td>{_pct(row.plus20_pct)}</td><td>{_pct(row.minus10_pct)}</td>"
            f"<td>{_pct(row.minus20_pct)}</td><td>{_pct(row.max_up_pct, True)}</td>"
            f"<td>{_pct(row.max_down_pct, True)}</td><td>{_yen(row.cash_pl_100_yen)}</td>"
            f"<td>{_price(row.required_capital_yen)}</td><td>{_pct(row.capital_return_pct, True)}</td>"
            f"<td>{_pct(row.simple_annualized_pct, True)}</td></tr>"
        )
    return "".join(rows)


def _condition_cards() -> str:
    cards = []
    for selector_id in SELECTOR_ORDER:
        info = selector_info(selector_id)
        cards.append(
            '<article class="condition-card">'
            f"<span class=\"condition-id\">{html.escape(info.short_name)}</span>"
            f"<h3>{html.escape(info.display_name)}</h3>"
            f"<p>{html.escape(info.feature_summary)}</p>"
            f"<p class=\"subtle\">{html.escape(info.selection_summary)}</p>"
            "</article>"
        )
    return "".join(cards)


def _detection_rows(ledger: pd.DataFrame) -> str:
    if ledger.empty:
        return '<tr><td colspan="9">検出履歴がありません</td></tr>'
    data = ledger.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    rows = []
    grouped = data.groupby(["signal_date", "symbol"], sort=False)
    for (signal_date, symbol), group in sorted(grouped, key=lambda item: item[0], reverse=True):
        first = group.iloc[0]
        selectors = group["selector_id"].astype(str).tolist()
        badges = "".join(
            f'<span class="badge">{html.escape(selector_info(s).short_name)}</span>'
            for s in selectors
        )
        units = len(selectors)
        badges += f'<small>条件別積上げ: {units}ユニット / {units * 100}株</small>'
        name = str(first.get("company_name", "") or "").strip()
        gross = pd.to_numeric(group["gross_return"], errors="coerce").dropna()
        cash = pd.to_numeric(group["one_hundred_shares_pl_yen"], errors="coerce").dropna()
        status = "確定" if not gross.empty else ("保有中" if str(first["status"]) == "entered" else "寄付待ち")
        status_class = "mature" if not gross.empty else "pending"
        fundamental_url = next(
            (str(x) for x in group["fundamental_discord_url"] if pd.notna(x) and str(x).strip()), ""
        )
        fundamental_html = next(
            (str(x) for x in group["fundamental_html"] if pd.notna(x) and str(x).strip()), ""
        )
        actions = ""
        if fundamental_html:
            safe_analysis = html.escape(fundamental_html).replace("\n", "<br>")
            actions = (
                '<button class="fundamental-toggle" type="button">ファンダ分析</button>'
                f'<div class="fundamental-detail" hidden>{safe_analysis}</div>'
            )
        elif fundamental_url:
            actions = f'<a class="button-link" href="{html.escape(fundamental_url)}">ファンダ分析</a>'
        rows.append(
            f'<tr data-selectors="{html.escape(" ".join(selectors))}" data-symbol="{html.escape(str(symbol))}">'
            f"<td>{signal_date:%Y-%m-%d}</td>"
            f"<th><span class=\"symbol\">{html.escape(str(symbol))}</span> {html.escape(name)}<div class=\"actions\">{actions}</div></th>"
            f"<td>{badges}</td><td><span class=\"status {status_class}\">{status}</span></td>"
            f"<td>{_date(first['entry_date'])}<small>{_price(first['entry_open'])}</small></td>"
            f"<td>{_date(first['fifth_xtks_exit_date'])}<small>{_price(first['fifth_xtks_exit_close'])}</small></td>"
            f"<td class=\"number\">{_pct(gross.iloc[0] * 100, True) if not gross.empty else '—'}</td>"
            f"<td class=\"number\">{_yen(cash.iloc[0]) if not cash.empty else '—'}</td>"
            f"<td><a href=\"https://www.tradingview.com/chart/?symbol=TSE%3A{html.escape(str(symbol))}\">チャート</a></td>"
            "</tr>"
        )
    return "".join(rows)


def render_report(ledger: pd.DataFrame, metrics: pd.DataFrame, generated_at: pd.Timestamp) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    total_period = max(metrics["period"].astype(str), key=len) if not metrics.empty else "—"
    total = metrics[metrics["period"].eq(total_period)] if not metrics.empty else pd.DataFrame()
    best = total.sort_values("cash_pl_100_yen", ascending=False).iloc[0] if not total.empty else None
    detection_count = len(ledger)
    unique_count = ledger.groupby(["signal_date", "symbol"]).ngroups if not ledger.empty else 0
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Weak+Early スコアリング ベータ</title>
<style>
:root{{--bg:#f4f7fb;--panel:#fff;--ink:#172033;--muted:#60708a;--line:#dbe3ee;--blue:#2255d8;--cyan:#0d8795;--good:#08744f;--warn:#a25b00;--shadow:0 12px 32px rgba(25,45,80,.08)}}
:root[data-theme="dark"]{{--bg:#0e1420;--panel:#172131;--ink:#edf4ff;--muted:#9fb0c7;--line:#2b3b51;--blue:#88aaff;--cyan:#5bd0d4;--good:#65d6a7;--warn:#ffc56b;--shadow:none}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Noto Sans JP",sans-serif}}a{{color:var(--blue)}}
.topbar{{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--panel) 94%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}}
.nav{{max-width:1440px;margin:auto;padding:12px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}}.brand{{font-weight:850;margin-right:auto}}button,select,input{{font:inherit}}button{{cursor:pointer}}
.theme{{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:999px;padding:7px 12px}}main{{max-width:1440px;margin:auto;padding:28px 20px 60px}}
.hero{{display:grid;grid-template-columns:2fr 1fr;gap:18px;align-items:stretch}}.panel{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:var(--shadow);margin-bottom:20px}}
.eyebrow{{color:var(--cyan);font-weight:800;letter-spacing:.06em}}h1{{font-size:clamp(28px,5vw,52px);line-height:1.12;margin:.15em 0}}h2{{margin:0 0 16px;font-size:22px}}h3{{margin:8px 0}}.lead{{font-size:17px;color:var(--muted);max-width:62ch}}
.kpis{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.kpi{{background:var(--bg);border-radius:14px;padding:14px}}.kpi b{{display:block;font-size:24px}}.kpi small,.subtle,small{{display:block;color:var(--muted)}}
.condition-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}}.condition-card{{border:1px solid var(--line);border-radius:14px;padding:16px;background:linear-gradient(150deg,var(--panel),var(--bg))}}.condition-id,.badge{{display:inline-flex;border-radius:999px;background:color-mix(in srgb,var(--blue) 12%,var(--panel));color:var(--blue);padding:3px 8px;font-size:12px;font-weight:750;margin:2px}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:14px}}table{{width:100%;border-collapse:collapse;min-width:1050px;background:var(--panel)}}th,td{{border-bottom:1px solid var(--line);padding:10px 9px;text-align:right;white-space:nowrap}}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}thead th{{position:sticky;top:0;background:var(--panel);z-index:1;font-size:12px;color:var(--muted)}}
.filters{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}.filters input,.filters select{{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:9px;padding:9px 11px}}.status{{font-weight:750}}.status.mature{{color:var(--good)}}.status.pending{{color:var(--warn)}}.number{{font-variant-numeric:tabular-nums}}.symbol{{font-size:17px}}.actions{{margin-top:5px}}.button-link,.fundamental-toggle{{display:inline-flex;border:1px solid var(--line);background:var(--bg);color:var(--blue);text-decoration:none;border-radius:7px;padding:4px 8px}}.fundamental-detail{{white-space:normal;min-width:320px;max-width:650px;margin-top:8px;padding:12px;background:var(--bg);border-radius:10px}}
.note{{color:var(--muted);font-size:13px}}footer{{color:var(--muted);text-align:center;padding:28px}}
@media(max-width:1000px){{.hero{{grid-template-columns:1fr}}.condition-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:620px){{main{{padding:18px 12px 50px}}.panel{{padding:16px;border-radius:14px}}.condition-grid{{grid-template-columns:1fr}}.kpis{{grid-template-columns:1fr 1fr}}}}
</style><script src="/report-interactions.js" defer></script></head>
<body><header class="topbar"><nav class="nav"><span class="brand">Weak+Early ベータ</span><a href="#performance">成績</a><a href="#conditions">5つの条件</a><a href="#history">検出履歴</a><button class="theme" id="theme-toggle" type="button">表示切替</button></nav></header>
<main><section class="hero"><div class="panel"><span class="eyebrow">TRADINGVIEW-FREE / BETA</span><h1>引け後に選び、<br>翌営業日の寄り付きへ。</h1><p class="lead">因果的に生成したTail候補へ、特徴の異なる5条件を適用する独立ベータ版です。現行のStable・Sniper・Megaとは別系統で、条件判定後の銘柄だけを通知します。</p><p class="note">評価契約: {html.escape(ENDPOINT_LABEL)}。投資助言ではありません。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>条件別記録</small><b>{detection_count:,}</b></div><div class="kpi"><small>実銘柄・日付</small><b>{unique_count:,}</b></div><div class="kpi"><small>集計期間</small><b>{html.escape(total_period)}</b></div><div class="kpi"><small>100株損益 首位</small><b>{html.escape(str(best['selector_name'])) if best is not None else '—'}</b></div></div><p class="note">同じ銘柄が複数条件に該当することがあります。実銘柄数は重複を1件として数えています。</p></aside></section>
<section class="panel" id="performance"><h2>全期間の成績</h2><p class="note">順位は100株ずつ売買した累計損益額順です。参考元金は同時保有を賄うために必要だった最大金額、元金増加率は累計損益÷参考元金です。単純年率はそれを対象年数で割った値で、複利・売買コスト・税金は含みません。延べ投入額は表示していません。</p><div class="table-wrap"><table><thead><tr><th>順位</th><th>条件</th><th>確定n</th><th>未確定</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th><th>Top3除外平均</th><th>100株損益</th><th>参考元金</th><th>元金増加率</th><th>単純年率</th></tr></thead><tbody>{_overall_rows(metrics)}</tbody></table></div></section>
<section class="panel"><h2>全5条件の合計成績</h2><p class="note">「条件別積上げ」は1条件につき100株とし、3条件重複なら300株として集計します。「銘柄均等」は同一シグナル日×同一銘柄を100株に固定した比較用です。重複は条件同士が完全に独立とは限らないため、両方を併記します。</p><div class="table-wrap"><table><thead><tr><th>期間</th><th>配分方式</th><th>確定ユニット</th><th>未確定</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th><th>100株ユニット損益</th><th>参考元金</th><th>元金増加率</th><th>単純年率</th></tr></thead><tbody>{_combined_rows(metrics)}</tbody></table></div></section>
<section class="panel"><h2>年別の成績</h2><div class="table-wrap"><table><thead><tr><th>年</th><th>順位</th><th>条件</th><th>n</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>100株損益</th><th>参考元金</th><th>元金増加率</th><th>単純年率</th></tr></thead><tbody>{_yearly_rows(metrics)}</tbody></table></div></section>
<section class="panel" id="conditions"><h2>5つの条件</h2><div class="condition-grid">{_condition_cards()}</div><p class="note">共通gateは市場5日中央値リターン≤0、候補10日リターン≤0.5735294117647058。Tailは月初前に成熟したlabelだけで学習し、月次学習行数30,000以上、tail CDF≥0.999です。内部IDと閾値は復元版から変更していません。</p></section>
<section class="panel" id="history"><h2>検出履歴</h2><div class="filters"><input id="symbol-filter" inputmode="numeric" placeholder="証券コード 1234"><select id="selector-filter"><option value="">すべての条件</option>{''.join(f'<option value="{s}">{html.escape(selector_info(s).display_name)}</option>' for s in SELECTOR_ORDER)}</select></div><div class="table-wrap"><table id="detection-table"><thead><tr><th>シグナル日</th><th>銘柄</th><th>該当条件</th><th>状態</th><th>エントリー</th><th>5営業日目</th><th>騰落率</th><th>100株損益</th><th>操作</th></tr></thead><tbody>{_detection_rows(ledger)}</tbody></table></div></section>
<section class="panel"><h2>ベータ版について</h2><p>これからの検出は、専用Discordへ通知し、別の専用チャンネルでファンダ分析を行う前提です。過去分はトークン消費を抑えるため、ファンダ分析を一括生成しません。分析が登録された銘柄だけ履歴内にボタンが表示されます。</p><p class="note">Identity: {BETA_IDENTITY} / Generated: {generated:%Y-%m-%d %H:%M:%S JST}</p></section></main><footer>Weak+Early Scoring Beta — research-only parallel test</footer></body></html>'''


def write_report(
    ledger: pd.DataFrame,
    report_path: Path = DEFAULT_REPORT,
    metrics_path: Path = DEFAULT_METRICS,
) -> pd.DataFrame:
    generated = pd.Timestamp.now(tz="Asia/Tokyo")
    metrics = build_metrics(ledger, as_of=generated.tz_localize(None))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.12g")
    report_path.write_text(render_report(ledger, metrics, generated), encoding="utf-8")
    free_path = report_path.with_name(report_path.stem + "_free.html")
    free_path.write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>アクセス権限がありません</title><style>body{font-family:system-ui;background:#f4f7fb;color:#172033;margin:0;padding:40px}.box{max-width:680px;margin:auto;background:#fff;border:1px solid #dbe3ee;border-radius:16px;padding:28px}a{color:#2255d8}</style></head><body><main class="box"><h1>Discordロールが必要です</h1><p>Weak+Early ベータ版は、現行レポートと同じDiscordロールを持つユーザーだけが閲覧できます。</p><p><a href="/auth/logout">Discordで再ログイン</a></p></main></body></html>',
        encoding="utf-8",
    )
    return metrics
