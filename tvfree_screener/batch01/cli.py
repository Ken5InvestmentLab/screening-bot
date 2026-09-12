"""Research-only CLI for checking the TV-Free batch01 evidence package.

This module has no Codex, LLM, network, broker, or production integration.
The screen command is deliberately a no-candidate dry-run, not a market scan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


BATCH_DIR = Path(__file__).resolve().parent
REPORT_DIR = BATCH_DIR / "reports"
LEADERBOARD_JSON = REPORT_DIR / "tvfree_research_leaderboard_2026-09-13.json"
LEADERBOARD_MARKDOWN = REPORT_DIR / "tvfree_research_leaderboard_2026-09-13.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _console_safe(text: str, encoding: str) -> str:
    """Keep the local report readable on Windows code pages with ASCII escapes."""
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def load_verified_leaderboard() -> dict[str, Any]:
    """Load the pinned scorecard and fail closed if a source report changed."""
    board = json.loads(LEADERBOARD_JSON.read_text(encoding="utf-8"))
    reports = board.get("source_reports")
    hashes = board.get("source_report_sha256")
    if not isinstance(reports, list) or not isinstance(hashes, dict):
        raise ValueError("scorecard does not pin its source report hashes")
    if set(reports) != set(hashes):
        raise ValueError("source report list and hash manifest differ")
    for relative in reports:
        rel_path = Path(str(relative))
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError(f"unsafe source report path: {relative}")
        path = BATCH_DIR / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"scorecard source report is missing: {relative}")
        if _sha256(path) != hashes[relative]:
            raise ValueError(f"scorecard source report hash changed: {relative}")
        if path.suffix.lower() == ".json":
            json.loads(path.read_text(encoding="utf-8"))
    return board


def command_result(command: str, board: dict[str, Any]) -> dict[str, Any]:
    """Build status output without consulting external services or scanning prices."""
    if command == "audit":
        return {
            "command": "audit",
            "status": "PASS",
            "production_migration_decision": board["production_migration_decision"],
            "pinned_source_report_count": len(board["source_reports"]),
            "same_definition_outperformance_established": board[
                "same_definition_outperformance_over_current_bot_established"
            ],
        }
    if command == "experiment":
        return {
            "command": "experiment",
            "mode": "recorded_status_only",
            "core": board["core"],
            "monster": board["monster"],
            "v29": board["v29"],
            "fundamental_v2": board["fundamental_v2"],
        }
    if command == "screen":
        if board.get("core", {}).get("decision") != "NO_VIABLE_CANDIDATE":
            raise ValueError("safe screen dry-run is locked to the recorded no-candidate state")
        return {
            "command": "screen",
            "status": "NO_VIABLE_CANDIDATE",
            "screening_executed": False,
            "market_data_loaded": False,
            "recommendations": [],
            "reason": "No frozen Core or Monster selection policy passed its registered gates.",
            "production_migration_decision": board["production_migration_decision"],
        }
    if command == "evaluate":
        return {
            "command": "evaluate",
            "status": board["core"]["decision"],
            "production_migration_decision": board["production_migration_decision"],
            "evidence_level": board["evidence_level"],
            "leaderboard": board,
        }
    raise ValueError(f"unsupported structured command: {command}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("audit", "experiment", "screen", "evaluate", "report"),
        help="report is a local document view; screen is explicitly a no-candidate dry-run",
    )
    args = parser.parse_args()
    if args.command == "report":
        text = LEADERBOARD_MARKDOWN.read_text(encoding="utf-8")
        encoding = sys.stdout.encoding or "utf-8"
        print(_console_safe(text, encoding), end="")
        return
    board = load_verified_leaderboard()
    print(json.dumps(command_result(args.command, board), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()