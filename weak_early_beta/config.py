"""Frozen public metadata for the Weak+Early beta lanes."""

from __future__ import annotations

from dataclasses import dataclass


BETA_IDENTITY = "WEAK_EARLY_FIVE_LANE_BETA_V1"
ENDPOINT_LABEL = "シグナル翌営業日寄付 → 5営業日目終値（コスト0%）"
COMBINED_STACKED_ID = "all_conditions_stacked"
COMBINED_STACKED_NAME = "全5条件合計（条件別積上げ）"
COMBINED_UNIQUE_ID = "all_conditions_unique"
COMBINED_UNIQUE_NAME = "全5条件合計（銘柄均等）"
COMBINED_SELECTOR_IDS = (COMBINED_STACKED_ID, COMBINED_UNIQUE_ID)


@dataclass(frozen=True)
class SelectorInfo:
    selector_id: str
    display_name: str
    short_name: str
    feature_summary: str
    selection_summary: str


SELECTORS: dict[str, SelectorInfo] = {
    "volr20_low": SelectorInfo(
        selector_id="volr20_low",
        display_name="出来高沈静リバウンド",
        short_name="出来高沈静",
        feature_summary="直近20日平均に対して出来高が相対的に静かな候補を優先",
        selection_summary="弱い地合いのTail候補から、20日出来高比が最も低い1銘柄",
    ),
    "body_pct_low": SelectorInfo(
        selector_id="body_pct_low",
        display_name="陰線沈み込みリバウンド",
        short_name="陰線沈み込み",
        feature_summary="ローソク足の符号付き実体比が低く、陰線側へ沈んだ候補を優先",
        selection_summary="弱い地合いのTail候補から、実体比が最も低い1銘柄",
    ),
    "mean_rank_volr20_body_pct": SelectorInfo(
        selector_id="mean_rank_volr20_body_pct",
        display_name="静かな売られ過ぎバランス",
        short_name="静穏バランス",
        feature_summary="出来高沈静と陰線沈み込みを片寄りなく組み合わせる",
        selection_summary="20日出来高比順位と実体比順位の平均が最も低い1銘柄",
    ),
    "dual_top1_agreement": SelectorInfo(
        selector_id="dual_top1_agreement",
        display_name="2条件一致リバウンド",
        short_name="2条件一致",
        feature_summary="出来高沈静と陰線沈み込みが同じ銘柄を首位に選んだ日だけ検出",
        selection_summary="2つの独立Top1が一致した銘柄。不同意の日は見送り",
    ),
    "dual_top1_agreement_g3_no_acute_selloff": SelectorInfo(
        selector_id="dual_top1_agreement_g3_no_acute_selloff",
        display_name="地合い安定・2条件一致",
        short_name="地合い安定一致",
        feature_summary="2条件一致に、市場全体の急落を避ける確認を追加",
        selection_summary="2条件一致かつ市場1日中央値リターンが-1%以上",
    ),
}


SELECTOR_ORDER = tuple(SELECTORS)


def selector_info(selector_id: str) -> SelectorInfo:
    try:
        return SELECTORS[selector_id]
    except KeyError as exc:
        raise ValueError(f"unknown selector: {selector_id}") from exc
