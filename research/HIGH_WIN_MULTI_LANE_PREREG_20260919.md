# High-win multi-lane scoring research preregistration — 2026-09-19

Status: **FROZEN BEFORE DISCOVERY / RESEARCH ONLY / 2026 FORBIDDEN FOR SELECTION**

## Objective

TradingView非依存の固定Weak+Early population上で、勝率5割前後から明確に改善しつつ、件数・平均・right tailを失わない最大3つの異質なscoring laneを探す。既存exact条件は上書きせず、新identity `HIGH_WIN_MULTI_LANE_RESEARCH_V1` として評価する。

## Data split

- 2023: discovery。
- 2024: internal validation。
- 2025: finalist freeze後に一度だけ開くholdout。
- 2026: reporting済みの値を含め、feature/direction/family/finalist/gate/threshold/cooldown選択へ使用禁止。
- InputとSHA、全12候補、selection、tie-break、eligibility、holdout gateはmachine-readable JSONを正とする。

## Fixed population and endpoint

- Preserved causal V7 Tail。
- Gate: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`。
- 1 signal dateにつき1候補。
- 各候補のscoreは、宣言方向にそろえたwithin-date percentile rankの単純平均。重み最適化なし。
- Tie-break: `tail_cdf DESC`, then `symbol ASC`。cooldownなし。
- Endpoint: next official XTKS open → fifth official XTKS close、cost 0%、win=`gross > 0`。

## Four distinct families

1. `EARLY_PRESSURE`: volume/body/one-day moveの小ささ。
2. `DEFENSIVE_PULLBACK`: ATR、BB位置、RSIの低さ。
3. `REVERSAL_WICK`: lower wickの強さと弱いbody/volume/BB位置。
4. `MODEL_CONVICTION`: frozen Tail確信度とweak/early特徴の組合せ。

各familyはJSON記載の3候補だけ。数値threshold search、3変数以上、重み探索、2025を見た候補追加は禁止。

## Selection before holdout

各family winnerは2023/2024のうち低い方のwin率を第一優先とし、aggregate win、低い方のmedian、aggregate Top3-ex、aggregate mean、candidate idの順で決める。2023 n>=45、2024 n>=70、aggregate mean>0、Top3-ex>0が必要。

family winnerから最大3つを同じ順で選び、development identity Jaccardが0.85を超える重複laneは後順位を除外する。finalist specをcommit/pushするまで2025を計算しない。

## 2025 holdout pass gate

全て事前固定:

- n >= 35
- win >= 55%
- mean >= +3%
- median > 0%
- Top3-ex > 0%
- +20% >= 15%
- -10% <= 25%

通過が0件なら`NO_VIABLE_NEW_LANE`を有効な結論とする。holdout後に条件を緩めない。2〜3件通れば、特徴の異なる複数laneとしてforward shadowへ送る。1件だけなら単独shadow候補であり、無理に2件目を作らない。

## Production boundary

これはresearch-only。main、production、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder、watchlist-updaterは変更しない。既存Cloud/Weak exact packと2026 reporting rowsも変更しない。
