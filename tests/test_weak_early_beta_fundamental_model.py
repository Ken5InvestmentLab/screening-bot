import json
import re
import tempfile
import unittest
from pathlib import Path

from weak_early_beta.fundamental import (
    FUNDAMENTAL_MODEL,
    FUNDAMENTAL_REASONING_EFFORT,
    prepare_claim,
)


class CloudFundamentalModelTests(unittest.TestCase):
    def test_new_forward_claim_aligns_with_runner_and_preserves_legacy_completed_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = root / "queue.json"
            state_path = root / "state.json"
            claim_path = root / "claim.json"
            old_id = "weak-early-beta:2026-09-01:1234"
            legacy = {"delivery": "html", "report": {"model": "gpt-5.6-luna", "fields": []}}
            state_path.write_text(json.dumps({"completed": {old_id: legacy}, "claims": {}}), encoding="utf-8")
            queue.write_text(json.dumps([
                {"signal_date": "2026-09-01", "symbol": "1234", "company_name": "Fixture"},
                {"signal_date": "2026-10-09", "symbol": "1234", "company_name": "Fixture"},
            ]), encoding="utf-8")

            claim = prepare_claim(queue, root / "missing-ledger.csv", state_path, claim_path,
                                  analysis_cutoff="2026-10-09T17:00:00+09:00")
            self.assertEqual(claim["claimedCount"], 1)
            self.assertEqual(claim["alerts"][0]["signalDate"], "2026-10-09")
            self.assertEqual(claim["rules"]["model"], "gpt-6.1-sol")
            self.assertEqual(claim["rules"]["reasoningEffort"], "xhigh")
            self.assertNotIn("astra", claim["rules"]["model"])
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["completed"][old_id], legacy)

            runner = Path(__file__).resolve().parents[1] / "scripts/windows/weak-early-beta-fundamental-runner.mjs"
            source = runner.read_text(encoding="utf-8")
            model = re.search(r"const FUNDAMENTAL_MODEL = '([^']+)';", source).group(1)
            effort = re.search(r"const FUNDAMENTAL_REASONING_EFFORT = '([^']+)';", source).group(1)
            self.assertEqual(model, FUNDAMENTAL_MODEL)
            self.assertEqual(effort, FUNDAMENTAL_REASONING_EFFORT)
            self.assertEqual(json.loads(claim_path.read_text(encoding="utf-8"))["rules"]["model"], model)


if __name__ == "__main__":
    unittest.main()
