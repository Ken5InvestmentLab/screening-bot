import os
import unittest
from unittest.mock import patch

from generate_mega_validation_report import fetch_premium_discord_links


DISCORD_URL = (
    "https://discord.com/channels/1479418833352785944/"
    "1501035137817640960/1526446551566913548"
)


class FakeRequest:
    def __init__(self, values):
        self.values = values

    def execute(self):
        outcome = self.values.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeValues:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return FakeRequest(self)


class FakeSpreadsheets:
    def __init__(self, values):
        self._values = values

    def values(self):
        return self._values


class FakeService:
    def __init__(self, outcomes):
        self.values = FakeValues(outcomes)
        self._spreadsheets = FakeSpreadsheets(self.values)

    def spreadsheets(self):
        return self._spreadsheets


def premium_log_response():
    return {
        "values": [
            [
                "event_at",
                "event_type",
                "alert_id",
                "symbol_code",
                "symbol_name",
                "signal_type",
                "title",
                "tradingview_url",
                "disclosure_links",
                "source_urls",
                "reason",
            ],
            [
                "2026-07-14T04:33:38.067Z",
                "POSTED",
                "tv_b5d8d6de7db52d0d999a41f4ed8c745e",
                "7807",
                "幸和製作所",
                "BOTTOM",
                "",
                "",
                "",
                "",
                f"[混在/要確認]({DISCORD_URL})",
            ],
        ]
    }


class PremiumDiscordLinksTest(unittest.TestCase):
    def env(self, attempts="3"):
        return patch.dict(
            os.environ,
            {
                "MEGA_REPORT_PREMIUM_LOG_READ_ATTEMPTS": attempts,
                "PREMIUM_LOG_SPREADSHEET_ID": "premium-sheet",
                "PREMIUM_LOG_SHEET_NAME": "premium_alert_log",
            },
            clear=False,
        )

    def test_retries_transient_sheet_timeout_and_returns_exact_alert_link(self):
        service = FakeService([TimeoutError("read timed out"), premium_log_response()])

        with self.env(), patch("generate_mega_validation_report.time.sleep") as sleep:
            result = fetch_premium_discord_links(service)

        self.assertEqual(len(service.values.calls), 2)
        self.assertEqual(service.values.calls[0]["range"], "'premium_alert_log'!A1:K")
        self.assertEqual(service.values.calls[0]["majorDimension"], "ROWS")
        self.assertEqual(service.values.calls[0]["valueRenderOption"], "UNFORMATTED_VALUE")
        sleep.assert_called_once_with(1)
        self.assertEqual(result["matched_urls"], 1)
        self.assertEqual(
            result["by_alert_id"]["tv_b5d8d6de7db52d0d999a41f4ed8c745e"]["url"],
            DISCORD_URL,
        )

    def test_raises_instead_of_publishing_without_fundamentals_after_retries(self):
        service = FakeService([TimeoutError("one"), TimeoutError("two"), TimeoutError("three")])

        with self.env(), patch("generate_mega_validation_report.time.sleep"):
            with self.assertRaisesRegex(
                RuntimeError,
                "refusing to publish a report without fundamental analysis",
            ):
                fetch_premium_discord_links(service)

        self.assertEqual(len(service.values.calls), 3)


if __name__ == "__main__":
    unittest.main()
