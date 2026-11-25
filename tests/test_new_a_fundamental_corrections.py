"""Reviewed prose amendments preserve frozen data, source links and receipts."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from tests import test_new_a_fundamentals as fixtures
from weak_early_beta.new_a import fundamental_corrections as editorial
from weak_early_beta.new_a.files import atomic_write, digest, file_sha, read
from weak_early_beta.new_a.fundamentals import _bundle, _manifest, _rows


class EditorialCorrectionTests(unittest.TestCase):
    def setUp(self):
        h=self.h=fixtures.NewAFundamentalTests()
        h.setUp();self.addCleanup(h.doCleanups)
        self.identity='3133|2026-11-18|1'
        self.original={'identity':h.day+'|3133','symbol':'3133','signalDate':h.day,
          'analysisCutoff':h.day+'T16:15:00+09:00','auditStatus':'pass',
          'fields':[{'label':label,'text':('様子見：受注は横ばい。' if label=='材料インパクト'
             else '受注は横ばい。潜在株式の最新残高は未確認。' if label=='注意点'
             else '[一次資料](https://example.com/original.pdf)' if label=='開示リンク'
             else '[IR一覧](https://example.com/ir)' if label=='Sources' else '検証用の確認済み本文')}
             for label in editorial.FIELDS]}
        self.corrected=deepcopy(self.original)
        self.corrected['fields'][4]['text']='受注は横ばい。'
        row={**h.row,'identity':self.identity,'analysisCutoff':self.original['analysisCutoff'],'fundamental':self.original}
        manifest,receipt=_manifest(h.base)
        atomic_write(h.base/'presentation-000.json',[row])
        descriptor=manifest['collections']['presentation'][0]
        descriptor.update(sha256=file_sha(h.base/descriptor['name']),bytes=(h.base/descriptor['name']).stat().st_size)
        atomic_write(h.base/'manifest.json',manifest)
        receipt['manifest_sha256']=file_sha(h.base/'manifest.json');atomic_write(h.base/'receipt.json',receipt)
        (h.runtime/'daily.lock').unlink()
        atomic_write(h.runtime/'daily-latest.json',{'date':h.day,'ok':True,'completedAt':h.day+'T09:30:00Z'})
        atomic_write(h.repo/'.cache/weak_early_beta/daily-runner.config.json',{'runtimeDir':str(h.runtime)})
        run=read(h.root/'latest-run.json')
        atomic_write(h.root/'latest-publication.json',{'as_of':h.day,'snapshot_sha256':run['snapshot_sha256'],
          'source_version':run['source_version'],'published':True,'active_readback_verified':True})
        self.ledger={'schema':editorial.SCHEMA,'scope':'presentation-prose-only','previous_sha256':None,
          'review':{'source_version':manifest['source_version'],'snapshot_sha256':run['snapshot_sha256'],
            'bundle_manifest_sha256':file_sha(h.base/'manifest.json'),'reviewed_at':h.day+'T12:00:00Z',
            'method':'explicit-editorial-review-no-absence-inference'},
          'entries':{self.identity:{'original':self.original,'corrected':self.corrected,
            'reason':'Remove only an unsupported research-gap warning while preserving issuer facts and sources.'}}}
        self.review=h.repo/'editorial-review.json';atomic_write(self.review,self.ledger)

    def register(self):
        with patch('weak_early_beta.new_a.fundamentals.approved_recovery_source',return_value='e'*40):
            return editorial.register(self.h.repo,self.review,file_sha(self.review))

    def test_verified_correction_rebuilds_only_presentation_and_replay_is_a_noop(self):
        h=self.h
        frozen={p:file_sha(p) for p in [h.base/'manifest.json',h.base/'presentation-000.json',
          h.target/'snapshot.json',h.root/'latest-run.json',h.runtime/'daily-latest.json']}
        original_receipt=h.root/'fundamentals/verified/fixture-original.json'
        atomic_write(original_receipt,{'verified_report':self.original,'sent':True})
        receipt_sha=file_sha(original_receipt)
        result=self.register();self.assertEqual(result['reports'],1);self.assertFalse(result['published'])
        self.assertEqual(editorial.retained(h.root),self.ledger)
        self.assertTrue(self.register()['same_ledger_replay'])
        manifest,receipt=_manifest(h.base);rows=_rows(h.base,manifest)
        output,source=_bundle(h.base,manifest,receipt,h.target,rows,{self.identity:self.original},correction_root=h.root)
        self.assertNotEqual(source,'c'*64)
        manifest2,receipt2=_manifest(output);rows2=_rows(output,manifest2)
        self.assertEqual(rows2[0]['fundamental'],self.corrected)
        self.assertEqual(manifest2['daily_snapshot_sha256'],self.ledger['review']['snapshot_sha256'])
        again=_bundle(output,manifest2,receipt2,h.target,rows2,{self.identity:self.original},correction_root=h.root)
        self.assertEqual(again,(output,source))
        self.assertEqual(file_sha(original_receipt),receipt_sha)
        self.assertEqual({p:file_sha(p) for p in frozen},frozen)

    def test_unreviewed_conflicting_analysis_still_fails(self):
        self.register();h=self.h;manifest,receipt=_manifest(h.base);rows=_rows(h.base,manifest)
        conflicting=deepcopy(self.original);conflicting['fields'][1]['text']='Different unreviewed analysis'
        with self.assertRaisesRegex(ValueError,'overwrite other presentation'):
            _bundle(h.base,manifest,receipt,h.target,rows,{self.identity:conflicting},correction_root=h.root)

    def test_identity_cutoff_sources_and_nonprose_edits_are_rejected(self):
        for key,value in [('analysisCutoff','2026-11-19T16:15:00+09:00'),('symbol','9999'),('auditStatus','fail')]:
            ledger=deepcopy(self.ledger);ledger['entries'][self.identity]['corrected'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):editorial.checked_ledger(ledger)
        ledger=deepcopy(self.ledger);ledger['entries'][self.identity]['corrected']['fields'][5]['text']='[Changed](https://example.com/new.pdf)'
        with self.assertRaisesRegex(ValueError,'prose scope'):editorial.checked_ledger(ledger)

    def test_live_owner_or_changed_source_cannot_register(self):
        lock=self.h.runtime/'daily.lock';lock.write_text('live-owner')
        with self.assertRaisesRegex(ValueError,'live daily'):self.register()
        lock.unlink();ledger=deepcopy(self.ledger);ledger['review']['source_version']='f'*64;atomic_write(self.review,ledger)
        with self.assertRaisesRegex(ValueError,'immutable bundle'):self.register()
        self.assertIsNone(editorial.retained(self.h.root))
        self.assertFalse((self.h.runtime/'fundamental-correction.lock').exists())

    def test_changed_saved_bytes_and_replacement_of_history_are_rejected(self):
        self.register();folder=self.h.root/'fundamentals/editorial-corrections'
        changed=deepcopy(self.ledger);changed['review']['method']='unreviewed';atomic_write(folder/(digest(self.ledger)+'.json'),changed)
        with self.assertRaises(ValueError):editorial.retained(self.h.root)
        atomic_write(folder/(digest(self.ledger)+'.json'),self.ledger)
        changed=deepcopy(self.ledger)
        changed['entries'][self.identity]['reason']='Different replacement without retaining the previous review identity.'
        atomic_write(self.review,changed)
        with self.assertRaisesRegex(ValueError,'append-only predecessor'):self.register()


if __name__=='__main__':unittest.main()
