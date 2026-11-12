"""Evidence-backed run-local entry revision quarantine, never a price repair."""
import hashlib
import json
import math
import re
from pathlib import Path
import pandas as pd
from .jpx_holds import digest

COLUMN = "endpoint_symbol_hold_evidence"
ISSUE = "unresolved_entry_price_revision"

def verify(group):
    if COLUMN not in group:
        return None
    entries = group[COLUMN].fillna("").astype(str)
    entries = entries[entries.ne("")]
    if entries.empty:
        return None
    if len(entries) != 1:
        raise ValueError("endpoint hold requires one symbol anchor")
    evidence = json.loads(entries.iloc[0])
    if (evidence.get("identity") != "CLOUD_ENDPOINT_SYMBOL_HOLD_V1"
            or evidence.get("symbol") != str(group.symbol.iloc[0])
            or evidence.get("current_rows_sha256") != digest(group)):
        raise ValueError("endpoint hold identity/current rows mismatch")
    for field in ("source_sha256", "ledger_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", evidence.get(field, "")):
            raise ValueError("endpoint hold missing input identity")
    if not evidence.get("conflicts"):
        raise ValueError("endpoint hold has no conflict")
    for conflict in evidence["conflicts"]:
        old, new = conflict["ledger_entry_open"], conflict["source_entry_open"]
        if (conflict.get("symbol") != evidence["symbol"]
                or conflict.get("reason") != ISSUE or not conflict.get("detection_id")
                or not all(math.isfinite(x) and x > 0 for x in (old, new))
                or abs(old - new) <= max(.01, abs(old) * 1e-6)):
            raise ValueError("endpoint hold unsupported conflict")
    return evidence

def audit(frame):
    return [e for _, group in frame.groupby("symbol", sort=False)
            if (e := verify(group))]

def notification_holds(receipt_path, target_date, ledger):
    """Fail closed on stale/mismatched detection evidence before any send."""
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    target = pd.Timestamp(target_date).strftime("%Y-%m-%d")
    if (receipt.get("identity") != "WEAK_EARLY_FIVE_LANE_BETA_V1"
            or receipt.get("latest_session") != target
            or receipt.get("score_to") != target
            or "endpoint_holds" not in receipt):
        raise ValueError("notification requires same-day endpoint hold receipt")
    def sha(path):
        with Path(path).open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    if sha(receipt["daily_corpus"]) != receipt["daily_sha256"]:
        raise ValueError("notification daily source identity changed")
    quality = receipt["source_quality"]
    if sha(quality["audit_path"]) != quality["audit_sha256"]:
        raise ValueError("notification source quality identity changed")
    quality_body = json.loads(Path(quality["audit_path"]).read_text(encoding="utf-8"))
    if quality_body.get("identity") != "CLOUD_SOURCE_QUALITY_V1" or quality_body.get("daily_sha256") != receipt["daily_sha256"]:
        raise ValueError("notification source quality mismatch")
    if sha(receipt["endpoint_hold_audit"]) != receipt["endpoint_hold_audit_sha256"]:
        raise ValueError("notification hold audit identity changed")
    evidence = json.loads(Path(receipt["endpoint_hold_audit"]).read_text(encoding="utf-8"))
    if (evidence.get("identity") != "CLOUD_ENDPOINT_HOLD_AUDIT_V1"
            or evidence.get("daily_sha256") != receipt["daily_sha256"]
            or evidence.get("holds") != receipt["endpoint_holds"]):
        raise ValueError("notification hold audit mismatch")
    blocked = set()
    for hold in evidence["holds"]:
        if hold.get("identity") != "CLOUD_ENDPOINT_SYMBOL_HOLD_V1" or hold.get("source_sha256") != receipt["daily_sha256"] or not hold.get("conflicts"):
            raise ValueError("invalid notification hold")
        for conflict in hold["conflicts"]:
            rows = ledger[ledger.detection_id.eq(conflict["detection_id"])]
            if len(rows) != 1 or str(rows.iloc[0].symbol) != hold["symbol"] or float(rows.iloc[0].entry_open) != conflict["ledger_entry_open"]:
                raise ValueError("notification hold ledger changed")
        blocked.add(hold["symbol"])
    return blocked

def quarantine(ledger, raw, source_sha256):
    """Hold full symbols before mutation; unknown/session errors stay fatal.

    Original CSV remains unchanged. All selector rows and endpoint receipts of
    a held symbol remain frozen. Source rows retain their calendar positions.
    """
    from .corporate_actions import normalize_daily
    from .model import PRICE_BASIS_VERSION, is_frozen_trade, add_bank_business_days
    frame = normalize_daily(raw)
    if ledger.empty:
        return raw, []
    prices = frame.set_index(["symbol", "date"])
    conflicts = {}
    for _, row in ledger[ledger.source_scope.eq("FORWARD_CAUSAL")].iterrows():
        if is_frozen_trade(row) or row.get("price_basis") != PRICE_BASIS_VERSION or pd.isna(row.get("entry_open")):
            continue
        symbol = str(row.symbol)
        signal = pd.Timestamp(row.signal_date).normalize()
        entry = pd.Timestamp(add_bank_business_days(signal.date(), 1))
        if (symbol, signal) not in prices.index or (symbol, entry) not in prices.index:
            continue
        if not bool(prices.loc[(symbol, signal), "source_usable"]):
            continue
        if pd.Timestamp(row.entry_date).normalize() != entry:
            raise ValueError(f"entry session revision requires review: {row.detection_id}")
        exit_date = pd.Timestamp(add_bank_business_days(signal.date(), 5))
        if pd.notna(row.get("fifth_xtks_exit_date")) and pd.Timestamp(row.fifth_xtks_exit_date).normalize() != exit_date:
            raise ValueError(f"exit session revision requires review: {row.detection_id}")
        old = float(row.entry_open)
        new = float(prices.loc[(symbol, entry), "actual_open"])
        if abs(old - new) > max(.01, abs(old) * 1e-6):
            conflicts.setdefault(symbol, []).append({"symbol": symbol,
                "detection_id": str(row.detection_id), "reason": ISSUE,
                "entry_date": entry.strftime("%Y-%m-%d"),
                "ledger_entry_open": old, "source_entry_open": new})
    if not conflicts:
        return raw, []
    ledger_sha = hashlib.sha256(ledger.to_json(orient="split", date_format="iso", double_precision=15).encode()).hexdigest()
    out = frame.copy()
    out[COLUMN] = ""
    for symbol, records in conflicts.items():
        group = out[out.symbol.eq(symbol)]
        evidence = {"identity": "CLOUD_ENDPOINT_SYMBOL_HOLD_V1", "symbol": symbol,
            "source_sha256": source_sha256, "ledger_sha256": ledger_sha,
            "current_rows_sha256": digest(group), "conflicts": records}
        out.at[group.index[-1], COLUMN] = json.dumps(evidence, sort_keys=True)
        usable = out.loc[group.index, "source_usable"].astype(bool)
        out.loc[group.index[usable], "source_issue"] = ISSUE
        out.loc[group.index, "source_usable"] = False
    out = normalize_daily(out)
    return out, audit(out)
