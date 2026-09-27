"""Premium-compatible material-impact formatting for Cloud historical snapshots."""

from __future__ import annotations

import copy
import hashlib
import re


IMPACT_LABELS = (
    "ポジティブ材料",
    "ネガティブ材料",
    "様子見",
    "混在/要確認",
)
_LABEL_PATTERNS = (
    (r"^ポジティブ(?:材料)?(?=$|[\s:：。、「」])", "ポジティブ材料"),
    (r"^ネガティブ(?:材料)?(?=$|[\s:：。、「」])", "ネガティブ材料"),
    (r"^様子見(?=$|[\s:：。、「」])", "様子見"),
    (r"^(?:混在[/・]要確認|混在|要確認)(?=$|[\s:：。、「」])", "混在/要確認"),
    (r"^(?:positive)(?=$|[\s:：。、「」])", "ポジティブ材料"),
    (r"^(?:negative)(?=$|[\s:：。、「」])", "ネガティブ材料"),
    (r"^(?:watch|neutral)(?=$|[\s:：。、「」])", "様子見"),
    (r"^(?:mixed)(?=$|[\s:：。、「」])", "混在/要確認"),
)
_POSITIVE = re.compile(
    r"ポジティブ|positive|前向き|増収|増益|黒字転換|黒字化|営業黒字|"
    r"最高益|過去最高|利益.{0,5}改善|収益性向上|回復|増配|復配|増額|"
    r"上方修正|上振|受注.{0,6}(?:獲得|増加|拡大)|採用|好調|堅調|成長材料|"
    r"売上.{0,8}(?:増え|増加|拡大)|営業利益.{0,6}(?:増加|拡大|上回)"
)
_NEGATIVE = re.compile(
    r"ネガティブ|negative|赤字継続|赤字が続|赤字が残|赤字拡大|赤字予想|"
    r"営業赤字|営業損失|経常損失|純損失|損失.{0,6}(?:拡大|継続)|減収|減益|"
    r"下方修正|予想.{0,6}下回|下振|未達|減配|無配|債務超過|継続企業|"
    r"営業CF.{0,8}(?:マイナス|赤字|流出)|CF.{0,8}流出|希薄化|破産|中止|撤退|"
    r"自己資本比率.{0,8}低下|利益.{0,6}(?:減少|低下)|悪化|資金繰り|減損|訴訟"
)
_UNCERTAIN = re.compile(
    r"未開示|非開示|未確定|未確立|不明|不透明|未確認|未了|承認前|精査中|"
    r"影響額.{0,8}(?:不明|未開示)|業績影響.{0,8}(?:不明|未定)|"
    r"寄与.{0,8}(?:不明|未開示|未確定)|効果.{0,8}(?:不明|未開示|未確定)|"
    r"収益化.{0,8}(?:未|不明)|条件付き|継続性.{0,8}確認|未達|懸念|リスク"
)
_PREFIX_MIXED = ("混在", "併存", "mixed", "成長材料と収益面", "業績改善/注意", "回復進展")
_PREFIX_NEUTRAL = ("様子見", "中立", "慎重", "watch", "neutral")


def _short_summary(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    prefix = re.match(r"^([^：:]{1,48})[：:]\s*", text)
    if prefix and any(
        token in prefix.group(1).lower()
        for token in (
            "材料", "混在", "要確認", "様子見", "中立", "注意", "慎重", "警戒",
            "改善", "回復", "成長", "プラス", "ネガティブ", "ポジティブ",
            "positive", "negative", "mixed", "watch", "neutral", "前向き", "併存",
        )
    ):
        text = text[prefix.end():].strip()
    sentence = re.split(r"(?<=[。！？])\s*", text, maxsplit=1)[0].strip()
    if len(sentence) > 90:
        sentence = f"{sentence[:89].rstrip(' 、，,・/：:')}…"
    return sentence


def _label_legacy_impact(raw: str) -> str:
    lower = str(raw or "").lower()
    prefix_match = re.match(r"^([^：:]{1,48})[：:]", raw)
    prefix = prefix_match.group(1).lower() if prefix_match else ""
    positive = bool(_POSITIVE.search(lower))
    # A past-period loss mentioned as the base for a clear turnaround is not
    # itself a current negative signal.
    current_negative_text = re.sub(
        r"(?:前期|前年|前年度|前回).{0,12}(?:赤字|損失).{0,10}(?:から|ものの|一方で)",
        " ",
        lower,
    )
    negative = bool(_NEGATIVE.search(current_negative_text))
    uncertain = bool(_UNCERTAIN.search(lower))

    if any(term in prefix for term in _PREFIX_MIXED) or (positive and negative) or (
        (positive or negative) and uncertain
    ):
        return "混在/要確認"
    if any(term in prefix for term in _PREFIX_NEUTRAL):
        return "様子見"
    if positive:
        return "ポジティブ材料"
    if negative:
        return "ネガティブ材料"
    return "様子見"


def normalize_material_impact(
    fields: list[tuple[str, str]],
) -> tuple[str, str, bool]:
    """Return Premium-formatted text, its exact Premium color class, and changed flag."""
    values = {str(name or "").strip(): str(value or "").strip() for name, value in fields}
    raw = values.get("材料インパクト", "")
    if not raw:
        return "", "", False

    label = ""
    remainder = raw
    for pattern, normalized in _LABEL_PATTERNS:
        match = re.match(pattern, raw, flags=re.IGNORECASE)
        if match:
            label = normalized
            remainder = raw[match.end():].lstrip(" \t:：、。-・")
            break
    if not label:
        label = _label_legacy_impact(raw)

    summary = _short_summary(remainder)
    if not summary:
        summary = _short_summary(values.get("足元材料", ""))
    if not summary:
        summary = _short_summary(values.get("ファンダ要点", ""))
    if not summary:
        summary = "既存の分析記載から個別材料の影響を特定できません。"
    normalized = f"{label}：{summary}"

    # Match premium_worker._embedColor() exactly: watch/mixed/neutral takes
    # precedence, then positive, then negative.
    if re.search(r"様子見|中立|要確認|混在|watch|neutral|mixed", normalized, re.IGNORECASE):
        impact_class = " impact-watch"
    elif re.search(r"ポジティブ|positive", normalized, re.IGNORECASE):
        impact_class = " impact-positive"
    elif re.search(r"ネガティブ|negative", normalized, re.IGNORECASE):
        impact_class = " impact-negative"
    else:
        impact_class = " impact-watch"
    return normalized, impact_class, normalized != raw


def normalize_report_material_impact(report: dict) -> tuple[dict, dict | None]:
    """Normalize only the existing impact field; return an auditable before/after record."""
    normalized_report = copy.deepcopy(report)
    fields = normalized_report.get("fields", [])
    pairs = [
        (str(item.get("name", "")), str(item.get("value", "")))
        for item in fields
        if isinstance(item, dict)
    ]
    normalized, _impact_class, _changed = normalize_material_impact(pairs)
    impact_field = next(
        (item for item in fields if isinstance(item, dict) and item.get("name") == "材料インパクト"),
        None,
    )
    if impact_field is None or not normalized:
        return normalized_report, None

    old = str(impact_field.get("value", ""))
    old_top = str(normalized_report.get("materialImpact", ""))
    impact_field["value"] = normalized
    normalized_report["materialImpact"] = normalized
    if old == normalized and old_top == normalized:
        return normalized_report, None

    identity = f"{normalized_report.get('signalDate', '')}|{normalized_report.get('symbolCode', '')}"
    return normalized_report, {
        "identity": identity,
        "previous_value": old,
        "normalized_value": normalized,
        "previous_sha256": hashlib.sha256(old.encode("utf-8")).hexdigest(),
        "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }
