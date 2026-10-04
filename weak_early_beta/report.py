"""Standalone user-friendly HTML report for the Weak+Early beta."""

from __future__ import annotations

import html
import json
import re
import base64
import gzip
import hashlib
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .config import (
    COMBINED_STACKED_ID,
    COMBINED_SELECTOR_IDS,
    COMBINED_UNIQUE_ID,
    ENDPOINT_LABEL,
    SELECTOR_ORDER,
    selector_info,
)
from .entry_feasibility import annotate_entry_feasibility, performance_eligible
from .impact import normalize_material_impact
from .analytics import build_analytics, build_presentation_metrics, validated_unique_detections as combined_detections
from .endpoint_receipts import signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified
from .report_preferences import (
    DEFAULT_PRICE_CAP, ENDPOINT_LABELS, select_report_view, visible_history, released_history,
    verified_signal_prices,
)
from .reviewed_endpoint_overlay import load_reviewed_endpoint_overlay, apply_reviewed_endpoint_overlay
from .reviewed_d5_overlay import apply_reviewed_d5_overlay
from .metrics import (
    build_metrics,
    build_monthly_metrics,
    coverage_years,
    required_capital,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "weak_early_beta_latest.html"
DEFAULT_METRICS = ROOT / "weak_early_beta" / "state" / "metrics.csv"
DEFAULT_MONTHLY_METRICS = ROOT / "weak_early_beta" / "state" / "monthly_metrics.csv"
MAX_REPORT_BYTES = 24 * 1024 * 1024
GUIDE_PAGE_NAME = "weak_early_beta_guide.html"
ANALYTICS_PAGE_NAME = "weak_early_beta_analytics.html"
MODE_PAGE_NAMES = {
    selector_id: f"weak_early_beta_{selector_info(selector_id).short_name.lower()}.html"
    for selector_id in SELECTOR_ORDER
}

TOTAL_EQUITY_EXPLANATION = (
    "成績集計対象の取引を100株ずつ運用するために同時保有も含めて必要だった資金の目安から開始し、"
    "各取引が決済した日に損益を加えた推移です。"
)
REFERENCE_POLICY_NOTE = (
    "ストップ高で買付が難しい銘柄は、参考値として履歴に残し、成績とグラフには含めません。"
    "実際の注文結果を示すものではありません。"
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


def _source_label(url: str, company_name: str, symbol: str) -> str:
    subject = company_name or symbol or "発行体"
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "finance.yahoo.co.jp" in host and "/disclosure" in path:
        return f"Yahoo!ファイナンス {symbol} 適時開示一覧"
    if "irbank.net" in host:
        return f"IRBANK {subject} 開示一覧"
    if "/news" in path or "/category/news" in path:
        return f"{subject} ニュース一覧"
    if "/library" in path or "/ir-docs" in path:
        return f"{subject} IR資料一覧"
    return f"{subject} IR情報"


def _link_entries(value: str) -> list[str]:
    return [entry.strip().lstrip("・• ").strip() for entry in re.split(r"[\r\n;；]+", str(value or "")) if entry.strip()]


def _source_links_html(value: str, company_name: str, symbol: str) -> str:
    links: list[str] = []
    seen: set[str] = set()
    for entry in _link_entries(value):
        # Source lines often carry parenthetical research notes after a Markdown
        # link. Keep only the source label and URL, as in the Premium report.
        markdown_links = list(MARKDOWN_LINK_RE.finditer(entry))
        if markdown_links:
            candidates = [(match.group(2), match.group(1)) for match in markdown_links]
        else:
            matches = list(BARE_URL_RE.finditer(entry))
            if len(matches) != 1:
                continue
            match = matches[0]
            url = match.group(0).rstrip(".,;:!?、。)]}）】」』")
            label = entry[: match.start()].strip(" ：:・•-–—") or _source_label(url, company_name, symbol)
            candidates = [(url, label)]
        for url, label in candidates:
            if url not in seen:
                links.append("・" + _anchor(url, label))
                seen.add(url)
    if not links:
        return _linkify(value)
    return "<br>".join(links)


@lru_cache(maxsize=1)
def _historical_snapshot_metadata() -> dict[tuple[str, str], dict]:
    path = ROOT / "weak_early_beta" / "fundamental_worker" / "out" / "historical_backfill_receipts.json"
    try:
        reports = json.loads(path.read_text(encoding="utf-8")).get("reports", [])
    except (OSError, ValueError):
        return {}
    lookup: dict[tuple[str, str], dict] = {}
    for report in reports:
        if report.get("auditStatus") != "pass":
            continue
        labels: dict[str, str] = {}
        for disclosure in report.get("disclosures", []):
            url = str(disclosure.get("url") or "").strip()
            title = str(disclosure.get("title") or "").strip()
            published = str(disclosure.get("publishedAt") or "").strip()
            if not (url and title and published and disclosure.get("contentReviewed")):
                continue
            try:
                stamp = pd.Timestamp(published).tz_convert("Asia/Tokyo")
            except (ValueError, TypeError):
                continue
            labels[url] = f"{stamp:%Y-%m-%d} {title}({stamp:%H:%M})"
        key = (str(report.get("signalDate") or ""), str(report.get("symbolCode") or ""))
        lookup[key] = {"cutoff": str(report.get("analysisCutoff") or ""), "disclosures": labels}
    return lookup


def _bare_disclosure_label(prefix: str) -> str:
    dated = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(.*))?$", prefix)
    if not dated:
        return prefix.strip(" 「」")
    date = dated.group(1)
    title = (dated.group(2) or "").strip()
    time = ""
    time_prefix = re.match(r"^(\d{1,2}:\d{2})(?:\+09:00)?\s*(.*)$", title)
    if time_prefix:
        time = time_prefix.group(1)
        title = time_prefix.group(2).strip()
    if title.startswith("「") and title.endswith("」"):
        title = title[1:-1].strip()
    time_suffix = re.search(r"\s*\((\d{1,2}:\d{2})\)$", title)
    if time_suffix:
        time = time or time_suffix.group(1)
        title = title[: time_suffix.start()].rstrip()
    return f"{date} {title}" + (f"({time})" if time else "")


def _disclosure_links_html(value: str, metadata: dict | None = None) -> str:
    """Render both Markdown and plain disclosure URLs as Premium-style links."""
    rendered: list[str] = []
    seen: set[str] = set()
    disclosure_labels = (metadata or {}).get("disclosures", {})
    for entry in _link_entries(value):
        markdown = MARKDOWN_LINK_RE.fullmatch(entry)
        if markdown:
            label, url = markdown.group(1), markdown.group(2)
        else:
            matches = list(BARE_URL_RE.finditer(entry))
            if len(matches) != 1:
                rendered.append(_linkify(entry))
                continue
            match = matches[0]
            url = match.group(0).rstrip(".,;:!?、。)]}）】」』")
            label = _bare_disclosure_label(entry[: match.start()].strip())
        if url not in seen:
            rendered.append("・" + _anchor(url, disclosure_labels.get(url) or label or "開示資料"))
            seen.add(url)

    return "<br>".join(rendered)


def _fundamental_html(
    value: str, company_name: str, symbol: str, signal_date: str, metadata: dict | None = None
) -> str:
    """Turn the stored Premium-style field text into a safe, linked embed."""
    fields: list[tuple[str, str]] = []
    for block in re.split(r"\n\s*\n", str(value or "").strip()):
        lines = block.splitlines()
        if len(lines) >= 2 and lines[0].strip():
            fields.append((lines[0].strip(), "\n".join(lines[1:]).strip()))
    title = f"{company_name or symbol}({symbol}) | TradingView チャート"
    chart_url = f"https://jp.tradingview.com/chart/?symbol=TSE%3A{symbol}"
    title_html = f"<h4>{_anchor(chart_url, title)}</h4>"
    cutoff = (metadata or {}).get("cutoff")
    timing = f"基準時点: {cutoff}" if cutoff else f"分析対象日: {signal_date}"
    meta_html = (
        '<p class="discord-meta">'
        f"{html.escape('Cloud fundamental snapshot / Not investment advice / ' + timing)}"
        "</p>"
    )
    if not fields:
        return (
            '<div class="discord-message"><article class="discord-embed">'
            f"{title_html}<p>{_linkify(value)}</p>{meta_html}</article></div>"
        )
    impact, impact_class, _changed = normalize_material_impact(fields)
    field_html = "".join(
        f"<div><dt>{html.escape(name)}</dt><dd>"
        f"{_source_links_html(content, company_name, symbol) if name == 'Sources' else _disclosure_links_html(content, metadata) if name == '開示リンク' else _linkify(impact) if name == '材料インパクト' else _linkify(content)}"
        "</dd></div>"
        for name, content in fields
    )
    return (
        f'<div class="discord-message"><article class="discord-embed{impact_class}">'
        f"{title_html}<dl>{field_html}</dl>{meta_html}</article></div>"
    )


def _display_material_impact(fields: list[tuple[str, str]]) -> tuple[str, str]:
    """Compatibility wrapper around the shared persisted-impact formatter."""
    value, impact_class, _changed = normalize_material_impact(fields)
    return value, impact_class


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
    if metrics.empty:
        return '<tr><td colspan="16">集計対象がありません</td></tr>'
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
    # Free pages omit the entire unreleased record, including otherwise
    # identifying dates, prices, mode combinations and individual economics.
    ledger = annotate_entry_feasibility(select_report_view(released_history(ledger) if mask_pending else visible_history(ledger), None, "d5_close"))
    if ledger.empty:
        return '<tr><td colspan="8">検出履歴がありません</td></tr>'
    data = ledger.copy()
    data["signal_date"] = pd.to_datetime(data["signal_date"])
    rows = []
    historical_metadata = _historical_snapshot_metadata()
    visible_count = 0
    grouped = data.groupby(["signal_date", "symbol"], sort=False)
    for index, ((signal_date, symbol), group) in enumerate(
        sorted(grouped, key=lambda item: item[0], reverse=True)
    ):
        first = group.iloc[0]
        selectors = str(first.get("report_matched_selectors", "") or "").split() or group["selector_id"].astype(str).tolist()
        badges = "".join(
            f'<span class="badge">{html.escape(selector_info(s).short_name)}</span>'
            for s in selectors
        )
        units = len(selectors)
        badges += f'<small>一致した条件: {units}個</small>'
        raw_name = first.get("company_name", "")
        name = "" if pd.isna(raw_name) else str(raw_name).strip()
        if name.lower() == "nan":
            name = ""
        gross = pd.to_numeric(group["gross_return"], errors="coerce").dropna()
        cash = pd.to_numeric(group["one_hundred_shares_pl_yen"], errors="coerce").dropna()
        reference_only = (
            bool(group["performance_reference_only"].fillna(False).any())
            if "performance_reference_only" in group else False
        )
        if reference_only:
            status, status_class = ("参考値・成績に含めません" if not gross.empty else "価格未確認・成績に含めません"), "reference"
        else:
            status = "確定" if not gross.empty else ("保有中" if str(first["status"]) == "entered" else "買付待ち")
            status_class = "mature" if not gross.empty else "pending"
        # A D5 return, elapsed date or an adjusted reference open is not enough
        # to release an identity. All overlapping receipts must be verified.
        d6_verified = all(sixth_endpoint_verified(row) for _, row in group.iterrows())
        is_masked = mask_pending and not d6_verified
        signal_verified = all(signal_actual_close_verified(row) for _, row in group.iterrows())
        signal_price = float(first["signal_actual_close"]) if signal_verified else None
        default_match = signal_price is not None and signal_price <= DEFAULT_PRICE_CAP
        initial_hidden = not default_match or visible_count >= 20
        if default_match:
            visible_count += 1
        evidence_url = str(first.get("performance_reference_evidence_url", "") or "")
        evidence_label = (
            "JPX一値記録"
            if first.get("performance_reference_verification_note") == "user_designated_one_price"
            else "JPX日報"
        )
        evidence_link = (
            f' <a href="{html.escape(evidence_url, quote=True)}" target="_blank" rel="noopener noreferrer">{evidence_label}</a>'
            if not is_masked and reference_only and evidence_url.startswith("https://www.jpx.co.jp/") else ""
        )
        reference_note = (
            '<small class="reference-note">ストップ高で買付が難しいため、成績に含めません。'
            f'{"騰落率と損益は参考値です。" if not gross.empty else "価格を確認できないため、損益は表示しません。"}{evidence_link}</small>'
            if reference_only else ""
        )
        reference_marker = '<small class="reference-value">参考値</small>' if reference_only else ""
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
            signal_day = f"{signal_date:%Y-%m-%d}"
            snapshot_metadata = historical_metadata.get((signal_day, str(symbol)))
            actions = (
                '<button class="fundamental-toggle" data-fundamental-toggle type="button" '
                'aria-expanded="false">ファンダ分析</button>'
                '<dialog class="fundamental-detail" aria-label="ファンダ分析の詳細">'
                '<button class="fundamental-close" type="button" aria-label="ファンダ分析を閉じる">×</button>'
                f'{_fundamental_html(fundamental_html, name, str(symbol), signal_day, snapshot_metadata)}'
                '</dialog>'
            )
        elif fundamental_url:
            actions = f'<a class="button-link" href="{html.escape(fundamental_url)}">ファンダ分析</a>'
        display_symbol = "••••" if is_masked else str(symbol)
        display_name = "検出から6営業日後の実始値取得・確定まで会員限定" if is_masked else name
        search_text = "" if is_masked else f"{symbol} {name}".strip()
        entry_display = "会員限定" if is_masked else f"{_date(first['entry_date'])}<small>{_price(first['entry_open'])}</small>"
        d5_price = _price(first['fifth_xtks_exit_close']) if pd.notna(first.get('fifth_xtks_exit_close')) else ""
        exit_display = "会員限定" if is_masked else f"{_date(first['fifth_xtks_exit_date'])}<small>{d5_price}</small>"
        today = pd.Timestamp.now(tz="Asia/Tokyo").tz_localize(None).normalize()
        d5_day = pd.Timestamp(first.get("fifth_xtks_exit_date"))
        d5_verified = pd.notna(first.get("gross_return")) and pd.notna(first.get("fifth_xtks_exit_close"))
        d5_price_status = "取得済み" if d5_verified else ("確定日待ち" if pd.notna(d5_day) and d5_day > today else "未取得")
        if not d5_verified:
            exit_display += f'<small class="endpoint-status">{d5_price_status}</small>'
        if not is_masked and str(first.get("price_basis", "")).startswith("LEGACY_"):
            entry_display += "<small>保存時の調整価格参考値</small>"
            exit_display += "<small>保存時の調整価格参考値</small>"
        from .bank_calendar import add_bank_business_days
        d6_session = pd.Timestamp(first.get("sixth_xtks_exit_date"))
        if pd.isna(d6_session):
            d6_session = pd.Timestamp(add_bank_business_days(signal_date.date(), 6))
        d6_day = _date(d6_session)
        d6_price = _price(first.get("sixth_xtks_exit_open")) if d6_verified else ""
        d6_status = "取得済み" if d6_verified else ("確定日待ち" if d6_session > today else "未取得")
        d6_display = "会員限定" if is_masked else f"{d6_day}<small>{d6_price}</small>" + ("" if d6_verified else f"<small>{d6_status}</small>")
        signal_display = "会員限定" if is_masked else (_price(signal_price) if signal_verified else "未取得")
        sixth_return = pd.to_numeric(first.get("sixth_gross_return"), errors="coerce")
        sixth_cash = pd.to_numeric(first.get("sixth_one_hundred_shares_pl_yen"), errors="coerce")
        d6_economic = sixth_economics_verified(first)
        d6_result_status = "結果あり" if d6_economic else ("損益を確認中" if d6_verified else ("保有中" if str(first["status"]) == "entered" else "買付待ち"))
        acquired_date = first.get('sixth_entry_date') if d6_economic else first.get('entry_date')
        acquired_open = first.get('sixth_entry_open') if d6_economic else first.get('entry_open')
        d6_entry_display = "会員限定" if is_masked else (
            f"{_date(acquired_date)}<small>{_price(acquired_open)}</small>"
            if pd.notna(acquired_open) else "未取得"
        )
        d6_return_display = _pct(sixth_return * 100, True) if d6_economic and pd.notna(sixth_return) else ""
        d6_cash_display = _yen(sixth_cash) if d6_economic and pd.notna(sixth_cash) else ""
        chart_action = (
            '<a class="button-link" href="/purchase">アクセス権を購入する</a>'
            if is_masked
            else f'<a class="button-link" href="https://jp.tradingview.com/chart/?symbol=TSE%3A{html.escape(str(symbol))}">チャート</a>'
        )
        actions += chart_action
        export_fields = {
            "name": name,
            "reference": str(reference_only).lower(),
            "historical": str(str(first.get("source_scope", "")).startswith("EXACT_CANONICAL")).lower(),
            "entry-date": _date(first.get("entry_date")),
            "entry-open": first.get("entry_open"),
            "entry-cost": first.get("entry_cost_yen"),
            "entry-shares": first.get("entry_shares"),
            "d5-proceeds": first.get("exit_proceeds_yen"),
            "d5-exit-shares": first.get("exit_shares"),
            "d5-date": _date(first.get("fifth_xtks_exit_date")),
            "d5-close": first.get("fifth_xtks_exit_close"),
            "d5-return": first.get("gross_return"),
            "d5-status": d5_price_status,
            "d6-date": d6_day,
            "d6-open": first.get("sixth_xtks_exit_open") if d6_verified else None,
            "d6-return": sixth_return if d6_economic else None,
            "d6-status": d6_status,
            "d6-entry-date": _date(acquired_date) if pd.notna(acquired_open) else None,
            "d6-entry-open": acquired_open,
            "d6-entry-cost": first.get("sixth_entry_cost_yen") if d6_economic else first.get("entry_cost_yen"),
            "d6-entry-shares": first.get("sixth_entry_shares") if d6_economic else first.get("entry_shares"),
            "d6-proceeds": first.get("sixth_exit_proceeds_yen") if d6_economic else None,
            "d6-exit-shares": first.get("sixth_exit_shares") if d6_economic else None,
        }
        export_attributes = " ".join(
            f'data-{key}="{html.escape(str(value), quote=True)}"'
            for key, value in export_fields.items()
            if not is_masked and value is not None and pd.notna(value)
        )
        rows.append(
            f'<tr data-selectors="{html.escape(" ".join(selectors))}" '
            f'data-date="{signal_date:%Y-%m-%d}" '
            f'data-signal-actual-close="{signal_price if signal_verified else ""}" '
            f'data-signal-price-status="{"verified" if signal_verified else "missing"}" '
            f'data-signal-price-verified="{str(signal_verified).lower()}" '
            f'data-d6-verified="{str(d6_verified).lower()}" '
            f'{export_attributes} '
            f'data-symbol="{"" if is_masked else html.escape(str(symbol))}" data-search="{html.escape(search_text)}"'
            f'{" hidden" if initial_hidden else ""}>'
            '<td colspan="8" class="history-record"><div class="history-visible-grid">'
            f'<div data-label="検出日">{signal_date:%Y-%m-%d}</div>'
            f'<div class="history-company"><strong><span class="symbol">{html.escape(display_symbol)}</span> {html.escape(display_name)}</strong><small>検出日 終値 {signal_display}</small><div class="actions">{actions}</div></div>'
            f'<div data-label="該当モード">{badges}<small data-scenario-shares>100株で買付</small></div>'
            f'<div data-label="保有状況"><span data-exit-key="d5_close" class="status {status_class}">{"結果あり" if status == "確定" else status}</span><span data-exit-key="d6_open" class="status {"reference" if reference_only else "mature" if d6_economic else "pending"}" hidden>{"参考値・成績に含めません" if reference_only else d6_result_status}</span></div>'
            f'<div data-label="買付日・始値"><span data-exit-key="d5_close">{entry_display}</span><span data-exit-key="d6_open" hidden>{d6_entry_display}</span><small data-scenario-cost></small></div>'
            f'<div data-label="5営業日後 終値">{exit_display}</div>'
            f'<div data-label="6営業日後 始値">{d6_display}</div>'
            f'<div data-label="成績" class="number"><small class="history-endpoint-label" data-scenario-endpoint-label>6営業日後 始値</small><strong data-scenario-pl>{_yen(cash.iloc[0]) if not cash.empty else "—"}</strong><small data-scenario-return>{_pct(gross.iloc[0] * 100, True) if not gross.empty else "—"}</small>{reference_marker}</div>'
            '</div>' + reference_note + '</td>'
            "</tr>"
        )
    return "".join(rows)


REPORT_CSS = """
#detection-table{width:100%;min-width:0;table-layout:fixed}#detection-table thead th:nth-child(1){width:34%}#detection-table thead th:nth-child(n+2){width:16.5%}

#cloud-notification-settings label,.cloud-notification-settings label{display:block;margin:12px 0}
#cloud-notification-settings input[type="checkbox"],.cloud-notification-settings input[type="checkbox"]{width:auto;min-width:20px;min-height:20px;margin-right:10px;vertical-align:middle}
#cloud-notification-settings summary,.cloud-notification-settings summary{min-height:44px;padding:10px 0;cursor:pointer;font-weight:700}
#cloud-settings-status[data-state="error"]{color:var(--warn)}
.cloud-settings button{min-height:44px;padding:8px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel-solid);color:var(--ink)}
@media(max-width:620px){.cloud-settings .filters .filter-field{grid-column:1/-1}}

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
.history-details{border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--bg) 38%,var(--panel-solid));padding:14px}.history-heading{font-weight:800;margin:0 0 14px;color:var(--blue)}.filters{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin-bottom:14px}.filter-field{display:grid;gap:4px}.filter-field span{font-size:12px;color:var(--muted);font-weight:700}.filters input,.filters select{border:1px solid var(--line);background:var(--panel-solid);color:var(--ink);border-radius:10px;padding:10px 12px}.filters input[type="search"]{min-width:min(360px,100%)}.result-count{color:var(--muted);font-weight:700}.history-pagination{display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;margin-top:14px}.status{font-weight:750}.status.mature{color:var(--good)}.status.pending{color:var(--warn)}.number{font-variant-numeric:tabular-nums}.symbol{font-size:17px}.actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:5px}.button-link,.fundamental-toggle{display:inline-flex;align-items:center;border:1px solid var(--line);background:var(--bg);color:var(--blue);text-decoration:none;border-radius:7px;padding:4px 8px}.fundamental-detail{white-space:normal;min-width:320px;max-width:650px;margin-top:8px;padding:12px;background:var(--bg);border-radius:10px}.discord-embed{border-left:4px solid var(--blue);background:var(--panel-solid);border-radius:8px;padding:12px;text-align:left}.discord-embed.impact-positive{border-left-color:#12b76a;background:color-mix(in srgb,#12b76a 10%,var(--panel-solid))}.discord-embed.impact-watch{border-left-color:#fdb022;background:color-mix(in srgb,#fdb022 11%,var(--panel-solid))}.discord-embed.impact-negative{border-left-color:#f04438;background:color-mix(in srgb,#f04438 9%,var(--panel-solid))}.discord-embed dl{display:grid;gap:10px;margin:0}.discord-embed dt{font-weight:800;color:var(--muted)}.discord-embed dd{margin:2px 0 0;overflow-wrap:anywhere;white-space:normal}
.note{color:var(--muted);font-size:13px}.monthly-details{margin-top:16px;border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--bg) 55%,var(--panel-solid));padding:0 14px 14px}.monthly-details summary{cursor:pointer;font-weight:800;padding:14px 2px;color:var(--blue)}.guide-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.guide-card{border:1px solid var(--line);border-radius:16px;background:var(--panel-solid);padding:18px}.site-footer{border-top:1px solid var(--line);background:color-mix(in srgb,var(--panel-solid) 78%,transparent);padding:26px 20px}.site-footer-inner{max-width:1440px;margin:auto;display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap}.footer-copy{margin:0;color:var(--muted)}.footer-links{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.footer-link{display:inline-flex;align-items:center;justify-content:center;min-width:42px;min-height:40px;padding:6px 8px;border:1px solid transparent;border-radius:8px;background:transparent;text-decoration:none}.footer-link:hover{border-color:#b7c8e4;background:#eef5ff}.footer-logo{display:block;object-fit:contain}.footer-logo-dark{display:none}.footer-logo-x{width:24px;height:24px}.footer-logo-discord{width:35px;height:27px}.footer-logo-coconala{width:76px;height:42px}:root[data-theme="dark"] .footer-link:hover{background:#183250;border-color:#4f8dff}:root[data-theme="dark"] .footer-logo-light{display:none}:root[data-theme="dark"] .footer-logo-dark{display:block}
@media(max-width:1100px){.insight-grid{grid-template-columns:1fr}.insight-grid .annual-pl-row{grid-template-columns:minmax(160px,220px) minmax(0,1fr) minmax(135px,175px);gap:14px}}
@media(max-width:1000px){.hero{grid-template-columns:1fr}.condition-grid{grid-template-columns:repeat(2,1fr)}.chart-grid,.guide-grid{grid-template-columns:1fr}}
@media(max-width:760px){.nav{grid-template-columns:minmax(0,1fr) auto;padding:8px 12px;gap:4px 8px}.brand{grid-column:1;grid-row:1}.brand-logo{width:min(250px,61vw);height:44px}.theme-toggle{grid-column:2;grid-row:1;min-height:38px}.nav-links{grid-column:1/-1;grid-row:2;justify-content:flex-start;flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;padding-bottom:3px}.nav-link{flex:0 0 auto;font-size:13px;padding:6px 9px}}
@media(max-width:620px){main{padding:18px 12px 50px;min-width:0}.panel{padding:16px;border-radius:14px;min-width:0}.condition-grid{grid-template-columns:1fr}.kpis{grid-template-columns:1fr 1fr}.chart-stats{grid-template-columns:1fr}.insight-grid .annual-pl-row{grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;margin:19px 0}.annual-pl-track{grid-column:1/-1;grid-row:2}.annual-pl-value{grid-column:2;grid-row:1}.payoff-kpis{gap:5px}.payoff-kpi strong{font-size:22px}.filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:end}.filter-field{min-width:0}.filters input,.filters select{width:100%;min-width:0!important}.filters .filter-field:first-child,#selector-filter,#search-result-count{grid-column:1/-1}.history-table-wrap{overflow:visible;border:0;background:transparent}#detection-table{min-width:0;background:transparent}#detection-table thead{display:none}#detection-table tbody{display:grid;gap:12px}#detection-table tbody tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));padding:10px;border:1px solid var(--line);border-radius:12px;background:var(--panel-solid)}#detection-table tbody tr>*{display:block;min-width:0;white-space:normal;border:0;padding:6px 8px;text-align:left}#detection-table tbody tr>td:first-child,#detection-table tbody tr>th,#detection-table tbody tr>td:nth-child(3){grid-column:1/-1}#detection-table tbody tr>th{font-size:16px;border-bottom:1px solid var(--line);padding-bottom:10px}#detection-table tbody tr>td::before{content:attr(data-label);display:block;color:var(--muted);font-size:11px;font-weight:800}.fundamental-detail{min-width:0;max-width:100%;overflow-wrap:anywhere}.discord-embed{min-width:0}.button-link,.fundamental-toggle{min-height:36px;align-items:center}.kpi b.period-range{font-size:15px;white-space:normal}}
.status.reference{color:var(--warn)}
.reference-note,.reference-value{display:block;color:var(--muted);font-size:11px;line-height:1.45;white-space:normal}
.reference-note{max-width:250px;margin-top:4px}.reference-note a{color:var(--blue)}
/* Match the current report's fundamental popup, independent of the table header's typography. */
.fundamental-detail{position:relative;box-sizing:border-box;width:100%;min-width:0;max-width:520px;margin-top:8px;padding:10px 38px 10px 10px;border:1px solid var(--line);border-radius:6px;background:#fbfdff;color:#182230;text-align:left;white-space:normal;font:400 14px/1.55 "Yu Gothic","Meiryo","Segoe UI",sans-serif}
.fundamental-detail{scroll-margin-top:110px}
.fundamental-close{position:absolute;top:8px;right:8px;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:1px solid #cfd8e6;border-radius:999px;background:#fff;color:#344054;font-size:18px;font-weight:700;line-height:1;cursor:pointer;box-shadow:0 2px 8px rgba(16,24,40,.08)}
.fundamental-close:hover{background:#eef5ff;color:#1849a9}
.discord-message{display:grid;gap:8px;min-width:0;max-width:100%;color:#182230}
.discord-embed{min-width:0;max-width:100%;border-left:4px solid #5865f2;border-radius:6px;background:#f8f9ff;padding:10px;text-align:left;font-size:14px;font-weight:400;line-height:1.55}
.discord-embed.impact-positive{border-left-color:#2E7D32;background:#edf7ee}
.discord-embed.impact-watch{border-left-color:#F9A825;background:#fff8e6}
.discord-embed.impact-negative{border-left-color:#C62828;background:#fff1f0}
.discord-embed h4{margin:0 0 8px;font-size:13px}
.discord-embed dl{display:grid;gap:8px;margin:0;min-width:0}
.discord-embed dt{margin-bottom:2px;color:#344054;font-weight:700}
.discord-embed dd{margin:0;min-width:0;color:#182230;font-weight:400;overflow-wrap:anywhere;word-break:break-word;white-space:normal}
.discord-embed a{color:#1849a9;text-decoration:underline;overflow-wrap:anywhere;word-break:break-word}
.discord-meta{margin:8px 0 0;color:#667085;font-size:11px;font-weight:400}
dialog.fundamental-detail{position:fixed;inset:0;box-sizing:border-box;width:min(760px,calc(100vw - 32px));max-width:none;max-height:min(84vh,calc(100dvh - 32px));margin:auto;padding:14px 48px 14px 14px;overflow:auto;border:1px solid var(--line);border-radius:10px;box-shadow:0 22px 56px rgba(16,24,40,.32);transform:none}
dialog.fundamental-detail::backdrop{background:rgba(12,18,28,.62);backdrop-filter:blur(2px)}
:root[data-theme="dark"] .fundamental-detail{background:var(--panel-solid);color:var(--ink)}
:root[data-theme="dark"] .discord-message,:root[data-theme="dark"] .discord-embed dt,:root[data-theme="dark"] .discord-embed dd{color:var(--ink)}
:root[data-theme="dark"] .discord-embed{background:#18263a;border-left-color:#7f8cff}
:root[data-theme="dark"] .discord-embed.impact-positive{background:#102a22;border-left-color:#63d49b}
:root[data-theme="dark"] .discord-embed.impact-watch{background:#332710;border-left-color:#f4c15d}
:root[data-theme="dark"] .discord-embed.impact-negative{background:#351b20;border-left-color:#ff8a7c}
:root[data-theme="dark"] .discord-embed a{color:#9cc7ff}
:root[data-theme="dark"] .discord-meta{color:var(--muted)}
.cloud-research-page{font-variant-numeric:tabular-nums;padding-bottom:20px}
.cloud-research-page h1{font-size:24px;letter-spacing:-.5px;margin:0}
.research-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:8px 0 18px}.research-heading>span{color:var(--muted);font-size:12px}
.research-conditions{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;color:var(--muted);font-size:13px}.research-conditions>span{padding:7px 11px;border:1px solid var(--line);border-radius:8px;background:var(--panel-solid)}
.research-notice{padding:12px 16px;margin:0 0 20px;border-left:3px solid var(--warn);background:color-mix(in srgb,var(--warn) 7%,var(--panel-solid));font-size:13px;line-height:1.8;border-radius:0 8px 8px 0}
.research-card{background:var(--panel-solid);box-shadow:0 4px 18px color-mix(in srgb,var(--blue) 5%,transparent);padding:24px}.research-card h2{font-size:17px;font-weight:650;margin:0 0 24px}
.research-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:32px}.research-strategy+.research-strategy{border-left:1px solid var(--line);padding-left:32px}.research-strategy h3{font-size:17px;font-weight:650;margin:0;display:flex;align-items:center;gap:9px}
.research-swatch{display:inline-block;width:12px;height:12px;border-radius:3px;background:var(--blue);flex:none}.research-swatch.stacked{background:var(--violet)}
.research-profit{margin:22px 0;display:grid;gap:4px}.research-profit>span{font-size:12px;color:var(--muted)}.research-profit strong{font-size:clamp(25px,3.2vw,38px);line-height:1.2;letter-spacing:-1px;font-weight:650}.research-profit .positive{color:var(--good)}.research-profit .negative{color:#cc4357}:root[data-theme="dark"] .research-profit .negative{color:#ff98a7}
.research-stat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 16px;margin:0}.research-stat-grid dt{font-size:12px;color:var(--muted)}.research-stat-grid dd{font-size:21px;font-weight:600;margin:4px 0 0}
.research-footnote{font-size:12px;color:var(--muted);line-height:1.8;margin:18px 0 0}.research-legend{display:flex;justify-content:center;gap:22px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-bottom:12px}.research-legend>span{display:flex;align-items:center;gap:7px}
.research-chart{width:100%;height:auto;display:block;overflow:visible}.research-line{fill:none;stroke:var(--series);stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.research-bar,.research-point{fill:var(--series);outline-offset:4px}.research-point{stroke:var(--panel-solid);stroke-width:1.5}.research-zero{stroke:var(--muted);stroke-width:1;opacity:.65}.research-chart .axis-label{font-size:12px}
.research-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin-bottom:22px}.research-grid>.panel{margin-bottom:0;min-width:0}.research-grid .research-chart{min-height:210px}
.research-normalization{display:grid;gap:20px}.research-normalization>div{display:flex;justify-content:space-between;gap:18px;border-bottom:1px solid var(--line);padding-bottom:14px;font-size:13px}.research-normalization strong{white-space:nowrap;font-weight:650}
.research-table table{min-width:560px;font-size:13px}.research-table th,.research-table td{padding:13px 14px}.research-table tbody th{font-weight:500;text-align:left}.research-table tbody td{text-align:right}.research-table caption{text-align:left;color:var(--muted);font-size:12px;padding:10px}.research-table tbody tr:last-child>*{border-bottom:0}
.research-data{margin-top:18px}.research-data>summary{cursor:pointer;padding:12px 0;min-height:44px;color:var(--muted);font-size:12px;font-weight:600}.research-data[open]>summary{margin-bottom:10px}.research-empty{display:grid;place-items:center;min-height:160px;color:var(--muted);font-size:13px}
body[data-page="analytics"]{background:var(--bg)}body[data-page="analytics"] main{max-width:1280px;padding-top:22px}body[data-page="analytics"] .cloud-settings h2{font-size:16px;margin-bottom:12px}body[data-page="analytics"] .cloud-settings{padding:18px 22px;box-shadow:0 4px 18px color-mix(in srgb,var(--blue) 5%,transparent)}body[data-page="analytics"] .cloud-settings select{font-size:13px}body[data-page="analytics"] .cloud-settings p{font-size:12px;margin:8px 0}body[data-page="analytics"] .cloud-provenance{padding:0;border:0;background:transparent;box-shadow:none;backdrop-filter:none}body[data-page="analytics"] .cloud-provenance h2{font-size:13px;margin-bottom:8px}body[data-page="analytics"] .cloud-provenance p{font-size:12px;line-height:1.7;margin:6px 0}
@media(max-width:800px){.research-grid{grid-template-columns:1fr}.research-grid .research-chart{min-height:0}}
@media(max-width:650px){.research-pair{grid-template-columns:1fr;gap:24px}.research-strategy+.research-strategy{border-left:0;border-top:1px solid var(--line);padding-left:0;padding-top:24px}.research-profit strong{font-size:32px}.research-heading{display:block}.research-heading>span{display:block;margin-top:6px}.research-conditions{gap:6px;font-size:11px}.research-conditions>span{padding:6px 8px}.research-card{padding:18px}.research-chart{min-height:180px}.research-normalization>div{gap:12px}.research-table table{min-width:520px}.research-notice{font-size:12px}.research-card h2{margin-bottom:18px}body[data-page="analytics"] .cloud-settings{padding:16px}.research-chart-line .axis-label{font-size:25px}.research-chart-bar .axis-label{font-size:18px}}
"""


def _nav(current: str) -> str:
    links = [
        f'<a class="nav-link {"active" if current == "home" else ""}" '
        'href="./weak_early_beta_latest.html">ダッシュボード</a>',
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
    result = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(document_title)}</title><script src="./weak-early-beta-theme-init.js?v=20261004-v06-01"></script><style>{REPORT_CSS}</style>
<script src="./weak-early-beta-scenarios.js?v=20261004-v06-01" defer></script><script src="./weak-early-beta-interactions.js?v=20261004-v06-01" defer></script><script src="./weak-early-beta-push.js?v=20261004-v07" defer></script></head>
<body data-page="{html.escape(current)}"><header class="topbar"><nav class="nav"><a class="brand" href="./weak_early_beta_latest.html" aria-label="天底極致 Cloud トップへ"><img class="brand-logo brand-logo-light" src="report-assets/cloud-logo-light.png?v=transparent-1" alt="天底極致 -Cloud-"><img class="brand-logo brand-logo-dark" src="report-assets/cloud-logo-dark.png?v=20260923-1" alt="天底極致 -Cloud-"></a><div class="nav-links" aria-label="ページ移動">{_nav(current)}</div><button class="theme-toggle" id="theme-toggle" type="button" data-theme-toggle aria-pressed="false" aria-label="ダークモードに切り替える"><span class="theme-toggle-track" aria-hidden="true"><span class="theme-toggle-knob"></span></span><span class="theme-toggle-label">ダーク</span></button></nav></header>
<main>{body}</main>{_site_footer()}</body></html>'''
    # Cloudflare's per-asset limit must be checked before overwriting the
    # corresponding existing report. A failed generation must not be deployed.
    # Hidden theme images and below-fold footer icons should not compete with
    # the selected view's data on a constrained connection.
    result = re.sub(r'<img(?![^>]*\bloading=)', '<img loading="lazy"', result)
    old_navigation = f'<div class="nav-links" aria-label="ページ移動">{_nav(current)}</div>'
    menu_links = _nav(current).replace('class="nav-link active"', 'class="nav-link active" aria-current="page"')
    navigation_items = re.findall(r'<a\b.*?</a>', menu_links)
    primary_links, secondary_links = ''.join(navigation_items[:2]), ''.join(navigation_items[2:])
    new_navigation = (f'<div class="cloud-main-nav" aria-label="ページ移動"><span class="cloud-primary-nav">{primary_links}</span><span class="cloud-secondary-nav">{secondary_links}</span></div>'
        f'<div class="nav-tools"><button id="cloud-menu-toggle" class="nav-control {"active" if current not in ("home", "analytics") else ""}" type="button" aria-controls="cloud-navigation" aria-expanded="false" aria-label="その他のページを開く">その他 <span aria-hidden="true">⌄</span></button>'
        '<button id="cloud-settings-open" class="nav-control" type="button" aria-haspopup="dialog" aria-controls="cloud-settings-dialog" aria-label="表示・試算設定を開く"><span aria-hidden="true">⚙</span> 設定</button></div>'
        f'<div id="cloud-navigation" class="nav-links cloud-navigation" aria-label="その他のページ" hidden>{secondary_links}</div>')
    result = result.replace(old_navigation, new_navigation)
    result = re.sub(r'<button class="theme-toggle".*?</button>', '', result, flags=re.S)
    if len(result.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError(f"Cloud report {current} exceeds the 24 MiB asset budget; no oversized HTML was written")
    return result


def _equity_chart(
    frame: pd.DataFrame,
    title: str,
    chart_id: str,
    explanation: str = "",
    as_of: pd.Timestamp | None = None,
) -> str:
    frame = performance_eligible(frame)
    completed = frame[
        pd.to_numeric(frame["one_hundred_shares_pl_yen"], errors="coerce").notna()
        & pd.to_numeric(frame["gross_return"], errors="coerce").notna()
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
    annualized = capital_return / coverage_years(frame, observed_as_of)
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
    ledger = performance_eligible(ledger)
    returns = pd.to_numeric(ledger["gross_return"], errors="coerce").dropna()
    if returns.empty:
        return '<h2>利益構造</h2><p class="note">確定取引がありません。</p>'
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
        f'<div class="payoff-heading"><h2>利益構造</h2><span class="payoff-ratio">{ratio_label}</span></div>'
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
    eligible = performance_eligible(ledger)
    completed = eligible[pd.to_numeric(eligible["gross_return"], errors="coerce").notna()]
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
    if metrics.empty:
        return '<tr><td colspan="16">集計対象がありません</td></tr>'
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
    if metrics.empty:
        return '<tr><td colspan="14">集計対象がありません</td></tr>'
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
        '<div class="note"><strong>無料版で見られる情報</strong><p>検出から6営業日後の始値を確認できた銘柄を公開しています。グラフや成績も、公開済みの銘柄だけで計算しています。</p>'
        '<p>最新の検出銘柄は、有料会員向けに公開しています。</p><a href="/purchase">有料版について</a></div>'
        if mask_pending else ""
    )
    return (
        '<section class="panel" id="history"><h2>検出履歴</h2>'
        + access_notice
        + '<div class="history-details"><p class="history-heading">新しい順に表示します。検索はこの一覧だけを絞り込みます。株価の上限・確定日は「設定」で変更できます。</p>'
        '<div class="filters"><label class="filter-field"><span>銘柄</span><input id="symbol-filter" type="search" autocomplete="off" '
        'aria-label="証券コードまたは銘柄名で検索" placeholder="証券コード・銘柄名で検索"></label>'
        '<label class="filter-field"><span>開始日</span><input id="history-date-from" type="date" aria-label="検出日の開始日"></label>'
        '<label class="filter-field"><span>終了日</span><input id="history-date-to" type="date" aria-label="検出日の終了日"></label>'
        '<label class="filter-field"><span>並び順</span><select id="history-sort"><option value="newest">新しい順</option><option value="oldest">古い順</option><option value="symbol">証券コード順</option></select></label>'
        + mode_filter
        + '<button class="clear-search" id="clear-search" type="button">検索をクリア</button>'
        '<output class="result-count" id="search-result-count" aria-live="polite"></output></div>'
        '<noscript><p class="note">検索機能を使うにはJavaScriptを有効にしてください。</p></noscript>'
        '<div class="table-wrap history-table-wrap"><table id="detection-table"><thead><tr><th colspan="8"><div class="history-visible-grid"><div>検出日</div><div>銘柄</div><div>該当モード</div><div>保有状況</div><div>買付日・始値</div><div>5営業日後 終値</div><div>6営業日後 始値</div><div class="number">成績<small data-scenario-endpoint-label>6営業日後 始値</small></div></div></th></tr></thead>'
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


def _latest_signal_label(ledger: pd.DataFrame) -> str:
    dates = pd.to_datetime(ledger["signal_date"], errors="coerce").dropna()
    return f"{dates.max():%Y-%m-%d}" if not dates.empty else "—"


def _mode_pages_section(generated: pd.Timestamp, include_updated: bool = True) -> str:
    updated = (
        f'<p class="note">最終更新: {generated:%Y-%m-%d %H:%M:%S JST}</p>'
        if include_updated else ""
    )
    return (
        '<section class="panel" id="conditions"><h2>モード別ページ</h2>'
        f'<div class="condition-grid">{_condition_cards()}</div>{updated}</section>'
    )


def _render_dashboard_body(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
    mask_pending: bool = False,
) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    unique_ledger = combined_detections(ledger)
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">TEN-TEI-KYOKUCHI / CLOUD</span><h1>天底極致 -Cloud- ダッシュボード</h1><p class="lead">条件に該当した銘柄を新しい順に確認し、5つのモード別ページへ進めます。</p><p class="note">評価ルール: {html.escape(ENDPOINT_LABEL.replace("検出から", ""))}。詳しい見方と注意事項は「見方・使い方」をご覧ください。</p><p class="note">{html.escape(REFERENCE_POLICY_NOTE)}</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>モード別の記録件数</small><b>{len(ledger):,}件</b></div><div class="kpi"><small>重複を除いた検出件数</small><b>{len(unique_ledger):,}件</b></div><div class="kpi"><small>記録期間</small><b class="period-range">{_actual_period_html(ledger, generated)}</b></div><div class="kpi"><small>最終検出日</small><b>{_latest_signal_label(ledger)}</b></div></div></aside></section>
{_mode_pages_section(generated)}'''
    return body


def _research_number(value, suffix: str = "", *, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{decimals}f}{suffix}"


def _research_table(headers: list[str], rows: list[list[str]], *, caption: str = "") -> str:
    head = "".join(f"<th scope=\"col\">{html.escape(label)}</th>" for label in headers)
    body = "".join("<tr>" + "".join(f'<{"th scope=\"row\"" if index == 0 else "td"}>{cell}</{"th" if index == 0 else "td"}>' for index, cell in enumerate(row)) + "</tr>" for row in rows)
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">この条件で確定した取引はありません。</td></tr>'
    return f'<div class="table-wrap research-table"><table>{f"<caption>{html.escape(caption)}</caption>" if caption else ""}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _research_legend() -> str:
    return '<div class="research-legend"><span data-cloud-allocation="unique"><i class="research-swatch"></i>一律100株</span><span data-cloud-allocation="stacked"><i class="research-swatch stacked"></i>条件数×100株</span></div>'


def _research_data_table(headers: list[str], rows: list[list[str]]) -> str:
    return '<details class="research-data"><summary>集計データを見る</summary>' + _research_table(headers, rows) + '</details>'


def _research_plot(rows: list[dict], *, category: str, fields: tuple[str, ...], labels: tuple[str, ...], kind: str, unit: str, title: str) -> str:
    """Render aggregate-only SVG plus a keyboard-accessible data table."""
    if not rows:
        return '<p class="research-empty">この条件で確定した取引はありません。</p>'
    width, height, left, right, top, bottom = (1000 if kind == "line" else 580), 300, 80, 28, 24, 50
    vals = [float(row[field]) for row in rows for field in fields if row.get(field) is not None]
    low, high = min([0.0, *vals]), max([0.0, *vals])
    span = high - low or 1.0
    low, high = low - span * .07, high + span * .12
    plot_w, plot_h = width - left - right, height - top - bottom
    def y(value):
        return top + (high - float(value)) / (high - low) * plot_h
    def axis(value):
        return f"{value / 10000:,.1f}万" if unit == "円" and abs(value) >= 10000 else f"{value:,.0f}"
    parts = [f'<svg class="research-chart research-chart-{kind}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title>']
    for index in range(5):
        value = low + (high - low) * index / 4
        ypos = y(value)
        parts.append(f'<line class="grid-line" x1="{left}" y1="{ypos:.1f}" x2="{width-right}" y2="{ypos:.1f}"/><text class="axis-label" x="{left-12}" y="{ypos+4:.1f}" text-anchor="end">{axis(value)}</text>')
    parts.append(f'<line class="research-zero" x1="{left}" y1="{y(0):.1f}" x2="{width-right}" y2="{y(0):.1f}"/><text class="axis-label" x="{left-12}" y="13" text-anchor="end">{unit}</text>')
    if kind == "line":
        dates = [pd.Timestamp(row[category]) for row in rows]
        days = max(1, (dates[-1] - dates[0]).days)
        xs = [left + (date - dates[0]).days / days * plot_w for date in dates]
    else:
        xs = [left + (index + .5) / len(rows) * plot_w for index in range(len(rows))]
    for field_index, field in enumerate(fields):
        color = "var(--blue)" if field_index == 0 else "var(--violet)"
        allocation = f' data-cloud-allocation="{field}"' if field in {"unique", "stacked"} else ""
        parts.append(f'<g{allocation} style="--series:{color}">')
        if kind == "line":
            points = " ".join(f'{x:.1f},{y(row[field]):.1f}' for x, row in zip(xs, rows))
            parts.append(f'<polyline class="research-line" points="{points}"/>')
        for index, (xpos, row) in enumerate(zip(xs, rows)):
            value = row.get(field)
            if value is None:
                continue
            tooltip = html.escape(f'{row[category]} · {labels[field_index]}: {_research_number(value, unit, decimals=2 if unit == "%" else 0)}')
            if kind == "line":
                # Sparse focus targets keep long historical curves compact;
                # the complete aggregate series is available in the table.
                if index not in {0, len(rows)-1} and index % max(1, len(rows)//10):
                    continue
            else:
                bar_width = min(54, plot_w / len(rows) * .65 / len(fields))
                x = xpos + (field_index - len(fields)/2) * bar_width
                parts.append(f'<rect class="research-bar" x="{x:.1f}" y="{min(y(value), y(0)):.1f}" width="{bar_width-3:.1f}" height="{max(1,abs(y(value)-y(0))):.1f}" rx="3" tabindex="0"><title>{tooltip}</title></rect>')
        parts.append('</g>')
    label_indexes = sorted({0, len(rows)-1, *(round(index*(len(rows)-1)/4) for index in range(5))}) if kind == "line" else range(len(rows))
    for index in label_indexes:
        label = str(rows[index][category])
        if kind == "line":
            label = label[:7]
        parts.append(f'<text class="axis-label" x="{xs[index]:.1f}" y="{height-18}" text-anchor="middle">{html.escape(label)}</text>')
    parts.append('</svg>')
    data_rows = [[html.escape(str(row[category])), *[_research_number(row.get(field), unit, decimals=2 if unit == "%" else 0) for field in fields]] for row in rows]
    return ''.join(parts) + _research_data_table(["確定日" if kind == "line" else "検出年" if category == "year" else "条件数", *labels], data_rows)


def _render_analytics_body(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    data = build_analytics(ledger, as_of=generated.tz_localize(None))
    counts, strategies = data["counts"], data["strategies"]
    unique_ledger = combined_detections(ledger)
    cards = []
    for key, label, explanation in [("unique", "一律100株", UNIQUE_EXPLANATION), ("stacked", "条件数×100株", STACKED_EXPLANATION)]:
        values = strategies[key]
        stats = [("確定した検出", _research_number(values["resolved_signals"], "件")), ("100株単位の取引", _research_number(values["resolved_lots"], "口")), ("検出単位の勝率", _pct(values["signal_win_pct"])), ("数量で加重した勝率", _pct(values["lot_win_pct"])), ("検出単位の平均騰落率", _pct(values["signal_mean_pct"], True)), ("検出単位の中央値", _pct(values["signal_median_pct"], True))]
        cells = ''.join(f'<div><dt>{name}</dt><dd>{value}</dd></div>' for name, value in stats)
        tone = "positive" if values["cash_pl_yen"] >= 0 else "negative"
        cards.append(f'<article class="research-strategy"><h3><i class="research-swatch {key}"></i>{label}</h3><div class="research-profit"><span>累積確定損益</span><strong class="{tone}">{_yen(values["cash_pl_yen"])}</strong></div><dl class="research-stat-grid">{cells}</dl><p class="research-footnote">{html.escape(explanation)}</p></article>')
    risk_definitions = [
        ("最低初期資金（事後計算）", "minimum_initial_cash_yen", "円"),
        ("最大同時保有の取得額", "peak_open_principal_yen", "円"),
        ("確定損益の最大ドローダウン", "max_drawdown_yen", "円"),
        ("最も大きい1検出の損失", "worst_signal_cash_pl_yen", "円"),
        ("最も低い騰落率", "worst_return_pct", "%"),
        ("最大同時保有100株口数", "max_concurrent_lots", "口"),
        ("最大同時保有銘柄数", "max_concurrent_symbols", "銘柄"),
        ("利益上位3検出を除く損益", "profit_excluding_best3_signals_yen", "円"),
    ]
    risk_rows = [[label, *[_research_number(strategies[key][field], unit, decimals=2 if unit == "%" else 0) for key in ["unique", "stacked"]]] for label, field, unit in risk_definitions]
    normalization = data["normalization"]
    normal_rows = [("一律100株の損益", strategies["unique"]["cash_pl_yen"]), ("条件数×100株の損益", strategies["stacked"]["cash_pl_yen"]), ("総買付株数を一律100株に揃えた損益", normalization["shares_normalized_stacked_pl_yen"]), ("総買付金額を一律100株に揃えた損益", normalization["entry_cost_normalized_stacked_pl_yen"])]
    normal_html = ''.join(f'<div><span>{label}</span><strong>{_yen(value)}</strong></div>' for label, value in normal_rows)
    payoff_definitions = [("利益の合計", "gross_win_cash_pl_yen", "円"), ("損失の合計", "gross_loss_cash_pl_yen", "円"), ("勝ち検出の平均損益", "average_win_cash_pl_yen", "円"), ("負け検出の平均損益", "average_loss_cash_pl_yen", "円"), ("数量加重の平均騰落率", "lot_mean_pct", "%"), ("数量加重の中央値", "lot_median_pct", "%"), ("数量加重の勝率", "lot_win_pct", "%"), ("勝ち取引の平均騰落率", "lot_average_win_pct", "%"), ("負け取引の平均騰落率", "lot_average_loss_pct", "%"), ("未確定の検出数", "pending_signals", "件"), ("未確定の100株口数", "pending_lots", "口")]
    payoff_rows = [[label, *[_research_number(strategies[key][field], unit, decimals=2 if unit == "%" else 0) for key in ["unique", "stacked"]]] for label, field, unit in payoff_definitions]
    overlap_rows = [[f'{row["selector_count"]}条件', _research_number(row["resolved_signals"], "件"), _pct(row["mean_pct"], True), _pct(row["median_pct"], True), _pct(row["win_pct"]), _yen(row["cash_pl_100_yen"])] for row in data["overlap"]]
    coverage_rows = [[f'{row["year"]}年', _research_number(row["historical"], "件"), _research_number(row["forward"], "件"), _research_number(row["other"], "件")] for row in data["coverage"]["years"]]
    current_year_rows = [row for row in data["annual"] if row["year"] == generated.year]
    current_year_label = ""
    if current_year_rows:
        latest = pd.Timestamp(current_year_rows[-1]["latest_completed_signal_date"])
        current_year_label = f"{latest.year}年（{latest.month}月{latest.day}日検出分まで）。"
    monthly_metrics = monthly_metrics if monthly_metrics is not None else pd.DataFrame()
    table_head = f'<thead><tr><th>期間</th><th>確定取引数</th><th>未確定取引数</th><th>100株損益</th><th>{CAPITAL_HEADER}</th><th>資金増加率</th><th>単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th></tr></thead>'
    monthly_head = f'<thead><tr><th>月</th><th>確定取引数</th><th>未確定取引数</th><th>100株損益</th><th>{CAPITAL_HEADER}</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th></tr></thead>'
    detailed_tables = []
    for key, selector, label in [("unique", COMBINED_UNIQUE_ID, "銘柄均等（一律100株）"), ("stacked", COMBINED_STACKED_ID, "モード別積み上げ（条件数×100株）")]:
        monthly = monthly_metrics[monthly_metrics["selector_id"].eq(selector)] if not monthly_metrics.empty else monthly_metrics
        detailed_tables.append(f'<details class="research-data" data-cloud-allocation="{key}" id="{key}-performance"><summary>Cloud全体の成績 — {label}</summary><div class="table-wrap"><table data-paginated-table>{table_head}<tbody>{_combined_rows(metrics, selector)}</tbody></table></div>{_table_pagination()}<h3>月別の詳しい成績</h3><div class="table-wrap"><table data-paginated-table>{monthly_head}<tbody>{_monthly_rows(monthly, show_mode=False)}</tbody></table></div>{_table_pagination()}</details>')
    return f'''<div class="cloud-research-page">
<div class="research-heading"><h1>アナリティクス</h1><span>最終更新 {generated.strftime('%Y-%m-%d %H:%M')} JST</span></div>
<div class="research-conditions"><span>検出履歴</span><span>検出から1営業日後 始値で買付</span><span>手数料0・配当なし</span><span>記録期間 {_actual_period_label(ledger, generated)}</span><span>最終検出: {_latest_signal_label(ledger)}</span></div><!--cloud-provenance-->
<p class="research-notice">表示中 <strong>{counts['display_signals']:,}検出 / {counts['display_lots']:,}条件一致</strong>のうち、成績対象は{counts['eligible_signals']:,}検出。参考扱いの{counts['reference_excluded_signals']:,}検出（{counts['reference_excluded_lots']:,}条件一致）を成績から除外しています。対象内の損益確定 {counts['completed_signals']:,}件・未確定 {counts['pending_signals']:,}件。以下の比較・グラフ・資金計算は、結果が出た同じ取引です。</p>
<section class="panel research-card"><h2>株数方式の比較</h2><div class="research-pair">{''.join(cards)}</div><p class="research-footnote">検出は「同じ日・同じ銘柄」で1件。口数は買付時100株を1口とし、分割・併合後の売却株数ではありません。数量を増やしても、同じ検出の騰落率は変わりません。</p></section>
<section class="panel research-card" id="realized-profit"><h2>累積確定損益</h2>{_research_legend()}{_research_plot(data['cumulative'], category='date', fields=('unique','stacked'), labels=('一律100株','条件数×100株'), kind='line', unit='円', title='確定日ごとの累積確定損益')}<p class="research-footnote">0円から始め、選択した確定日の損益を加えています。未決済の含み損益を含む時価評価の曲線ではありません。</p></section>
<section class="panel research-card" id="capital-risk"><h2>必要資金・損失・集中度</h2>{_research_table(['指標','一律100株','条件数×100株'], risk_rows)}<p class="research-footnote">最低初期資金は、確定済みの注文を固定し、同日の買付を売却代金の受領より先に行う事後計算です。最大同時保有の取得額とは異なります。ドローダウンは確定損益だけから算出し、保有中の下落・保証金・税金・注文制約を含みません。欠損がある指標は空欄（—）です。</p></section>
<div class="research-grid"><section class="panel research-card" id="annual-pl"><h2>検出年別の損益</h2>{_research_legend()}{_research_plot(data['annual'], category='year', fields=('unique','stacked'), labels=('一律100株','条件数×100株'), kind='bar', unit='円', title='検出年別の確定損益')}<p class="research-footnote">{current_year_label}検出年で分類し、年をまたいだ決済も元の検出年へ含めます。選択した年の全期間集計です。</p></section><section class="panel research-card"><h2>株数増加だけの影響を確認</h2><div class="research-normalization">{normal_html}</div><p class="research-footnote">株数・買付金額の比率で損益を事後的に縮小した参考比較です。端株を含む仮想的な正規化で、同じ資金で実行できたポートフォリオや実際の約定を示しません。</p></section></div>
<div class="research-grid"><section class="panel research-card"><h2>検出条件の重なり</h2>{_research_plot(data['overlap'], category='selector_count', fields=('resolved_signals',), labels=('確定した検出',), kind='bar', unit='件', title='一致した条件数別の確定検出件数')}</section><section class="panel research-card"><h2>重なり別の平均騰落率</h2>{_research_plot(data['overlap'], category='selector_count', fields=('mean_pct',), labels=('平均騰落率',), kind='bar', unit='%', title='一致した条件数別の平均騰落率')}<p class="research-footnote">検出ごとの単純平均。条件数が多いほど将来成績が良いと保証するものではありません。</p></section></div>
<section class="panel research-card" id="payoff-structure"><h2>勝ち・負けと加重集計</h2>{_research_table(['指標','一律100株','条件数×100株'], payoff_rows)}<p class="research-footnote">勝ちは騰落率が0より大きい取引。0%は勝率の分母に含みます。数量加重の平均・中央値・勝率は100株口数で重みを付けます。</p><details class="research-data"><summary>勝ち負けの幅を比較（条件数×100株）</summary>{_payoff_structure(ledger)}</details></section>
<section class="panel research-card"><h2>条件の重なり別の内訳</h2>{_research_table(['一致条件数','確定した検出','平均騰落率','中央値','勝率','一律100株の損益'], overlap_rows)}</section>
<section class="panel research-card"><h2>検出履歴・取引の明細</h2><p>銘柄・検出日・条件で検索する一覧は、<a href="./weak_early_beta_latest.html#history">ダッシュボードの検出履歴</a>から確認できます。価格上限・確定日・検出年は共通の表示設定です。</p><p class="research-footnote">{html.escape(REFERENCE_POLICY_NOTE)}</p></section>
<p class="note">過去データによる試算を含みます。2026年の過去データも、結果が分かった期間の試算です。</p>
<section class="panel research-card" id="growth"><details class="research-data"><summary>必要資金を起点にしたトータルの資産推移</summary><p class="note">{html.escape(TOTAL_EQUITY_EXPLANATION)}</p><div class="chart-grid"><div data-cloud-allocation="unique">{_equity_chart(unique_ledger, '銘柄均等', 'unique', UNIQUE_EXPLANATION, generated.tz_localize(None))}</div><div data-cloud-allocation="stacked">{_equity_chart(ledger, 'モード別積み上げ', 'stacked', STACKED_EXPLANATION, generated.tz_localize(None))}</div></div></details>{''.join(detailed_tables)}</section>
{_mode_pages_section(generated)}</div>'''


def _render_mode_body(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    monthly_metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    selector_id: str,
    mask_pending: bool = False,
) -> str:
    info = selector_info(selector_id)
    lane = ledger[ledger["selector_id"].eq(selector_id)].copy()
    lane_monthly = monthly_metrics[monthly_metrics["selector_id"].eq(selector_id)] if not monthly_metrics.empty else monthly_metrics
    lane_metrics = metrics[metrics["selector_id"].eq(selector_id)] if not metrics.empty else metrics
    total_period = max(lane_metrics["period"].astype(str), key=len) if not lane_metrics.empty else "—"
    total = lane_metrics[lane_metrics["period"].eq(total_period)].iloc[0] if not lane_metrics.empty else None
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">CLOUD MODE</span><h1>{html.escape(info.display_name)}</h1><p class="lead">{html.escape(info.feature_summary)}</p><p>{html.escape(info.selection_summary)}</p><p class="note">評価ルール: {html.escape(ENDPOINT_LABEL.replace("検出から", ""))}。投資助言ではありません。</p><p class="note">{html.escape(REFERENCE_POLICY_NOTE)}</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>確定取引数</small><b>{int(total['n']) if total is not None else 0}件</b></div><div class="kpi"><small>平均騰落率</small><b>{_pct(total['mean_pct'], True) if total is not None else '—'}</b></div><div class="kpi"><small>勝率</small><b>{_pct(total['win_pct']) if total is not None else '—'}</b></div><div class="kpi"><small>100株損益</small><b>{_yen(total['cash_pl_100_yen']) if total is not None else '—'}</b></div></div></aside></section>
<section class="panel"><h2>{html.escape(info.display_name)} の資産推移</h2><p class="note">{html.escape(TOTAL_EQUITY_EXPLANATION)}</p>{_equity_chart(lane, info.display_name, selector_id.replace('_', '-'), as_of=generated.tz_localize(None))}</section>
<section class="panel" id="performance"><h2>全期間の成績</h2><div class="table-wrap"><table><thead><tr><th>期間</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th class="metric-focus">資金増加率</th><th class="metric-focus">単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th><th>最大上昇</th><th>最大下落</th></tr></thead><tbody>{_mode_overall_row(metrics, selector_id)}</tbody></table></div></section>
<section class="panel"><h2>年別の成績</h2><div class="table-wrap"><table data-paginated-table><thead><tr><th>年</th><th>確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th class="metric-focus">資金増加率</th><th class="metric-focus">単純年率</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th></tr></thead><tbody>{_mode_yearly_rows(metrics, selector_id)}</tbody></table></div>{_table_pagination()}<details class="monthly-details"><summary>月別の詳しい成績を見る</summary><div class="table-wrap"><table data-paginated-table><thead><tr><th>月</th><th>モード</th><th>確定取引数</th><th>未確定取引数</th><th class="metric-focus">100株損益</th><th class="metric-focus">{CAPITAL_HEADER}</th><th>平均</th><th>中央値</th><th>勝率</th><th>+10%</th><th>+20%</th><th>-10%</th><th>-20%</th></tr></thead><tbody>{_monthly_rows(lane_monthly)}</tbody></table></div>{_table_pagination()}</details></section>
{_mode_pages_section(generated)}'''
    return body


def _scope_definitions(source: pd.DataFrame) -> dict[str, dict]:
    """Derive signal years from the already audience-restricted source."""
    dates = pd.to_datetime(source.get("signal_date", pd.Series(dtype="object")), errors="coerce")
    years = sorted(int(year) for year in dates.dt.year.dropna().unique() if year != 2022)
    scopes = {"all": {"label": "記録期間すべて", "years": None}}
    scopes.update({str(year): {"label": f"{year}年", "years": [year]} for year in years})
    return scopes


def _settings_panel(scopes: dict[str, dict] | None = None) -> str:
    options = "".join(f'<option value="{html.escape(key)}">{html.escape(scope["label"])}</option>' for key, scope in (scopes or {"all": {"label": "記録期間すべて"}}).items())
    return '''<dialog id="cloud-settings-dialog" class="cloud-settings-dialog" aria-labelledby="cloud-settings-title"><section class="cloud-settings">
<div class="settings-heading"><h2 id="cloud-settings-title">表示・試算設定</h2><button id="cloud-settings-close" class="settings-close" type="button" aria-label="設定を閉じる"><svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6L18 18M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div>
<div class="settings-tabs" role="tablist" aria-label="設定の項目"><button id="settings-tab-trial" role="tab" aria-selected="true" aria-controls="settings-trial" type="button">試算方法</button><button id="settings-tab-notifications" role="tab" aria-selected="false" aria-controls="settings-notifications" tabindex="-1" type="button">通知</button><button id="settings-tab-display" role="tab" aria-selected="false" aria-controls="settings-display" tabindex="-1" type="button">表示</button></div>
<div id="settings-trial" role="tabpanel" aria-labelledby="settings-tab-trial"><div class="filters">
<label class="filter-field"><span>検出年</span><select id="cloud-year-scope">''' + options + '''</select></label>
<label class="filter-field"><span>検出日 終値の上限</span><select id="cloud-price-preset"><option value="1000" selected>1,000円以下</option><option value="2000">2,000円以下</option><option value="3000">3,000円以下</option><option value="5000">5,000円以下</option><option value="unlimited">上限なし</option><option value="custom">自由入力</option></select></label>
<label class="filter-field" id="cloud-price-custom-field" hidden><span>任意の上限（円・小数2桁まで）</span><input id="cloud-price-custom" type="number" step="0.01" min="0.01" inputmode="decimal" value="1000"></label>
<label class="filter-field"><span>確定日</span><select id="cloud-exit-endpoint"><option value="d5_close">5営業日後 終値</option><option value="d6_open" selected>6営業日後 始値</option></select></label>
<label class="filter-field"><span>買付方法</span><select id="cloud-allocation"><option value="all">両方式を比較</option><option value="unique">各銘柄を同じ株数で買う</option><option value="stacked">一致した条件数に応じて株数を増やす</option></select></label>
<label class="filter-field"><span>基準となる株数</span><input id="cloud-base-shares" type="number" min="100" max="1000000" step="100" inputmode="numeric" value="100"></label>
<label class="filter-field"><span>売買コスト（片道 %）</span><input id="cloud-cost-percent" type="number" min="0" max="10" step="0.01" inputmode="decimal" value="0"></label></div>
<p class="note">初期表示は1,000円以下・確定日は6営業日後始値・両方式・基準となる株数100株・コスト0%。保存した設定がある場合は、そちらを使います。各銘柄を同じ株数で買う場合は基準となる株数、一致した条件数に応じて増やす場合は基準となる株数×条件数で試算します。株数を増やすと必要な資金も増えます。</p>
<p class="note">上限は検出済みの銘柄を絞る条件で、検出対象を広げません。コストは買付額・売却額の両方にかかります。配当・税金は含みません。</p>
<p class="note">確定日は試算で使う売却価格を確認する日です。5営業日後の終値と6営業日後の始値から選びます。予定日前は「確定日待ち」、予定日を過ぎても価格が分からない場合は「未取得」と表示します。</p></div>
<div id="settings-notifications" role="tabpanel" aria-labelledby="settings-tab-notifications" hidden><p id="cloud-notification-readiness" role="status">通知の利用状況を確認しています。</p><div id="cloud-notification-settings"></div></div>
<div id="settings-display" role="tabpanel" aria-labelledby="settings-tab-display" hidden><div class="filters">
<label class="filter-field"><span>テーマ</span><select id="cloud-theme"><option value="light">ライト</option><option value="dark" selected>ダーク</option><option value="system">端末に合わせる</option></select></label>
<label class="filter-field"><span>文字サイズ</span><select id="cloud-font-size"><option value="small">小さめ</option><option value="standard" selected>標準</option><option value="large">大きめ</option></select></label>
<label class="filter-field"><span>一覧件数</span><select id="cloud-page-size"><option value="20">20件</option><option value="50">50件</option><option value="100">100件</option></select></label></div><p class="note">表示設定はこの端末に保存します。未保存のテーマ・文字サイズは確認用に表示し、キャンセルで元に戻ります。</p></div>
<p id="cloud-settings-status" role="status" aria-live="polite">保存済みの設定を読み込んでいます。</p>
<div class="settings-actions"><button id="cloud-research-reset" class="settings-secondary" type="button">試算方法をリセット</button><button id="cloud-settings-cancel" class="settings-secondary" type="button">キャンセル</button><button id="cloud-settings-save" class="settings-primary" type="button">設定を保存</button></div></section></dialog><output id="cloud-settings-feedback" role="status" aria-live="polite"></output><output id="cloud-applied-summary" class="scenario-apply" aria-live="polite"></output>'''


def _provenance_notice(source: pd.DataFrame, selected: pd.DataFrame, exit_key: str, *, missing: int | None = None, compact: bool = False) -> str:
    return '<p class="note">過去データによる試算と、運用開始後の検出記録を含みます。過去の成績は将来の利益を保証しません。</p>'


def _json_records(frame: pd.DataFrame) -> list[dict]:
    # pandas handles NumPy scalars and non-finite summary values as JSON null.
    return json.loads(frame.to_json(orient="records", force_ascii=False, double_precision=15))


def _breakpoint_key(value: float) -> str:
    # Round-trip representation avoids collisions between nearby actual prices.
    # The explicit key array also handles Python/JavaScript exponent spelling.
    return repr(float(value)).removesuffix(".0")


class _SharedHtmlFragments:
    """Deduplicate only known presentation blocks, within one page payload.

    The dictionary never sees history rows, ledger JSON or fundamental content.
    No fragment refers to another fragment; expansion is exactly one pass.
    """

    token = re.compile(r"<!--cloud-shared:([a-z0-9_-]+)-->")

    def __init__(self, generated: pd.Timestamp):
        self.fragments: dict[str, str] = {}
        self._keys: dict[str, str] = {}
        self._mode_links = _mode_pages_section(generated)

    def _replace(self, content: str) -> str:
        if "<!--cloud-shared:" in content:
            raise ValueError("nested shared HTML fragment")
        key = self._keys.get(content)
        if key is None:
            key = f"s{len(self.fragments)}"
            self._keys[content] = key
            self.fragments[key] = content
        return f"<!--cloud-shared:{key}-->"

    def pack(self, body: str) -> str:
        if "<!--cloud-shared:" in body:
            raise ValueError("reserved shared HTML token in rendered content")
        body = body.replace(self._mode_links, self._replace(self._mode_links))
        # Outer blocks go first so their content can never become a nested token.
        patterns = [
            r'<section class="panel research-card"><h2>検出履歴・取引の明細</h2>.*?</section>',
            r'<div class="research-legend">.*?</div>',
            r'<thead>.*?</thead>',
            r'<p class="research-footnote">.*?</p>',
        ]
        for pattern in patterns:
            def replace(match):
                content = match.group(0)
                # The annual coverage note contains the selected source's
                # latest completed date, so keep it local to that variant.
                if "検出年で分類し" in content:
                    return content
                return self._replace(content)
            body = re.sub(pattern, replace, body, flags=re.DOTALL)
        return body

    def expand(self, body: str) -> str:
        def replace(match):
            key = match.group(1)
            if key not in self.fragments:
                raise ValueError("unknown shared HTML fragment")
            return self.fragments[key]
        return self.token.sub(replace, body)


def _aggregate_variant_payload(source: pd.DataFrame, generated: pd.Timestamp, current: str, *, _summary_cache: dict | None = None, bundle_assets: dict | None = None, bundle_context: dict | None = None) -> tuple[str, str]:
    as_of = generated.tz_localize(None)
    summary_cache = _summary_cache if _summary_cache is not None else {}
    shared_html = _SharedHtmlFragments(generated)
    prices = verified_signal_prices(source)
    scopes = _scope_definitions(source)
    signal_years = pd.to_datetime(source["signal_date"], errors="coerce").dt.year
    scoped_sources = {}
    for scope_key, scope in scopes.items():
        scope_mask = pd.Series(True, index=source.index) if scope["years"] is None else signal_years.isin(scope["years"])
        scoped_sources[scope_key] = source.loc[scope_mask]
        scope["priceBreakpoints"] = sorted(float(value) for value in prices.loc[scope_mask].dropna().unique())
        scope["priceBreakpointKeys"] = [_breakpoint_key(value) for value in scope["priceBreakpoints"]]
    breakpoints = scopes["all"]["priceBreakpoints"]
    variants: dict[str, dict] = {}
    default_breakpoints = [value for value in breakpoints if value <= DEFAULT_PRICE_CAP]
    default_key = _breakpoint_key(default_breakpoints[-1]) if default_breakpoints else "empty"
    default_html = ""
    bundle_variants: dict[str, dict] = {}
    chunk = 0

    def flush_bundle():
        nonlocal chunk
        if not bundle_variants:
            return
        context = bundle_context
        filename = f"weak_early_beta_data_{context['audience']}_{context['page']}_{context['snapshot']}_{chunk:04d}.json"
        bundle = {"version": 1, "encoding": "gzip-base64-json", **context, "chunk": chunk, "variants": dict(bundle_variants)}
        encoded = json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 160_000:
            raise ValueError("Cloud variant bundle exceeds 160 KB")
        bundle_assets[filename] = encoded
        for variant_key in bundle_variants:
            variants[variant_key] = {"bundle": f"./{filename}"}
        bundle_variants.clear()
        chunk += 1
    for exit_key in ENDPOINT_LABELS:
        # Verify receipts once per endpoint; each subsequent cap only selects
        # rows from this immutable, already verified presentation view.
        endpoint_view = select_report_view(source, None, exit_key)
        for scope_key, scope in scopes.items():
            scoped_source = scoped_sources[scope_key]
            scoped_view = endpoint_view.loc[scoped_source.index]
            scoped_prices = prices.loc[scoped_source.index]
            missing_prices = int(verified_signal_prices(combined_detections(scoped_source)).isna().sum())
            # Each scope gets only its own exact price breakpoints, avoiding the
            # global-price × year Cartesian product. Allocation is a series
            # display choice and introduces no additional variants.
            for key, cap in [("empty", DEFAULT_PRICE_CAP), ("all", None), *((_breakpoint_key(value), value) for value in scope["priceBreakpoints"])]:
                view = scoped_view.iloc[0:0].copy() if key == "empty" else scoped_view.copy() if cap is None else scoped_view.loc[scoped_prices.le(cap)].copy()
                selected_ids = COMBINED_SELECTOR_IDS if current == "analytics" else (current,) if current in SELECTOR_ORDER else None
                metrics, monthly = build_presentation_metrics(view, as_of=as_of, selector_ids=selected_ids, _summary_cache=summary_cache)
                if current == "analytics":
                    body = _render_analytics_body(view, metrics, generated, monthly_metrics=monthly)
                elif current == "home":
                    body = _render_dashboard_body(view, metrics, generated, monthly_metrics=monthly, mask_pending=False)
                else:
                    body = _render_mode_body(view, metrics, monthly, generated, current, mask_pending=False)
                body = body.replace(ENDPOINT_LABEL.replace("検出から", ""), f"1営業日後 始値 → {ENDPOINT_LABELS[exit_key]}（コスト0%）")
                body = body.replace("5営業日後の終値が確定した取引", f"{ENDPOINT_LABELS[exit_key]}の損益が確定した取引")
                notice = _provenance_notice(scoped_source, view, exit_key, missing=missing_prices, compact=current == "analytics")
                body = body.replace("<!--cloud-provenance-->", notice) if current == "analytics" else notice + body
                variant = {"html": shared_html.pack(body), "metrics": _json_records(metrics), "monthlyMetrics": _json_records(monthly)}
                packed = gzip.compress(json.dumps(variant, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"), compresslevel=9, mtime=0)
                variant_key = f"{exit_key}:{key}" if scope_key == "all" else f"{exit_key}:{scope_key}:{key}"
                packed_variant = {"gzip": base64.b64encode(packed).decode("ascii")}
                is_default = exit_key == "d5_close" and scope_key == "all" and key == default_key
                if bundle_assets is None or is_default:
                    variants[variant_key] = packed_variant
                else:
                    # Bound each fetch by both count and bytes. The initial
                    # view stays inline; other caps/years load only on demand.
                    if bundle_variants and (len(bundle_variants) >= 4 or sum(len(item["gzip"]) for item in bundle_variants.values()) + len(packed_variant["gzip"]) > 150_000):
                        flush_bundle()
                    bundle_variants[variant_key] = packed_variant
                if exit_key == "d5_close" and scope_key == "all" and key == default_key:
                    default_html = body
    flush_bundle() if bundle_assets is not None else None
    payload = {
        "version": 1,
        "encoding": "gzip-base64-json",
        "page": current,
        "default": {"exitKey": "d5_close", "priceCapYen": DEFAULT_PRICE_CAP, "yearScope": "all"},
        "scopes": scopes,
        "priceBreakpoints": breakpoints,
        "priceBreakpointKeys": [_breakpoint_key(value) for value in breakpoints],
        "sharedHtml": shared_html.fragments,
        "variants": variants,
    }
    if bundle_assets is not None:
        payload["bundleContext"] = bundle_context
    # Only aggregate render fragments and metric rows are serialized. No raw
    # ledger, identity, company, URL, entry-price path or fundamental snapshot.
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return default_html, serialized


def _variant_page(
    ledger: pd.DataFrame,
    generated_at: pd.Timestamp,
    current: str,
    *,
    mask_pending: bool = False,
    _variant_cache: dict | None = None,
) -> str:
    # Restrict the source before generating dates, counts, price breakpoints,
    # CSV aggregates, compressed variants, or the history table. Omitting only
    # symbols cannot protect identities inferable from a price/return path.
    source = annotate_entry_feasibility(released_history(ledger) if mask_pending else visible_history(ledger))
    if current in SELECTOR_ORDER:
        # A mode page selects its own detections, but proportional buying uses
        # the same full set of matched modes as the combined Cloud strategy.
        source["report_matched_selectors"] = source.groupby(["signal_date", "symbol"])["selector_id"].transform(lambda ids: " ".join(dict.fromkeys(ids.astype(str))))
        source = source[source["selector_id"].eq(current)].copy()
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    # write_report owns a local cache, and the full key also prevents accidental
    # reuse across audiences, source frames or generation dates by other callers.
    # Calculate from audience-visible, validated presentation economics only.
    # Never embed raw ledger/provenance or a grid of all setting combinations.
    selected = select_report_view(source, 1000, "d6_open")
    metrics, monthly = build_presentation_metrics(selected, as_of=generated.tz_localize(None))
    if current == "home":
        default_html = _render_dashboard_body(selected, metrics, generated, monthly)
    elif current == "analytics":
        default_html = _render_analytics_body(selected, metrics, generated, monthly)
    else:
        default_html = _render_mode_body(selected, metrics, monthly, generated, current)
    default_html = re.sub(r'<section class="panel" id="conditions">.*?</section>', '', default_html, flags=re.S)
    scopes = _scope_definitions(source)
    serialized = json.dumps({"version": 2, "page": current, "scopes": scopes,
        "variants": {}, "generated": generated.isoformat(),
        "modeNames": {key: selector_info(key).display_name for key in SELECTOR_ORDER}}, ensure_ascii=False).replace('<', '\u003c')
    if current == "analytics":
        # A minimal audience-checked calculator input, without a visible stock
        # list, links, analysis or raw ledger/provenance. Free rows are released
        # before this template is derived, just as on the history page.
        opening_rows = re.findall(r'<tr\b[^>]*data-date="[^>]*>', _detection_rows(source, mask_pending=mask_pending))
        history = '<template id="cloud-scenario-rows"><table><tbody>' + ''.join(tag + '<td></td></tr>' for tag in opening_rows) + '</tbody></table></template>'
    else:
        history = _history_section(source, include_mode_filter=current == "home", mask_pending=mask_pending)
    mode_context = ''
    if current in SELECTOR_ORDER:
        info = selector_info(current)
        mode_context = f'<div id="cloud-mode-context" hidden data-feature="{html.escape(info.feature_summary, quote=True)}" data-selection="{html.escape(info.selection_summary, quote=True)}"></div>'
    access_notice = ('<section class="panel"><h2>無料版で見られる情報</h2><p>検出から6営業日後の始値を確認できた銘柄を公開しています。グラフや成績も、公開済みの銘柄だけで計算しています。</p><p>最新の検出銘柄は、有料会員向けに公開しています。</p></section>' if mask_pending and current == 'analytics' else '')
    body = (f'<div id="cloud-analytics-content">{default_html}</div>' + access_notice
        + _settings_panel(scopes) + mode_context + history + _mode_pages_section(generated, include_updated=False)
        + f'<script id="cloud-analytics-data" type="application/json">{serialized}</script>')
    title = "ダッシュボード" if current == "home" else "アナリティクス" if current == "analytics" else selector_info(current).display_name
    return _page_shell(title, current, body)


def render_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
    mask_pending: bool = False,
    _variant_cache: dict | None = None,
) -> str:
    return _variant_page(ledger, generated_at, "home", mask_pending=mask_pending, _variant_cache=_variant_cache)


def render_analytics_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    monthly_metrics: pd.DataFrame | None = None,
    mask_pending: bool = False,
    _variant_cache: dict | None = None,
) -> str:
    return _variant_page(ledger, generated_at, "analytics", mask_pending=mask_pending, _variant_cache=_variant_cache)


def render_mode_report(
    ledger: pd.DataFrame,
    metrics: pd.DataFrame,
    monthly_metrics: pd.DataFrame,
    generated_at: pd.Timestamp,
    selector_id: str,
    mask_pending: bool = False,
    _variant_cache: dict | None = None,
) -> str:
    return _variant_page(ledger, generated_at, selector_id, mask_pending=mask_pending, _variant_cache=_variant_cache)


def render_guide(generated_at: pd.Timestamp, scopes: dict | None = None) -> str:
    generated = generated_at.tz_convert("Asia/Tokyo") if generated_at.tzinfo else generated_at.tz_localize("Asia/Tokyo")
    mode_routes = {selector_info(key).short_name: MODE_PAGE_NAMES[key] for key in SELECTOR_ORDER}
    mode_links = "、".join(f'<a href="./{html.escape(mode_routes[name])}">{name}</a>' for name in ("Shadow", "Dive", "Silence", "Fusion", "Balance"))
    body = f'''
<section class="hero"><div class="panel hero-main"><span class="eyebrow">GUIDE</span><h1>見方・使い方</h1>
<p class="lead">はじめての方でも、見つかった銘柄と過去の成績を順番に確認できるガイドです。</p></div>
<aside class="panel"><div class="kpis"><div class="kpi"><small>買付</small><b>検出の翌営業日 始値</b></div><div class="kpi"><small>確定日</small><b>5営業日後 終値 / 6営業日後 始値</b></div><div class="kpi"><small>基準となる株数</small><b>初期値100株</b></div><div class="kpi"><small>売買コスト</small><b>初期値0%</b></div></div></aside></section>
<section class="panel"><h2>無料版で見られる情報</h2><p>検出から6営業日後の始値を確認できた銘柄を公開しています。グラフや成績も、公開済みの銘柄だけで計算しています。</p><p>最新の検出銘柄は、有料会員向けに公開しています。</p></section>
<section class="panel"><h2>まず見る場所</h2><div class="guide-grid">
<article class="guide-card"><h3><a href="./weak_early_beta_latest.html">ダッシュボード</a></h3><p>最初に開くページです。条件に当てはまった銘柄を新しい順に確認し、銘柄名・証券コード・日付・モードで絞り込めます。</p></article>
<article class="guide-card"><h3><a href="./{ANALYTICS_PAGE_NAME}">アナリティクス</a></h3><p>Cloud全体の過去成績を見るページです。選択した株数とコストで試算した損益、勝率、平均騰落率、資産の動きを確認できます。</p></article>
<article class="guide-card"><h3>5つのモード</h3><p>モードは、銘柄を選ぶ「見方の違い」です。{mode_links}を押すと、それぞれの成績と検出銘柄を確認できます。</p></article>
</div></section>
<section class="panel"><h2>成績の読み方</h2><div class="guide-grid">
<article class="guide-card"><h3>株数とコスト</h3><p>株数は100株ずつ変更できます。コストは買付額と売却額の両方にかかり、損益とグラフに反映します。分割・併合による株数の変化も計算します。配当・税金は含みません。</p></article>
<article class="guide-card"><h3>5営業日後・6営業日後</h3><p>検出日を基準に、次の営業日を1日目と数えます。5日目の終値と6日目の始値は、別の日に確認します。予定日前は「確定日待ち」、価格を確認できない場合は「未取得」と表示します。</p></article>
<article class="guide-card"><h3>株価の上限</h3><p>検出日 終値が上限以下の検出銘柄を表示します。検出済みの銘柄を絞る設定なので、上限を引き上げても検出対象は広がりません。終値が未取得の記録は上限ありでは除外し、上限なしでは表示します。</p></article>
<article class="guide-card"><h3>過去の成績</h3><p>過去データによる試算は、実際の運用実績ではありません。2026年の過去データも、結果が分かった期間の試算です。運用開始後の検出記録とは区別しています。価格を取得できていない取引の損益は表示しません。</p></article>
<article class="guide-card"><h3>必要資金（目安）</h3><p>複数の銘柄を同時に持つ期間も考えたうえで、選択した株数とコストで取引するために最も多く必要だった資金の目安です。</p></article>
<article class="guide-card"><h3>資金増加率・単純年率</h3><p>必要資金に対して損益が何%だったかと、それを1年あたりに単純換算した参考値です。利益を再投資する複利計算ではありません。</p></article>
<article class="guide-card"><h3>勝率と騰落率</h3><p>勝率は、結果が出た取引のうち利益になった割合です。損益が0の取引も数えます。騰落率は、買付額に対する損益の割合です。選択したコストも含みます。</p></article>
<article class="guide-card"><h3>参考値・成績に含めません</h3><p>{html.escape(REFERENCE_POLICY_NOTE)} 履歴の騰落率と損益は仮定上の参考値として残します。</p></article>
</div></section>
<section class="panel"><h2>2つの買付方法</h2><div class="guide-grid"><article class="guide-card"><h3>各銘柄を同じ株数で買う</h3><p>同じ日・同じ銘柄を<span data-guide-base-shares>100</span>株で試算します。複数の条件に一致しても株数は増やしません。</p></article><article class="guide-card"><h3>一致した条件数に応じて株数を増やす</h3><p>基準となる株数が<span data-guide-base-shares>100</span>株なら、3条件に一致した銘柄は<span data-guide-stacked-shares>300</span>株で試算します。</p></article></div><p class="note">条件が複数一致しても、将来の値動きを保証しません。</p></section>
<section class="panel"><h2>設定と通知</h2><p>「設定」は全ページで共通です。「試算方法」「通知」「表示」の3タブで変更し、「設定を保存」で反映します。キャンセル・×・画面外のクリック・Escapeでは元に戻ります。</p><p>通知は現在利用できません。有料会員向けの機能で、初期値はOFFです。通知名は「確定日の朝8時（日本時間）」です。選んだ確定日の朝8時にお知らせします。その日の価格はまだ確定していません。通知本文は「今日は、設定した確定日です」です。</p></section>
<section class="panel"><h2>大切な注意事項</h2>
<p>本サイトは過去データとルールに基づく情報提供・検証を目的としたもので、特定銘柄の売買を勧める投資助言ではありません。将来の収益や価格上昇を保証するものでもありません。</p>
<p>実際の取引では、手数料、税金、スリッページ、流動性、値幅制限、寄付で約定できない可能性などにより結果が異なります。投資判断は、ご自身で最新の開示・株価・財務情報を確認したうえで行ってください。</p>
<p class="note">最終更新: {generated:%Y-%m-%d %H:%M:%S JST}</p></section>'''
    metadata = json.dumps({"version": 2, "page": "guide", "scopes": scopes or {"all": {"label": "記録期間すべて", "years": None}}, "variants": {}, "generated": generated.isoformat(), "modeNames": {}}, ensure_ascii=False).replace('<', '\u003c')
    guide_settings = _settings_panel(scopes).replace('<output id="cloud-applied-summary" class="scenario-apply" aria-live="polite"></output>', '')
    return _page_shell("見方・使い方", "guide", body + guide_settings + f'<script id="cloud-analytics-data" type="application/json">{metadata}</script>')


def write_report(
    ledger: pd.DataFrame,
    report_path: Path = DEFAULT_REPORT,
    metrics_path: Path = DEFAULT_METRICS,
    monthly_metrics_path: Path = DEFAULT_MONTHLY_METRICS,
    *,
    apply_reviewed_prices: bool = True,
) -> pd.DataFrame:
    variant_cache: dict = {"bundle-assets": {}}
    generated = pd.Timestamp.now(tz="Asia/Tokyo")
    # The hash-pinned private sidecar enriches only this presentation copy.
    # Raw ledger reads and frozen D5 economics remain unchanged.
    if apply_reviewed_prices:
        ledger, _overlay_audit = apply_reviewed_endpoint_overlay(ledger, load_reviewed_endpoint_overlay())
        ledger, _d5_overlay_audit = apply_reviewed_d5_overlay(ledger)
        from .forward_price_overlay import apply_reviewed_forward_close
        ledger = apply_reviewed_forward_close(ledger)
    ledger = annotate_entry_feasibility(ledger)
    default_view = select_report_view(ledger)
    metrics = build_metrics(default_view, as_of=generated.tz_localize(None))
    monthly_metrics = build_monthly_metrics(default_view, as_of=generated.tz_localize(None))
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
        render_report(ledger, metrics, generated, monthly_metrics=monthly_metrics, _variant_cache=variant_cache),
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
            _variant_cache=variant_cache,
        ),
        encoding="utf-8",
    )
    analytics_path = report_path.with_name(ANALYTICS_PAGE_NAME)
    analytics_html = render_analytics_report(
        ledger,
        metrics,
        generated,
        monthly_metrics=monthly_metrics,
        _variant_cache=variant_cache,
    )
    analytics_path.write_text(analytics_html, encoding="utf-8")
    analytics_path.with_name(analytics_path.stem + "_free.html").write_text(
        render_analytics_report(ledger, metrics, generated, monthly_metrics=monthly_metrics, mask_pending=True, _variant_cache=variant_cache),
        encoding="utf-8",
    )
    guide_path = report_path.with_name(GUIDE_PAGE_NAME)
    guide_html = render_guide(generated, _scope_definitions(visible_history(ledger)))
    guide_path.write_text(guide_html, encoding="utf-8")
    guide_path.with_name(guide_path.stem + "_free.html").write_text(
        render_guide(generated, _scope_definitions(released_history(ledger))),
        encoding="utf-8",
    )
    for selector_id, filename in MODE_PAGE_NAMES.items():
        mode_path = report_path.with_name(filename)
        mode_path.write_text(
            render_mode_report(ledger, metrics, monthly_metrics, generated, selector_id, _variant_cache=variant_cache),
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
                _variant_cache=variant_cache,
            ),
            encoding="utf-8",
        )
    for filename, encoded in variant_cache["bundle-assets"].items():
        report_path.with_name(filename).write_bytes(encoded)
    # Remove only older generated Cloud bundles, after every page and current
    # bundle succeeded. A failed generation preserves its previous snapshot.
    output_directory = report_path.parent.resolve()
    for candidate in report_path.parent.glob("weak_early_beta_data_*.json"):
        if re.fullmatch(r"weak_early_beta_data_(full|free)_(latest|analytics|silence|dive|shadow|fusion|balance|guide)_[a-f0-9]{16}_\d{4}\.json", candidate.name) and candidate.name not in variant_cache["bundle-assets"]:
            if candidate.resolve().parent != output_directory or candidate.is_symlink():
                raise ValueError("unsafe stale Cloud bundle path")
            candidate.unlink()
    return metrics


# Last rules deliberately override the legacy wide-table/mobile cell layout.
REPORT_CSS += """
main{min-width:0}.history-table-wrap{overflow:visible}#detection-table{min-width:0;table-layout:fixed;width:100%}.history-main{display:grid;grid-template-columns:minmax(0,2.05fr) repeat(4,minmax(0,1fr));gap:12px;align-items:center}.history-main>div{min-width:0;white-space:normal;overflow-wrap:anywhere}.history-main small{display:block}.history-company strong{font-size:15px}.history-record{white-space:normal!important;padding:14px!important}.history-expand summary{cursor:pointer;min-height:44px;padding:10px 0;color:var(--blue);font-weight:700}.history-detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;padding:14px;border:1px solid var(--line);border-radius:12px}.history-detail-grid>div{min-width:0;overflow-wrap:anywhere}.history-detail-grid b,.history-detail-grid small{display:block}.history-detail-grid b{font-size:12px;color:var(--muted);margin-bottom:8px}.history-expand .reference-note{max-width:none;width:100%;padding:14px;font-size:13px;background:color-mix(in srgb,var(--warn) 12%,var(--panel-solid));border-radius:8px}.history-main .status{white-space:normal}.history-expand .actions{margin-top:14px}.scenario-details{margin-top:20px}.scenario-details summary{min-height:44px;cursor:pointer;font-weight:700}.scenario-table{width:100%;min-width:0;table-layout:fixed}.scenario-table td,.scenario-table th{white-space:normal;overflow-wrap:anywhere}.scenario-table td.number{text-align:right}.scenario-empty{padding:20px}.scenario-chart{width:100%;height:auto;display:block}.scenario-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.scenario-stats{display:grid;grid-template-columns:1fr 1fr;gap:12px}.scenario-stats dt{font-size:12px;color:var(--muted)}.scenario-stats dd{margin:0;font-size:18px;font-weight:700}.scenario-profit{font-size:34px;font-weight:800}.scenario-apply{display:block;margin-top:12px;font-weight:700;color:var(--ink)}
@media(max-width:760px){#detection-table thead{display:none}#detection-table tbody{display:grid;gap:12px}#detection-table tbody tr{display:block!important;padding:0!important}#detection-table tbody tr>.history-record{display:block!important}#detection-table tbody tr>.history-record:before{display:none}.history-main{grid-template-columns:1fr 1fr;gap:12px}.history-company{grid-column:1/-1}.history-main>div[data-label]::before{content:attr(data-label);display:block;font-size:11px;color:var(--muted)}.history-detail-grid{grid-template-columns:1fr 1fr}.history-record .number{text-align:left}.scenario-pair{grid-template-columns:1fr}.scenario-table{font-size:12px}.scenario-table td,.scenario-table th{padding:8px 5px}}
@media(min-width:761px){#detection-table tbody tr>.history-record{display:table-cell!important}.history-table-wrap #detection-table thead{display:table-header-group}}
#detection-table tbody tr[hidden]{display:none!important}
#cloud-history-export-csv{min-height:44px;padding:9px 14px;border:1px solid var(--line);border-radius:10px;background:var(--panel-solid);color:var(--ink);font:inherit;cursor:pointer;margin:10px 0}
@media(max-width:760px){.scenario-chart text{font-size:36px}.scenario-chart{min-height:130px}}
"""

REPORT_CSS += """
:root{--text-scale:1}:root[data-font-size="small"]{--text-scale:.9333}:root[data-font-size="large"]{--text-scale:1.1333}
body{font-size:calc(15px * var(--text-scale))}body[data-page="analytics"]{background:radial-gradient(circle at 12% -8%,color-mix(in srgb,var(--cyan) 18%,transparent),transparent 34%),radial-gradient(circle at 94% 5%,color-mix(in srgb,var(--violet) 16%,transparent),transparent 30%),var(--bg)}body[data-page="analytics"] main{max-width:1440px;padding-top:30px}
.nav{grid-template-columns:minmax(0,1fr) auto;position:relative}.nav-tools{display:flex;gap:8px;align-items:center}.nav-control{display:inline-flex;align-items:center;gap:6px;min-height:44px;border:1px solid var(--line);border-radius:12px;background:var(--panel-solid);color:var(--ink);padding:8px 14px;font-weight:700;cursor:pointer}.nav-control span{font-size:22px;line-height:1}.cloud-navigation{position:absolute;right:20px;top:calc(100% + 8px);width:min(280px,calc(100vw - 24px));display:grid;gap:2px;padding:8px;border:1px solid var(--line);border-radius:12px;background:var(--panel-solid);box-shadow:var(--shadow);z-index:30}.cloud-navigation[hidden]{display:none!important}.cloud-navigation .nav-link{display:block;border-radius:8px;padding:10px 12px;min-height:44px;line-height:24px}.cloud-navigation .nav-link[aria-current="page"]{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid));color:var(--blue)}
.cloud-settings-dialog{width:min(760px,calc(100vw - 24px));max-height:calc(100dvh - 24px);border:1px solid var(--line);border-radius:20px;padding:0;color:var(--ink);background:var(--panel-solid);box-shadow:0 24px 70px rgba(0,0,0,.32);overflow:auto}.cloud-settings-dialog::backdrop{background:rgba(12,18,28,.58);backdrop-filter:blur(4px)}.cloud-settings-dialog .cloud-settings{padding:24px}.settings-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.settings-heading h2{font-size:22px;margin:0}.settings-close{width:40px;min-height:40px;font-size:24px!important;cursor:pointer}.settings-tabs{display:flex;gap:8px;border-bottom:1px solid var(--line);margin-bottom:20px;padding-bottom:12px}.settings-tabs button{flex:1;font-weight:700;cursor:pointer}.settings-tabs [aria-selected="true"]{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid));border-color:var(--blue);color:var(--blue)}.cloud-settings .filters{display:grid;grid-template-columns:1fr 1fr;gap:16px}.cloud-settings .filters .filter-field{min-width:0}.cloud-settings select,.cloud-settings input{width:100%;min-width:0;font-size:calc(15px * var(--text-scale));min-height:44px}.settings-actions{display:flex;justify-content:flex-end;gap:10px;position:sticky;bottom:0;background:var(--panel-solid);padding-top:18px;border-top:1px solid var(--line);margin-top:20px}.cloud-settings button.settings-primary{background:#4169e1;color:#fff;border-color:#4169e1;font-weight:800}.cloud-settings button.settings-secondary{background:color-mix(in srgb,var(--muted) 6%,var(--panel-solid));color:var(--muted);border-color:var(--line)}.cloud-settings button:focus-visible,.nav-control:focus-visible,[role="tab"]:focus-visible{outline:3px solid var(--cyan);outline-offset:3px}.cloud-settings button:disabled{opacity:.55;cursor:wait}.cloud-settings .note{font-size:max(12px,calc(13px * var(--text-scale)))}.cloud-settings #cloud-settings-status[data-state="error"]{color:var(--warn)}#cloud-settings-feedback:empty{display:none}#cloud-settings-feedback{display:block;color:var(--muted);font-size:13px;padding:8px 0}#cloud-applied-summary{font-size:12px;color:var(--muted);font-weight:400;margin:0 0 14px}
.history-visible-grid{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.7fr) minmax(0,1.25fr) minmax(0,.85fr) repeat(3,minmax(0,1fr)) minmax(0,1.25fr);align-items:start;gap:14px;font-size:max(12px,calc(13px * var(--text-scale)))}.history-visible-grid>div{min-width:0;white-space:normal;overflow-wrap:anywhere}.history-visible-grid small{display:block;font-size:max(11px,calc(11px * var(--text-scale)));color:var(--muted)}.history-visible-grid .actions{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.history-visible-grid .actions button,.history-visible-grid .actions a{font-size:12px;padding:4px 7px;min-height:32px}.history-visible-grid .badge{font-size:11px;margin:2px 1px;padding:3px 7px}.history-visible-grid .history-company strong{font-size:calc(14px * var(--text-scale))}.history-method{display:block;margin-bottom:6px;font-size:calc(14px * var(--text-scale))}.history-record .reference-note{max-width:none;width:100%;padding:10px 12px;margin-top:10px;border-radius:10px;background:color-mix(in srgb,var(--warn) 9%,var(--panel-solid));font-size:12px}.endpoint-status{color:var(--muted)}#detection-table thead th{width:auto!important}.history-record{padding:14px 12px!important}#detection-table tbody tr[hidden]{display:none!important}
.chart-card.research-strategy+.research-strategy{padding:18px;border-left:1px solid var(--line)}.chart-card.research-strategy h3{font-size:18px}.chart-card .scenario-stats{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}.chart-card .chart-stats small{font-size:12px}.chart-card .chart-stats b{font-size:calc(19px * var(--text-scale))}.positive{color:var(--good)}.negative{color:#bc4253}:root[data-theme="dark"] .negative{color:#ff98a7}.cloud-equity-chart{overflow:visible}.cloud-equity-chart .axis-label{fill:var(--muted)}.payoff-comparison{display:grid;gap:28px}.payoff-comparison article+article{padding-top:20px;border-top:1px solid var(--line)}.payoff-kpis{margin-left:0;padding:0}.payoff-kpi strong{font-size:calc(27px * var(--text-scale))}.payoff-kpi small{font-size:12px}.payoff-ratio{font-size:12px}.payoff-heading h3{font-size:16px;margin:0}.research-swatch.negative{background:#df6670}.cloud-horizontal-bars{display:grid;gap:18px}.cloud-bar-row>strong{font-size:15px}.cloud-bar-item{display:grid;grid-template-columns:minmax(0,1fr) minmax(110px,auto);gap:4px 12px;margin:8px 0}.cloud-bar-track{display:block;height:17px;overflow:hidden;border-radius:999px;background:color-mix(in srgb,var(--blue) 8%,var(--bg))}.cloud-bar-track i{display:block;height:100%;min-width:0;border-radius:999px}.cloud-bar-item b{text-align:right;font-size:13px}.cloud-bar-item small{font-size:11px;color:var(--muted)}.annual-chart-details summary,.scenario-details summary{cursor:pointer;min-height:44px;padding:10px 0;font-weight:700}.scenario-table{font-size:max(12px,calc(14px * var(--text-scale)))}.scenario-table td:first-child{font-weight:600}.scenario-table td{font-variant-numeric:tabular-nums}.cloud-period-note{margin-bottom:22px}.kpi b{overflow-wrap:anywhere}.hero h1{font-size:clamp(27px,3vw,42px)}
@media(max-width:760px){.nav{grid-template-columns:minmax(0,1fr) auto;padding:8px 12px}.brand{grid-column:1;grid-row:1}.brand-logo{width:min(230px,100%);height:44px}.nav-tools{grid-column:2;grid-row:1;gap:5px}.nav-control{font-size:12px;padding:8px;gap:4px}.nav-control span{font-size:19px}.cloud-navigation{right:12px;top:calc(100% + 6px);grid-column:auto;grid-row:auto;overflow:auto;max-height:calc(100dvh - 85px)}.history-visible-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;font-size:max(13px,calc(14px * var(--text-scale)))}.history-visible-grid>div:before{content:attr(data-label);display:block;color:var(--muted);font-size:11px}.history-visible-grid .history-company{grid-column:1/-1;order:-1}.history-visible-grid .history-company strong{font-size:calc(16px * var(--text-scale))}.history-record .number{text-align:left}.history-visible-grid .actions button,.history-visible-grid .actions a{min-height:40px;padding:6px 10px;font-size:13px}.history-method{font-size:calc(16px * var(--text-scale))}.cloud-settings-dialog .cloud-settings{padding:16px}.settings-heading h2{font-size:20px}.cloud-settings .filters{grid-template-columns:1fr}.settings-actions{gap:7px}.settings-actions button{padding:9px 11px}.scenario-table thead{display:none}.scenario-table tbody{display:grid;gap:12px}.scenario-table tbody tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border:1px solid var(--line);border-radius:12px;padding:8px;background:var(--panel-solid)}.scenario-table tbody td{display:block;padding:7px;border:0}.scenario-table tbody td:first-child{grid-column:1/-1}.scenario-table tbody td:before{content:attr(data-label);display:block;font-size:11px;color:var(--muted);font-weight:400;margin-bottom:3px}.scenario-table tr[hidden]{display:none!important}.scenario-stats dd{font-size:calc(18px * var(--text-scale))}.cloud-equity-chart text{font-size:27px}.cloud-equity-chart{min-height:150px}.payoff-kpi strong{font-size:calc(23px * var(--text-scale))}.hero h1{font-size:calc(27px * var(--text-scale))}.lead{font-size:calc(15px * var(--text-scale))}.cloud-bar-item{grid-template-columns:minmax(0,1fr) auto}}
"""

REPORT_CSS += """
.note,.history-heading,#cloud-applied-summary{font-size:max(12px,calc(13px * var(--text-scale)))}.lead{font-size:calc(16px * var(--text-scale))}.settings-tabs button,.settings-actions button,.nav-control{font-size:calc(14px * var(--text-scale))}.cloud-navigation .nav-link{font-size:calc(14px * var(--text-scale))}.cloud-bar-item b,.payoff-ratio,.research-legend,.payoff-kpi small,.chart-stats small{font-size:max(12px,calc(13px * var(--text-scale)))}.cloud-bar-item small{font-size:max(11px,calc(12px * var(--text-scale)))}.history-visible-grid small,.history-visible-grid .badge{font-size:max(11px,calc(12px * var(--text-scale)))}
@media(max-width:760px){.nav-control{font-size:12px}.cloud-equity-chart text{font-size:32px}.settings-heading h2{font-size:calc(20px * var(--text-scale))}.settings-actions button{font-size:calc(13px * var(--text-scale))}}
"""

REPORT_CSS += """
.insight-grid{align-items:start}#annual-pl{box-sizing:border-box}#annual-older-toggle{min-height:44px;margin-top:16px;padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--panel-solid);color:var(--ink);font:inherit;cursor:pointer}.cloud-bar-row[hidden],#annual-older-toggle[hidden]{display:none!important}
"""

REPORT_CSS += ".kpi b.period-range{font-size:calc(16px * var(--text-scale));white-space:normal;line-height:1.5}"

REPORT_CSS += ".settings-actions{flex-wrap:wrap}#cloud-research-reset{margin-right:auto}"

REPORT_CSS += """
.nav{grid-template-columns:minmax(180px,.85fr) minmax(0,2fr) auto}.brand-logo{width:min(340px,100%)}.cloud-main-nav{display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:2px;min-width:0}.cloud-primary-nav,.cloud-secondary-nav{display:contents}.cloud-main-nav .nav-link{font-size:calc(14px * var(--text-scale));padding:8px 10px;min-height:44px;display:inline-flex;align-items:center}.cloud-main-nav .nav-link[aria-current="page"],.nav-control.active{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid));color:var(--blue)}#cloud-menu-toggle{display:none}
@media(max-width:760px){.nav{grid-template-columns:minmax(0,1fr) auto;gap:4px 8px}.brand-logo{width:min(230px,100%)}.cloud-main-nav{grid-column:1/-1;grid-row:2;justify-content:flex-start}.cloud-secondary-nav{display:none}.cloud-main-nav .nav-link{flex:1;justify-content:center;font-size:calc(14px * var(--text-scale));border-radius:10px}#cloud-menu-toggle{display:inline-flex}.cloud-navigation{top:calc(100% + 4px)}}
"""

REPORT_CSS += "[data-scenario-cost]>span{display:block;margin:3px 0;white-space:normal;overflow-wrap:anywhere}[data-scenario-shares]>span{display:inline;white-space:normal;overflow-wrap:anywhere}"
REPORT_CSS += ".history-record .history-endpoint-label{display:none}@media(max-width:760px){.history-record .history-endpoint-label{display:block}}"

REPORT_CSS += ".research-swatch.positive{background:var(--good)}.cloud-bar-item .positive{color:var(--good)}.cloud-bar-item .negative{color:#bc4253}:root[data-theme=dark] .cloud-bar-item .negative{color:#ff98a7}"

REPORT_CSS += """
body[data-page=analytics] .analytics-detail-table-wrap{width:100%;max-width:100%;overflow:auto;border:1px solid var(--line);border-radius:12px;margin:12px 0;isolation:isolate}body[data-page=analytics] .analytics-detail-table{width:var(--detail-width);table-layout:fixed;font-size:calc(14px * var(--text-scale));margin:0;border-collapse:separate;border-spacing:0}body[data-page=analytics] .analytics-detail-table th,body[data-page=analytics] .analytics-detail-table td{padding:12px 14px;vertical-align:middle;text-align:right;overflow-wrap:normal}body[data-page=analytics] .analytics-detail-table td{white-space:nowrap}body[data-page=analytics] .analytics-detail-table th:first-child,body[data-page=analytics] .analytics-detail-table td:first-child{position:sticky;left:0;z-index:2;text-align:left;background:var(--panel-solid)}body[data-page=analytics] .analytics-detail-table th:nth-child(2),body[data-page=analytics] .analytics-detail-table td:nth-child(2){position:sticky;left:160px;z-index:2;text-align:left;background:var(--panel-solid);border-right:1px solid var(--line)}.detail-method-mobile{display:none}.analytics-detail-table-wrap:focus-visible{outline:3px solid var(--cyan);outline-offset:3px}
@media(max-width:760px){body[data-page=analytics] .analytics-detail-table thead{display:table-header-group}body[data-page=analytics] .analytics-detail-table tbody{display:table-row-group}body[data-page=analytics] .analytics-detail-table tr{display:table-row;border:0;padding:0;background:var(--panel-solid)}body[data-page=analytics] .analytics-detail-table td{display:table-cell;grid-column:auto}body[data-page=analytics] .analytics-detail-table td:before{display:none}body[data-page=analytics] .analytics-detail-table th:nth-child(2),body[data-page=analytics] .analytics-detail-table td:nth-child(2){position:static}.detail-method-mobile{display:block;font-size:12px}body[data-page=analytics] .analytics-detail-table tr[hidden]{display:none!important}}
"""

REPORT_CSS += ".cloud-bar-track{position:relative}.cloud-bar-track:after{content:'';position:absolute;left:var(--bar-zero,0%);top:0;bottom:0;width:1px;background:var(--muted);opacity:.65}"

REPORT_CSS += ".cloud-settings .settings-close{display:grid;place-items:center;flex:0 0 44px;width:44px;height:44px;min-height:44px;padding:0!important;line-height:1;border-radius:12px;align-self:center}.settings-close svg{display:block;width:20px;height:20px}.settings-heading h2{line-height:1.3}"
