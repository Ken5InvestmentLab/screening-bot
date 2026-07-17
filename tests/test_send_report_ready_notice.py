import unittest
from datetime import datetime, timedelta, timezone

from send_report_ready_notice import (
    NOTICE_FIELD_NAME,
    NOTICE_FIELD_VALUE,
    NOTICE_FOOTER,
    NOTICE_TITLE,
    build_notice_embed,
    send_report_ready_notice,
)


NOW = datetime(2026, 7, 17, 11, 43, 37, tzinfo=timezone.utc)
WEBHOOK_URL = "https://discord.com/api/webhooks/123/token"
CHANNEL_MESSAGES_URL = "https://discord.com/api/v10/channels/456/messages?limit=50"


def notice_message(message_id, timestamp, webhook_id="123"):
    return {
        "id": str(message_id),
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "webhook_id": webhook_id,
        "embeds": [build_notice_embed(timestamp)],
    }


class FakeDiscord:
    def __init__(self, message_reads):
        self.message_reads = list(message_reads)
        self.calls = []

    def __call__(self, url, method, headers, payload):
        self.calls.append((url, method, headers, payload))
        if method == "GET" and url == WEBHOOK_URL:
            return {"id": "123", "channel_id": "456"}
        if method == "GET" and url == CHANNEL_MESSAGES_URL:
            return self.message_reads.pop(0)
        if method == "POST":
            return notice_message("new", NOW)
        if method == "DELETE":
            return None
        raise AssertionError(f"unexpected request: {method} {url}")


class ReportReadyNoticeTests(unittest.TestCase):
    def test_embed_copy_matches_existing_notice(self):
        embed = build_notice_embed(NOW)
        self.assertEqual(embed["title"], NOTICE_TITLE)
        self.assertEqual(embed["fields"][0]["name"], NOTICE_FIELD_NAME)
        self.assertEqual(embed["fields"][0]["value"], NOTICE_FIELD_VALUE)
        self.assertEqual(embed["footer"]["text"], NOTICE_FOOTER)

    def test_recent_matching_notice_skips_post(self):
        fake = FakeDiscord([[notice_message("old", NOW - timedelta(seconds=30))]])

        result = send_report_ready_notice(
            WEBHOOK_URL,
            "bot-token",
            now=NOW,
            request_json=fake,
        )

        self.assertEqual(result, "skipped_duplicate")
        self.assertFalse(any(call[1] == "POST" for call in fake.calls))

    def test_notice_older_than_window_does_not_block_post(self):
        fake = FakeDiscord(
            [
                [notice_message("old", NOW - timedelta(minutes=16))],
                [notice_message("new", NOW)],
            ]
        )

        result = send_report_ready_notice(
            WEBHOOK_URL,
            "bot-token",
            now=NOW,
            request_json=fake,
        )

        self.assertEqual(result, "sent")
        posts = [call for call in fake.calls if call[1] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertIn("wait=true", posts[0][0])

    def test_post_send_race_removes_this_runs_duplicate(self):
        earlier = notice_message("earlier", NOW - timedelta(seconds=1), webhook_id="other")
        current = notice_message("new", NOW + timedelta(seconds=1))
        fake = FakeDiscord([[], [earlier, current]])

        result = send_report_ready_notice(
            WEBHOOK_URL,
            "bot-token",
            now=NOW,
            request_json=fake,
        )

        self.assertEqual(result, "removed_duplicate")
        deletes = [call for call in fake.calls if call[1] == "DELETE"]
        self.assertEqual([call[0] for call in deletes], [f"{WEBHOOK_URL}/messages/new"])


if __name__ == "__main__":
    unittest.main()
