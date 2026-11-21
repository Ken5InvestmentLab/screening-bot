"""新A接続の境界試験。合成価格だけ、ネットワーク/通知は使用しない。"""
import copy,datetime,json,sqlite3,sys,tempfile,unittest
from contextlib import closing
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from weak_early_beta.new_a import monitor
from weak_early_beta.new_a.pipeline import Pipeline
from weak_early_beta.new_a.publisher import LocalD1,publish_bundle,verify_dataset,pointer,literal
from weak_early_beta.new_a.files import atomic_write,digest,encode

def market_days():
 values=[];d=datetime.date(2026,5,1)
 while len(values)<80:
  if d.weekday()<5:values.append(d.isoformat())
  d+=datetime.timedelta(days=1)
 return values
def bar(candidate=False):return dict(open=104.,high=108.,low=100.,close=104.,actual_close=104.,volume=100000.,actual_volume=100000.,split_factor=1.,source_usable=True,candidate=candidate,low20=100.,high20=110.,median_turnover20=20000000.)
class DailyResume(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.cal=market_days();self.day=self.cal[-1];self.seed=monitor.initial(self.cal,['1111','2222'],'SYNTHETIC_A_ONLY');self.seed['cursor']=78;self.seed['previous']={s:bar() for s in self.seed['symbols']};self.p=Pipeline(Path(self.temp.name)/'state.sqlite',self.seed);self.rows={self.cal[-2]:{s:bar() for s in self.seed['symbols']},self.day:{'1111':bar(True),'2222':None}}
 def tearDown(self):self.p.close();self.temp.cleanup()
 def run_day(self,**patch):
  args=dict(as_of=self.day,observed_at=self.day+'T08:00:00Z',calendar=self.cal,rows_by_day=self.rows,source_hash='a'*64,quality_verified=True,universe=self.seed['symbols'],dry_run=True);args.update(patch);return self.p.run(**args)
 def test_one_late_held_quote_same_day_does_not_advance_other_symbol(self):
  first=self.run_day();healthy=monitor.encode(self.p.read('1111'));count=self.p.db.execute('SELECT count(*) FROM symbol_days WHERE symbol="1111"').fetchone()[0];self.assertEqual(first['processed_symbol_sessions'],1);self.rows[self.day]['2222']=bar(True)
  later=self.run_day(source_hash='b'*64,resume_held=True,predecessor_source_hash='a'*64);self.assertTrue(later['held_resume']);self.assertEqual(later['processed_symbol_sessions'],1);self.assertEqual(later['new_event_count'],1);self.assertFalse(later['held']);self.assertEqual(monitor.encode(self.p.read('1111')),healthy);self.assertEqual(self.p.db.execute('SELECT count(*) FROM symbol_days WHERE symbol="1111"').fetchone()[0],count);self.assertEqual(self.p.read('1111')['calendar'],self.cal);self.assertEqual(self.p.read('1111')['pending'],json.loads(healthy)['pending']);self.assertEqual(self.p.db.execute('SELECT count(*) FROM events').fetchone()[0],2)
  again=self.run_day(source_hash='b'*64);self.assertEqual(again['new_event_count'],0);self.assertEqual(monitor.encode(self.p.read('1111')),healthy)
  with self.assertRaisesRegex(ValueError,'stale source'):self.run_day()
 def test_late_held_resume_rejects_any_committed_bar_change(self):
  self.run_day();healthy=monitor.encode(self.p.read('1111'));self.rows[self.day]['2222']=bar(True);self.rows[self.day]['1111']['volume']+=1
  with self.assertRaisesRegex(ValueError,'committed input'):self.run_day(source_hash='b'*64,resume_held=True,predecessor_source_hash='a'*64)
  self.assertEqual(monitor.encode(self.p.read('1111')),healthy);self.assertEqual(self.p.read('2222')['cursor'],78)
 def test_held_resume_keeps_existing_watch_age_and_pending_holding_indices(self):
  seed=copy.deepcopy(self.seed);episode=dict(symbol='1111',candidate_date=self.cal[70],episode_id=2,support=100.,resistance=110.,priority_score=20000000.,detection_count=1)
  seed['active']['1111']=copy.deepcopy(episode);seed['watches']['1111|2']={'episode':copy.deepcopy(episode),'start_index':70}
  seed['pending']=[dict(episode,episode_id=1,trigger_date=self.cal[69],entry_index=70,reference_exit_index=89,reference_entry_date=self.cal[70],reference_exit_date=None,reference_open=104.,price_status='HISTORICAL_REFERENCE_ONLY',execution_status='NOT_EXECUTED')]
  rich=Pipeline(Path(self.temp.name)/'rich-state.sqlite',seed)
  try:
   rows=copy.deepcopy(self.rows);rows[self.day]['1111']=bar(False)
   args=dict(as_of=self.day,observed_at=self.day+'T08:00:00Z',calendar=self.cal,rows_by_day=rows,source_hash='c'*64,quality_verified=True,universe=seed['symbols'],dry_run=True)
   first=rich.run(**args);healthy=rich.read('1111');self.assertEqual(first['processed_symbol_sessions'],1)
   age=healthy['cursor']-healthy['watches']['1111|2']['start_index'];holding_age=healthy['cursor']-healthy['pending'][0]['entry_index'];self.assertEqual((age,holding_age),(9,9))
   rows[self.day]['2222']=bar(True);args.update(source_hash='d'*64,resume_held=True,predecessor_source_hash='c'*64)
   later=rich.run(**args);after=rich.read('1111');self.assertEqual(later['processed_symbol_sessions'],1);self.assertEqual(later['new_event_count'],1)
   self.assertEqual(monitor.encode(after),monitor.encode(healthy));self.assertEqual((after['cursor']-after['watches']['1111|2']['start_index'],after['cursor']-after['pending'][0]['entry_index']),(age,holding_age));self.assertEqual(after['pending'][0]['reference_exit_index'],89)
   self.assertEqual(rich.db.execute('SELECT count(*) FROM symbol_days WHERE symbol="1111"').fetchone()[0],1)
   self.assertEqual(rich.run(**args)['new_event_count'],0)
  finally:rich.close()
 def test_no_generic_same_day_revision_or_dry_live_switch(self):
  self.run_day()
  with self.assertRaisesRegex(ValueError,'requires review'):self.run_day(source_hash='b'*64)
  with self.assertRaisesRegex(ValueError,'requires review'):self.run_day(source_hash='b'*64,resume_held=True,predecessor_source_hash='c'*64)
 def test_causal_designation_and_relisting_intervals(self):
  restrictions={'1111':[{'start':self.day,'end':None,'reason':'VERIFIED_RESTRICTED'}],'2222':[{'start':self.cal[-3],'end':self.day,'reason':'VERIFIED_DELISTED'}]};self.rows[self.day]['2222']=bar(True);r=self.run_day(restrictions=restrictions);self.assertEqual(r['held']['1111']['reason'],'VERIFIED_RESTRICTED');self.assertNotIn('2222',r['held'])
 def test_late_catchup_is_not_live_and_new_universe_warmup_emits_no_backfill(self):
  rows={d:{'1111':bar(False),'2222':bar(False),'999A':bar(True)} for d in self.cal};r=self.run_day(rows_by_day=rows,universe=['1111','2222','999A']);events=[e for e in r['events'] if e['symbol']=='999A'];self.assertEqual(len(events),1);self.assertEqual(events[0]['session'],self.day);self.assertFalse(events[0]['is_new_live_signal'])
 def test_new_member_missing_prelisting_warmup_does_not_stall_current_day(self):
  from weak_early_beta.new_a.features import compute_features
  import pandas as pd
  values=[]
  for day in self.cal[-3:]:values.append({'date':day,**{k:v for k,v in bar().items() if k not in ['candidate','low20','high20','median_turnover20']}})
  features=compute_features(pd.DataFrame(values),self.cal);self.assertFalse(bool(features.loc[pd.Timestamp(self.day),'quality60']));self.assertFalse(bool(features.loc[pd.Timestamp(self.day),'candidate']))
  rows={d:{'1111':bar(False),'2222':bar(False),'999A':None} for d in self.cal};rows[self.day]['999A']=bar(False);r=self.run_day(rows_by_day=rows,universe=['1111','2222','999A']);self.assertEqual(self.p.read('999A')['cursor'],79);self.assertNotIn('999A',r['held']);self.assertFalse([e for e in r['events'] if e['symbol']=='999A'])
class Publisher(unittest.TestCase):
 def test_sql_literal_does_not_move_placeholders_or_leak_values(self):
  self.assertEqual(literal("x?'雪;"),"'x?''雪;'")
 def test_activation_is_closed_without_actual_owner_evidence(self):
  from weak_early_beta.new_a.acceptance import validate_activation
  with self.assertRaisesRegex(ValueError,'activation'):validate_activation({},Path('.'))
  with self.assertRaisesRegex(ValueError,'owner acceptance'):validate_activation({'schema':'NEW_A_OWNER_ACTIVATION_V1','active':True,'external_actions_approved':True,'strategy':'A_BASE'},Path('.'))
class Notifications(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'new-a-private';self.root.mkdir();self.day='2026-06-01';self.calls=[]
  self.snapshot={'schema':'NEW_A_OWNER_DAILY_SNAPSHOT_V1','strategy':'A_BASE','audience':'EXISTING_CLOUD_OWNER_ONLY','as_of':self.day,'source_sha256':'a'*64,'observation_kind':'LIVE_OBSERVATION','data_status':'COMPLETED','held_symbols':{},'new_live_signals':1,'events':[{'event_id':'b'*64,'kind':'WATCH_STARTED','symbol':'1111','session':self.day,'is_new_live_signal':True}],'published':False};self.save()
 def save(self):
  self.snapshot['payload_sha256']=digest({k:v for k,v in self.snapshot.items() if k!='payload_sha256'});atomic_write(self.root/'snapshot.json',self.snapshot);atomic_write(self.root/'latest-run.json',{'strategy':'A_BASE','source_sha256':'a'*64,'source_version':'c'*64,'snapshot_sha256':self.snapshot['payload_sha256'],'snapshot_file':str(self.root/'snapshot.json')});atomic_write(self.root/'latest-publication.json',{'published':True,'active_readback_verified':True,'existing_owner_gate_verified':True,'snapshot_sha256':self.snapshot['payload_sha256'],'source_version':'c'*64})
 def tearDown(self):self.temp.cleanup()
 def test_only_newA_receipts_and_existing_transport_callback_no_repeat(self):
  from weak_early_beta.new_a.notifications import notify_day
  before=notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/');self.assertEqual((before['signal_notifications'],before['completion_notifications']),(1,1));self.assertFalse(self.calls)
  def fake(payload):self.calls.append(payload['batch_id']);return{'confirmed':True,'message_id':'SYNTHETIC_ONLY'}
  sent=notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=fake);self.assertEqual(len(self.calls),1);self.assertEqual(sent['signal_notifications'],1)
  remaining=notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/');self.assertEqual(remaining['signal_notifications']+remaining['completion_notifications'],0)
  notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=fake);self.assertEqual(len(self.calls),1)
 def test_unknown_send_never_retries_automatically(self):
  from weak_early_beta.new_a.notifications import notify_day
  def uncertain(payload):self.calls.append(payload['batch_id']);return{'confirmed':False}
  with self.assertRaises(RuntimeError):notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=uncertain)
  with self.assertRaisesRegex(ValueError,'unconfirmed'):notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/')
  self.assertEqual(len(self.calls),1)
 def test_live_unpublished_blocks_summary_and_signals_before_callback(self):
  from weak_early_beta.new_a.notifications import notify_day
  pub=json.loads((self.root/'latest-publication.json').read_text());pub['published']=False;atomic_write(self.root/'latest-publication.json',pub)
  for dry in [True,False]:
   with self.assertRaisesRegex(ValueError,'publication'):notify_day(self.root,date=self.day,dry_run=dry,report_url='https://synthetic.invalid/',transport=lambda p:self.calls.append(p))
  self.assertFalse(self.calls);self.assertFalse((self.root/'notification-outbox.sqlite').exists())
 def test_corrupt_private_snapshot_rejected_before_callback(self):
  from weak_early_beta.new_a.notifications import notify_day
  self.snapshot['events'][0]['symbol']='9999';atomic_write(self.root/'snapshot.json',self.snapshot)
  with self.assertRaisesRegex(ValueError,'bytes changed'):notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/',transport=lambda p:self.calls.append(p))
  self.assertFalse(self.calls)
 def test_historical_local_preview_has_zero_notifications_and_no_credentials(self):
  from weak_early_beta.new_a.notifications import notify_day
  self.snapshot['observation_kind']='DRY_RUN_HISTORICAL';self.snapshot['new_live_signals']=0;self.snapshot['events'][0]['is_new_live_signal']=False;self.save();pub=json.loads((self.root/'latest-publication.json').read_text());pub.update(published=False,existing_owner_gate_verified=False,local_d1_emulation=True);atomic_write(self.root/'latest-publication.json',pub)
  with patch('weak_early_beta.new_a.notifications.default_transport',side_effect=AssertionError('credentials forbidden')):
   preview=notify_day(self.root,date=self.day,dry_run=True,report_url='https://synthetic.invalid/');self.assertEqual(preview['signal_notifications']+preview['completion_notifications'],0)
  with self.assertRaises(ValueError):notify_day(self.root,date=self.day,dry_run=False,report_url='https://synthetic.invalid/')

class BatchedDiscord(unittest.TestCase):
    def setUp(self):
        from weak_early_beta import notify
        self.fixture = Notifications()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root, self.day = self.fixture.root, self.fixture.day
        self.snapshot = self.fixture.snapshot
        self.report = "https://synthetic.invalid/"
        self.posts = []
        self.webhook_id = "123456789"
        self.webhook_url = f"https://discord.com/api/webhooks/{self.webhook_id}/synthetic"
        self.channel_id = notify.CHANNEL_ID
        self.guild_id = notify.GUILD_ID
        self.message_id = "987654321"
        self.enterContext(patch.dict("os.environ", {
            notify.WEBHOOK_ENV: self.webhook_url,
            "WEAK_EARLY_BETA_DISCORD_BOT_TOKEN": "synthetic",
        }))
        self.post = self.enterContext(patch.object(notify.requests, "post", side_effect=self.capture_post))
        self.get = self.enterContext(patch.object(notify.requests, "get", side_effect=self.capture_metadata))

    def capture_metadata(self, url, **kwargs):
        from unittest.mock import Mock

        self.assertEqual(url, self.webhook_url)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["User-Agent"], "DiscordBot (screening-bot, 1.0)")
        response = Mock(status_code=200)
        response.json.return_value = {
            "id": self.webhook_id, "channel_id": self.channel_id, "guild_id": self.guild_id,
        }
        return response

    def capture_post(self, url, **kwargs):
        from unittest.mock import Mock

        self.assertEqual(url, self.webhook_url)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["User-Agent"], "DiscordBot (screening-bot, 1.0)")
        self.assertEqual(kwargs["params"]["wait"], "true")
        payload = kwargs["json"] if "json" in kwargs else json.loads(kwargs["data"]["payload_json"])
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        files = kwargs.get("files", {})
        attachments = [
            {"filename": filename, "size": len(data)} for filename, data, _ in files.values()
        ]
        message = {
            "id": self.message_id, "webhook_id": self.webhook_id, "channel_id": self.channel_id,
            "content": payload["content"], "embeds": payload["embeds"], "attachments": attachments,
        }
        if "components" in payload:
            message["components"] = copy.deepcopy(payload["components"])
        self.posts.append((message, files))
        response = Mock(status_code=200)
        response.json.return_value = message
        return response

    def call(self, **kwargs):
        from weak_early_beta.new_a.notifications import notify_day

        return notify_day(self.root, date=self.day, report_url=self.report,
                          dry_run=kwargs.pop("dry_run", False), **kwargs)

    def events(self, count):
        self.snapshot["events"] = [{
            "event_id": digest(["synthetic", i]), "kind": "WATCH_STARTED", "symbol": f"{i:04}",
            "session": self.day, "is_new_live_signal": True,
        } for i in range(count)]
        self.snapshot["new_live_signals"] = count
        self.fixture.save()

    def update_rows(self, status, ids):
        with closing(sqlite3.connect(self.root / "notification-outbox.sqlite")) as db:
            db.executemany("UPDATE new_a_delivery SET status = ?, receipt_json = ? WHERE event_id = ?",
                           [(status, '{"message_id":"legacy"}', event_id) for event_id in ids])
            db.commit()

    def receipts(self):
        with closing(sqlite3.connect(self.root / "notification-outbox.sqlite")) as db:
            return db.execute("SELECT event_id, status, receipt_json FROM new_a_delivery").fetchall()

    def test_eight_symbols_and_summary_in_one_post_then_no_pending(self):
        self.events(8)
        self.snapshot["held_symbols"] = {"T1": {}, "T2": {}}
        self.snapshot["data_status"] = "COMPLETED_WITH_HELD_SYMBOLS"
        self.fixture.save()
        preview = self.call(dry_run=True)
        self.assertEqual((preview["signal_notifications"], preview["completion_notifications"]), (8, 1))
        self.assertEqual((preview["pending_discord_messages"], preview["external_sends"]), (1, 0))
        self.post.assert_not_called()
        sent = self.call()
        self.assertEqual((sent["external_sends"], sent["pending_discord_messages"]), (1, 0))
        self.assertEqual(self.post.call_count, 1)
        message, files = self.posts[0]
        embed = message["embeds"][0]
        self.assertEqual(embed["url"], self.report + "weak_early_beta_latest.html")
        for event in self.snapshot["events"]:
            self.assertIn(f"[{event['symbol']}](https://jp.tradingview.com/chart/", embed["description"])
        self.assertEqual([field["value"] for field in embed["fields"]][0], self.day)
        self.assertEqual([field["value"] for field in embed["fields"]][1][0], "8")
        self.assertEqual([field["value"] for field in embed["fields"]][2][0], "2")
        self.assertFalse(files)
        receipts = self.receipts()
        self.assertEqual(len(receipts), 9)
        self.assertEqual({(status, json.loads(receipt)["message_id"]) for _, status, receipt in receipts},
                         {("SENT", self.message_id)})
        self.assertEqual(self.call(dry_run=True)["pending_discord_messages"], 0)
        self.assertEqual(self.call()["external_sends"], 0)
        self.assertEqual(self.post.call_count, 1)

    def test_verified_zero_is_silent_unknown_is_not_zero(self):
        self.events(0)
        self.assertEqual(self.call(dry_run=True)["pending_discord_messages"], 0)
        self.assertEqual(self.call()["external_sends"], 0)
        self.snapshot["data_status"] = "INCOMPLETE"
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "completed"):
            self.call()
        self.post.assert_not_called()

    def prepare_next_session(self, symbols=("2345", "417A"), entry_date="2026-06-03", previous=None):
        from datetime import date
        from weak_early_beta.new_a import owner_notice_producer

        observed_at = self.day + "T17:40:00+09:00"
        self.snapshot["observed_at"] = observed_at
        self.snapshot["events"].extend({
            "event_id": digest(["entry", symbol]), "kind": "ENTRY_CANDIDATE",
            "symbol": symbol, "session": self.day, "trigger_date": self.day,
            "observation_kind": "LIVE_OBSERVATION", "observed_at": observed_at,
            "execution_status": "NOT_EXECUTED", "price_status": "UNCONFIRMED_NEXT_OPEN",
            "reference_entry_date": entry_date,
        } for symbol in symbols)
        self.fixture.save()
        self.update_receipt("latest-run.json", identity="NEW_A_CLOUD_DAILY_V1", latest_session=self.day,
                            dry_run=False, detection_executed=True, same_run_replay=False)
        self.update_receipt("latest-publication.json", schema="NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1",
                            as_of=self.day, same_dataset_replay=False, local_d1_emulation=False)
        dates = [self.day, "2026-06-03", "2026-06-04"]
        if previous:
            dates.insert(0, previous)
        return self.enterContext(patch.object(owner_notice_producer, "_verified_calendar", return_value=[
            date.fromisoformat(day) for day in dates
        ]))

    def update_receipt(self, name, **fields):
        path = self.root / name
        receipt = json.loads(path.read_text(encoding="utf-8"))
        atomic_write(path, {**receipt, **fields})

    def test_evening_conditions_are_in_the_existing_watch_message(self):
        calendar = self.prepare_next_session()
        preview = self.call(dry_run=True)
        self.assertEqual((preview["signal_notifications"], preview["completion_notifications"]), (1, 1))
        self.post.assert_not_called()
        from weak_early_beta.new_a import notifications

        with patch.object(notifications, "_shared_trial_order_rule",
                          side_effect=AssertionError("retry must use the stored order rule")):
            sent = self.call()
        self.assertEqual((sent["signal_notifications"], sent["completion_notifications"], sent["external_sends"]),
                         (1, 1, 1))
        calendar.assert_called_once()
        embed = self.posts[0][0]["embeds"][0]
        self.assertIn("[1111]", embed["description"])
        next_open = embed["fields"][-1]
        self.assertEqual(next_open["name"], "翌取引日の仮想保有開始候補（2026-06-03）")
        self.assertIn("2345・417A", next_open["value"])
        self.assertIn("注文額の条件：始値5,000円以下（100株・1注文50万円）", next_open["value"])
        self.assertIn("手数料込みで残資金内、同時保有枠（最大10銘柄）に空き", next_open["value"])
        self.assertIn("同じ銘柄を仮想保有中でない", next_open["value"])
        self.assertIn("正の出来高があり、高値と安値が異なる", next_open["value"])
        self.assertIn("利益優先：優先順で1日最大3件", next_open["value"])
        self.assertEqual(self.call()["external_sends"], 0)
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual({(status, json.loads(raw)["message_id"]) for _, status, raw in self.receipts()},
                         {("SENT", self.message_id)})

    def test_missing_shared_order_rule_cannot_stage_unverified_candidates(self):
        from weak_early_beta.new_a import notifications

        self.prepare_next_session()
        with patch.object(notifications.subprocess, "run", side_effect=OSError):
            with self.assertRaisesRegex(ValueError, "shared trial order rule unavailable"):
                self.call(dry_run=True)
        self.post.assert_not_called()
        self.assertFalse(self.receipts())

    def test_zero_watches_with_candidates_still_has_one_completion_batch(self):
        self.events(0)
        self.prepare_next_session(symbols=("2345",))
        preview = self.call(dry_run=True)
        self.assertEqual((preview["signal_notifications"], preview["completion_notifications"]), (0, 1))
        self.assertEqual(preview["pending_discord_messages"], 1)
        sent = self.call()
        self.assertEqual((sent["signal_notifications"], sent["completion_notifications"], sent["external_sends"]),
                         (0, 1, 1))
        embed = self.posts[0][0]["embeds"][0]
        self.assertNotIn("description", embed)
        self.assertIn("2345", embed["fields"][-1]["value"])

    def test_legacy_pending_without_summary_does_not_gain_evening_payload(self):
        from weak_early_beta.new_a import notifications

        calendar = self.prepare_next_session()
        with patch.object(notifications, "_fresh_ordinary_result", return_value=False):
            self.call(dry_run=True)
        with closing(sqlite3.connect(self.root / "notification-outbox.sqlite")) as db:
            db.execute("DELETE FROM new_a_delivery WHERE event_id=?", (digest(["A_BASE", self.day, "DAILY_SUMMARY"]),))
            db.commit()
        self.assertEqual(self.call()["external_sends"], 1)
        calendar.assert_not_called()
        self.assertNotIn("翌営業日", json.dumps(self.posts[0][0], ensure_ascii=False))

    def test_legacy_pending_candidates_keep_original_message_and_csv(self):
        import csv
        import io
        from weak_early_beta.new_a import notifications

        candidates = [f"{1000 + i:04}" for i in range(250)]
        self.prepare_next_session(symbols=candidates)
        legacy = {
            "next_session_entries": {
                "session": "2026-06-03", "symbols": candidates,
                "snapshot_sha256": self.snapshot["payload_sha256"],
            },
        }
        with patch.object(notifications, "_shared_trial_order_rule",
                          side_effect=AssertionError("stored candidates must not read current terms")):
            with patch.object(notifications, "_summary_details", return_value=legacy):
                self.call(dry_run=True)
            self.assertEqual(self.call()["external_sends"], 1)
        message, files = self.posts[0]
        field = message["embeds"][0]["fields"][-1]
        self.assertEqual(field["name"], "翌営業日の買付候補（2026-06-03）")
        self.assertNotIn("始値上限", field["value"])
        rows = list(csv.reader(io.StringIO(files["files[0]"][1].decode("utf-8-sig"))))[1:]
        self.assertEqual({row[2] for row in rows if row[0] == "買付候補（未約定）"}, set(candidates))

    def test_existing_uncertain_evening_batch_uses_exact_history_without_resending(self):
        from unittest.mock import Mock
        from weak_early_beta.new_a.outbox import Outbox

        calendar = self.prepare_next_session()
        with patch.object(Outbox, "confirm_batch", side_effect=RuntimeError("interrupted after delivery")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.call()
        response = Mock(status_code=200)
        edited = copy.deepcopy(self.posts[0][0])
        edited["embeds"][0]["fields"][-1]["value"] = "変更済み"
        response.json.return_value = [edited]
        self.get.side_effect = None
        self.get.return_value = response
        with self.assertRaisesRegex(ValueError, "expected one exact"):
            self.call(reconcile_only=True)
        response.json.return_value = [edited, self.posts[0][0]]
        self.assertTrue(self.call(reconcile_only=True)["reconciled_batch"])
        self.assertEqual(self.call()["external_sends"], 0)
        calendar.assert_called_once()
        self.assertEqual(self.post.call_count, 1)

    def test_replay_or_local_run_does_not_stage_a_next_session_notice(self):
        self.events(0)
        calendar = self.prepare_next_session()
        for name, key in (("latest-run.json", "same_run_replay"),
                          ("latest-run.json", "dry_run"),
                          ("latest-publication.json", "same_dataset_replay"),
                          ("latest-publication.json", "local_d1_emulation")):
            with self.subTest(key=key):
                self.update_receipt(name, **{key: True})
                self.assertEqual(self.call()["external_sends"], 0)
                self.update_receipt(name, **{key: False})
        self.post.assert_not_called()
        calendar.assert_not_called()

    def test_candidate_must_bind_to_the_next_exchange_session(self):
        self.events(0)
        self.prepare_next_session(entry_date="2026-06-04")
        with self.assertRaisesRegex(ValueError, "verified next market session"):
            self.call()
        self.post.assert_not_called()
        self.assertFalse(self.receipts())

    def test_long_evening_list_uses_the_existing_single_attachment(self):
        import csv
        import io

        self.events(220)
        candidates = tuple(f"{1000 + i:04}" for i in range(250))
        self.prepare_next_session(symbols=candidates)
        self.assertEqual(self.call()["external_sends"], 1)
        message, files = self.posts[0]
        self.assertLessEqual(len(message["embeds"][0]["fields"][-1]["value"]), 1024)
        self.assertEqual(list(files), ["files[0]"])
        rows = list(csv.reader(io.StringIO(files["files[0]"][1].decode("utf-8-sig"))))[1:]
        self.assertEqual({row[2] for row in rows if row[0] == "仮想保有開始候補"}, set(candidates))
        self.assertEqual(len([row for row in rows if row[0] == "監視開始"]), 220)

    def add_closing_opening(self, symbol, price, *, event=True, previous="2026-05-29"):
        identity = {"symbol": symbol, "candidate_date": "2026-05-26", "episode_id": 4}
        status = "HISTORICAL_REFERENCE_ONLY" if price is not None else "UNRESOLVED_OPEN"
        state = self.snapshot.setdefault("monitor_state", {
            "schema": "NEW_A_CURRENT_MONITOR_STATE_V1", "strategy": "A_BASE", "actual_fills": False,
            "pending_references": [],
        })
        state["pending_references"].append({
            **identity, "entry_index": 1, "reference_entry_date": self.day, "trigger_date": previous,
            "execution_status": "NOT_EXECUTED", "reference_open": price,
            "price_status": status if event else "UNCONFIRMED_NEXT_OPEN",
        })
        if event:
            self.snapshot["events"].append({
                **identity, "event_id": digest(["closing", symbol]), "kind": "REFERENCE_OPEN",
                "session": self.day, "observation_kind": "LIVE_OBSERVATION", "observed_at": self.snapshot["observed_at"],
                "execution_status": "NOT_EXECUTED", "reference_open": price, "price_status": status,
            })
        else:
            self.snapshot["data_status"] = "COMPLETED_WITH_HELD_SYMBOLS"
            self.snapshot["held_symbols"][symbol] = {"day": self.day, "reason": "MISSING_SOURCE"}
        self.fixture.save()
        self.update_receipt("latest-run.json", identity="NEW_A_CLOUD_DAILY_V1", latest_session=self.day,
                            dry_run=False, detection_executed=True, same_run_replay=False)
        self.update_receipt("latest-publication.json", schema="NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1",
                            as_of=self.day, same_dataset_replay=False, local_d1_emulation=False)

    def test_closing_outcome_and_next_session_share_one_daily_post(self):
        calendar = self.prepare_next_session(previous="2026-05-29")
        self.add_closing_opening("5001", 1271.5)
        self.add_closing_opening("5002", None)
        self.add_closing_opening("5003", None, event=False)
        self.snapshot["monitor_state"]["opening_cash_yen"] = 713158963
        self.fixture.save()
        self.update_receipt("latest-run.json", identity="NEW_A_CLOUD_DAILY_V1", latest_session=self.day,
                            dry_run=False, detection_executed=True, same_run_replay=False)
        self.update_receipt("latest-publication.json", schema="NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1",
                            as_of=self.day, same_dataset_replay=False, local_d1_emulation=False)
        preview = self.call(dry_run=True)
        self.assertEqual(preview["pending_discord_messages"], 1)
        self.post.assert_not_called()
        self.assertEqual(self.call()["external_sends"], 1)
        self.assertEqual(self.call()["external_sends"], 0)
        calendar.assert_called_once()
        message = self.posts[0][0]
        fields = {field["name"]: field["value"] for field in message["embeds"][0]["fields"]}
        self.assertEqual(fields["終了後に確認した始値（日足始値）"],
                         "5001　1,271.5円\n5002　始値保留\n5003　始値保留")
        self.assertIn("2345", fields["翌取引日の仮想保有開始候補（2026-06-03）"])
        self.assertNotIn("713158963", json.dumps(message, ensure_ascii=False))
        button = message["components"][0]["components"][0]
        self.assertEqual(button, {
            "type": 2, "style": 5, "label": "Cloudダッシュボードで試算を確認",
            "url": self.report + "weak_early_beta_latest.html",
        })

    def test_near_limit_chart_inline_text_moves_to_shared_csv_when_daily_embed_would_overflow(self):
        import csv
        import io
        from weak_early_beta.notify import chart_components
        from weak_early_beta.new_a.notifications import FOOTER_PREFIX

        lines = []
        for idx in range(100):
            symbol = f"{idx:04}"
            url = chart_components(symbol)[0]["components"][0]["url"]
            trial = [*lines, f"[{symbol}]({url})"]
            heading = f"**検出一覧（{len(trial)}銘柄）**\n仕込み候補・監視開始（未約定）\n"
            if len(heading + " ・ ".join(trial)) > 4096:
                break
            lines = trial
        self.events(len(lines))
        candidates = tuple(str(1000 + i) for i in range(170))
        self.prepare_next_session(symbols=candidates, previous="2026-05-29")
        for i in range(47):
            self.add_closing_opening(str(5000 + i), 123456789.12)
        self.assertEqual(self.call()["external_sends"], 1)
        message, files = self.posts[0]
        embed = message["embeds"][0]
        other_chars = len(embed["title"]) + len(FOOTER_PREFIX) + 64 + sum(
            len(field["name"]) + len(field["value"]) for field in embed["fields"]
        )
        unabridged = f"**検出一覧（{len(lines)}銘柄）**\n仕込み候補・監視開始（未約定）\n" + " ・ ".join(lines)
        self.assertGreater(len(unabridged) + other_chars, 6000)
        self.assertLessEqual(len(embed["description"]) + other_chars, 6000)
        self.assertTrue(all(len(field["value"]) <= 1024 for field in embed["fields"]))
        self.assertEqual(list(files), ["files[0]"])
        rows = list(csv.reader(io.StringIO(files["files[0]"][1].decode("utf-8-sig"))))[1:]
        self.assertEqual(len(rows), len(lines) + len(candidates) + 47)
        self.assertTrue(any(row[:3] == ["終了後に確認した始値", self.day, "5000"] for row in rows))

    def test_closing_outcome_alone_can_send_and_preserves_exact_reconciliation(self):
        from unittest.mock import Mock
        from weak_early_beta.new_a.outbox import Outbox

        self.events(0)
        self.prepare_next_session(symbols=(), previous="2026-05-29")
        self.add_closing_opening("5001", 1000)
        with patch.object(Outbox, "confirm_batch", side_effect=RuntimeError("interrupted after delivery")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.call()
        original = self.posts[0][0]
        edited = copy.deepcopy(original)
        edited["components"][0]["components"][0]["url"] = "https://synthetic.invalid/wrong"
        response = Mock(status_code=200)
        response.json.return_value = [edited]
        self.get.side_effect = None
        self.get.return_value = response
        with self.assertRaisesRegex(ValueError, "expected one exact"):
            self.call(reconcile_only=True)
        response.json.return_value = [edited, original]
        recovered = self.call(reconcile_only=True)
        self.assertTrue(recovered["reconciled_batch"])
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual(self.call()["external_sends"], 0)

    def test_closing_outcome_requires_exact_episode_and_original_same_day_observation(self):
        self.events(0)
        self.prepare_next_session(symbols=(), previous="2026-05-29")
        self.add_closing_opening("5001", 900, previous="2026-05-28")
        with self.assertRaisesRegex(ValueError, "preceding market-session episode"):
            self.call()
        self.snapshot["monitor_state"]["pending_references"][0]["trigger_date"] = "2026-05-29"
        self.snapshot["events"][-1]["observed_at"] = "2026-06-01T16:58:00+09:00"
        self.fixture.save()
        self.update_receipt("latest-run.json", identity="NEW_A_CLOUD_DAILY_V1", latest_session=self.day,
                            dry_run=False, detection_executed=True, same_run_replay=False)
        self.update_receipt("latest-publication.json", schema="NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1",
                            as_of=self.day, same_dataset_replay=False, local_d1_emulation=False)
        self.assertEqual(self.call()["external_sends"], 0)
        self.post.assert_not_called()

    def test_all_legacy_sent_preserves_existing_rows_and_stays_silent(self):
        self.events(8)
        self.call(dry_run=True)
        self.update_rows("SENT", [event_id for event_id, _, _ in self.receipts()])
        before = self.receipts()
        self.assertEqual(self.call()["external_sends"], 0)
        self.assertEqual(self.receipts(), before)
        self.post.assert_not_called()

    def test_partial_legacy_sends_only_pending_symbols_and_preserves_summary(self):
        self.events(4)
        self.call(dry_run=True)
        sent_events = [self.snapshot["events"][0]["event_id"],
                       digest(["A_BASE", self.day, "DAILY_SUMMARY"])]
        self.update_rows("SENT", sent_events)
        sent = self.call()
        self.assertEqual((sent["signal_notifications"], sent["completion_notifications"], sent["external_sends"]),
                         (3, 0, 1))
        embed = self.posts[0][0]["embeds"][0]
        self.assertEqual(len(embed["fields"]), 1)
        self.assertNotIn("[0000]", embed["description"])
        self.assertIn("[0003]", embed["description"])
        self.assertEqual({json.loads(receipt)["message_id"] for event_id, _, receipt in self.receipts()
                          if event_id in sent_events}, {"legacy"})

    def test_unverified_webhook_destination_stops_before_claim_and_post(self):
        for mismatch in ("id", "channel_id", "guild_id", "redirect"):
            with self.subTest(mismatch=mismatch):
                response = self.capture_metadata(
                    self.webhook_url, allow_redirects=False,
                    headers={"User-Agent": "DiscordBot (screening-bot, 1.0)"},
                )
                if mismatch == "redirect":
                    response.status_code = 302
                else:
                    response.json.return_value[mismatch] = "737373"
                self.get.side_effect = None
                self.get.return_value = response
                with self.assertRaisesRegex(RuntimeError, "existing_signal_destination_unverified"):
                    self.call()
                self.assertEqual({status for _, status, _ in self.receipts()}, {"PENDING"})
        self.post.assert_not_called()

    def test_webhook_url_cannot_redirect_posts_to_another_destination(self):
        from weak_early_beta import notify

        invalid_urls = [
            self.webhook_url + "?thread_id=222222",
            self.webhook_url + "#fragment",
            self.webhook_url.replace("discord.com", "discord.com:8443"),
            self.webhook_url.replace("discord.com", "other@discord.com"),
            self.webhook_url.replace("/api/", "/other/"),
        ]
        for url in invalid_urls:
            with patch.dict("os.environ", {notify.WEBHOOK_ENV: url}):
                with self.assertRaisesRegex(RuntimeError, "existing_signal_transport_unavailable"):
                    self.call()
        self.get.assert_not_called()
        self.post.assert_not_called()
        self.assertEqual({status for _, status, _ in self.receipts()}, {"PENDING"})

    def test_legacy_unknown_is_not_reposted_or_accepted_as_a_batch(self):
        self.call(dry_run=True)
        self.update_rows("ATTEMPTED_UNCONFIRMED", [self.snapshot["events"][0]["event_id"]])
        for reconcile in [False, True]:
            with self.assertRaisesRegex(ValueError, "unconfirmed"):
                self.call(reconcile_only=reconcile)
        self.post.assert_not_called()
        self.get.assert_not_called()

    def test_lost_result_reconciles_only_exact_webhook_message_with_get(self):
        from unittest.mock import Mock
        from weak_early_beta.new_a.outbox import Outbox

        self.events(8)
        with patch.object(Outbox, "confirm_batch", side_effect=RuntimeError("interrupted after POST")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.call()
        self.assertEqual({status for _, status, _ in self.receipts()}, {"ATTEMPTED_UNCONFIRMED"})
        with self.assertRaisesRegex(ValueError, "reconcile-only"):
            self.call()
        with self.assertRaisesRegex(ValueError, "reconcile-only"):
            self.call(dry_run=True)
        message = self.posts[0][0]
        forged = {**message, "webhook_id": "212121"}
        edited = copy.deepcopy(message)
        edited["embeds"][0]["description"] = "wrong body"
        response = Mock(status_code=200)
        response.json.return_value = [forged, edited]
        self.get.side_effect = None
        self.get.return_value = response
        with self.assertRaisesRegex(ValueError, "expected one exact"):
            self.call(reconcile_only=True)
        self.assertEqual(self.get.call_args.kwargs["headers"]["User-Agent"], "DiscordBot (screening-bot, 1.0)")
        self.assertFalse(self.get.call_args.kwargs["allow_redirects"])
        self.assertEqual({status for _, status, _ in self.receipts()}, {"ATTEMPTED_UNCONFIRMED"})
        response.json.return_value = [forged, edited, message]
        recovered = self.call(reconcile_only=True)
        self.assertTrue(recovered["reconciled_batch"])
        self.assertEqual(recovered["external_sends"], 0)
        self.assertEqual(self.call(dry_run=True)["pending_discord_messages"], 0)
        self.assertEqual(self.call()["external_sends"], 0)
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual({(status, json.loads(receipt)["message_id"]) for _, status, receipt in self.receipts()},
                         {("SENT", self.message_id)})

    def test_concurrent_claim_allows_one_post(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        entered, release = Event(), Event()
        post = self.capture_post

        def wait_for_other(*args, **kwargs):
            entered.set()
            if not release.wait(timeout=10):
                raise RuntimeError("timed out waiting for competing delivery")
            return post(*args, **kwargs)

        self.post.side_effect = wait_for_other
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.call)
            self.assertTrue(entered.wait(timeout=10))
            try:
                second = pool.submit(self.call)
                with self.assertRaisesRegex(ValueError, "unconfirmed"):
                    second.result(timeout=10)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=10)["external_sends"], 1)
        self.assertEqual(self.post.call_count, 1)

    def test_full_csv_attachment_keeps_every_long_day_result_in_one_post(self):
        import csv
        import io

        self.events(220)
        sent = self.call()
        self.assertEqual(sent["signal_notifications"], 220)
        self.assertEqual(sent["external_sends"], 1)
        self.assertEqual(self.post.call_count, 1)
        message, files = self.posts[0]
        self.assertLessEqual(len(message["embeds"][0]["description"]), 4096)
        filename, data, content_type = files["files[0]"]
        self.assertEqual(filename, f"cloud-new-a-{self.day}.csv")
        self.assertEqual(content_type, "text/csv")
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))[1:]
        self.assertEqual(len(rows), 220)
        self.assertEqual({row[1] for row in rows}, {event["symbol"] for event in self.snapshot["events"]})
        self.assertTrue(all(row[0] == self.day and row[2].endswith(row[1]) for row in rows))


if __name__ == "__main__":
    unittest.main()
