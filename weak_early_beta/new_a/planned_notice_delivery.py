"""Delivery boundary for the isolated New A owner notification plans.

There is no live adapter, task entry, webhook, or credential handling here.
The caller must provide authorized, read-only proof and an authorized transport.
"""

from datetime import date, datetime, timedelta, timezone
import json
import re
import sqlite3

from .files import digest, encode

JST = timezone(timedelta(hours=9))
HOLDING = "WATCH_TO_SIMULATED_HOLDING"
MORNING = "EVALUATION_DAY_MORNING"
AUDIENCE = "EXISTING_CLOUD_OWNER_ONLY"
UNKNOWN = "ATTEMPTED_UNCONFIRMED"
SENT = "SENT"
SHA256 = re.compile(r"[0-9a-f]{64}")
SYMBOL = re.compile(r"[0-9A-Z]{4}")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _day(value):
    _require(isinstance(value, str), "invalid notice date")
    parsed = date.fromisoformat(value)
    _require(parsed.isoformat() == value, "invalid notice date")
    return parsed


def _instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    _require(isinstance(value, datetime) and value.utcoffset() is not None,
             "verified clock with a timezone required")
    return value


def _clock():
    return datetime.now(timezone.utc)


def _assert_window(kind, target, current):
    local = _instant(current).astimezone(JST)
    _require(local.date().isoformat() == target, "notice delivery is outside its JST date")
    if kind == MORNING:
        _require(local.hour == 8, "evaluation notice is outside the 08:00 JST window")
    else:
        _require(local.hour >= 17, "holding notice requires same-day evening publication")


def _validate_plan(plan, kind):
    _require(kind in (HOLDING, MORNING) and plan.get("status") == "planned",
             "verified planned notices required")
    target = plan["target_date"]
    _day(target)
    basis = plan["basis"]
    fields = {"dataset_id", "revision", "manifest_sha256", "source_version",
              "snapshot_sha256", "preferences_revision"}
    if kind == MORNING:
        fields.add("calendar_sha256")
    _require(set(basis) == fields and re.fullmatch(r"a-[0-9a-f]{24}", str(basis.get("dataset_id", ""))) and
             all(_hash(basis.get(key)) for key in ("manifest_sha256", "source_version", "snapshot_sha256")) and
             all(type(basis.get(key)) is int and basis[key] > 0 for key in ("revision", "preferences_revision")),
             "published source and saved configuration binding required")
    _require(kind != MORNING or _hash(basis.get("calendar_sha256")),
             "morning notice requires its verified market calendar")
    notices = plan["notices"]
    _require(isinstance(notices, list) and len(notices) <= 1000, "notice batch exceeds the source bound")
    common = {"event_id", "kind", "symbol", "candidate_date", "simulated_entry_date",
              "title", "description", "execution_status"}
    morning = {"scheduled_evaluation_date", "evaluation_endpoint", "evaluation_timing",
               "evaluation_price_status"}
    endpoints = {"d5_close": "CLOSE", "d5_open": "OPEN", "d6_open": "OPEN", "a20_close": "CLOSE"}
    ids = set()
    for row in notices:
        event = row["event_id"]
        _require(set(row) == (common | morning if kind == MORNING else common) and
                 _hash(event) and event not in ids and bool(SYMBOL.fullmatch(row["symbol"])) and
                 row["kind"] == kind and row["execution_status"] == "SIMULATED_NOT_ACTUAL_TRADES" and
                 _day(row["candidate_date"]) <= _day(row["simulated_entry_date"]),
                 "notice is inconsistent with the owner-only model")
        ids.add(event)
        if kind == MORNING:
            _require(row["scheduled_evaluation_date"] == target and
                     _day(row["simulated_entry_date"]) < _day(target) and
                     row["evaluation_timing"] == endpoints.get(row["evaluation_endpoint"]) and
                     row["evaluation_timing"] in ("OPEN", "CLOSE") and
                     row["title"] == "確定日の朝8時（日本時間）" and
                     row["description"] == "今日は、設定した確定日です。その日の価格はまだ確定していません。" and
                     row["evaluation_price_status"] == "NOT_YET_OBSERVED",
                     "morning notice cannot claim an evaluated price")
        else:
            _require(row["simulated_entry_date"] == target and row["title"] == "監視から仮想保有に移行" and
                     row["description"] == "保存した条件による仮想保有です。実際の取引は行われていません。",
                     "holding notice must refer to this day's simulated position")
    return target, notices


def _verify_recipient(proof, owner, recipient, current):
    clock = _instant(current)
    _require(_hash(owner) and _hash(recipient) and
             proof.get("schema") == "NEW_A_OWNER_NOTICE_RECIPIENT_V1" and
             proof.get("audience") == AUDIENCE and proof.get("enabled") is True and
             proof.get("owner_verified") is True and proof.get("fresh_paid_role") is True and
             proof.get("owner_binding_sha256") == owner and
             proof.get("recipient_binding_sha256") == recipient,
             "owner-only notice recipient authorization is unverified")
    observed = _instant(proof["observed_at"])
    expires = _instant(proof["expires_at"])
    _require(observed <= clock < expires <= observed + timedelta(minutes=2),
             "owner-only notice recipient authorization is stale")


def _verify_source(proof, plan, owner, current):
    _require(proof.get("schema") == "NEW_A_OWNER_NOTICE_SOURCE_V1" and
             proof.get("current") is True and proof.get("owner_binding_sha256") == owner and
             proof.get("plan_sha256") == digest(plan) and proof.get("basis") == plan["basis"],
             "published source or saved owner revision changed before notice")
    clock = _instant(current)
    observed = _instant(proof["observed_at"])
    _require(observed <= clock < observed + timedelta(minutes=2),
             "publication or saved owner readback is stale")


def _confirmed(receipt, batch, recipient):
    return (isinstance(receipt, dict) and receipt.get("confirmed") is True and
            receipt.get("batch_id") == batch["batch_id"] and
            receipt.get("delivery_sha256") == digest(batch) and
            receipt.get("recipient_binding_sha256") == recipient and
            isinstance(receipt.get("message_id"), str) and
            re.fullmatch(r"[1-9][0-9]{16,19}", receipt["message_id"]) is not None)


class NoticeOutbox:
    """Separate SQLite namespace; never reuses or edits historical send state."""

    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5)
        try:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS new_a_owner_notice_batches(
                    batch_id TEXT PRIMARY KEY, owner TEXT NOT NULL, recipient TEXT NOT NULL, kind TEXT NOT NULL,
                    target_date TEXT NOT NULL, payload_json TEXT NOT NULL,
                    status TEXT NOT NULL, receipt_json TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS new_a_owner_notice_one_claim
                ON new_a_owner_notice_batches(owner, kind, target_date)
                WHERE status = 'ATTEMPTED_UNCONFIRMED';
                CREATE TABLE IF NOT EXISTS new_a_owner_notice_members(
                    owner TEXT NOT NULL, event_id TEXT NOT NULL, batch_id TEXT NOT NULL,
                    PRIMARY KEY(owner,event_id),
                    FOREIGN KEY(batch_id) REFERENCES new_a_owner_notice_batches(batch_id)
                );
            """)
            self.db.execute("PRAGMA foreign_keys = ON")
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def unknown(self, owner, kind, day):
        row = self.db.execute("""
            SELECT payload_json FROM new_a_owner_notice_batches
            WHERE owner=? AND kind=? AND target_date=? AND status=?
        """, (owner, kind, day, UNKNOWN)).fetchone()
        return json.loads(row[0]) if row else None

    def claim(self, owner, recipient, kind, day, basis, notices):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.unknown(owner, kind, day):
                return "reconciliation_required", None
            known = self.db.execute("""
                SELECT event_id FROM new_a_owner_notice_members AS m
                JOIN new_a_owner_notice_batches AS b USING(batch_id)
                WHERE m.owner=? AND b.kind=? AND b.target_date=?
            """, (owner, kind, day))
            existing = {row[0] for row in known}
            pending = sorted((row for row in notices if row["event_id"] not in existing),
                             key=lambda row: row["event_id"])
            if not pending:
                return "nothing_to_send", None
            batch_id = digest(["NEW_A_OWNER_NOTICE_BATCH_V1", owner, recipient, kind, day,
                               [row["event_id"] for row in pending]])
            batch = {"batch_id": batch_id, "kind": kind, "target_date": day,
                     "audience": AUDIENCE, "owner_binding_sha256": owner, "recipient_binding_sha256": recipient,
                     "basis": basis, "notices": pending}
            self.db.execute("""
                INSERT INTO new_a_owner_notice_batches
                    (batch_id, owner, recipient, kind, target_date, payload_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (batch_id, owner, recipient, kind, day, encode(batch), UNKNOWN))
            self.db.executemany("INSERT INTO new_a_owner_notice_members VALUES (?, ?, ?)", [
                (owner, row["event_id"], batch_id) for row in pending
            ])
            return "claimed", batch

    def confirm(self, recipient, batch, receipt):
        _require(_confirmed(receipt, batch, recipient), "transport receipt is not exact")
        stored_receipt = encode({key: receipt[key] for key in (
            "message_id", "batch_id", "recipient_binding_sha256", "delivery_sha256")})
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            state = self.db.execute("""
                SELECT recipient, payload_json, status, receipt_json
                FROM new_a_owner_notice_batches WHERE batch_id=?
            """, (batch["batch_id"],)).fetchone()
            _require(state is not None and state[0:2] == (recipient, encode(batch)),
                     "saved claim is inconsistent")
            if state[2:] == (SENT, stored_receipt):
                return
            _require(state[2] == UNKNOWN, "saved claim is no longer pending reconciliation")
            self.db.execute("""
                UPDATE new_a_owner_notice_batches SET status=?, receipt_json=? WHERE batch_id=?
            """, (SENT, stored_receipt, batch["batch_id"]))


def dispatch(outbox, plan, *, kind, owner, recipient, read_recipient, read_source,
             send, now=_clock):
    """Send at most one claimed batch. All callbacks are supplied by a trusted host."""
    plan = json.loads(encode(plan))
    target, notices = _validate_plan(plan, kind)
    if not notices:
        return {"status": "nothing_to_send", "count": 0}
    _assert_window(kind, target, now())
    _verify_recipient(read_recipient(), owner, recipient, now())
    _verify_source(read_source(), plan, owner, now())
    outcome, batch = outbox.claim(owner, recipient, kind, target, plan["basis"], notices)
    if batch is None:
        return {"status": outcome, "count": 0}

    # The durable claim precedes any transport. If a proof changes after the
    # claim or the transport outcome is ambiguous, preserve it for lookup only.
    _assert_window(kind, target, now())
    _verify_recipient(read_recipient(), owner, recipient, now())
    _verify_source(read_source(), plan, owner, now())
    try:
        receipt = send(recipient, json.loads(encode(batch)))
    except Exception:
        return {"status": "reconciliation_required", "count": 0}
    if not _confirmed(receipt, batch, recipient):
        return {"status": "reconciliation_required", "count": 0}
    outbox.confirm(recipient, batch, receipt)
    return {"status": "sent", "count": len(batch["notices"])}


def reconcile(outbox, *, kind, target, owner, recipient, read_recipient, lookup, now=_clock):
    """Use the exact stored claim with a read-only lookup; never call a sender."""
    _require(kind in (HOLDING, MORNING), "invalid notice kind")
    _day(target)
    _verify_recipient(read_recipient(), owner, recipient, now())
    batch = outbox.unknown(owner, kind, target)
    if batch is None:
        return {"status": "nothing_to_reconcile", "count": 0}
    _require(batch.get("owner_binding_sha256") == owner and
             batch.get("recipient_binding_sha256") == recipient,
             "stored notice claim belongs to a different destination")
    try:
        receipt = lookup(recipient, json.loads(encode(batch)))
    except Exception:
        return {"status": "reconciliation_required", "count": 0}
    if not _confirmed(receipt, batch, recipient):
        return {"status": "reconciliation_required", "count": 0}
    outbox.confirm(recipient, batch, receipt)
    return {"status": "reconciled", "count": len(batch["notices"])}
