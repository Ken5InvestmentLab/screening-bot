"""
monitor_live.py — ライブ実績モニタリング + 自動ロールバック

champion_state.json の live_log を集計し、Champion の live 勝率が
backtest 95% CI 下限を下回った場合に自動ロールバックを実行する。

実行タイミング: GAS の runDailyMaintenance 後に GitHub Actions optimize.yml
または単独で呼び出す。

使い方:
    py monitor_live.py             # 本番実行（2日連続 CI 下限割れでロールバック）
    py monitor_live.py --dry-run   # ドライラン（ロールバック・SCP なし、判定のみ表示）
    py monitor_live.py --reset     # ブリーチカウンターをリセット
"""

import json
import os
import sys
import argparse
import subprocess
from datetime import datetime, timezone

# ── パス設定（optimize_screener.py と同じディレクトリ）─────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAMPION_STATE_PATH  = os.path.join(BASE_DIR, "champion_state.json")
CURRENT_LOGIC_PATH   = os.path.join(BASE_DIR, "current_logic.json")
SCREENER_JS_PATH     = os.path.join(BASE_DIR, "screener.js")
LOGIC_HISTORY_PATH   = os.path.join(BASE_DIR, "current_logic_history.jsonl")
MONITOR_STATE_PATH   = os.path.join(BASE_DIR, "monitor_state.json")

import platform as _platform
_ON_VM = _platform.system() == "Linux" and os.path.isdir("/home/ubuntu/screening-bot")
SSH_KEY  = "/home/ubuntu/ssh-key-2026-03-08.key" if _ON_VM else \
           r"C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key"
VM_HOST  = "ubuntu@168.110.60.126"
VM_PATH  = "/home/ubuntu/screening-bot"

# ── 設定 ─────────────────────────────────────────────────────────────
MIN_CONFIRMED_S6      = 10   # live_log の確定★6が最低これ以上ないと判定保留
BREACH_REQUIRED_DAYS  = 2    # 連続何日 CI 下限割れで自動ロールバック
DISCORD_WEBHOOK_URL   = (
    "https://discord.com/api/webhooks/1479431524674965729/"
    "sRCEG2lmoBLpEtZCdbf5N4kg2zEI7LHjtxxHm9g2Y1rFXPwoFSPDxpnOjsP0HAObSdyZ"
)


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _jst_date():
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date().isoformat()


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠ {os.path.basename(path)} 読み込みエラー: {e}")
        return default if default is not None else {}


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ {os.path.basename(path)} 保存エラー: {e}")


def compute_live_wr(live_log):
    """live_log の確定★6エントリから live 勝率を集計する。"""
    confirmed_s6 = [
        r for r in live_log
        if r.get("champion_score") == 6 and r.get("perf_5bd") is not None
    ]
    if not confirmed_s6:
        return 0, 0.0
    n = len(confirmed_s6)
    wins = sum(1 for r in confirmed_s6 if r["perf_5bd"] > 0)
    return n, wins / n


def notify_discord(message: str):
    """Discord Webhook に通知を送る。"""
    import urllib.request
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (screening-bot, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"  ⚠ Discord 通知失敗: {e}")


def rollback_to_prev_champion(champion_state, dry_run=False):
    """prev_champion のロジックを current_logic.json と screener.js に復元する。"""
    prev = champion_state.get("prev_champion")
    if not prev:
        print("  ⚠ prev_champion が存在しません。ロールバック不可。")
        return False

    method     = prev["method"]
    conditions = prev["conditions"]
    thresholds = prev.get("thresholds", {})
    backtest   = prev.get("backtest_snapshot", {})

    print(f"  ⏪ ロールバック対象: 方式{method} / {conditions}")

    if dry_run:
        print("  [dry-run] ロールバック処理をスキップ")
        return True

    # current_logic.json を prev_champion の内容で上書き
    new_logic = {
        "method": method,
        "conditions": conditions,
        "updated_at": _utc_now(),
        "rolled_back_at": _utc_now(),
    }
    if thresholds:
        new_logic["thresholds"] = thresholds
    if backtest:
        new_logic["backtest"] = backtest
    save_json(CURRENT_LOGIC_PATH, new_logic)
    print("  ✅ current_logic.json をロールバック済みロジックで更新")

    # screener.js の calculateScore() を prev_champion ロジックで再生成
    # optimize_screener.py の build_func_a/b を動的 import して利用
    try:
        sys.path.insert(0, BASE_DIR)
        import optimize_screener as _opt
        if method == "A":
            baseline_dummy = {"wr_raw": 0.0, "avg_raw": 0.0, "n": 0,
                              "win10_raw": 0.0, "lose10_raw": 0.0, "composite": 0.0}
            stats_dummy = baseline_dummy.copy()
            new_code = _opt.build_func_a(conditions, stats_dummy, baseline_dummy, 1, thresholds)
        else:
            new_code = _opt.build_func_b(conditions, {}, {}, 1)
        if not _opt.update_screener_js(new_code):
            print("  ⚠ screener.js 更新失敗")
            return False
        print("  ✅ screener.js をロールバック済みロジックで更新")
    except Exception as e:
        print(f"  ⚠ screener.js ロールバック失敗: {e}")
        return False

    # SCP + pm2 restart
    try:
        if _ON_VM:
            result = subprocess.run(
                ["pm2", "restart", "screening-bot"],
                capture_output=True, encoding="utf-8", errors="replace"
            )
        else:
            scp_result = subprocess.run(
                ["scp", "-i", SSH_KEY, SCREENER_JS_PATH,
                 f"{VM_HOST}:{VM_PATH}/screener.js"],
                capture_output=True, encoding="utf-8", errors="replace"
            )
            if scp_result.returncode != 0:
                print(f"  ⚠ SCP 失敗: {(scp_result.stderr or '').strip()}")
                return False
            result = subprocess.run(
                ["ssh", "-i", SSH_KEY, VM_HOST, "pm2 restart screening-bot"],
                capture_output=True, encoding="utf-8", errors="replace"
            )
        if result.returncode == 0:
            print("  ✅ pm2 restart 完了")
            return True
        else:
            print(f"  ⚠ pm2 restart 失敗: {(result.stderr or '').strip()}")
            return False
    except Exception as e:
        print(f"  ⚠ デプロイエラー: {e}")
        return False


def run(dry_run=False):
    print("=" * 60)
    print("天底極致 ライブ実績モニタリング")
    print("=" * 60)
    today = _jst_date()

    champion_state = load_json(CHAMPION_STATE_PATH)
    if not champion_state:
        print("  ℹ champion_state.json が存在しません。モニタリングをスキップ。")
        return

    champion = champion_state.get("champion")
    if not champion:
        print("  ℹ Champion が未設定です。スキップ。")
        return

    live_log  = champion_state.get("live_log", [])
    n_s6, live_wr = compute_live_wr(live_log)

    backtest = champion.get("backtest_snapshot", {})
    wr_ci = backtest.get("wr_95ci", [0.0, 1.0])
    ci_lo = float(wr_ci[0]) if wr_ci else 0.0

    print(f"  Champion 展開日: {champion.get('deployed_at', '不明')}")
    print(f"  live_log 確定★6: {n_s6}件 / live 勝率: {live_wr*100:.1f}%")
    print(f"  backtest 95% CI 下限: {ci_lo*100:.1f}%")

    if n_s6 < MIN_CONFIRMED_S6:
        print(f"  ℹ 確定★6 < {MIN_CONFIRMED_S6}件のため判定保留")
        return

    monitor_state = load_json(MONITOR_STATE_PATH, default={"streak": 0, "last_date": ""})
    streak = monitor_state.get("streak", 0)

    if live_wr < ci_lo:
        # CI 下限割れ
        if monitor_state.get("last_date") == _jst_date_yesterday():
            streak += 1
        else:
            streak = 1
        print(f"  ⚠ live 勝率 {live_wr*100:.1f}% < CI下限 {ci_lo*100:.1f}% "
              f"({streak}/{BREACH_REQUIRED_DAYS}日目)")

        monitor_state["streak"]    = streak
        monitor_state["last_date"] = today
        if not dry_run:
            save_json(MONITOR_STATE_PATH, monitor_state)

        if streak >= BREACH_REQUIRED_DAYS:
            print(f"\n🔴 {streak}日連続 CI 下限割れ → ロールバックを実行します")
            success = rollback_to_prev_champion(champion_state, dry_run=dry_run)
            if success and not dry_run:
                # champion_state を更新（prev を champion に戻す）
                prev = champion_state.get("prev_champion", {})
                champion_state["champion"] = {
                    **prev,
                    "rolled_back_at": _utc_now(),
                }
                champion_state["prev_champion"] = champion
                champion_state["live_log"] = []
                save_json(CHAMPION_STATE_PATH, champion_state)
                monitor_state["streak"] = 0
                save_json(MONITOR_STATE_PATH, monitor_state)
                msg = (
                    f"🔴 **ライブ実績によるロールバック実行**\n"
                    f"live★6勝率 {live_wr*100:.1f}% が backtest 95% CI 下限 "
                    f"{ci_lo*100:.1f}% を {streak}日連続で下回りました。\n"
                    f"前のロジック（{prev.get('conditions', [])}）に復元しました。"
                )
                notify_discord(msg)
                print("  ✅ Discord 通知送信完了")
    else:
        # 正常
        if streak > 0:
            print(f"  ✅ live 勝率 {live_wr*100:.1f}% ≥ CI下限 {ci_lo*100:.1f}% — 回復（streak リセット）")
        else:
            print(f"  ✅ live 勝率 {live_wr*100:.1f}% ≥ CI下限 {ci_lo*100:.1f}% — 正常")
        monitor_state["streak"] = 0
        if not dry_run:
            save_json(MONITOR_STATE_PATH, monitor_state)


def _jst_date_yesterday():
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=9) - timedelta(days=1)).date().isoformat()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ライブ実績モニタリング")
    parser.add_argument("--dry-run", action="store_true", help="判定のみ、ロールバックなし")
    parser.add_argument("--reset",   action="store_true", help="ブリーチカウンターをリセット")
    args = parser.parse_args()

    if args.reset:
        save_json(MONITOR_STATE_PATH, {"streak": 0, "last_date": ""})
        print("✅ monitor_state.json をリセットしました")
        sys.exit(0)

    run(dry_run=args.dry_run)
