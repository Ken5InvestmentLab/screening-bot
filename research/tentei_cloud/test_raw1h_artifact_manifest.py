import tempfile, unittest
from pathlib import Path
import pandas as pd
from raw1h_artifact_manifest import build_manifest

class TestRaw1HManifest(unittest.TestCase):
    def row(self,i):
        return {"symbol":f"{1000+i}.T","timestamp":"2025-01-06 09:00:00+09:00","open":1,"high":2,"low":1,"close":2,"volume":100}
    def test_complete_eight_shards_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(8): pd.DataFrame([self.row(i)]).to_csv(root/f"ohlcv_1h_shard_{i}.csv",index=False)
            m=build_manifest(root)
            self.assertEqual(m["status"],"PASS"); self.assertEqual(m["shard_count"],8); self.assertEqual(m["total_rows"],8)
            self.assertFalse(m["outcome_informed"]); self.assertFalse(m["performance_opened"])
    def test_missing_shard_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(7): pd.DataFrame([self.row(i)]).to_csv(root/f"ohlcv_1h_shard_{i}.csv",index=False)
            with self.assertRaises(RuntimeError): build_manifest(root)
    def test_duplicate_shard_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"a").mkdir(); (root/"b").mkdir()
            for i in range(8): pd.DataFrame([self.row(i)]).to_csv(root/"a"/f"ohlcv_1h_shard_{i}.csv",index=False)
            pd.DataFrame([self.row(0)]).to_csv(root/"b"/"ohlcv_1h_shard_0.csv",index=False)
            with self.assertRaises(RuntimeError): build_manifest(root)
if __name__=='__main__': unittest.main()
