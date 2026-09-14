from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from prospective_shadow_resolution_receipt import (
    build_resolution_receipt,
    verify_resolution_receipt,
    write_immutable_receipt,
)


class ResolutionReceiptTests(unittest.TestCase):
    def _file(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")
        return path

    def _bundle(self, root: Path):
        freeze = {"experiment_id":"EXP","model_freeze_id":"FREEZE"}
        freeze_path = self._file(root/"freeze.json", json.dumps(freeze))
        shadow = self._file(root/"shadow.jsonl", '{"key":"k"}\n')
        daily = self._file(root/"daily.csv", "symbol,date,open,close\n1111.T,2026-09-16,100,101\n")
        daily_manifest = self._file(root/"daily.manifest.json", '{"csv_sha256":"x"}\n')
        sessions = self._file(root/"sessions.csv", "date,session_index\n2026-09-16,0\n")
        sessions_manifest = self._file(root/"sessions.manifest.json", '{"calendar_id":"XTKS"}\n')
        resolved = self._file(root/"resolved.jsonl", '{"status":"RESOLVED"}\n')
        import hashlib
        resolved_sha=hashlib.sha256(resolved.read_bytes()).hexdigest()
        result={
            "resolved_written":True,
            "decision":"VERIFIED_RESOLUTION_WRITE_COMPLETE",
            "output_sha256_after":resolved_sha,
        }
        return freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result

    def _build(self, root: Path):
        freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=self._bundle(root)
        receipt=build_resolution_receipt(
            freeze_manifest=freeze,
            freeze_manifest_path=freeze_path,
            shadow_path=shadow,
            daily_path=daily,
            daily_manifest_path=daily_manifest,
            sessions_csv_path=sessions,
            sessions_manifest_path=sessions_manifest,
            resolved_path=resolved,
            resolve_result=result,
            created_at="2026-09-25T18:05:00+09:00",
        )
        return receipt,(freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result)

    def test_valid_receipt_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=bundle
            out=verify_resolution_receipt(
                receipt,freeze_manifest=freeze,freeze_manifest_path=freeze_path,shadow_path=shadow,
                daily_path=daily,daily_manifest_path=daily_manifest,sessions_csv_path=sessions,
                sessions_manifest_path=sessions_manifest,resolved_path=resolved,resolve_result=result,
            )
            self.assertTrue(out["valid"])

    def test_daily_change_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=bundle
            daily.write_text(daily.read_text()+"\n",encoding="utf-8")
            out=verify_resolution_receipt(
                receipt,freeze_manifest=freeze,freeze_manifest_path=freeze_path,shadow_path=shadow,
                daily_path=daily,daily_manifest_path=daily_manifest,sessions_csv_path=sessions,
                sessions_manifest_path=sessions_manifest,resolved_path=resolved,resolve_result=result,
            )
            self.assertFalse(out["valid"])
            self.assertIn("daily_input_sha256_mismatch",out["errors"])

    def test_resolved_change_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=bundle
            resolved.write_text('{"status":"RESOLVED","x":1}\n',encoding="utf-8")
            out=verify_resolution_receipt(
                receipt,freeze_manifest=freeze,freeze_manifest_path=freeze_path,shadow_path=shadow,
                daily_path=daily,daily_manifest_path=daily_manifest,sessions_csv_path=sessions,
                sessions_manifest_path=sessions_manifest,resolved_path=resolved,resolve_result=result,
            )
            self.assertFalse(out["valid"])
            self.assertIn("resolved_output_sha256_mismatch",out["errors"])

    def test_receipt_self_hash_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            receipt["source_note"]="tampered"
            freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=bundle
            out=verify_resolution_receipt(
                receipt,freeze_manifest=freeze,freeze_manifest_path=freeze_path,shadow_path=shadow,
                daily_path=daily,daily_manifest_path=daily_manifest,sessions_csv_path=sessions,
                sessions_manifest_path=sessions_manifest,resolved_path=resolved,resolve_result=result,
            )
            self.assertFalse(out["valid"])
            self.assertIn("receipt_sha256_mismatch",out["errors"])

    def test_receipt_file_is_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,_=self._build(root)
            path=root/"receipt.json"
            write_immutable_receipt(path,receipt)
            snapshot=path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_immutable_receipt(path,receipt)
            self.assertEqual(snapshot,path.read_bytes())

    def test_unsuccessful_resolution_cannot_build_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=self._bundle(root)
            result["resolved_written"]=False
            with self.assertRaises(ValueError):
                build_resolution_receipt(
                    freeze_manifest=freeze,freeze_manifest_path=freeze_path,shadow_path=shadow,
                    daily_path=daily,daily_manifest_path=daily_manifest,sessions_csv_path=sessions,
                    sessions_manifest_path=sessions_manifest,resolved_path=resolved,resolve_result=result,
                    created_at="2026-09-25T18:05:00+09:00",
                )


if __name__ == "__main__":
    unittest.main()
