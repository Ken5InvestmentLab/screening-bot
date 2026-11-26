import copy
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from weak_early_beta.new_a import monitor, source_baseline as baseline, restriction_exits as exits
from weak_early_beta.new_a.pipeline import Pipeline
from weak_early_beta.new_a.files import atomic_write, file_sha, digest


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'new-a-private';self.root.mkdir()
        self.calendar=['2026-11-24','2026-11-25','2026-11-26','2026-11-27','2026-11-30']
        seed=monitor.initial(self.calendar,list(baseline.SYMBOLS)+list(baseline.MISSING),'SYNTHETIC_ONLY')
        seed['cursor']=0
        self.p=Pipeline(self.root/'daily.sqlite',seed)
        rows=[]
        for symbol in baseline.SYMBOLS:
            for day in self.calendar[:2]:
                rows.append(dict(symbol=symbol,date=pd.Timestamp(day),open=100.,high=102.,low=99.,close=101.,volume=100.,
                     actual_open=100.,actual_high=102.,actual_low=99.,actual_close=101.,actual_volume=100.,
                     split_factor=1.,source_usable=False,source_issue='unresolved_jpx_historical_revision',jpx_symbol_hold_evidence=''))
        self.frame=pd.DataFrame(rows)
        self.path=self.root/'review.json'
        atomic_write(self.path,baseline.make_review(self.frame,'a'*64))
    def tearDown(self):
        self.p.close();self.temp.cleanup()
    def register(self):
        return baseline.register(self.p,self.path,file_sha(self.path),'a'*64)
    def source(self,frame=None):
        return dict(frame=self.frame if frame is None else frame,source_hash='a'*64,source_revision={})
    def test_acceptance_skips_gap_without_rewriting_quotes_events_or_recorded_missing_decisions(self):
        with self.p.db:
            self.p.db.execute('INSERT INTO held VALUES(?,?,?)',(baseline.MISSING[0],'2026-11-25','MISSING_SOURCE'))
            self.p.db.execute('INSERT INTO held VALUES(?,?,?)',('9999','2026-11-25','VERIFIED_RESTRICTED'))
        before=[self.p.db.execute('SELECT * FROM '+table).fetchall() for table in ('events','observed_quotes','symbol_days','runs')]
        self.register()
        self.assertEqual(self.p.read('2978')['cursor'],1)
        self.assertIn((baseline.MISSING[0],'2026-11-25'),self.p.missing_quote_days())
        self.assertEqual(self.p.db.execute('SELECT symbol FROM held').fetchall(),[('9999',)])
        self.assertEqual(before,[self.p.db.execute('SELECT * FROM '+table).fetchall() for table in ('events','observed_quotes','symbol_days','runs')])
        self.assertTrue(baseline.apply(self.source(),self.p,'2026-11-26')['frame'].source_usable.all())
        self.assertFalse(self.frame.source_usable.any())
    def test_revision_recurrence_is_recorded_and_never_cleared(self):
        self.register();changed=self.frame.copy();changed.loc[0,'actual_open']=105.
        output=baseline.apply(self.source(changed),self.p,'2026-11-26')
        self.assertFalse(output['frame'].loc[0,'source_usable'])
        audit=output['source_revision']['ownerAcceptedBaseline']['symbols']
        self.assertEqual(audit[0]['status'],'REVISION_RECURRED')
        self.assertFalse(baseline.apply(self.source(),self.p,'2026-11-25')['frame'].source_usable.any())
    def test_unknown_quality_issue_and_invalid_ohlc_are_not_accepted(self):
        self.register();changed=self.frame.copy();changed.loc[0,'source_issue']='new_unknown_issue';changed.loc[2,'low']=105.
        result=baseline.apply(self.source(changed),self.p,'2026-11-26')['frame']
        self.assertFalse(result.loc[0,'source_usable']);self.assertFalse(result.loc[2,'source_usable'])
    def test_forced_settlement_quotes_are_pinned_and_do_not_create_monitor_observations(self):
        symbol='2978';anchor=self.frame.loc[self.frame.symbol.eq(symbol)].iloc[-1].to_dict()
        anchor['source_usable']=True;anchor['source_issue']=''
        with self.p.db:
            self.p.db.execute('INSERT INTO observed_quotes VALUES(?,?,?,?)',(symbol,'2026-11-25',monitor.encode({k:v for k,v in anchor.items() if k not in ('date','symbol')}),digest({k:v for k,v in anchor.items() if k not in ('date','symbol')})))
        rows=[anchor]
        for day in ('2026-11-26','2026-11-27'):
            rows.append({**anchor,'date':pd.Timestamp(day)})
        frame=pd.DataFrame(rows)
        rule=dict(symbol=symbol,confirmed_on='2026-11-26',exit_date='2026-11-27',reason='整理銘柄入り')
        first=exits.settlement_quotes(self.p,frame,[rule],self.calendar,'2026-11-27','a'*64)
        self.assertEqual(len(first),2)
        frame.loc[frame.date.eq(pd.Timestamp('2026-11-27')),'open']=102.
        self.assertEqual(first,exits.settlement_quotes(self.p,frame,[rule],self.calendar,'2026-11-30','b'*64))
        self.assertEqual(len(self.p.observed_quotes()),1)
        self.assertEqual(self.p.all_events(),[])

    def test_live_confirmation_is_first_seen_and_uses_the_verified_next_market_session(self):
        rows=[dict(code='1111',designation='上場廃止の決定・整理銘柄指定',designation_date='2026-11-24'),
              dict(code='2222',designation='監理銘柄（確認中）指定',designation_date='2026-11-24'),
              dict(code='3333',delisting_date='2026-12-01',delisting_source_url='https://www.jpx.co.jp/'),
              dict(code='4444',delisting_date='2026-11-24')]
        with patch.object(exits.datetime,'datetime') as clock:
            clock.now.return_value.date.return_value.isoformat.return_value='2026-11-27'
            rules=exits.observe(self.p,rows,self.calendar,'2026-11-27',live=True)
            self.assertEqual([r['symbol'] for r in rules],['1111','3333'])
            self.assertTrue(all(r['exit_date']=='2026-11-30' for r in rules))
            self.assertEqual(rules,exits.observe(self.p,rows,self.calendar,'2026-11-27',live=True))
            self.assertEqual(exits.observe(self.p,rows,self.calendar,'2026-11-25',live=True),[])


if __name__=='__main__':unittest.main()
