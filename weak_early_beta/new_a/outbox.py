"""Private logical notification rows and atomic Discord batch receipts."""

import json
import sqlite3
from pathlib import Path

from .files import encode, read


ATTEMPTED = "ATTEMPTED_UNCONFIRMED"


def eligible(snapshot):
    delayed = snapshot["observation_kind"] == "DELAYED_SCHEDULED_OBSERVATION"
    return [
        event for event in snapshot["events"]
        if event["kind"] == "WATCH_STARTED" and event["session"] == snapshot["as_of"]
        and (event.get("is_new_live_signal") is True
             or (delayed and event.get("is_delayed_scheduled_signal") is True))
    ]


class Outbox:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(self.path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS new_a_delivery(
                event_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
                status TEXT NOT NULL, receipt_json TEXT
            );
            CREATE TABLE IF NOT EXISTS new_a_discord_batch(
                batch_id TEXT PRIMARY KEY, signal_date TEXT NOT NULL,
                payload_json TEXT NOT NULL, status TEXT NOT NULL, receipt_json TEXT
            );
        """)

    def stage(self, snapshot, publication_receipt, *, existing_notifications_enabled, summary=None):
        if not existing_notifications_enabled:
            return []
        from .operational_admission import publication_gate_verified
        if publication_receipt.get("operational_gate_continuity_verified") is True:
            from .operational_admission import action_context
            action_context(
                self.path.parent.parents[2], date=snapshot.get("as_of"),
                run=read(self.path.parent / "latest-run.json"), snapshot=snapshot,
                publication=publication_receipt, required=True,
            )
        delayed = snapshot.get("observation_kind") == "DELAYED_SCHEDULED_OBSERVATION"
        if delayed:
            from .delayed_recovery import delivery_context
            delivery_context(self.path.parent.parents[2], snapshot, publication_receipt)
        if (snapshot.get("observation_kind") != "LIVE_OBSERVATION" and not delayed
                or publication_receipt.get("published") is not True):
            return []
        if (publication_receipt.get("snapshot_sha256") != snapshot.get("payload_sha256")
                or not publication_gate_verified(publication_receipt)):
            raise ValueError("verified publication required")
        payloads = []
        for event in eligible(snapshot):
            payload = {
                "event_id": event["event_id"], "symbol": event["symbol"],
                "signal_date": event["session"], "strategy": "A_BASE",
                "signal_phase": "WATCH_STARTED", "display_label": "仕込み候補・監視開始",
                "execution_status": "NOT_EXECUTED",
            }
            if delayed:
                payload.update(
                    observation_kind=snapshot["observation_kind"],
                    observed_at=snapshot["observed_at"], delayed_recovery=snapshot["delayed_recovery"],
                )
            payloads.append(payload)
        if summary is not None:
            payloads.append(summary)
        staged = []
        with self.db:
            for payload in payloads:
                inserted = self.db.execute(
                    "INSERT OR IGNORE INTO new_a_delivery VALUES (?, ?, 'PENDING', NULL)",
                    (payload["event_id"], encode(payload)),
                ).rowcount
                if inserted:
                    staged.append(payload)
        return staged

    def day_rows(self, date):
        rows = self.db.execute(
            """SELECT event_id, payload_json, status FROM new_a_delivery
               WHERE json_extract(payload_json, '$.signal_date') = ? ORDER BY event_id""",
            (date,),
        )
        return [(event_id, json.loads(raw), status) for event_id, raw, status in rows]

    def unconfirmed_batch(self, date):
        rows = self.db.execute(
            "SELECT payload_json FROM new_a_discord_batch WHERE signal_date = ? AND status = ?",
            (date, ATTEMPTED),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("notification outcome unconfirmed; reconcile existing receipts before retry")
        return json.loads(rows[0][0])

    def claim_batch(self, date, build):
        with self.db:
            # Read the pending set only after serializing concurrent writers.
            self.db.execute("BEGIN IMMEDIATE")
            rows = self.day_rows(date)
            if any(status == ATTEMPTED for _, _, status in rows):
                raise ValueError("notification outcome unconfirmed; reconcile before retry")
            if not any(status == "PENDING" for _, _, status in rows):
                return None
            batch = build(rows)
            self.db.execute(
                "INSERT INTO new_a_discord_batch VALUES (?, ?, ?, ?, NULL)",
                (batch["batch_id"], date, encode(batch), ATTEMPTED),
            )
            self.db.executemany(
                "UPDATE new_a_delivery SET status = ? WHERE event_id = ? AND status = 'PENDING'",
                [(ATTEMPTED, event_id) for event_id in batch["event_ids"]],
            )
        return batch

    def confirm_batch(self, batch, message_id):
        receipt = {"confirmed": True, "message_id": message_id, "batch_id": batch["batch_id"]}
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            stored = self.db.execute(
                "SELECT payload_json, status, receipt_json FROM new_a_discord_batch WHERE batch_id = ?",
                (batch["batch_id"],),
            ).fetchone()
            if stored is None or stored[0] != encode(batch):
                raise ValueError("notification batch claim differs")
            if stored[1] == "SENT" and json.loads(stored[2]) == receipt:
                return
            if stored[1] != ATTEMPTED:
                raise ValueError("notification batch receipt differs")
            updated = self.db.executemany(
                """UPDATE new_a_delivery SET status = 'SENT', receipt_json = ?
                   WHERE event_id = ? AND status = ?""",
                [(encode(receipt), event_id, ATTEMPTED) for event_id in batch["event_ids"]],
            ).rowcount
            if updated != len(batch["event_ids"]):
                raise ValueError("notification batch members differ")
            self.db.execute(
                "UPDATE new_a_discord_batch SET status = 'SENT', receipt_json = ? WHERE batch_id = ?",
                (encode(receipt), batch["batch_id"]),
            )

    def close(self):
        self.db.close()
