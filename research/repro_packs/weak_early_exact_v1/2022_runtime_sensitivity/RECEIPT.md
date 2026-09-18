# 2022 fixed-spec runtime-sensitivity receipt

Status: **EXACT_NOT_YET_RECOVERED for the historical 89/29/23 identity**. These are fixed-spec diagnostic replays, not a retuned replacement.

## Frozen inputs and code

- Daily corpus artifact: `10264205130`; SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.
- Validation source commit: `d9792122a541847c3e4ed82604bffa220dab4a33`.
- V7 blob: `f7f49ab2e09496494adfb365c94e969973c4070c`.
- V9 blob: `45a1272fe49c526bbf69956419e34e96d696f7d6`.
- Period: `2022-06-01..2022-12-31`.
- Tail definition: monthly causal V7 model, `tail_cdf >= 0.999`.
- Gate: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`.
- Historical 89 raw / 29 gated / 23 dates is comparison evidence only and was never an optimization target.

## Fixed-spec results

| Runtime | Raw Tail | Gated rows | Gated dates | Historical identity |
|---|---:|---:|---:|---|
| Windows x86-64 | 94 | 30 | 22 | mismatch |
| WSL2 Linux x86-64 | 95 | 25 | 20 | mismatch |

Both used Python 3.12 with `numpy==2.5.3`, `pandas==2.3.3`, `scikit-learn==1.9.1`, and `xgboost==3.4.1`. The Linux run also pinned `requests==2.34.2` and `yfinance==0.2.66`, matching the preserved-cache Actions installation log. The cross-platform identity drift proves the 2022 historical model rows cannot be called exact from source/input/version pins alone.

## Saved ledgers

- `linux_tail_raw_2022.csv`: `9541aac0689f635a13bf271dbd8cb6cccf3fbdd26a4975207341145665fe009c`
- `linux_weak_early_gated_2022.csv`: `8473e8247cc95a53bf60977f6348fc578640f6f3a56cd06ef8cd57f841f0f186`
- `windows_tail_raw_2022.csv`: `cf5e5cc08d99e71c1d3370ff6a3b93c684027f5a605554db79340c6df8810b6d`
- `windows_weak_early_gated_2022.csv`: `b4b5a63cc77afd12eadca2027394533fcd2e02998ad136be60706b588e046ccc`

Do not choose one runtime because it is numerically closer to 89/29/23. Exact recovery now requires the original saved 2022 prediction ledger/model artifact or stronger historical environment evidence.
