import copy
import datetime
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import closing

from weak_early_beta import notify
from weak_early_beta.new_a import opening_discord as opening
from weak_early_beta.new_a.files import digest


class OpeningDiscord(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(self.directory) / "opening.sqlite"
        self.outbox = self.enterContext(closing(opening.OpeningDiscordOutbox(self.path)))
        self.target = "2026-06-08"
        self.now = datetime.datetime.fromisoformat(self.target + "T09:05:00+09:00")
        self.webhook = "123456789012345678"
        self.candidates = {
            "schema": opening.CANDIDATE_SCHEMA, "audience": opening.CANDIDATE_AUDIENCE,
            "ordinary_publication_verified": True,
            "source_date": "2026-06-05", "target_date": self.target,
            "snapshot_sha256": "1" * 64, "publication_sha256": "2" * 64, "calendar_sha256": "3" * 64,
            "candidates": [{"symbol": symbol, "security_id": "XTKS:" + symbol} for symbol in ("1111", "417A")],
        }
        self.observation = {
            "schema": opening.OBSERVATION_SCHEMA, "target_date": self.target, "rows": [self.trade("1111")],
        }

    def trade(self, symbol, **changes):
        return {
            "status": "FIRST_REGULAR_TRADE_VERIFIED", "symbol": symbol, "security_id": "XTKS:" + symbol,
            "exchange": "XTKS", "market": "REGULAR", "session": "MORNING", "price_basis": "ACTUAL_JPY",
            "first_trade_evidence": "VENUE_OPEN_MARKER", "source_id": "approved-provider",
            "source_sha256": "4" * 64, "trade_size": 200, "actual_price_yen": 751.5,
            "trade_at": self.target + "T09:03:05.125+09:00",
            "observed_at": self.target + "T09:03:15.200+09:00", **changes,
        }

    def scope(self, observation_sha, candidate_sha, **changes):
        return {
            "schema": opening.SHARING_SCHEMA, "shared_market_data": True,
            "candidate_receipt_sha256": candidate_sha, "observation_sha256": observation_sha,
            "authority_receipt_sha256": "5" * 64, "provider_id": "approved-provider",
            "source_ids": ["approved-provider"],
            "guild_id": notify.GUILD_ID, "channel_id": notify.CHANNEL_ID, "webhook_id": self.webhook,
            "observed_at": self.target + "T09:04:00+09:00", "not_after": self.target + "T09:10:00+09:00",
            **changes,
        }

    def claim(self, outbox=None, *, scope=None):
        return (outbox or self.outbox).claim(
            self.observation, read_candidates=lambda date: self.candidates,
            read_sharing_scope=scope or self.scope, now=self.now,
        )

    def message(self, batch, **changes):
        body = copy.deepcopy(batch["payload"])
        return {
            "id": "123456789012345679", "channel_id": notify.CHANNEL_ID, "webhook_id": self.webhook,
            "content": body["content"], "embeds": body["embeds"], "attachments": [], **changes,
        }

    def test_payload_contains_only_actual_public_price_and_pending_status(self):
        self.observation["rows"].append(self.trade("9999", actual_price_yen=12345))
        self.observation["rows"][0].update({"owner_initial_cash_yen": 9_876_543, "status_details": "FILLED"})
        claim = self.claim()
        self.assertEqual(claim["status"], "claimed")
        body = claim["batch"]["payload"]
        encoded = json.dumps(body, ensure_ascii=False)
        self.assertIn("1111 ｜ 09:03:05.125 JST ｜ 751.5円", encoded)
        self.assertIn("仮想保有判定待ち", encoded)
        for private in ("FILLED", "9876543", "12345", "9999", "approved-provider"):
            self.assertNotIn(private, encoded)
        self.assertEqual(body["allowed_mentions"], {"parse": []})
        self.assertEqual(self.outbox.reconcile(self.target, [self.message(claim["batch"])])["count"], 1)

    def test_no_notice_for_unverified_or_non_candidate(self):
        self.observation["rows"] = [
            self.trade("1111", status="AWAITING_FIRST_TRADE"),
            self.trade("9999"),
        ]
        self.assertEqual(self.claim(), {"status": "nothing_to_send"})

    def test_untrusted_venue_indicative_afternoon_future_wrong_security_and_basis(self):
        for changes in [
            {"market": "ODD_LOT"}, {"exchange": "XNGO"}, {"session": "AFTERNOON"},
            {"first_trade_evidence": "INDICATIVE"}, {"trade_size": 0}, {"price_basis": "ADJUSTED"},
            {"security_id": "XTKS:OTHER"}, {"source_id": "other-provider"}, {"trade_at": self.target + "T12:30:00+09:00"},
            {"observed_at": self.target + "T09:06:00+09:00"}, {"actual_price_yen": True},
        ]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "verified first|nominal"):
                self.observation["rows"] = [self.trade("1111", **changes)]
                self.claim()
        self.assertEqual(self.outbox.reconcile(self.target, []), {"status": "nothing_to_reconcile"})

    def test_scope_must_bind_both_inputs_and_existing_discord_channel(self):
        for changes in [
            {"observation_sha256": "6" * 64}, {"candidate_receipt_sha256": "7" * 64},
            {"channel_id": "123456789012345679"}, {"guild_id": "123456789012345679"},
            {"not_after": self.target + "T09:04:59+09:00"}, {"shared_market_data": False},
            {"authority_receipt_sha256": None}, {"source_ids": []},
        ]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "sharing"):
                self.claim(scope=lambda obs, candidate: self.scope(obs, candidate, **changes))
        self.candidates["ordinary_publication_verified"] = False
        with self.assertRaisesRegex(ValueError, "ordinary evening"):
            self.claim()

    def test_revalidation_precedes_any_future_host_transport(self):
        batch = self.claim()["batch"]

        def verify(**changes):
            return self.outbox.verify_claim(batch, self.observation, read_candidates=lambda date: self.candidates,
                                            read_sharing_scope=self.scope, **changes)

        self.assertEqual(verify(now=self.now), batch["payload"])
        newly_observed = copy.deepcopy(self.observation["rows"])
        newly_observed.append(self.trade("417A"))
        self.observation["rows"] = newly_observed
        with self.assertRaisesRegex(ValueError, "proofs or payload changed"):
            verify(now=self.now)
        self.observation["rows"].pop()
        with self.assertRaisesRegex(ValueError, "expired"):
            verify(now=self.now + datetime.timedelta(minutes=5))
        self.assertEqual(self.claim(), {"status": "reconciliation_required"})

    def test_cross_poll_duplicate_and_correction_do_not_resend(self):
        first = self.claim()["batch"]
        self.outbox.reconcile(self.target, [self.message(first)])
        self.observation["rows"][0]["observed_at"] = self.target + "T09:04:00+09:00"
        self.observation["rows"][0]["trade_at"] = self.target + "T00:03:05.125Z"
        self.observation["rows"][0]["source_sha256"] = "f" * 64
        self.assertEqual(self.claim(), {"status": "nothing_to_send"})
        self.observation["rows"].append(self.trade("417A", actual_price_yen=833))
        second = self.claim()["batch"]
        self.assertEqual([item["symbol"] for item in second["trades"]], ["417A"])
        self.outbox.reconcile(self.target, [self.message(second)])
        self.observation["rows"][0]["actual_price_yen"] += 1
        with self.assertRaisesRegex(ValueError, "changed after its notification"):
            self.claim()

    def test_uncertain_send_is_durable_and_requires_exact_unique_readback(self):
        first = self.claim()["batch"]
        self.observation["rows"].append(self.trade("417A"))
        with closing(opening.OpeningDiscordOutbox(self.path)) as reopened:
            self.assertEqual(self.claim(reopened), {"status": "reconciliation_required"})
            measured = self.message(first)
            edited = self.message(first)
            edited["embeds"][0]["description"] += "改変"
            forged = self.message(first, webhook_id="123456789012345679")
            for messages in ([], [edited, forged], [measured, measured]):
                self.assertEqual(reopened.reconcile(self.target, messages), {"status": "reconciliation_required"})
                self.assertEqual(self.claim(reopened), {"status": "reconciliation_required"})
            result = reopened.reconcile(self.target, [edited, forged, measured])
            self.assertEqual(result, {"status": "confirmed", "count": 1, "message_id": measured["id"]})
            self.assertEqual(self.claim(reopened)["batch"]["trades"][0]["symbol"], "417A")

    def test_replayed_day_and_duplication_are_rejected(self):
        self.observation["target_date"] = "2026-06-05"
        with self.assertRaisesRegex(ValueError, "current market"):
            self.claim()
        self.observation["target_date"] = self.target
        self.observation["rows"].append(self.trade("1111"))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.claim()
