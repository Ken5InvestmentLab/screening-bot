"""Local SQLite and synthetic adapters only; no actual notification endpoints."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest

from weak_early_beta.new_a.files import digest
from weak_early_beta.new_a.planned_notice_delivery import (
    AUDIENCE, HOLDING, MORNING, NoticeOutbox, dispatch, reconcile,
)


class OwnerNoticeDeliveryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "owner-notice.sqlite"
        self.outbox = NoticeOutbox(self.path)
        self.addCleanup(self.outbox.close)
        self.owner = "1" * 64
        self.recipient = "2" * 64
        self.day = "2026-11-25"
        self.clock = datetime.fromisoformat(self.day + "T17:15:00+09:00")
        self.plan = self.make_plan(HOLDING)

    def make_plan(self, kind):
        basis = {
            "dataset_id": "a-" + "a" * 24, "revision": 4, "preferences_revision": 2,
            "manifest_sha256": "3" * 64, "source_version": "4" * 64, "snapshot_sha256": "5" * 64,
        }
        notice = {
            "event_id": "a" * 64 if kind == HOLDING else "b" * 64, "kind": kind,
            "symbol": "123A", "candidate_date": "2026-11-16",
            "simulated_entry_date": self.day, "execution_status": "SIMULATED_NOT_ACTUAL_TRADES",
            "title": "監視から仮想保有に移行",
            "description": "保存した条件による仮想保有です。実際の取引は行われていません。",
        }
        if kind == MORNING:
            basis["calendar_sha256"] = "6" * 64
            notice.update(
                simulated_entry_date="2026-11-18", scheduled_evaluation_date=self.day,
                evaluation_endpoint="d5_open", evaluation_timing="OPEN",
                evaluation_price_status="NOT_YET_OBSERVED",
                title="確定日の朝8時（日本時間）",
                description="今日は、設定した確定日です。その日の価格はまだ確定していません。",
            )
        return {"status": "planned", "target_date": self.day, "basis": basis, "notices": [notice]}

    def recipient_proof(self):
        return {
            "schema": "NEW_A_OWNER_NOTICE_RECIPIENT_V1", "audience": AUDIENCE,
            "owner_binding_sha256": self.owner, "recipient_binding_sha256": self.recipient,
            "enabled": True, "owner_verified": True, "fresh_paid_role": True,
            "observed_at": self.clock.isoformat(),
            "expires_at": (self.clock + timedelta(minutes=1)).isoformat(),
        }

    def source_proof(self):
        return {
            "schema": "NEW_A_OWNER_NOTICE_SOURCE_V1", "owner_binding_sha256": self.owner,
            "current": True, "basis": self.plan["basis"], "plan_sha256": digest(self.plan),
            "observed_at": self.clock.isoformat(),
        }

    def receipt(self, recipient, batch):
        return {
            "confirmed": True, "batch_id": batch["batch_id"], "delivery_sha256": digest(batch),
            "recipient_binding_sha256": recipient, "message_id": "1000000000000000001",
        }

    def dispatch(self, send, *, outbox=None, **overrides):
        options = dict(kind=self.plan["notices"][0]["kind"], owner=self.owner,
                       recipient=self.recipient, read_recipient=self.recipient_proof,
                       read_source=self.source_proof, send=send, now=lambda: self.clock)
        return dispatch(outbox or self.outbox, self.plan, **{**options, **overrides})

    def reconcile(self, lookup, **overrides):
        options = dict(kind=self.plan["notices"][0]["kind"], target=self.day, owner=self.owner,
                       recipient=self.recipient, read_recipient=self.recipient_proof,
                       lookup=lookup, now=lambda: self.clock)
        return reconcile(self.outbox, **{**options, **overrides})

    def count_claims(self):
        return self.outbox.db.execute("SELECT count(*) FROM new_a_owner_notice_batches").fetchone()[0]

    def cannot_send(self, *_):
        self.fail("must not call transport")

    def test_claim_precedes_send_and_completed_event_is_deduplicated_across_reopen(self):
        def send(recipient, batch):
            self.assertEqual(self.outbox.unknown(self.owner, HOLDING, self.day), batch)
            return self.receipt(recipient, batch)

        self.assertEqual(self.dispatch(send), {"status": "sent", "count": 1})
        reopened = NoticeOutbox(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(self.dispatch(self.cannot_send, outbox=reopened)["status"], "nothing_to_send")
        self.assertEqual(self.count_claims(), 1)

    def test_morning_uses_08_jst_and_can_never_send_a_confirmed_price_claim(self):
        self.plan = self.make_plan(MORNING)
        with self.assertRaisesRegex(ValueError, "outside the 08:00 JST"):
            self.dispatch(self.cannot_send)
        self.clock = datetime.fromisoformat(self.day + "T08:00:00+09:00")
        self.plan["notices"][0]["evaluation_price_status"] = "CONFIRMED"
        with self.assertRaisesRegex(ValueError, "cannot claim an evaluated price"):
            self.dispatch(self.cannot_send)
        self.assertEqual(self.count_claims(), 0)
        self.plan = self.make_plan(MORNING)
        self.assertEqual(self.dispatch(self.receipt)["status"], "sent")

    def test_owner_destination_and_fresh_source_are_required_before_claim(self):
        for change in [{"fresh_paid_role": False}, {"recipient_binding_sha256": "a" * 64},
                       {"owner_binding_sha256": "b" * 64}, {"audience": "ALL"}]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "owner-only"):
                self.dispatch(self.cannot_send, read_recipient=lambda: {**self.recipient_proof(), **change})
        with self.assertRaisesRegex(ValueError, "source or saved owner revision"):
            self.dispatch(self.cannot_send, read_source=lambda: {**self.source_proof(), "plan_sha256": "d" * 64})
        with self.assertRaisesRegex(ValueError, "readback is stale"):
            self.dispatch(self.cannot_send, read_source=lambda: {
                **self.source_proof(), "observed_at": (self.clock - timedelta(minutes=3)).isoformat(),
            })
        self.assertEqual(self.count_claims(), 0)

    def test_unknown_result_is_only_reconciled_by_exact_lookup_even_after_target_date(self):
        def send_then_timeout(*_):
            raise TimeoutError("receipt not received")

        self.assertEqual(self.dispatch(send_then_timeout)["status"], "reconciliation_required")
        self.assertEqual(self.dispatch(self.cannot_send)["status"], "reconciliation_required")
        self.clock += timedelta(days=1)
        self.assertEqual(self.reconcile(lambda *_: None)["status"], "reconciliation_required")
        self.assertEqual(self.reconcile(lambda r, b: {**self.receipt(r, b), "delivery_sha256": "f" * 64})["status"],
                         "reconciliation_required")
        self.assertEqual(self.reconcile(self.receipt), {"status": "reconciled", "count": 1})
        self.assertEqual(self.reconcile(self.cannot_send)["status"], "nothing_to_reconcile")

    def test_each_kind_uses_a_separate_claim_scope(self):
        self.assertEqual(self.dispatch(lambda *_: None)["status"], "reconciliation_required")
        self.plan = self.make_plan(MORNING)
        self.clock = datetime.fromisoformat(self.day + "T08:00:00+09:00")
        self.assertEqual(self.dispatch(self.receipt)["status"], "sent")
        self.assertEqual(self.count_claims(), 2)

    def test_revoked_after_claim_never_calls_transport(self):
        reads = iter([True, False])
        with self.assertRaisesRegex(ValueError, "recipient authorization is unverified"):
            self.dispatch(self.cannot_send, read_recipient=lambda: {
                **self.recipient_proof(), "fresh_paid_role": next(reads),
            })
        self.assertEqual(self.count_claims(), 1)
        self.assertEqual(self.dispatch(self.cannot_send)["status"], "reconciliation_required")

    def test_simultaneous_independent_workers_cannot_post_the_same_event(self):
        entered, release = Event(), Event()
        def send(recipient, batch):
            entered.set()
            self.assertTrue(release.wait(3))
            return self.receipt(recipient, batch)

        def first():
            connection = NoticeOutbox(self.path)
            try:
                return self.dispatch(send, outbox=connection)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as scheduler:
            result = scheduler.submit(first)
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.dispatch(self.cannot_send)["status"], "reconciliation_required")
            finally:
                release.set()
            self.assertEqual(result.result()["status"], "sent")
        self.assertEqual(self.count_claims(), 1)

    def test_recipient_rotation_cannot_replay_a_sent_event_or_look_up_the_wrong_destination(self):
        self.assertEqual(self.dispatch(lambda *_: None)["status"], "reconciliation_required")
        original = self.recipient
        self.recipient = "8" * 64
        with self.assertRaisesRegex(ValueError, "different destination"):
            self.reconcile(self.cannot_send)
        self.assertEqual(self.dispatch(self.cannot_send)["status"], "reconciliation_required")
        self.recipient = original
        self.assertEqual(self.reconcile(self.receipt)["status"], "reconciled")
        self.recipient = "8" * 64
        self.assertEqual(self.dispatch(self.cannot_send)["status"], "nothing_to_send")
        self.assertEqual(self.count_claims(), 1)

    def test_basis_cannot_carry_unapproved_fields_to_the_transport(self):
        self.plan["basis"]["unapproved_field"] = "withheld"
        with self.assertRaisesRegex(ValueError, "published source"):
            self.dispatch(self.cannot_send)
        self.assertEqual(self.count_claims(), 0)


if __name__ == "__main__":
    unittest.main()
