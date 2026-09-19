"""Standalone user-friendly HTML report for the Weak+Early beta."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from .config import (
    COMBINED_SELECTOR_IDS,
    ENDPOINT_LABEL,
    SELECTOR_ORDER,
    selector_info,
)
from .metrics import build_metrics, build_monthly_metrics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "weak_early_beta_latest.html"
DEFAULT_METRICS = ROOT / "weak_early_beta" / "state" / "metrics.csv"
DEFAULT_MONTHLY_METRICS = ROOT / "weak_early_beta" / "state" / "monthly_metrics.csv"


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


def _monthly_rows(metrics: pd.DataFrame) -> str:
    if metrics.empty:
        return '<tr><td colspan="13">集計対象がありません</td></tr>'
    mode_order = {
        selector_id: index
        for index, selector_id in enumerate((*SELECTOR_ORDER, *COMBINED_SELECTOR_IDS))
    }
    data = metrics.copy()
    data["_mode_order"] = data["selector_id"].map(mode_order)
    rows = []
    for row in data.sort_values(["period", "_mode_order"], ascending=[False, True]).itertuples():
        rows.append(
            "<tr>"
            f"<th>{html.escape(str(row.period))}</th><th>{html.escape(row.selector_name)}</th>"
            f"<td>{row.n}</td><td>{row.pending}</td>"
            f"<td>{_pct(row.mean_pct, True)}</td><td>{_pct(row.median_pct, True)}</td>"
            f"<td>{_pct(row.win_pct)}</td><td>{_pct(row.plus10_pct)}</td>"
            f"<td>{_pct(row.plus20_pct)}</td><td>{_pct(row.minus10_pct)}</td>"
            f"<td>{_pct(row.minus20_pct)}</td><td>{_yen(row.cash_pl_100_yen)}</td>"
            f"<td>{_price(row.required_capital_yen)}</td></tr>"
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
        badges += f'<small>モード別配分: {units}口（{units * 100}株）</small>'
        raw_name = first.get("company_name", "")
        name = "" if pd.isna(raw_name) else str(raw_name).strip()
        if name.lower() == "nan":
            name = ""
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


def render_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    total_period = max(metrics["period"].astype(str), key=len) if not metrics.empty else "—"
    total = metrics[metrics["period"].eq(total_period)] if not metrics.empty else pd.DataFrame()
    selector_total = total[total["selector_id"].isin(SELECTOR_ORDER)] if not total.empty else total
    best = (
        selector_total.sort_values("cash_pl_100_yen", ascending=False).iloc[0]
        if not selector_total.empty
        else None
    )
    monthly_metrics = monthly_metrics if monthly_metrics is not None else pd.DataFrame()
    detection_count = len(ledger)
    unique_count = ledger.groupby(["signal_date", "symbol"]).ngroups if not ledger.empty else 0
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>天底極致 -Cloud-</title>
<style>
:root{{--bg:#edf4ff;--panel:rgba(255,255,255,.9);--panel-solid:#fff;--ink:#14213d;--muted:#60708a;--line:#d4e1f3;--blue:#4169e1;--cyan:#149fba;--violet:#725fda;--good:#08744f;--warn:#a25b00;--shadow:0 18px 46px rgba(54,84,145,.12)}}
:root[data-theme="dark"]{{--bg:#0c1424;--panel:rgba(21,32,51,.94);--panel-solid:#152033;--ink:#edf4ff;--muted:#a3b3ca;--line:#2b405e;--blue:#91adff;--cyan:#65d5e6;--violet:#ad9bff;--good:#65d6a7;--warn:#ffc56b;--shadow:0 18px 46px rgba(0,0,0,.28)}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 12% -8%,color-mix(in srgb,var(--cyan) 18%,transparent),transparent 34%),radial-gradient(circle at 94% 5%,color-mix(in srgb,var(--violet) 16%,transparent),transparent 30%),var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Noto Sans JP",sans-serif}}a{{color:var(--blue)}}
.topbar{{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--panel-solid) 86%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(16px)}}
.nav{{max-width:1440px;margin:auto;padding:12px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}}.brand{{font-weight:850;margin-right:auto}}button,select,input{{font:inherit}}button{{cursor:pointer}}
.theme{{border:1px solid var(--line);background:var(--panel-solid);color:var(--ink);border-radius:999px;padding:7px 12px}}main{{max-width:1440px;margin:auto;padding:34px 20px 60px}}
.hero{{display:grid;grid-template-columns:2fr 1fr;gap:18px;align-items:stretch}}.panel{{background:var(--panel);border:1px solid color-mix(in srgb,var(--line) 84%,transparent);border-radius:22px;padding:24px;box-shadow:var(--shadow);margin-bottom:22px;backdrop-filter:blur(10px)}}
.hero-main{{position:relative;overflow:hidden;background:linear-gradient(135deg,color-mix(in srgb,var(--panel-solid) 94%,var(--cyan)),color-mix(in srgb,var(--panel-solid) 92%,var(--violet)))}}.hero-main:after{{content:"";position:absolute;width:240px;height:240px;border-radius:50%;right:-70px;bottom:-130px;background:color-mix(in srgb,var(--cyan) 16%,transparent)}}
.eyebrow{{color:var(--cyan);font-weight:800;letter-spacing:.06em}}h1{{font-size:clamp(28px,5vw,52px);line-height:1.12;margin:.15em 0}}h2{{margin:0 0 16px;font-size:22px}}h3{{margin:8px 0}}.lead{{font-size:17px;color:var(--muted);max-width:62ch}}
.kpis{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.kpi{{background:color-mix(in srgb,var(--bg) 76%,var(--panel-solid));border:1px solid var(--line);border-radius:16px;padding:14px}}.kpi b{{display:block;font-size:24px;line-height:1.3}}.kpi small,.subtle,small{{display:block;color:var(--muted)}}
.condition-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}}.condition-card{{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:16px;padding:17px;background:linear-gradient(150deg,var(--panel-solid),color-mix(in srgb,var(--bg) 88%,var(--violet)));transition:transform .18s ease,box-shadow .18s ease}}.condition-card:before{{content:"";position:absolute;left:0;top:0;width:100%;height:4px;background:linear-gradient(90deg,var(--cyan),var(--violet))}}.condition-card:hover{{transform:translateY(-2px);box-shadow:0 12px 28px rgba(54,84,145,.12)}}.condition-id,.badge{{display:inline-flex;border-radius:999px;background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid));color:var(--blue);padding:3px 8px;font-size:12px;font-weight:750;margin:2px}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:16px}}table{{width:100%;border-collapse:collapse;min-width:1050px;background:var(--panel-solid)}}th,td{{border-bottom:1px solid var(--line);padding:11px 10px;text-align:right;white-space:nowrap}}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}thead th{{position:sticky;top:0;background:color-mix(in srgb,var(--panel-solid) 94%,var(--bg));z-index:1;font-size:12px;color:var(--muted)}}tbody tr:nth-child(even){{background:color-mix(in srgb,var(--bg) 42%,transparent)}}tbody tr:hover{{background:color-mix(in srgb,var(--blue) 7%,var(--panel-solid))}}
.filters{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}.filters input,.filters select{{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:9px;padding:9px 11px}}.status{{font-weight:750}}.status.mature{{color:var(--good)}}.status.pending{{color:var(--warn)}}.number{{font-variant-numeric:tabular-nums}}.symbol{{font-size:17px}}.actions{{margin-top:5px}}.button-link,.fundamental-toggle{{display:inline-flex;border:1px solid var(--line);background:var(--bg);color:var(--blue);text-decoration:none;border-radius:7px;padding:4px 8px}}.fundamental-detail{{white-space:normal;min-width:320px;max-width:650px;margin-top:8px;padding:12px;background:var(--bg);border-radius:10px}}
.note{{color:var(--muted);font-size:13px}}.monthly-details{{margin-top:16px;border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--bg) 55%,var(--panel-solid));padding:0 14px 14px}}.monthly-details summary{{cursor:pointer;font-weight:800;padding:14px 2px;color:var(--blue)}}footer{{color:var(--muted);text-align:center;padding:28px}}
@media(max-width:1000px){{.hero{{grid-template-columns:1fr}}.condition-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:620px){{main{{padding:18px 12px 50px}}.panel{{padding:16px;border-radius:14px}}.condition-grid{{grid-template-columns:1fr}}.kpis{{grid-template-columns:1fr 1fr}}}}
</style><script src="/report-interactions.js" defer></script></head>
<body><header class="topbar"><nav class="nav"><span class="brand">天底極致 -Cloud-</span><a href="#performance">成績</a><a href="#conditions">5つのモード</a><a href="#history">検出履歴</a><button class="theme" id="theme-toggle" type="button">表示切替</button></nav></header>
<main><section class="hero"><div class="panel hero-main"><span class="eyebrow">TEN-TEI-KYOKUCHI / CLOUD</span><h1>反転の兆しを、<br>雲の先から。</h1><p class="lead">日足データから候補を選び、特徴の異なる5つのモードで引け後に検出します。翌営業日の寄り付きから5営業日目の終値までを、すべて同じルールで記録します。</p><p class="note">評価ルール: {html.escape(ENDPOINT_LABEL)}。投資助言ではありません。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>モード別の記録件数</small><b>{detection_count:,}件</b></div><div class="kpi"><small>重複を除いた検出件数</small><b>{unique_count:,}件</b></div><div class="kpi"><small>集計期間</small><b>{html.escape(total_period)}</b></div><div class="kpi"><small>100株損益 首位</small><b>{html.escape(str(best['selector_name'])) if best is not None else '—'}</b></div></div><p class="note">同じ銘柄が複数モードに該当することがあります。重複を除いた検出件数では、同じ日・同じ銘柄を1件として数えています。</p></aside></section>
<section class="panel" id="performance"><h2>全期間のモード別成績</h2><p class="note">順位は100株ずつ売買した累計損益額順です。参考元金は同時保有を賄うために必要だった最大金額、元金増加率は累計損益÷参考元金です。単純年率はそれを対象年数で割った値で、複利・売買コスト・税金は含みません。</p><div class="table-wrap"><table><thead><tr><th>順位</th><th>モード</th><th>確定取引数</th><th>未確定取引数</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th><th>Top3除外平均</th><th>100株損益</th><th>参考元金</th><th>元金増加率</th><th>単純年率</th></tr></thead><tbody>{_overall_rows(metrics)}</tbody></table></div></section>
<section class="panel"><h2>Cloud 全体の成績</h2><p class="note">「モード別積上げ」は該当モードごとに100株を配分し、3モード重複なら合計300株として集計します。「銘柄均等」は同じ日・同じ銘柄を100株に固定します。重複を投資確度として活かす場合と、1銘柄への偏りを抑える場合を比較できます。</p><div class="table-wrap"><table><thead><tr><th>期間</th><th>配分方式</th><th>確定取引数</th><th>未確定取引数</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th><th>100株損益</th><th>参考元金</th><th>元金増加率</th><th>単純年率</th></tr></thead><tbody>{_combined_rows(metrics)}</tbody></table></div></section>
<section class="panel"><h2>年別の成績</h2><div class="table-wrap"><table><thead><tr><th>年</th><th>順位</th><th>モード</th><th>確定取引数</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>100株損益</th><th>参考元金</th><th>元金増加率</th><th>単純年率</th></tr></thead><tbody>{_yearly_rows(metrics)}</tbody></table></div><details class="monthly-details"><summary>月別の詳しい成績を見る</summary><p class="note">各モードとCloud全体の2つの配分方式を、月ごとに確認できます。</p><div class="table-wrap"><table><thead><tr><th>月</th><th>モード／配分方式</th><th>確定取引数</th><th>未確定取引数</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>100株損益</th><th>参考元金</th></tr></thead><tbody>{_monthly_rows(monthly_metrics)}</tbody></table></div></details></section>
<section class="panel" id="conditions"><h2>5つのモード</h2><div class="condition-grid">{_condition_cards()}</div><p class="note">各モードの判定ルールと評価方法は固定し、後から過去の結果に合わせて変更しません。</p></section>
<section class="panel" id="history"><h2>検出履歴</h2><div class="filters"><input id="symbol-filter" inputmode="numeric" placeholder="証券コード 1234"><select id="selector-filter"><option value="">すべてのモード</option>{''.join(f'<option value="{s}">{html.escape(selector_info(s).display_name)}</option>' for s in SELECTOR_ORDER)}</select></div><div class="table-wrap"><table id="detection-table"><thead><tr><th>シグナル日</th><th>銘柄</th><th>該当モード</th><th>状態</th><th>エントリー</th><th>5営業日目</th><th>騰落率</th><th>100株損益</th><th>操作</th></tr></thead><tbody>{_detection_rows(ledger)}</tbody></table></div></section>
<section class="panel"><h2>このレポートについて</h2><p>これから検出される銘柄は専用Discordへ通知し、ファンダ分析が登録された銘柄は検出履歴から確認できるようにします。過去分のファンダ分析は一括生成せず、登録済みの銘柄だけボタンを表示します。</p><p class="note">最終更新: {generated:%Y-%m-%d %H:%M:%S JST}</p></section></main><footer>天底極致 -Cloud-</footer></body></html>'''


def write_report(
    ledger: pd.DataFrame,
    report_path: Path = DEFAULT_REPORT,
    metrics_path: Path = DEFAULT_METRICS,
    monthly_metrics_path: Path = DEFAULT_MONTHLY_METRICS,
) -> pd.DataFrame:
    generated = pd.Timestamp.now(tz="Asia/Tokyo")
    metrics = build_metrics(ledger, as_of=generated.tz_localize(None))
    monthly_metrics = build_monthly_metrics(ledger, as_of=generated.tz_localize(None))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    monthly_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.12g")
    monthly_metrics.to_csv(
        monthly_metrics_path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        float_format="%.12g",
    )
    report_path.write_text(
        render_report(ledger, metrics, generated, monthly_metrics=monthly_metrics),
        encoding="utf-8",
    )
    free_path = report_path.with_name(report_path.stem + "_free.html")
    free_path.write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>天底極致 -Cloud- | アクセス権限がありません</title><style>body{font-family:system-ui;background:radial-gradient(circle at 20% 0,#d8efff,transparent 45%),#edf4ff;color:#14213d;margin:0;padding:40px}.box{max-width:680px;margin:auto;background:rgba(255,255,255,.92);border:1px solid #d4e1f3;border-radius:22px;padding:32px;box-shadow:0 18px 46px rgba(54,84,145,.12)}a{color:#4169e1}</style></head><body><main class="box"><p>天底極致 -Cloud-</p><h1>Discordロールが必要です</h1><p>このレポートは、対象のDiscordロールを持つユーザーだけが閲覧できます。</p><p><a href="/auth/logout">Discordで再ログイン</a></p></main></body></html>',
        encoding="utf-8",
    )
    return metrics
