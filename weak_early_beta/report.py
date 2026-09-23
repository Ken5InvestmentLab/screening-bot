"""Standalone user-friendly HTML report for the Weak+Early beta."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

from .config import (
    COMBINED_STACKED_ID,
    COMBINED_SELECTOR_IDS,
    COMBINED_UNIQUE_ID,
    ENDPOINT_LABEL,
    SELECTOR_ORDER,
    selector_info,
)
from .metrics import (
    build_metrics,
    build_monthly_metrics,
    combined_detections,
    coverage_years,
    required_capital,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "weak_early_beta_latest.html"
DEFAULT_METRICS = ROOT / "weak_early_beta" / "state" / "metrics.csv"
DEFAULT_MONTHLY_METRICS = ROOT / "weak_early_beta" / "state" / "monthly_metrics.csv"
GUIDE_PAGE_NAME = "weak_early_beta_guide.html"
ANALYTICS_PAGE_NAME = "weak_early_beta_analytics.html"
MODE_PAGE_NAMES = {
    selector_id: f"weak_early_beta_{selector_info(selector_id).short_name.lower()}.html"
    for selector_id in SELECTOR_ORDER
}

TOTAL_EQUITY_EXPLANATION = (
    "100株ずつ運用するために同時保有も含めて必要だった資金の目安から開始し、"
    "各取引が決済した日に損益を加えた推移です。"
)
STACKED_EXPLANATION = (
    "同じ銘柄が複数モードに該当した場合、モードごとに100株ずつ買ったものとして集計します"
    "（例: 3モード該当なら合計300株）。"
)
UNIQUE_EXPLANATION = (
    "該当モード数にかかわらず、同じ日・同じ銘柄を100株だけ買ったものとして集計します。"
)

CAPITAL_HEADER = (
    '<span title="複数の取引が同時に重なった期間を含め、100株ずつ運用するために必要だった最大資金の目安です。">'
    "必要資金（目安）</span>"
)

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
BARE_URL_RE = re.compile(r"https?://[^\s<>]+")


def _anchor(url: str, label: str) -> str:
    return (
        f'<a href="{html.escape(url, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer">{html.escape(label)}</a>'
    )


def _linkify(value: str) -> str:
    """Render trusted link syntax while escaping every other character."""
    text = str(value or "")
    parts: list[str] = []
    cursor = 0
    for match in MARKDOWN_LINK_RE.finditer(text):
        plain = text[cursor : match.start()]
        plain_cursor = 0
        for url_match in BARE_URL_RE.finditer(plain):
            parts.append(html.escape(plain[plain_cursor : url_match.start()]))
            url = url_match.group(0).rstrip(".,;:!?、。)]}）】」』")
            trailing = url_match.group(0)[len(url) :]
            parts.append(_anchor(url, url))
            parts.append(html.escape(trailing))
            plain_cursor = url_match.end()
        parts.append(html.escape(plain[plain_cursor:]))
        parts.append(_anchor(match.group(2), match.group(1)))
        cursor = match.end()
    tail = text[cursor:]
    tail_cursor = 0
    for url_match in BARE_URL_RE.finditer(tail):
        parts.append(html.escape(tail[tail_cursor : url_match.start()]))
        url = url_match.group(0).rstrip(".,;:!?、。)]}）】」』")
        trailing = url_match.group(0)[len(url) :]
        parts.append(_anchor(url, url))
        parts.append(html.escape(trailing))
        tail_cursor = url_match.end()
    parts.append(html.escape(tail[tail_cursor:]))
    return "".join(parts).replace("\n", "<br>")


def _sources_html(value: str) -> str:
    """Render source references as concise Premium-style bullets."""
    links: list[str] = []
    seen: set[str] = set()
    entries = re.split(r"[\r\n;；]+", str(value or ""))
    for entry in entries:
        entry = entry.strip().lstrip("・•-–— ").strip()
        if not entry:
            continue
        markdown_matches = list(MARKDOWN_LINK_RE.finditer(entry))
        if markdown_matches:
            for match in markdown_matches:
                url, label = match.group(2), match.group(1)
                if url not in seen:
                    links.append(f"<li>{_anchor(url, label)}</li>")
                    seen.add(url)
            continue
        for match in BARE_URL_RE.finditer(entry):
            raw_url = match.group(0)
            url = raw_url.rstrip(".,;:!?、。)]}）】」』")
            if url in seen:
                continue
            label = entry[: match.start()].strip(" ：:・•-–—") or url
            links.append(f"<li>{_anchor(url, label)}</li>")
            seen.add(url)
    if not links:
        return _linkify(value)
    return '<ul class="source-links">' + "".join(links) + "</ul>"


def _disclosure_links_html(value: str) -> str:
    """Make each disclosure title the clickable text for its source URL."""
    rendered: list[str] = []
    for line in str(value or "").splitlines():
        line = line.strip()
        if not line:
            continue
        matches = list(BARE_URL_RE.finditer(line))
        if len(matches) != 1:
            rendered.append(_linkify(line))
            continue

        match = matches[0]
        raw_url = match.group(0)
        url = raw_url.rstrip(".,;:!?、。)]}）】」』")
        trailing = raw_url[len(url) :]
        prefix = line[: match.start()].rstrip()
        title = ""
        lead = ""

        quoted = re.search(r"「([^」]+)」$", prefix)
        if quoted:
            lead = prefix[: quoted.start()]
            title = quoted.group(1)
        else:
            dated = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(.*))?$", prefix)
            if dated:
                lead = dated.group(1)
                remainder = (dated.group(2) or "").strip()
                time_prefix = re.match(r"^(\d{1,2}:\d{2}(?:\+09:00)?)(?:\s+)?(.*)$", remainder)
                if time_prefix:
                    lead += " " + time_prefix.group(1)
                    title = time_prefix.group(2).strip()
                else:
                    title = remainder

        display_time = ""
        time_suffix = re.search(r"\s*\((\d{1,2}:\d{2})\)$", title)
        if time_suffix:
            display_time = " (" + time_suffix.group(1) + ")"
            title = title[: time_suffix.start()].rstrip()

        if not title:
            rendered.append(_linkify(line))
            continue

        title_link = _anchor(url, title)
        if quoted:
            text = f"{html.escape(lead)}「{title_link}」{html.escape(display_time)}"
        else:
            text = f"{html.escape(lead)} {title_link}{html.escape(display_time)}".strip()
        rendered.append(text + html.escape(trailing))

    return "<br>".join(rendered)


def _fundamental_html(value: str) -> str:
    """Turn the stored Premium-style field text into a safe, linked embed."""
    fields: list[tuple[str, str]] = []
    for block in re.split(r"\n\s*\n", str(value or "").strip()):
        lines = block.splitlines()
        if len(lines) >= 2 and lines[0].strip():
            fields.append((lines[0].strip(), "\n".join(lines[1:]).strip()))
    if not fields:
        return f'<article class="discord-embed"><p>{_linkify(value)}</p></article>'
    impact = next((content for name, content in fields if "材料インパクト" in name), "")
    impact_class = ""
    if "ネガティブ" in impact:
        impact_class = " impact-negative"
    elif any(word in impact for word in ("様子見", "混在", "要確認")):
        impact_class = " impact-watch"
    elif "ポジティブ" in impact:
        impact_class = " impact-positive"
    field_html = "".join(
        f"<div><dt>{html.escape(name)}</dt><dd>"
        f"{_sources_html(content) if name == 'Sources' else _disclosure_links_html(content) if name == '開示リンク' else _linkify(content)}"
        "</dd></div>"
        for name, content in fields
    )
    return f'<article class="discord-embed{impact_class}"><dl>{field_html}</dl></article>'


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
            f"<td class=\"metric-focus\">{_yen(row['cash_pl_100_yen'])}</td><td class=\"metric-focus\">{_price(row['required_capital_yen'])}</td>"
            f"<td class=\"metric-focus\">{_pct(row['capital_return_pct'], True)}</td><td class=\"metric-focus\">{_pct(row['simple_annualized_pct'], True)}</td>"
            f"<td>{_pct(row['mean_pct'], True)}</td><td>{_pct(row['median_pct'], True)}</td>"
            f"<td>{_pct(row['win_pct'])}</td><td>{_pct(row['plus10_pct'])}</td>"
            f"<td>{_pct(row['plus20_pct'])}</td><td>{_pct(row['minus10_pct'])}</td>"
            f"<td>{_pct(row['minus20_pct'])}</td><td>{_pct(row['max_up_pct'], True)}</td>"
            f"<td>{_pct(row['max_down_pct'], True)}</td><td>{_pct(row['top3_ex_mean_pct'], True)}</td>"
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
                f"<td class=\"metric-focus\">{_yen(row.cash_pl_100_yen)}</td><td class=\"metric-focus\">{_price(row.required_capital_yen)}</td>"
                f"<td class=\"metric-focus\">{_pct(row.capital_return_pct, True)}</td><td class=\"metric-focus\">{_pct(row.simple_annualized_pct, True)}</td>"
                "</tr>"
            )
    return "".join(rows)


def _combined_rows(metrics: pd.DataFrame, selector_id: str | None = None) -> str:
    combined = metrics[metrics["selector_id"].isin(COMBINED_SELECTOR_IDS)].copy()
    if selector_id:
        combined = combined[combined["selector_id"].eq(selector_id)]
    if combined.empty:
        return '<tr><td colspan="16">集計対象がありません</td></tr>'
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
            f"<th>{html.escape(label)}</th>"
            f"<td>{row.n}</td><td>{row.pending}</td>"
            f"<td class=\"metric-focus\">{_yen(row.cash_pl_100_yen)}</td><td class=\"metric-focus\">{_price(row.required_capital_yen)}</td>"
            f"<td class=\"metric-focus\">{_pct(row.capital_return_pct, True)}</td><td class=\"metric-focus\">{_pct(row.simple_annualized_pct, True)}</td>"
            f"<td>{_pct(row.mean_pct, True)}</td><td>{_pct(row.median_pct, True)}</td>"
            f"<td>{_pct(row.win_pct)}</td><td>{_pct(row.plus10_pct)}</td>"
            f"<td>{_pct(row.plus20_pct)}</td><td>{_pct(row.minus10_pct)}</td>"
            f"<td>{_pct(row.minus20_pct)}</td><td>{_pct(row.max_up_pct, True)}</td>"
            f"<td>{_pct(row.max_down_pct, True)}</td></tr>"
        )
    return "".join(rows)


def _monthly_rows(metrics: pd.DataFrame, show_mode: bool = True) -> str:
    if metrics.empty:
        return f'<tr><td colspan="{13 if show_mode else 12}">集計対象がありません</td></tr>'
    mode_order = {
        selector_id: index
        for index, selector_id in enumerate((*SELECTOR_ORDER, *COMBINED_SELECTOR_IDS))
    }
    data = metrics.copy()
    data["_mode_order"] = data["selector_id"].map(mode_order)
    rows = []
    for row in data.sort_values(["period", "_mode_order"], ascending=[False, True]).itertuples():
        mode_cell = f"<th>{html.escape(row.selector_name)}</th>" if show_mode else ""
        rows.append(
            "<tr>"
            f"<th>{html.escape(str(row.period))}</th>"
            f"{mode_cell}"
            f"<td>{row.n}</td><td>{row.pending}</td>"
            f"<td class=\"metric-focus\">{_yen(row.cash_pl_100_yen)}</td><td class=\"metric-focus\">{_price(row.required_capital_yen)}</td>"
            f"<td>{_pct(row.mean_pct, True)}</td><td>{_pct(row.median_pct, True)}</td>"
            f"<td>{_pct(row.win_pct)}</td><td>{_pct(row.plus10_pct)}</td>"
            f"<td>{_pct(row.plus20_pct)}</td><td>{_pct(row.minus10_pct)}</td>"
            f"<td>{_pct(row.minus20_pct)}</td></tr>"
        )
    return "".join(rows)


def _table_pagination() -> str:
    return (
        '<div class="table-pagination">'
        '<button class="table-load-more" type="button">次の20件を表示</button>'
        '<button class="table-collapse" type="button" hidden>最初の20件に戻す</button>'
        '<output class="result-count table-result-count" aria-live="polite"></output>'
        '</div>'
    )


def _condition_cards() -> str:
    cards = []
    for selector_id in SELECTOR_ORDER:
        info = selector_info(selector_id)
        cards.append(
            f'<a class="condition-card" href="./{MODE_PAGE_NAMES[selector_id]}">'
            f"<span class=\"condition-id\">{html.escape(info.short_name)}</span>"
            f"<h3>{html.escape(info.display_name)}</h3>"
            f"<p>{html.escape(info.feature_summary)}</p>"
            f"<p class=\"subtle\">{html.escape(info.selection_summary)}</p>"
            "<strong>成績と資産推移を見る →</strong></a>"
        )
    return "".join(cards)


def _detection_rows(ledger: pd.DataFrame, mask_pending: bool = False) -> str:
    if ledger.empty:
        return '<tr><td colspan="9">検出履歴がありません</td></tr>'
    data = ledger.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    rows = []
    grouped = data.groupby(["signal_date", "symbol"], sort=False)
    for index, ((signal_date, symbol), group) in enumerate(
        sorted(grouped, key=lambda item: item[0], reverse=True)
    ):
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
        is_masked = mask_pending and gross.empty
        fundamental_url = "" if is_masked else next(
            (str(x) for x in group["fundamental_discord_url"] if pd.notna(x) and str(x).strip()), ""
        )
        fundamental_html = "" if is_masked else next(
            (str(x) for x in group["fundamental_html"] if pd.notna(x) and str(x).strip()), ""
        )
        actions = ""
        if is_masked:
            actions = '<a class="button-link" href="/purchase">新着銘柄を見る</a>'
        elif fundamental_html:
            actions = (
                '<button class="fundamental-toggle" type="button" aria-expanded="false">ファンダ分析</button>'
                f'<div class="fundamental-detail" hidden>{_fundamental_html(fundamental_html)}</div>'
            )
        elif fundamental_url:
            actions = f'<a class="button-link" href="{html.escape(fundamental_url)}">ファンダ分析</a>'
        display_symbol = "••••" if is_masked else str(symbol)
        display_name = "5営業日終値確定まで会員限定" if is_masked else name
        search_text = "" if is_masked else f"{symbol} {name}".strip()
        entry_display = "会員限定" if is_masked else f"{_date(first['entry_date'])}<small>{_price(first['entry_open'])}</small>"
        exit_display = "未確定" if is_masked else f"{_date(first['fifth_xtks_exit_date'])}<small>{_price(first['fifth_xtks_exit_close'])}</small>"
        chart_action = (
            '<a class="button-link" href="/purchase">アクセス権を購入する</a>'
            if is_masked
            else f'<a href="https://jp.tradingview.com/chart/?symbol=TSE%3A{html.escape(str(symbol))}">チャート</a>'
        )
        rows.append(
            f'<tr data-selectors="{html.escape(" ".join(selectors))}" '
            f'data-date="{signal_date:%Y-%m-%d}" '
            f'data-symbol="{"" if is_masked else html.escape(str(symbol))}" data-search="{html.escape(search_text)}"'
            f'{" hidden" if index >= 20 else ""}>'
            f'<td data-label="シグナル日">{signal_date:%Y-%m-%d}</td>'
            f"<th><span class=\"symbol\">{html.escape(display_symbol)}</span> {html.escape(display_name)}<div class=\"actions\">{actions}</div></th>"
            f'<td data-label="該当モード">{badges}</td><td data-label="状態"><span class="status {status_class}">{status}</span></td>'
            f'<td data-label="エントリー">{entry_display}</td>'
            f'<td data-label="5営業日目">{exit_display}</td>'
            f'<td data-label="騰落率" class="number">{_pct(gross.iloc[0] * 100, True) if not gross.empty else "—"}</td>'
            f'<td data-label="100株損益" class="number">{_yen(cash.iloc[0]) if not cash.empty else "—"}</td>'
            f'<td data-label="操作">{chart_action}</td>'
            "</tr>"
        )
    return "".join(rows)


REPORT_CSS = """
:root{--bg:#edf4ff;--panel:rgba(255,255,255,.9);--panel-solid:#fff;--ink:#14213d;--muted:#60708a;--line:#d4e1f3;--blue:#4169e1;--cyan:#149fba;--violet:#725fda;--good:#08744f;--warn:#a25b00;--shadow:0 18px 46px rgba(54,84,145,.12)}
:root[data-theme="dark"]{--bg:#0c1424;--panel:rgba(21,32,51,.94);--panel-solid:#152033;--ink:#edf4ff;--muted:#a3b3ca;--line:#2b405e;--blue:#91adff;--cyan:#65d5e6;--violet:#ad9bff;--good:#65d6a7;--warn:#ffc56b;--shadow:0 18px 46px rgba(0,0,0,.28)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 12% -8%,color-mix(in srgb,var(--cyan) 18%,transparent),transparent 34%),radial-gradient(circle at 94% 5%,color-mix(in srgb,var(--violet) 16%,transparent),transparent 30%),var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Noto Sans JP",sans-serif}a{color:var(--blue)}
.topbar{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--panel-solid) 86%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(16px)}
.nav{max-width:1440px;margin:auto;padding:10px 20px;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px}.brand{display:inline-flex;align-items:center;min-width:0;text-decoration:none}.brand-logo{display:block;width:min(340px,42vw);height:52px;object-fit:contain;object-position:left center}.brand-logo-dark{display:none}:root[data-theme="dark"] .brand-logo-light{display:none}:root[data-theme="dark"] .brand-logo-dark{display:block}.nav-links{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:2px;min-width:0}.nav-link{padding:7px 10px;border-radius:999px;text-decoration:none;font-weight:700;white-space:nowrap}.nav-link.active,.nav-link:hover{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid))}button,select,input{font:inherit}button{cursor:pointer}
.theme-toggle{display:inline-flex;align-items:center;gap:7px;min-height:32px;padding:5px 9px;border:1px solid var(--line);border-radius:999px;background:var(--panel-solid);color:var(--ink);font-size:12px;font-weight:800;line-height:1;white-space:nowrap}.theme-toggle-track{position:relative;display:inline-block;width:36px;height:20px;border-radius:999px;background:#aebdd1;transition:background .2s ease}.theme-toggle-knob{position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(16,24,40,.28);transition:transform .2s ease}:root[data-theme="dark"] .theme-toggle-track{background:#4f8dff}:root[data-theme="dark"] .theme-toggle-knob{transform:translateX(16px)}.clear-search,.load-more,.collapse-results,.table-load-more,.table-collapse{border:1px solid var(--line);background:var(--panel-solid);color:var(--ink);border-radius:999px;padding:7px 12px}main{max-width:1440px;margin:auto;padding:34px 20px 60px}
.hero{display:grid;grid-template-columns:2fr 1fr;gap:18px;align-items:stretch}.panel{background:var(--panel);border:1px solid color-mix(in srgb,var(--line) 84%,transparent);border-radius:22px;padding:24px;box-shadow:var(--shadow);margin-bottom:22px;backdrop-filter:blur(10px)}
.hero-main{position:relative;overflow:hidden;background:linear-gradient(135deg,color-mix(in srgb,var(--panel-solid) 94%,var(--cyan)),color-mix(in srgb,var(--panel-solid) 92%,var(--violet)))}.hero-main:after{content:"";position:absolute;width:240px;height:240px;border-radius:50%;right:-70px;bottom:-130px;background:color-mix(in srgb,var(--cyan) 16%,transparent)}
.eyebrow{color:var(--cyan);font-weight:800;letter-spacing:.06em}h1{font-size:clamp(28px,5vw,52px);line-height:1.12;margin:.15em 0}h2{margin:0 0 16px;font-size:22px}h3{margin:8px 0}.lead{font-size:17px;color:var(--muted);max-width:62ch}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.kpi{background:color-mix(in srgb,var(--bg) 76%,var(--panel-solid));border:1px solid var(--line);border-radius:16px;padding:14px}.kpi b{display:block;font-size:24px;line-height:1.3}.kpi b.period-range{font-size:19px;white-space:nowrap}.kpi small,.subtle,small{display:block;color:var(--muted)}
.condition-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.condition-card{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:16px;padding:17px;background:linear-gradient(150deg,var(--panel-solid),color-mix(in srgb,var(--bg) 88%,var(--violet)));transition:transform .18s ease,box-shadow .18s ease;text-decoration:none;color:var(--ink)}.condition-card:before{content:"";position:absolute;left:0;top:0;width:100%;height:4px;background:linear-gradient(90deg,var(--cyan),var(--violet))}.condition-card:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(54,84,145,.12)}.condition-id,.badge{display:inline-flex;border-radius:999px;background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid));color:var(--blue);padding:3px 8px;font-size:12px;font-weight:750;margin:2px}
.chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.chart-card{border:1px solid var(--line);border-radius:18px;background:var(--panel-solid);padding:18px}.chart-card svg{width:100%;height:auto;display:block}.chart-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-top:10px}.chart-stats div{background:var(--bg);border-radius:12px;padding:10px}.chart-stats b{display:block}.axis-label{fill:var(--muted);font-size:12px}.grid-line{stroke:var(--line);stroke-width:1}.equity-line{fill:none;stroke:var(--blue);stroke-width:4;stroke-linejoin:round;stroke-linecap:round}.equity-area{fill:url(#equity-fill);opacity:.22}
.annual-pl{max-width:900px;margin:auto;padding:12px 0}.annual-pl-row{display:grid;grid-template-columns:minmax(160px,220px) minmax(0,1fr) minmax(135px,175px);align-items:center;gap:14px;margin:16px 0}.annual-pl-year{font-weight:800}.annual-pl-year small{font-weight:500}.annual-pl-track{position:relative;height:18px;border-radius:999px;background:color-mix(in srgb,var(--blue) 9%,var(--bg));overflow:hidden}.annual-pl-zero{position:absolute;top:0;bottom:0;width:2px;background:var(--muted);opacity:.55}.annual-pl-bar{position:absolute;top:0;bottom:0;border-radius:999px;background:linear-gradient(90deg,var(--blue),var(--cyan))}.annual-pl-bar.negative{background:#df6670}.annual-pl-value{text-align:right;font-weight:800;font-variant-numeric:tabular-nums}.annual-pl-value.negative{color:#bc4253}
.insight-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-bottom:22px}.insight-grid .panel{margin-bottom:0;min-width:0}.insight-grid .annual-pl-row{grid-template-columns:minmax(130px,190px) minmax(0,1fr) minmax(100px,125px);gap:8px}
.payoff-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.payoff-ratio{background:color-mix(in srgb,var(--warn) 12%,var(--panel-solid));color:var(--warn);border-radius:999px;padding:5px 12px;font-weight:800;white-space:nowrap}.payoff-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:20px 0}.payoff-kpi strong{display:block;font-size:clamp(22px,2.5vw,32px);line-height:1.25;font-variant-numeric:tabular-nums}.payoff-kpi.win strong{color:var(--good)}.payoff-kpi.loss strong{color:#c64c55}.payoff-track{position:relative;height:30px;border-radius:999px;background:color-mix(in srgb,var(--blue) 7%,var(--bg));overflow:hidden;margin-top:26px}.payoff-zero{position:absolute;left:50%;top:0;bottom:0;width:2px;background:var(--line)}.payoff-bar{position:absolute;top:0;bottom:0}.payoff-bar.win{left:50%;background:#14956d;border-radius:0 999px 999px 0}.payoff-bar.loss{right:50%;background:#df555a;border-radius:999px 0 0 999px}.payoff-axis{display:flex;justify-content:space-between;gap:12px;margin-top:7px;font-size:12px;font-weight:700}.payoff-axis .loss{color:#c64c55}.payoff-axis .win{color:var(--good)}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:16px}table{width:100%;border-collapse:collapse;min-width:1050px;background:var(--panel-solid)}th,td{border-bottom:1px solid var(--line);padding:11px 10px;text-align:right;white-space:nowrap}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}thead th{position:sticky;top:0;background:color-mix(in srgb,var(--panel-solid) 94%,var(--bg));z-index:1;font-size:12px;color:var(--muted)}tbody tr:nth-child(even){background:color-mix(in srgb,var(--bg) 42%,transparent)}tbody tr:hover{background:color-mix(in srgb,var(--blue) 7%,var(--panel-solid))}[hidden]{display:none!important}.metric-focus{color:var(--blue);font-weight:850;background:color-mix(in srgb,var(--blue) 8%,transparent)}.table-pagination{display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;margin-top:14px}
.history-details{border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--bg) 38%,var(--panel-solid));padding:14px}.history-heading{font-weight:800;margin:0 0 14px;color:var(--blue)}.filters{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin-bottom:14px}.filter-field{display:grid;gap:4px}.filter-field span{font-size:12px;color:var(--muted);font-weight:700}.filters input,.filters select{border:1px solid var(--line);background:var(--panel-solid);color:var(--ink);border-radius:10px;padding:10px 12px}.filters input[type="search"]{min-width:min(360px,100%)}.result-count{color:var(--muted);font-weight:700}.history-pagination{display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;margin-top:14px}.status{font-weight:750}.status.mature{color:var(--good)}.status.pending{color:var(--warn)}.number{font-variant-numeric:tabular-nums}.symbol{font-size:17px}.actions{margin-top:5px}.button-link,.fundamental-toggle{display:inline-flex;border:1px solid var(--line);background:var(--bg);color:var(--blue);text-decoration:none;border-radius:7px;padding:4px 8px}.fundamental-detail{white-space:normal;min-width:320px;max-width:650px;margin-top:8px;padding:12px;background:var(--bg);border-radius:10px}.discord-embed{border-left:4px solid var(--blue);background:var(--panel-solid);border-radius:8px;padding:12px;text-align:left}.discord-embed.impact-positive{border-left-color:#12b76a;background:color-mix(in srgb,#12b76a 10%,var(--panel-solid))}.discord-embed.impact-watch{border-left-color:#fdb022;background:color-mix(in srgb,#fdb022 11%,var(--panel-solid))}.discord-embed.impact-negative{border-left-color:#f04438;background:color-mix(in srgb,#f04438 9%,var(--panel-solid))}.discord-embed dl{display:grid;gap:10px;margin:0}.discord-embed dt{font-weight:800;color:var(--muted)}.discord-embed dd{margin:2px 0 0;overflow-wrap:anywhere;white-space:normal}
.note{color:var(--muted);font-size:13px}.monthly-details{margin-top:16px;border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--bg) 55%,var(--panel-solid));padding:0 14px 14px}.monthly-details summary{cursor:pointer;font-weight:800;padding:14px 2px;color:var(--blue)}.guide-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.guide-card{border:1px solid var(--line);border-radius:16px;background:var(--panel-solid);padding:18px}.site-footer{border-top:1px solid var(--line);background:color-mix(in srgb,var(--panel-solid) 78%,transparent);padding:26px 20px}.site-footer-inner{max-width:1440px;margin:auto;display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap}.footer-copy{margin:0;color:var(--muted)}.footer-links{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.footer-link{display:inline-flex;align-items:center;justify-content:center;min-width:42px;min-height:40px;padding:6px 8px;border:1px solid transparent;border-radius:8px;background:transparent;text-decoration:none}.footer-link:hover{border-color:#b7c8e4;background:#eef5ff}.footer-logo{display:block;object-fit:contain}.footer-logo-dark{display:none}.footer-logo-x{width:24px;height:24px}.footer-logo-discord{width:35px;height:27px}.footer-logo-coconala{width:76px;height:42px}:root[data-theme="dark"] .footer-link:hover{background:#183250;border-color:#4f8dff}:root[data-theme="dark"] .footer-logo-light{display:none}:root[data-theme="dark"] .footer-logo-dark{display:block}
@media(max-width:1100px){.insight-grid{grid-template-columns:1fr}.insight-grid .annual-pl-row{grid-template-columns:minmax(160px,220px) minmax(0,1fr) minmax(135px,175px);gap:14px}}
@media(max-width:1000px){.hero{grid-template-columns:1fr}.condition-grid{grid-template-columns:repeat(2,1fr)}.chart-grid,.guide-grid{grid-template-columns:1fr}}
@media(max-width:760px){.nav{grid-template-columns:minmax(0,1fr) auto;padding:8px 12px;gap:4px 8px}.brand{grid-column:1;grid-row:1}.brand-logo{width:min(250px,61vw);height:44px}.theme-toggle{grid-column:2;grid-row:1;min-height:38px}.nav-links{grid-column:1/-1;grid-row:2;justify-content:flex-start;flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;padding-bottom:3px}.nav-link{flex:0 0 auto;font-size:13px;padding:6px 9px}}
@media(max-width:620px){main{padding:18px 12px 50px;min-width:0}.panel{padding:16px;border-radius:14px;min-width:0}.condition-grid{grid-template-columns:1fr}.kpis{grid-template-columns:1fr 1fr}.chart-stats{grid-template-columns:1fr}.insight-grid .annual-pl-row{grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;margin:19px 0}.annual-pl-track{grid-column:1/-1;grid-row:2}.annual-pl-value{grid-column:2;grid-row:1}.payoff-kpis{gap:5px}.payoff-kpi strong{font-size:22px}.filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:end}.filter-field{min-width:0}.filters input,.filters select{width:100%;min-width:0!important}.filters .filter-field:first-child,#selector-filter,#search-result-count{grid-column:1/-1}.history-table-wrap{overflow:visible;border:0;background:transparent}#detection-table{min-width:0;background:transparent}#detection-table thead{display:none}#detection-table tbody{display:grid;gap:12px}#detection-table tbody tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));padding:10px;border:1px solid var(--line);border-radius:12px;background:var(--panel-solid)}#detection-table tbody tr>*{display:block;min-width:0;white-space:normal;border:0;padding:6px 8px;text-align:left}#detection-table tbody tr>td:first-child,#detection-table tbody tr>th,#detection-table tbody tr>td:nth-child(3),#detection-table tbody tr>td:last-child{grid-column:1/-1}#detection-table tbody tr>th{font-size:16px;border-bottom:1px solid var(--line);padding-bottom:10px}#detection-table tbody tr>td::before{content:attr(data-label);display:block;color:var(--muted);font-size:11px;font-weight:800}#detection-table tbody tr>td:last-child{border-top:1px solid var(--line)}.fundamental-detail{min-width:0;max-width:100%;overflow-wrap:anywhere}.discord-embed{min-width:0}.button-link,.fundamental-toggle{min-height:36px;align-items:center}.kpi b.period-range{font-size:15px;white-space:normal}}
/* Fundamentals sit inside a table header cell; reset inherited bold so only labels and explicitly emphasized text are bold, as in Premium. */
.discord-embed{font-weight:400;line-height:1.55}.discord-embed dt{font-weight:800;color:var(--muted)}.discord-embed dd{font-weight:400}
.discord-embed .source-links{display:grid;gap:4px;margin:0;padding-left:20px}.discord-embed .source-links li{padding-left:2px}.discord-embed .source-links li::marker{color:var(--blue)}
"""


def _nav(current: str) -> str:
    links = [
        f'<a class="nav-link {"active" if current == "home" else ""}" '
        'href="./weak_early_beta_latest.html">検出履歴</a>',
        f'<a class="nav-link {"active" if current == "analytics" else ""}" '
        f'href="./{ANALYTICS_PAGE_NAME}">アナリティクス</a>',
    ]
    for selector_id in SELECTOR_ORDER:
        info = selector_info(selector_id)
        active = "active" if selector_id == current else ""
        links.append(
            f'<a class="nav-link {active}" href="./{MODE_PAGE_NAMES[selector_id]}">'
            f"{html.escape(info.short_name)}</a>"
        )
    links.append(
        f'<a class="nav-link {"active" if current == "guide" else ""}" '
        f'href="./{GUIDE_PAGE_NAME}">見方・使い方</a>'
    )
    return "".join(links)


def _site_footer() -> str:
    return '''<footer class="site-footer"><div class="site-footer-inner">
<p class="footer-copy">© 2026 Ken5 Investment Lab. All rights reserved.</p>
<div class="footer-links" aria-label="公式リンク">
<a class="footer-link" href="https://discord.gg/PX3cCQTxAz" target="_blank" rel="noopener noreferrer" aria-label="Discord">
<img class="footer-logo footer-logo-light footer-logo-discord" src="report-assets/discord-light.png" alt="">
<img class="footer-logo footer-logo-dark footer-logo-discord" src="report-assets/discord-dark.png" alt=""></a>
<a class="footer-link" href="https://coconala.com/users/322523" target="_blank" rel="noopener noreferrer" aria-label="ココナラ">
<img class="footer-logo footer-logo-light footer-logo-coconala" src="report-assets/coconala-light.png" alt="">
<img class="footer-logo footer-logo-dark footer-logo-coconala" src="report-assets/coconala-dark.png" alt=""></a>
<a class="footer-link" href="https://x.com/ken5investlab" target="_blank" rel="noopener noreferrer" aria-label="X">
<img class="footer-logo footer-logo-light footer-logo-x" src="report-assets/x-light.png" alt="">
<img class="footer-logo footer-logo-dark footer-logo-x" src="report-assets/x-dark.png" alt=""></a>
</div></div></footer>'''


def _page_shell(title: str, current: str, body: str) -> str:
    document_title = "天底極致 -Cloud-" if current == "home" else f"{title} | 天底極致 -Cloud-"
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(document_title)}</title><script src="./weak-early-beta-theme-init.js?v=20260923-1"></script><style>{REPORT_CSS}</style>
<script src="./weak-early-beta-interactions.js?v=20260923-1" defer></script></head>
<body><header class="topbar"><nav class="nav"><a class="brand" href="./weak_early_beta_latest.html" aria-label="天底極致 Cloud トップへ"><img class="brand-logo brand-logo-light" src="report-assets/cloud-logo-light.png?v=transparent-1" alt="天底極致 -Cloud-"><img class="brand-logo brand-logo-dark" src="report-assets/cloud-logo-dark.png?v=20260923-1" alt="天底極致 -Cloud-"></a><div class="nav-links" aria-label="ページ移動">{_nav(current)}</div><button class="theme-toggle" id="theme-toggle" type="button" data-theme-toggle aria-pressed="false" aria-label="ダークモードに切り替える"><span class="theme-toggle-track" aria-hidden="true"><span class="theme-toggle-knob"></span></span><span class="theme-toggle-label">ダーク</span></button></nav></header>
<main>{body}</main>{_site_footer()}</body></html>'''


def _equity_chart(
    frame: pd.DataFrame,
    title: str,
    chart_id: str,
    explanation: str = "",
    as_of: pd.Timestamp | None = None,
) -> str:
    completed = frame[
        pd.to_numeric(frame["one_hundred_shares_pl_yen"], errors="coerce").notna()
        & pd.to_datetime(frame["fifth_xtks_exit_date"], errors="coerce").notna()
    ].copy()
    if completed.empty:
        return f'<article class="chart-card"><h3>{html.escape(title)}</h3><p>確定取引がありません。</p></article>'
    completed["exit"] = pd.to_datetime(completed["fifth_xtks_exit_date"])
    completed["pl"] = pd.to_numeric(completed["one_hundred_shares_pl_yen"], errors="coerce")
    daily = completed.groupby("exit", sort=True)["pl"].sum()
    initial = float(required_capital(completed))
    values = [initial, *(initial + daily.cumsum()).tolist()]
    dates = [pd.to_datetime(completed["entry_date"]).min(), *daily.index.tolist()]
    width, height = 900.0, 320.0
    left, right, top, bottom = 92.0, 24.0, 24.0, 54.0
    plot_w, plot_h = width - left - right, height - top - bottom
    low, high = min(values), max(values)
    padding = max((high - low) * .12, max(abs(high), 1) * .03)
    low, high = low - padding, high + padding
    span = max(high - low, 1.0)
    points = []
    for index, value in enumerate(values):
        x = left + (plot_w * index / max(len(values) - 1, 1))
        y = top + plot_h * (high - value) / span
        points.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = f"{left:.1f},{top + plot_h:.1f} {line} {left + plot_w:.1f},{top + plot_h:.1f}"
    grid = []
    for index in range(5):
        y = top + plot_h * index / 4
        value = high - span * index / 4
        grid.append(
            f'<line class="grid-line" x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}"/>'
            f'<text class="axis-label" x="{left - 10}" y="{y + 4:.1f}" text-anchor="end">¥{value:,.0f}</text>'
        )
    final = values[-1]
    pl = final - initial
    capital_return = pl / initial * 100 if initial else float("nan")
    observed_as_of = pd.Timestamp(as_of or dates[-1]).tz_localize(None)
    annualized = capital_return / coverage_years(completed, observed_as_of)
    explanation_html = f'<p class="note">{html.escape(explanation)}</p>' if explanation else ""
    return (
        f'<article class="chart-card"><h3>{html.escape(title)}</h3>'
        + explanation_html
        + f'<svg viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="{html.escape(title)}の資産推移">'
        f'<defs><linearGradient id="equity-fill-{chart_id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--blue)"/><stop offset="1" stop-color="var(--cyan)" stop-opacity="0"/></linearGradient></defs>'
        + "".join(grid)
        + f'<polygon points="{area}" fill="url(#equity-fill-{chart_id})" opacity=".24"/>'
        + f'<polyline class="equity-line" points="{line}"/>'
        + f'<text class="axis-label" x="{left}" y="{height - 18}">{pd.Timestamp(dates[0]):%Y-%m-%d}</text>'
        + f'<text class="axis-label" x="{left + plot_w}" y="{height - 18}" text-anchor="end">{pd.Timestamp(dates[-1]):%Y-%m-%d}</text></svg>'
        + '<div class="chart-stats">'
        + f'<div><small>開始時の必要資金（目安）</small><b>{_price(initial)}</b></div>'
        + f'<div><small>最終資産</small><b>{_price(final)}</b></div>'
        + f'<div><small>累計損益</small><b>{_yen(pl)}</b></div>'
        + f'<div><small>資金増加率</small><b>{_pct(capital_return, True)}</b></div>'
        + f'<div><small>単純年率</small><b>{_pct(annualized, True)}</b></div></div></article>'
    )


def _payoff_structure(ledger: pd.DataFrame) -> str:
    """Compare average gains and losses using completed stacked trades."""
    returns = pd.to_numeric(ledger["gross_return"], errors="coerce").dropna()
    if returns.empty:
        return '<h2>損小利大の構造</h2><p class="note">確定取引がありません。</p>'
    winners = returns[returns.gt(0)]
    losers = returns[returns.lt(0)]
    win_rate = len(winners) / len(returns) * 100
    avg_win = float(winners.mean() * 100) if not winners.empty else 0.0
    avg_loss = float(losers.mean() * 100) if not losers.empty else 0.0
    payoff_ratio = avg_win / abs(avg_loss) if avg_win and avg_loss else None
    max_move = max(avg_win, abs(avg_loss), 1.0)
    win_width = 42 * avg_win / max_move
    loss_width = 42 * abs(avg_loss) / max_move
    win_label = f"{avg_win:+.1f}%" if not winners.empty else "—"
    loss_label = f"{avg_loss:+.1f}%" if not losers.empty else "—"
    ratio_label = f"平均利益幅 ÷ 平均損失幅 {payoff_ratio:.2f}倍" if payoff_ratio else "平均利益幅 ÷ 平均損失幅 —"
    return (
        f'<div class="payoff-heading"><h2>損小利大の構造</h2><span class="payoff-ratio">{ratio_label}</span></div>'
        '<p class="note">確定取引の勝敗と平均騰落率（モード別積み上げ）</p>'
        '<div class="payoff-kpis">'
        f'<div class="payoff-kpi"><strong>{win_rate:.2f}%</strong><small>勝率</small></div>'
        f'<div class="payoff-kpi loss"><strong>{loss_label}</strong><small>平均負け</small></div>'
        f'<div class="payoff-kpi win"><strong>{win_label}</strong><small>平均勝ち</small></div></div>'
        f'<div class="payoff-track" role="img" aria-label="平均負け {loss_label}、平均勝ち {win_label}">'
        f'<span class="payoff-bar loss" style="width:{loss_width:.2f}%"></span>'
        '<span class="payoff-zero"></span>'
        f'<span class="payoff-bar win" style="width:{win_width:.2f}%"></span></div>'
        f'<div class="payoff-axis"><span class="loss">{loss_label} 平均負け</span>'
        f'<span class="win">{win_label} 平均勝ち</span></div>'
        f'<p class="note">勝ち {len(winners):,}件・負け {len(losers):,}件・引き分け {len(returns) - len(winners) - len(losers):,}件。勝率の分母には引き分けも含みます。</p>'
    )


def _annual_pl_chart(ledger: pd.DataFrame, metrics: pd.DataFrame, generated: pd.Timestamp) -> str:
    """Show the same stacked annual P/L as the proposal's 100-share chart."""
    if metrics.empty:
        return '<p class="note">集計対象がありません。</p>'
    yearly = metrics[
        metrics["selector_id"].eq(COMBINED_STACKED_ID)
        & metrics["period"].astype(str).str.fullmatch(r"\d{4}")
    ].sort_values("period")
    if yearly.empty:
        return '<p class="note">集計対象がありません。</p>'
    values = [float(value) for value in yearly["cash_pl_100_yen"]]
    positive_max = max([0.0, *values])
    negative_max = max([0.0, *(-value for value in values)])
    if positive_max and negative_max:
        baseline = 50.0
        scale = 50.0 / max(positive_max, negative_max)
    elif positive_max:
        baseline = 0.0
        scale = 100.0 / positive_max
    elif negative_max:
        baseline = 100.0
        scale = 100.0 / negative_max
    else:
        baseline = 0.0
        scale = 0.0
    rows = []
    completed = ledger[pd.to_numeric(ledger["gross_return"], errors="coerce").notna()]
    completed_dates = pd.to_datetime(completed["signal_date"], errors="coerce").dropna()
    for row in yearly.itertuples():
        year = int(row.period)
        label = f"{year}年"
        period_note = ""
        if year == generated.year:
            year_dates = completed_dates[completed_dates.dt.year.eq(year)]
            period_note = (
                f"{year_dates.max().month}月{year_dates.max().day}日検出分まで"
                if not year_dates.empty else "確定分なし"
            )
        full_label = f"{label}（{period_note}）" if period_note else label
        period_html = f"<small>{period_note}</small>" if period_note else ""
        value = float(row.cash_pl_100_yen)
        width = abs(value) * scale
        left = baseline - width if value < 0 else baseline
        negative = " negative" if value < 0 else ""
        zero_line = (
            f'<span class="annual-pl-zero" style="left:{baseline:.2f}%"></span>'
            if negative_max else ""
        )
        rows.append(
            '<div class="annual-pl-row">'
            f'<div class="annual-pl-year">{label}{period_html}<small>確定取引数 {int(row.n):,}件</small></div>'
            f'<div class="annual-pl-track" role="img" aria-label="{full_label}の100株損益 {_yen(value)}">'
            f'{zero_line}<span class="annual-pl-bar{negative}" style="left:{left:.2f}%;width:{width:.2f}%"></span></div>'
            f'<div class="annual-pl-value{negative}">{_yen(value)}</div></div>'
        )
    return '<div class="annual-pl">' + "".join(rows) + '</div>'


def _mode_overall_row(metrics: pd.DataFrame, selector_id: str) -> str:
    lane = metrics[metrics["selector_id"].eq(selector_id)]
    if lane.empty:
        return '<tr><td colspan="16">集計対象がありません</td></tr>'
    total_period = max(lane["period"].astype(str), key=len)
    row = lane[lane["period"].eq(total_period)].iloc[0]
    return (
        f"<tr><th>{html.escape(total_period)}</th><td>{int(row['n'])}</td><td>{int(row['pending'])}</td>"
        f"<td class=\"metric-focus\">{_yen(row['cash_pl_100_yen'])}</td><td class=\"metric-focus\">{_price(row['required_capital_yen'])}</td>"
        f"<td class=\"metric-focus\">{_pct(row['capital_return_pct'], True)}</td><td class=\"metric-focus\">{_pct(row['simple_annualized_pct'], True)}</td>"
        f"<td>{_pct(row['mean_pct'], True)}</td><td>{_pct(row['median_pct'], True)}</td>"
        f"<td>{_pct(row['win_pct'])}</td><td>{_pct(row['plus10_pct'])}</td><td>{_pct(row['plus20_pct'])}</td>"
        f"<td>{_pct(row['minus10_pct'])}</td><td>{_pct(row['minus20_pct'])}</td>"
        f"<td>{_pct(row['max_up_pct'], True)}</td><td>{_pct(row['max_down_pct'], True)}</td></tr>"
    )


def _mode_yearly_rows(metrics: pd.DataFrame, selector_id: str) -> str:
    lane = metrics[metrics["selector_id"].eq(selector_id)].copy()
    if lane.empty:
        return '<tr><td colspan="14">集計対象がありません</td></tr>'
    total_period = max(lane["period"].astype(str), key=len)
    rows = []
    for row in lane[~lane["period"].eq(total_period)].sort_values("period").itertuples():
        rows.append(
            f"<tr><th>{html.escape(str(row.period))}</th><td>{row.n}</td>"
            f"<td class=\"metric-focus\">{_yen(row.cash_pl_100_yen)}</td><td class=\"metric-focus\">{_price(row.required_capital_yen)}</td>"
            f"<td class=\"metric-focus\">{_pct(row.capital_return_pct, True)}</td><td class=\"metric-focus\">{_pct(row.simple_annualized_pct, True)}</td>"
            f"<td>{_pct(row.mean_pct, True)}</td><td>{_pct(row.median_pct, True)}</td><td>{_pct(row.win_pct)}</td>"
            f"<td>{_pct(row.plus10_pct)}</td><td>{_pct(row.plus20_pct)}</td><td>{_pct(row.minus10_pct)}</td><td>{_pct(row.minus20_pct)}</td></tr>"
        )
    return "".join(rows)


def _history_section(
    ledger: pd.DataFrame,
    include_mode_filter: bool,
    mask_pending: bool = False,
) -> str:
    mode_filter = ""
    if include_mode_filter:
        options = "".join(
            f'<option value="{selector_id}">{html.escape(selector_info(selector_id).display_name)}</option>'
            for selector_id in SELECTOR_ORDER
        )
        mode_filter = f'<select id="selector-filter" aria-label="モードで絞り込み"><option value="">すべてのモード</option>{options}</select>'
    access_notice = (
        '<p class="note"><strong>無料表示:</strong> 新着銘柄は5営業日目の終値が確定するまで伏せています。'
        '<a href="/purchase">アクセス権を購入すると確定前から確認できます。</a></p>'
        if mask_pending else ""
    )
    return (
        '<section class="panel" id="history"><h2>検出履歴</h2>'
        + access_notice
        + '<div class="history-details"><p class="history-heading">最新20件を表示中。ボタンで20件ずつ追加できます。</p>'
        '<div class="filters"><label class="filter-field"><span>銘柄</span><input id="symbol-filter" type="search" autocomplete="off" '
        'aria-label="証券コードまたは銘柄名で検索" placeholder="証券コード・銘柄名で検索"></label>'
        '<label class="filter-field"><span>開始日</span><input id="history-date-from" type="date" aria-label="シグナル日の開始日"></label>'
        '<label class="filter-field"><span>終了日</span><input id="history-date-to" type="date" aria-label="シグナル日の終了日"></label>'
        + mode_filter
        + '<button class="clear-search" id="clear-search" type="button">検索をクリア</button>'
        '<output class="result-count" id="search-result-count" aria-live="polite"></output></div>'
        '<noscript><p class="note">検索機能を使うにはJavaScriptを有効にしてください。</p></noscript>'
        '<div class="table-wrap history-table-wrap"><table id="detection-table"><thead><tr><th>シグナル日</th><th>銘柄</th><th>該当モード</th><th>状態</th><th>エントリー</th><th>5営業日目</th><th>騰落率</th><th>100株損益</th><th>操作</th></tr></thead>'
        f'<tbody>{_detection_rows(ledger, mask_pending=mask_pending)}</tbody></table></div>'
        '<div class="history-pagination"><button class="load-more" id="history-load-more" type="button">次の20件を表示</button>'
        '<button class="collapse-results" id="history-collapse" type="button" hidden>最初の20件に戻す</button></div>'
        '</div></section>'
    )


def _actual_period_label(ledger: pd.DataFrame, generated_at: pd.Timestamp) -> str:
    dates = pd.to_datetime(ledger.get("signal_date"), errors="coerce").dropna()
    if dates.empty:
        return "—"
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    return f"{dates.min():%Y-%m-%d}〜{generated:%Y-%m-%d}"


def _actual_period_html(ledger: pd.DataFrame, generated_at: pd.Timestamp) -> str:
    label = _actual_period_label(ledger, generated_at)
    if "〜" not in label:
        return html.escape(label)
    start, end = label.split("〜", 1)
    return f"{html.escape(start)}<br>〜{html.escape(end)}"


def _mode_pages_section(generated: pd.Timestamp, include_updated: bool = True) -> str:
    updated = (
        f'<p class="note">最終更新: {generated:%Y-%m-%d %H:%M:%S JST}</p>'
        if include_updated else ""
    )
    return (
        '<section class="panel" id="conditions"><h2>モード別ページ</h2>'
        f'<div class="condition-grid">{_condition_cards()}</div>{updated}</section>'
    )


def render_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
    mask_pending: bool = False,
) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    unique_ledger = combined_detections(ledger)
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">TEN-TEI-KYOKUCHI / CLOUD</span><h1>天底極致 -Cloud- ダッシュボード</h1><p class="lead">条件に該当した銘柄を新しい順に確認し、5つのモード別ページへ進めます。</p><p class="note">評価ルール: {html.escape(ENDPOINT_LABEL)}。詳しい見方と注意事項は「見方・使い方」をご覧ください。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>モード別の記録件数</small><b>{len(ledger):,}件</b></div><div class="kpi"><small>重複を除いた検出件数</small><b>{len(unique_ledger):,}件</b></div><div class="kpi"><small>記録期間</small><b class="period-range">{_actual_period_html(ledger, generated)}</b></div><div class="kpi"><small>最終検出日</small><b>{pd.to_datetime(ledger['signal_date']).max():%Y-%m-%d}</b></div></div></aside></section>
{_history_section(ledger, include_mode_filter=True, mask_pending=mask_pending)}
{_mode_pages_section(generated)}'''
    return _page_shell("ダッシュボード", "home", body)


def render_analytics_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    monthly_metrics = monthly_metrics if monthly_metrics is not None else pd.DataFrame()
    total_period = max(metrics["period"].astype(str), key=len) if not metrics.empty else "—"
    total = metrics[metrics["period"].eq(total_period)] if not metrics.empty else pd.DataFrame()
    selector_total = total[total["selector_id"].isin(SELECTOR_ORDER)] if not total.empty else total
    best = selector_total.sort_values("cash_pl_100_yen", ascending=False).iloc[0] if not selector_total.empty else None
    unique_ledger = combined_detections(ledger)
    stacked_monthly = monthly_metrics[monthly_metrics["selector_id"].eq(COMBINED_STACKED_ID)] if not monthly_metrics.empty else monthly_metrics
    unique_monthly = monthly_metrics[monthly_metrics["selector_id"].eq(COMBINED_UNIQUE_ID)] if not monthly_metrics.empty else monthly_metrics
    table_head = f'<thead><tr><th>期間</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th class="metric-focus">資金増加率</th><th class="metric-focus">単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th></tr></thead>'
    monthly_head = f'<thead><tr><th>月</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th></tr></thead>'
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">TEN-TEI-KYOKUCHI / CLOUD</span><h1>天底極致 -Cloud- アナリティクス</h1><p class="lead">5つのモードを合わせた成績と資産推移です。検出銘柄はダッシュボード、各モードの内訳は専用ページで確認できます。</p><p class="note">評価ルール: {html.escape(ENDPOINT_LABEL)}。詳しい見方と注意事項は「見方・使い方」をご覧ください。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>モード別の記録件数</small><b>{len(ledger):,}件</b></div><div class="kpi"><small>重複を除いた検出件数</small><b>{len(unique_ledger):,}件</b></div><div class="kpi"><small>記録期間</small><b class="period-range">{_actual_period_html(ledger, generated)}</b><small>最終検出: {pd.to_datetime(ledger['signal_date']).max():%Y-%m-%d}</small></div><div class="kpi"><small>100株損益 首位</small><b>{html.escape(str(best['selector_name'])) if best is not None else '—'}</b></div></div></aside></section>
<section class="panel" id="growth"><h2>トータルの資産推移</h2><p class="note">{html.escape(TOTAL_EQUITY_EXPLANATION)}</p><div class="chart-grid">{_equity_chart(ledger, 'モード別積み上げ', 'stacked', STACKED_EXPLANATION, generated.tz_localize(None))}{_equity_chart(unique_ledger, '銘柄均等', 'unique', UNIQUE_EXPLANATION, generated.tz_localize(None))}</div></section>
<div class="insight-grid"><section class="panel" id="payoff-structure">{_payoff_structure(ledger)}</section><section class="panel" id="annual-pl"><h2>年別100株損益</h2><p class="note">モード別積み上げの集計です。同じ日・同じ銘柄が複数モードに該当した場合は、モードごとに100株の別取引として数えます。5営業日後の終値が確定した取引を検出年ごとに合計し、日次レポート更新時に数値も更新します。</p>{_annual_pl_chart(ledger, metrics, generated)}</section></div>
<section class="panel" id="stacked-performance"><h2>Cloud全体の成績 — モード別積み上げ</h2><p class="note">{html.escape(STACKED_EXPLANATION)}</p><div class="table-wrap"><table data-paginated-table>{table_head}<tbody>{_combined_rows(metrics, COMBINED_STACKED_ID)}</tbody></table></div>{_table_pagination()}<details class="monthly-details"><summary>月別の詳しい成績を見る</summary><div class="table-wrap"><table data-paginated-table>{monthly_head}<tbody>{_monthly_rows(stacked_monthly, show_mode=False)}</tbody></table></div>{_table_pagination()}</details></section>
<section class="panel" id="unique-performance"><h2>Cloud全体の成績 — 銘柄均等</h2><p class="note">{html.escape(UNIQUE_EXPLANATION)}</p><div class="table-wrap"><table data-paginated-table>{table_head}<tbody>{_combined_rows(metrics, COMBINED_UNIQUE_ID)}</tbody></table></div>{_table_pagination()}<details class="monthly-details"><summary>月別の詳しい成績を見る</summary><div class="table-wrap"><table data-paginated-table>{monthly_head}<tbody>{_monthly_rows(unique_monthly, show_mode=False)}</tbody></table></div>{_table_pagination()}</details></section>
<section class="panel"><h2>モード別の全期間比較</h2><p class="note">順位は100株ずつ売買した累計損益額順です。</p><div class="table-wrap"><table><thead><tr><th>順位</th><th>モード</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th class="metric-focus">資金増加率</th><th class="metric-focus">単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th><th>Top3除外平均</th></tr></thead><tbody>{_overall_rows(metrics)}</tbody></table></div></section>
{_mode_pages_section(generated)}'''
    return _page_shell("アナリティクス", "analytics", body)


def render_mode_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    monthly_metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    selector_id: str,
    mask_pending: bool = False,
) -> str:
    info = selector_info(selector_id)
    lane = ledger[ledger["selector_id"].eq(selector_id)].copy()
    lane_monthly = monthly_metrics[monthly_metrics["selector_id"].eq(selector_id)]
    lane_metrics = metrics[metrics["selector_id"].eq(selector_id)]
    total_period = max(lane_metrics["period"].astype(str), key=len) if not lane_metrics.empty else "—"
    total = lane_metrics[lane_metrics["period"].eq(total_period)].iloc[0] if not lane_metrics.empty else None
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">CLOUD MODE</span><h1>{html.escape(info.display_name)}</h1><p class="lead">{html.escape(info.feature_summary)}</p><p>{html.escape(info.selection_summary)}</p><p class="note">評価ルール: {html.escape(ENDPOINT_LABEL)}。投資助言ではありません。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>確定取引数</small><b>{int(total['n']) if total is not None else 0}件</b></div><div class="kpi"><small>平均騰落率</small><b>{_pct(total['mean_pct'], True) if total is not None else '—'}</b></div><div class="kpi"><small>勝率</small><b>{_pct(total['win_pct']) if total is not None else '—'}</b></div><div class="kpi"><small>100株損益</small><b>{_yen(total['cash_pl_100_yen']) if total is not None else '—'}</b></div></div></aside></section>
<section class="panel"><h2>{html.escape(info.display_name)} の資産推移</h2><p class="note">{html.escape(TOTAL_EQUITY_EXPLANATION)}</p>{_equity_chart(lane, info.display_name, selector_id.replace('_', '-'), as_of=generated.tz_localize(None))}</section>
<section class="panel" id="performance"><h2>全期間の成績</h2><div class="table-wrap"><table><thead><tr><th>期間</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th class="metric-focus">資金増加率</th><th class="metric-focus">単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th></tr></thead><tbody>{_mode_overall_row(metrics, selector_id)}</tbody></table></div></section>
<section class="panel"><h2>年別の成績</h2><div class="table-wrap"><table data-paginated-table><thead><tr><th>年</th><th>確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th class="metric-focus">資金増加率</th><th class="metric-focus">単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th></tr></thead><tbody>{_mode_yearly_rows(metrics, selector_id)}</tbody></table></div>{_table_pagination()}<details class="monthly-details"><summary>月別の詳しい成績を見る</summary><div class="table-wrap"><table data-paginated-table><thead><tr><th>月</th><th>モード</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th></tr></thead><tbody>{_monthly_rows(lane_monthly)}</tbody></table></div>{_table_pagination()}</details></section>
{_history_section(lane, include_mode_filter=False, mask_pending=mask_pending)}
{_mode_pages_section(generated)}'''
    return _page_shell(info.display_name, selector_id, body)


def render_guide(generated_at: pd.Timestamp) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">GUIDE</span><h1>見方・使い方</h1>
<p class="lead">はじめての方でも、見つかった銘柄と過去の成績を順番に確認できるガイドです。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>エントリー</small><b>翌営業日寄付</b></div><div class="kpi"><small>評価</small><b>5営業日目終値</b></div><div class="kpi"><small>売買単位</small><b>100株</b></div><div class="kpi"><small>コスト</small><b>0%試算</b></div></div></aside></section>
<section class="panel"><h2>まず見る場所</h2><div class="guide-grid">
<article class="guide-card"><h3>ダッシュボード</h3><p>最初に開くページです。条件に当てはまった銘柄を新しい順に確認し、銘柄名・証券コード・日付・モードで絞り込めます。</p></article>
<article class="guide-card"><h3>アナリティクス</h3><p>Cloud全体の過去成績を見るページです。100株ずつ取引した場合の損益、勝率、平均騰落率、資産の動きを確認できます。</p></article>
<article class="guide-card"><h3>5つのモード</h3><p>モードは、銘柄を選ぶ「見方の違い」です。Shadow、Dive、Silence、Fusion、Balanceを押すと、それぞれの成績と検出銘柄を確認できます。</p></article>
<article class="guide-card"><h3>検出履歴</h3><p>条件に当てはまった銘柄の一覧です。最初は新しい順に20件を表示し、銘柄名・証券コード・日付で絞り込めます。「さらに20件表示」で続きを確認できます。</p></article>
<article class="guide-card"><h3>ファンダ分析</h3><p>会社がどんな事業をしているか、検出時点までに公表されていた決算やお知らせ、その内容から読み取れる注目点と注意点をまとめています。資料名を押すと根拠となる開示資料を確認できます。</p></article>
</div></section>
<section class="panel"><h2>成績の読み方</h2><div class="guide-grid">
<article class="guide-card"><h3>100株損益</h3><p>検出された銘柄を毎回100株ずつ売買した、と仮定した損益の合計です。税金や手数料は入れていません。</p></article>
<article class="guide-card"><h3>必要資金（目安）</h3><p>複数の銘柄を同時に持つ期間も考えたうえで、100株ずつ取引するために最も多く必要だった資金の目安です。</p></article>
<article class="guide-card"><h3>資金増加率・単純年率</h3><p>必要資金に対して損益が何%だったかと、それを1年あたりに単純換算した参考値です。利益を再投資する複利計算ではありません。</p></article>
<article class="guide-card"><h3>勝率と騰落率</h3><p>勝率は、利益になった取引の割合です。買値と売値が同じ取引は数えません。騰落率は、買った価格から売った価格まで何%動いたかを表します。</p></article>
</div></section>
<section class="panel"><h2>2つの合算方法</h2><div class="guide-grid"><article class="guide-card"><h3>モード別積み上げ</h3><p>{html.escape(STACKED_EXPLANATION)}</p></article><article class="guide-card"><h3>銘柄均等</h3><p>{html.escape(UNIQUE_EXPLANATION)}</p></article></div><p class="note">複数モードへの同時該当は、将来の値動きを保証するものではありません。</p></section>
<section class="panel"><h2>大切な注意事項</h2>
<p>本サイトは過去データとルールに基づく情報提供・検証を目的としたもので、特定銘柄の売買を勧める投資助言ではありません。将来の収益や価格上昇を保証するものでもありません。</p>
<p>実際の取引では、手数料、税金、スリッページ、流動性、値幅制限、寄付で約定できない可能性などにより結果が異なります。投資判断は、ご自身で最新の開示・株価・財務情報を確認したうえで行ってください。</p>
<p class="note">最終更新: {generated:%Y-%m-%d %H:%M:%S JST}</p></section>'''
    return _page_shell("見方・使い方", "guide", body)


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
        render_report(
            ledger,
            metrics,
            generated,
            monthly_metrics=monthly_metrics,
            mask_pending=True,
        ),
        encoding="utf-8",
    )
    analytics_path = report_path.with_name(ANALYTICS_PAGE_NAME)
    analytics_html = render_analytics_report(
        ledger,
        metrics,
        generated,
        monthly_metrics=monthly_metrics,
    )
    analytics_path.write_text(analytics_html, encoding="utf-8")
    analytics_path.with_name(analytics_path.stem + "_free.html").write_text(
        analytics_html,
        encoding="utf-8",
    )
    guide_path = report_path.with_name(GUIDE_PAGE_NAME)
    guide_html = render_guide(generated)
    guide_path.write_text(guide_html, encoding="utf-8")
    guide_path.with_name(guide_path.stem + "_free.html").write_text(
        guide_html,
        encoding="utf-8",
    )
    for selector_id, filename in MODE_PAGE_NAMES.items():
        mode_path = report_path.with_name(filename)
        mode_path.write_text(
            render_mode_report(ledger, metrics, monthly_metrics, generated, selector_id),
            encoding="utf-8",
        )
        mode_path.with_name(mode_path.stem + "_free.html").write_text(
            render_mode_report(
                ledger,
                metrics,
                monthly_metrics,
                generated,
                selector_id,
                mask_pending=True,
            ),
            encoding="utf-8",
        )
    return metrics
