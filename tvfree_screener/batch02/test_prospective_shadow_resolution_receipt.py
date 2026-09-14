from __future__ import annotations

import csv
import hashlib
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

    def _schema2_build(self, root: Path):
        freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=self._bundle(root)

        completeness_body = {
            "receipt_type": "PROSPECTIVE_SHADOW_ENDPOINT_COMPLETENESS_RECEIPT",
            "schema_version": 2,
            "decision": "ALLOW_SHADOW_ENDPOINT_RESOLUTION",
            "endpoint_completeness_valid": True,
            "production_authorized": False,
        }
        canonical = (json.dumps(completeness_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        completeness_sha = hashlib.sha256(canonical).hexdigest()
        completeness = dict(completeness_body)
        completeness["receipt_sha256"] = completeness_sha
        completeness_path = root / "completeness.receipt.json"
        completeness_path.write_text(
            json.dumps(completeness, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        result.update({
            "endpoint_completeness_receipt_sha256": completeness_sha,
            "endpoint_completeness_receipt_path": str(completeness_path),
            "daily_endpoint_manifest_sha256": hashlib.sha256(daily_manifest.read_bytes()).hexdigest(),
            "pinned_xtks_calendar_sha256": hashlib.sha256(sessions.read_bytes()).hexdigest(),
            "frozen_selection_ledger_sha256": hashlib.sha256(shadow.read_bytes()).hexdigest(),
            "integrity": {"provenance_chain_enforced": True},
        })
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
        bundle=(freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result)
        return receipt,bundle,completeness_path

    def _verify(self, receipt, bundle):
        freeze,freeze_path,shadow,daily,daily_manifest,sessions,sessions_manifest,resolved,result=bundle
        return verify_resolution_receipt(
            receipt,freeze_manifest=freeze,freeze_manifest_path=freeze_path,shadow_path=shadow,
            daily_path=daily,daily_manifest_path=daily_manifest,sessions_csv_path=sessions,
            sessions_manifest_path=sessions_manifest,resolved_path=resolved,resolve_result=result,
        )

    def test_valid_receipt_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            out=self._verify(receipt,bundle)
            self.assertTrue(out["valid"])

    def test_daily_change_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            daily=bundle[3]
            daily.write_text(daily.read_text()+"\n",encoding="utf-8")
            out=self._verify(receipt,bundle)
            self.assertFalse(out["valid"])
            self.assertIn("daily_input_sha256_mismatch",out["errors"])

    def test_resolved_change_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            resolved=bundle[7]
            resolved.write_text('{"status":"RESOLVED","x":1}\n',encoding="utf-8")
            out=self._verify(receipt,bundle)
            self.assertFalse(out["valid"])
            self.assertIn("resolved_output_sha256_mismatch",out["errors"])

    def test_receipt_self_hash_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle=self._build(root)
            receipt["source_note"]="tampered"
            out=self._verify(receipt,bundle)
            self.assertFalse(out["valid"])
            self.assertIn("receipt_sha256_mismatch",out["errors"])

    def test_schema2_provenance_link_tamper_matrix_fails_closed(self):
        cases = [
            ("shadow", 2, "frozen_selection_ledger_sha256_mismatch"),
            ("daily_manifest", 4, "daily_endpoint_manifest_sha256_mismatch"),
            ("sessions_csv", 5, "pinned_xtks_calendar_sha256_mismatch"),
            ("sessions_manifest", 6, "session_calendar_manifest_sha256_mismatch"),
        ]
        for label,index,expected_error in cases:
            with self.subTest(link=label), tempfile.TemporaryDirectory() as td:
                root=Path(td); receipt,bundle,_=self._schema2_build(root)
                target=bundle[index]
                target.write_text(target.read_text(encoding="utf-8")+"\n",encoding="utf-8")
                out=self._verify(receipt,bundle)
                self.assertFalse(out["valid"])
                self.assertIn(expected_error,out["errors"])

    def test_schema2_completeness_receipt_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle,completeness_path=self._schema2_build(root)
            payload=json.loads(completeness_path.read_text(encoding="utf-8"))
            payload["decision"]="TAMPERED"
            completeness_path.write_text(json.dumps(payload),encoding="utf-8")
            out=self._verify(receipt,bundle)
            self.assertFalse(out["valid"])
            self.assertIn("endpoint_completeness_receipt_invalid",out["errors"])

    def test_schema2_resolve_result_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); receipt,bundle,_=self._schema2_build(root)
            bundle[8]["audit_note"]="tampered"
            out=self._verify(receipt,bundle)
            self.assertFalse(out["valid"])
            self.assertIn("resolve_result_sha256_mismatch",out["errors"])

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
